from __future__ import annotations

import gzip
import logging
import os
import sys
import threading
from pathlib import Path

from mitmproxy import command, ctx, http

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gsloc_proxy.auth import AuthManager, load_auth_config  # noqa: E402
from gsloc_proxy.config import resolve_policy_path  # noqa: E402
from gsloc_proxy.management import start_management_server  # noqa: E402
from gsloc_proxy.log import GslocFileLogSink  # noqa: E402
from gsloc_proxy.patcher import PatchTarget, patch_gsloc_payload  # noqa: E402
from gsloc_proxy.policy import (  # noqa: E402
    describe_patch_decision,
    describe_request_decision,
    should_patch,
    should_reject_request,
)
from gsloc_proxy.service import GslocProxyService  # noqa: E402
from gsloc_proxy.state import resolve_state_path  # noqa: E402


class GslocMitmLogHandler(logging.Handler):
    def __init__(self, addon: "GslocProxyAddon") -> None:
        super().__init__()
        self.addon = addon
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        service = self.addon.service
        if service is None:
            return
        message = self.format(record)
        if message.startswith("gsloc-proxy["):
            return
        service.record_log(
            "mitmproxy_log",
            self.addon._python_log_level(record.levelno),
            message,
            layer="mitmproxy",
            source=record.name,
            details={"levelno": record.levelno},
            emit_terminal=False,
        )


class GslocProxyAddon:
    def __init__(self) -> None:
        self.service: GslocProxyService | None = None
        self.management_server = None
        self.auth_manager: AuthManager | None = None
        self.mitm_log_handler: GslocMitmLogHandler | None = None

    def load(self, loader):
        loader.add_option(
            name="gsloc_policy",
            typespec=str,
            default="",
            help="gs-loc static proxy policy JSON path. Defaults to GSLOC_POLICY_PATH or /etc/gsloc-proxy/policy.json.",
        )
        loader.add_option(
            name="gsloc_state",
            typespec=str,
            default="",
            help="gs-loc runtime state JSON path. Defaults to GSLOC_STATE_PATH or /etc/gsloc-proxy/state.json.",
        )
        loader.add_option(
            name="gsloc_manage_host",
            typespec=str,
            default=os.environ.get("GSLOC_MANAGE_HOST", "127.0.0.1"),
            help="gs-loc management HTTP API listen host.",
        )
        loader.add_option(
            name="gsloc_manage_port",
            typespec=int,
            default=int(os.environ.get("GSLOC_MANAGE_PORT", "8090")),
            help="gs-loc management HTTP API listen port.",
        )
        loader.add_option(
            name="gsloc_manage_user",
            typespec=str,
            default=os.environ.get("GSLOC_MANAGE_USER", "admin"),
            help="gs-loc management console username.",
        )
        loader.add_option(
            name="gsloc_manage_password",
            typespec=str,
            default=os.environ.get("GSLOC_MANAGE_PASSWORD", ""),
            help="gs-loc management console password. Leave empty to disable login in trusted local-only setups.",
        )
        loader.add_option(
            name="gsloc_restart_flag",
            typespec=str,
            default="",
            help="Path touched before programmatic restart so the local launcher can restart mitmdump.",
        )
        loader.add_option(
            name="gsloc_log_level",
            typespec=str,
            default=os.environ.get("GSLOC_LOG_LEVEL", "info"),
            help="Minimum gsloc-proxy log level kept for Web/API logs: debug, info, success, warning, error.",
        )
        loader.add_option(
            name="gsloc_terminal_log_level",
            typespec=str,
            default=os.environ.get("GSLOC_TERMINAL_LOG_LEVEL", os.environ.get("GSLOC_LOG_LEVEL", "info")),
            help="Minimum gsloc-proxy log level emitted to the mitmdump terminal.",
        )
        loader.add_option(
            name="gsloc_log_file",
            typespec=str,
            default=os.environ.get("GSLOC_LOG_FILE", ""),
            help="Optional gsloc-proxy log file path. Disabled when empty.",
        )
        loader.add_option(
            name="gsloc_file_log_level",
            typespec=str,
            default=os.environ.get("GSLOC_FILE_LOG_LEVEL", os.environ.get("GSLOC_LOG_LEVEL", "info")),
            help="Minimum gsloc-proxy log level written to the log file.",
        )
        loader.add_option(
            name="gsloc_log_format",
            typespec=str,
            default=os.environ.get("GSLOC_LOG_FORMAT", "jsonl"),
            help="gsloc-proxy file log format: jsonl or text.",
        )
        loader.add_option(
            name="gsloc_log_max_bytes",
            typespec=int,
            default=int(os.environ.get("GSLOC_LOG_MAX_BYTES", str(10 * 1024 * 1024))),
            help="Maximum gsloc-proxy log file size before rotation.",
        )
        loader.add_option(
            name="gsloc_log_backup_count",
            typespec=int,
            default=int(os.environ.get("GSLOC_LOG_BACKUP_COUNT", "5")),
            help="Number of rotated gsloc-proxy log files to keep.",
        )

    def configure(self, updated):
        if {
            "gsloc_policy",
            "gsloc_state",
            "confdir",
            "gsloc_log_level",
            "gsloc_terminal_log_level",
            "gsloc_log_file",
            "gsloc_file_log_level",
            "gsloc_log_format",
            "gsloc_log_max_bytes",
            "gsloc_log_backup_count",
        }.intersection(updated):
            policy_path, state_path, confdir = self._resolved_paths()
            file_sink = self._make_file_log_sink()
            if self.service is None:
                self.service = GslocProxyService(
                    state_path=state_path,
                    policy_path=policy_path,
                    confdir=confdir,
                    log_level=ctx.options.gsloc_log_level,
                    terminal_log_level=ctx.options.gsloc_terminal_log_level,
                    terminal_sink=self._terminal_log,
                    file_sink=file_sink,
                )
            else:
                self.service.reload(
                    state_path=state_path,
                    policy_path=policy_path,
                    confdir=confdir,
                    log_level=ctx.options.gsloc_log_level,
                    terminal_log_level=ctx.options.gsloc_terminal_log_level,
                    terminal_sink=self._terminal_log,
                    file_sink=file_sink,
                )
            settings = self.service.settings()
            self.service.record_log(
                "config_loaded",
                "info",
                "gsloc proxy config loaded",
                layer="mitm",
                source="addon.configure",
                details={
                    "target": {
                        "lat": settings.runtime.target.lat,
                        "lng": settings.runtime.target.lng,
                        "name": settings.runtime.target.name,
                        "mode": settings.runtime.target.mode,
                        "scale": settings.runtime.target.scale,
                    },
                    "enabled": settings.runtime.enabled,
                    "allow_rules": len(settings.policy.allow),
                    "policy_path": str(policy_path),
                    "state_path": str(state_path),
                    "confdir": str(confdir),
                },
            )

    def running(self) -> None:
        service = self._ensure_service()
        self._install_mitm_log_handler()
        if self.management_server is not None:
            return
        host = ctx.options.gsloc_manage_host
        port = int(ctx.options.gsloc_manage_port)
        static_dir = Path(__file__).resolve().parent / "static"
        auth_config = load_auth_config(ctx.options.gsloc_manage_user, ctx.options.gsloc_manage_password)
        self.auth_manager = AuthManager(auth_config)
        self.management_server = start_management_server(service, host, port, static_dir, self.auth_manager)
        service.record_log(
            "management_started",
            "info",
            f"management API listening on http://{host}:{port}",
            layer="management",
            source="addon.running",
            details={"host": host, "port": port, "static_dir": str(static_dir), "auth_enabled": auth_config.enabled},
        )
        if auth_config.enabled:
            service.record_log(
                "management_auth_enabled",
                "info",
                f"management auth enabled for user {auth_config.username!r}",
                layer="management",
                source="addon.running",
                details={"user": auth_config.username},
            )
        else:
            service.record_log(
                "management_auth_disabled",
                "warning",
                "management auth disabled; set GSLOC_MANAGE_PASSWORD to require login",
                layer="management",
                source="addon.running",
            )

    def done(self) -> None:
        self._uninstall_mitm_log_handler()
        if self.management_server is not None:
            self._ensure_service().record_log(
                "management_stopped",
                "info",
                "management API stopped",
                layer="management",
                source="addon.done",
            )
            self.management_server.stop()
            self.management_server = None
        if self.service is not None:
            self.service.close()

    @command.command("gsloc.restart")
    def restart(self) -> None:
        restart_flag = getattr(ctx.options, "gsloc_restart_flag", "")
        self._ensure_service().record_log(
            "restart_requested",
            "warning",
            "proxy restart requested",
            layer="system",
            source="addon.restart",
            details={"restart_flag": restart_flag},
        )
        if restart_flag:
            Path(restart_flag).write_text("restart\n", encoding="utf-8")
        ctx.master.shutdown()

    def request(self, flow: http.HTTPFlow) -> None:
        service = self._ensure_service()
        host = self._flow_host(flow)
        path = self._flow_path(flow)
        method = self._flow_method(flow)
        client = self._flow_client(flow)
        settings = service.settings()
        decision = describe_request_decision(flow, settings)
        service.record_request(host=host, path=path, method=method, client=client, details=decision)
        if should_reject_request(flow, settings):
            service.record_reject(host=host, path=path, method=method, client=client, details=decision)
            status_code = 503 if decision.get("reason") == "proxy_disabled" else 403
            message = (
                b"gsloc-proxy session is closed\n"
                if decision.get("reason") == "proxy_disabled"
                else b"gsloc-proxy only allows configured gs-loc traffic\n"
            )
            flow.response = http.Response.make(
                status_code,
                message,
                {"content-type": "text/plain; charset=utf-8"},
            )
        elif decision.get("action") == "pass_through":
            service.record_pass_through(host=host, path=path, method=method, client=client, details=decision)
        else:
            service.record_log(
                "patch_target",
                "info",
                "request matched patch target",
                layer="policy",
                source="addon.request",
                host=host,
                path=path,
                client=client,
                method=method,
                details=decision,
            )

    def response(self, flow: http.HTTPFlow) -> None:
        service = self._ensure_service()
        settings = service.settings()
        if not should_patch(flow, settings):
            decision = describe_patch_decision(flow, settings)
            if decision.get("action") != "reject":
                service.record_log(
                    "response_skip",
                    "info",
                    f"response not rewritten: {decision.get('reason')}",
                    layer="mitm",
                    source="addon.response",
                    host=self._flow_host(flow),
                    path=self._flow_path(flow),
                    status=self._flow_status(flow),
                    client=self._flow_client(flow),
                    method=self._flow_method(flow),
                    details=decision,
                )
            return

        try:
            assert flow.response is not None
            body = flow.response.raw_content or b""
            encoding = flow.response.headers.get("content-encoding", "").lower()
            raw = gzip.decompress(body) if "gzip" in encoding else body

            target_state = settings.runtime.target
            target = PatchTarget(
                lat=target_state.lat,
                lng=target_state.lng,
                mode=target_state.mode,
                scale=target_state.scale,
                sample_limit=settings.policy.logging.sample_limit,
            )
            new_raw, patch_stats = patch_gsloc_payload(raw, target)

            metadata = {
                "content_encoding": encoding or "identity",
                "raw_size": len(body),
                "decoded_size": len(raw),
            }
            if patch_stats.patched:
                new_body = gzip.compress(new_raw) if "gzip" in encoding else new_raw
                flow.response.raw_content = new_body
                flow.response.headers["content-length"] = str(len(new_body))
                service.record_patch_success(
                    patch_stats,
                    host=self._flow_host(flow),
                    path=self._flow_path(flow),
                    status=self._flow_status(flow),
                    details={**metadata, "encoded_size": len(new_body)},
                )
            else:
                service.record_patch_noop(
                    patch_stats,
                    host=self._flow_host(flow),
                    path=self._flow_path(flow),
                    status=self._flow_status(flow),
                    details={**metadata, "encoded_size": len(body)},
                )
        except Exception as exc:
            target_state = settings.runtime.target
            service.record_patch_error(
                {
                    "patched": 0,
                    "old_center": None,
                    "target": (target_state.lat, target_state.lng),
                    "mode": target_state.mode,
                    "scale": target_state.scale,
                    "sample": (),
                    "reason": f"error: {type(exc).__name__}",
                    "error": str(exc),
                },
                host=self._flow_host(flow),
                path=self._flow_path(flow),
                status=self._flow_status(flow),
            )
            if settings.policy.failure.patch_error == "reject" and flow.response is not None:
                flow.response = http.Response.make(
                    502,
                    b"gsloc patch error\n",
                    {"content-type": "text/plain; charset=utf-8"},
                )

    def _ensure_service(self) -> GslocProxyService:
        if self.service is None:
            policy_path, state_path, confdir = self._resolved_paths()
            self.service = GslocProxyService(
                state_path=state_path,
                policy_path=policy_path,
                confdir=confdir,
                log_level=ctx.options.gsloc_log_level,
                terminal_log_level=ctx.options.gsloc_terminal_log_level,
                terminal_sink=self._terminal_log,
                file_sink=self._make_file_log_sink(),
            )
        return self.service

    @staticmethod
    def _make_file_log_sink() -> GslocFileLogSink | None:
        path = str(getattr(ctx.options, "gsloc_log_file", "") or "").strip()
        if not path:
            return None
        return GslocFileLogSink(
            path,
            level=ctx.options.gsloc_file_log_level,
            log_format=ctx.options.gsloc_log_format,
            max_bytes=int(ctx.options.gsloc_log_max_bytes),
            backup_count=int(ctx.options.gsloc_log_backup_count),
        )

    @staticmethod
    def _terminal_log(level: str, message: str) -> None:
        if level == "error":
            ctx.log.error(message)
        elif level == "warning":
            ctx.log.warn(message)
        else:
            ctx.log.info(message)

    def _install_mitm_log_handler(self) -> None:
        if self.mitm_log_handler is not None:
            return
        self.mitm_log_handler = GslocMitmLogHandler(self)
        logging.getLogger().addHandler(self.mitm_log_handler)

    def _uninstall_mitm_log_handler(self) -> None:
        if self.mitm_log_handler is None:
            return
        logging.getLogger().removeHandler(self.mitm_log_handler)
        self.mitm_log_handler = None

    @staticmethod
    def _python_log_level(levelno: int) -> str:
        if levelno >= logging.ERROR:
            return "error"
        if levelno >= logging.WARNING:
            return "warning"
        if levelno <= logging.DEBUG:
            return "debug"
        return "info"

    @staticmethod
    def _flow_host(flow: http.HTTPFlow) -> str:
        return flow.request.pretty_host or flow.request.host or ""

    @staticmethod
    def _flow_path(flow: http.HTTPFlow) -> str:
        return flow.request.path or ""

    @staticmethod
    def _flow_status(flow: http.HTTPFlow) -> int | None:
        return flow.response.status_code if flow.response is not None else None

    @staticmethod
    def _flow_method(flow: http.HTTPFlow) -> str:
        return flow.request.method or ""

    @staticmethod
    def _flow_client(flow: http.HTTPFlow) -> str | None:
        peername = getattr(flow.client_conn, "peername", None)
        if not peername:
            return None
        if isinstance(peername, tuple):
            return ":".join(str(part) for part in peername if part is not None)
        return str(peername)

    def _resolved_paths(self) -> tuple[Path, Path, Path]:
        policy_path = resolve_policy_path(ctx.options.gsloc_policy or None)
        state_path = resolve_state_path(ctx.options.gsloc_state or None)
        confdir = Path(getattr(ctx.options, "confdir", str(Path.home() / ".mitmproxy")))
        return policy_path, state_path, confdir


addons = [GslocProxyAddon()]

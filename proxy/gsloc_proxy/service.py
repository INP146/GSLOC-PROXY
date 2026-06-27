from __future__ import annotations

import math
import threading
import time
from collections import deque
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Callable

from mitmproxy import certs

from .config import load_policy, policy_to_dict
from .log import (
    DEFAULT_LOG_LEVEL,
    GslocFileLogSink,
    format_log_record,
    normalize_log_level,
    should_emit_log,
)
from .models import FavoriteLocation, ProxyPolicy, ProxySettings, RuntimeState, TargetState
from .state import load_state, save_state, state_to_dict


TerminalLogSink = Callable[[str, str], None]
_FILE_SINK_UNSET = object()


class GslocProxyService:
    def __init__(
        self,
        state_path: Path,
        policy_path: Path,
        confdir: Path,
        *,
        log_level: str = DEFAULT_LOG_LEVEL,
        terminal_log_level: str | None = None,
        terminal_sink: TerminalLogSink | None = None,
        file_sink: GslocFileLogSink | None = None,
    ) -> None:
        self.state_path = state_path
        self.policy_path = policy_path
        self.confdir = confdir
        self.log_level = normalize_log_level(log_level)
        self.terminal_log_level = normalize_log_level(terminal_log_level or log_level)
        self.terminal_sink = terminal_sink
        self.file_sink = file_sink
        self.lock = threading.RLock()
        self.runtime: RuntimeState = load_state(state_path)
        self.policy: ProxyPolicy = load_policy(policy_path)
        self.stats = self._empty_stats()
        self.logs = deque(maxlen=1000)
        self.next_log_id = 1
        self.last_patch: dict[str, Any] | None = None

    def reload(
        self,
        state_path: Path,
        policy_path: Path,
        confdir: Path,
        *,
        log_level: str | None = None,
        terminal_log_level: str | None = None,
        terminal_sink: TerminalLogSink | None = None,
        file_sink: GslocFileLogSink | None | object = _FILE_SINK_UNSET,
    ) -> None:
        runtime = load_state(state_path)
        policy = load_policy(policy_path)
        with self.lock:
            self.state_path = state_path
            self.policy_path = policy_path
            self.confdir = confdir
            if log_level is not None:
                self.log_level = normalize_log_level(log_level)
            if terminal_log_level is not None:
                self.terminal_log_level = normalize_log_level(terminal_log_level)
            if terminal_sink is not None:
                self.terminal_sink = terminal_sink
            if file_sink is not _FILE_SINK_UNSET:
                old_file_sink = self.file_sink
                self.file_sink = file_sink if isinstance(file_sink, GslocFileLogSink) else None
                if old_file_sink is not None and old_file_sink is not file_sink:
                    old_file_sink.close()
            self.runtime = runtime
            self.policy = policy

    def settings(self) -> ProxySettings:
        with self.lock:
            return ProxySettings(runtime=self.runtime, policy=self.policy)

    def record_log(
        self,
        log_type: str,
        level: str,
        message: str,
        *,
        layer: str | None = None,
        source: str | None = None,
        host: str | None = None,
        path: str | None = None,
        status: int | None = None,
        client: str | None = None,
        method: str | None = None,
        details: dict[str, Any] | None = None,
        emit_terminal: bool = True,
    ) -> None:
        with self.lock:
            self._append_log_locked(
                log_type,
                level,
                message,
                layer=layer,
                source=source,
                host=host,
                path=path,
                status=status,
                client=client,
                method=method,
                details=details,
                emit_terminal=emit_terminal,
            )

    def record_request(
        self,
        host: str | None = None,
        path: str | None = None,
        *,
        client: str | None = None,
        method: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        with self.lock:
            self.stats["request_total"] += 1
            self._append_log_locked(
                "request",
                "info",
                "request received",
                layer="proxy",
                source="addon.request",
                host=host,
                path=path,
                client=client,
                method=method,
                details=details,
            )

    def record_reject(
        self,
        host: str | None = None,
        path: str | None = None,
        *,
        client: str | None = None,
        method: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        with self.lock:
            self.stats["reject_total"] += 1
            self._append_log_locked(
                "reject",
                "warning",
                "request rejected",
                layer="policy",
                source="addon.request",
                host=host,
                path=path,
                client=client,
                method=method,
                details=details,
            )

    def record_pass_through(
        self,
        host: str | None = None,
        path: str | None = None,
        *,
        client: str | None = None,
        method: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        with self.lock:
            self.stats["pass_through_total"] += 1
            self._append_log_locked(
                "pass_through",
                "info",
                "request passed through",
                layer="policy",
                source="addon.request",
                host=host,
                path=path,
                client=client,
                method=method,
                details=details,
            )

    def record_patch_success(
        self,
        patch_stats: Any,
        host: str | None = None,
        path: str | None = None,
        status: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        patch_payload = asdict(patch_stats)
        if details:
            patch_payload.update(details)
        self._record_patch(
            "patch_success",
            patch_payload,
            "success",
            f"rewrote {patch_payload.get('patched', 0)} record(s)",
            host=host,
            path=path,
            status=status,
        )

    def record_patch_noop(
        self,
        patch_stats: Any,
        host: str | None = None,
        path: str | None = None,
        status: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        patch_payload = asdict(patch_stats)
        if details:
            patch_payload.update(details)
        reason = patch_payload.get("reason") or "noop"
        self._record_patch(
            "patch_noop",
            patch_payload,
            "info",
            f"no rewrite: {reason}",
            host=host,
            path=path,
            status=status,
        )

    def record_patch_error(
        self,
        patch_payload: dict[str, Any],
        host: str | None = None,
        path: str | None = None,
        status: int | None = None,
    ) -> None:
        with self.lock:
            self.stats["patch_error"] += 1
            self.last_patch = patch_payload
            self._append_log_locked(
                "patch_error",
                "error",
                patch_payload.get("reason") or "patch error",
                layer="rewrite",
                source="addon.response",
                host=host,
                path=path,
                status=status,
                details=patch_payload,
            )

    def snapshot_status(self) -> dict[str, Any]:
        with self.lock:
            runtime = self.runtime
            policy = self.policy
            stats = dict(self.stats)
            last_patch = self.last_patch.copy() if self.last_patch is not None else None
            log_count = len(self.logs)
            latest_log_id = self.logs[-1]["id"] if self.logs else None
        ca_path = self.ca_cert_path()
        return {
            "runtime": state_to_dict(runtime),
            "policy": policy_to_dict(policy),
            "stats": stats,
            "last_patch": last_patch,
            "ca": {
                "available": ca_path.exists() and ca_path.is_file(),
                "url": "/ca.cer",
            },
            "logs": {
                "count": log_count,
                "latest_id": latest_log_id,
                "level": self.log_level,
                "terminal_level": self.terminal_log_level,
            },
            "web": {
                "mode": "live",
            },
        }

    def update_target(self, payload: dict[str, Any]) -> dict[str, Any]:
        lat = self._number_in_range(payload.get("lat"), "lat", -90, 90)
        lng = self._number_in_range(payload.get("lng"), "lng", -180, 180)
        scale = self._number_in_range(payload.get("scale"), "scale", 0, 10)
        name = "" if payload.get("name") is None else str(payload.get("name"))
        with self.lock:
            previous = state_to_dict(self.runtime)["target"]
            target = replace(self.runtime.target, lat=lat, lng=lng, name=name, scale=scale)
            runtime = replace(self.runtime, target=target)
            self._save_runtime_locked(runtime)
            runtime_data = state_to_dict(self.runtime)
            target_data = runtime_data["target"]
            self._append_log_locked(
                "runtime_target_updated",
                "info",
                "target updated",
                layer="runtime",
                source="service.runtime",
                details={"previous": previous, "next": target_data},
            )
        return {"ok": True, "target": target_data, "runtime": runtime_data}

    def add_favorite_location(self, payload: dict[str, Any]) -> dict[str, Any]:
        favorite = self._favorite_from_payload(payload)
        favorite_key = self._favorite_key(favorite)

        with self.lock:
            previous = state_to_dict(self.runtime)["favorites"]
            favorites = (
                favorite,
                *(
                    item
                    for item in self.runtime.favorites
                    if self._favorite_key(item) != favorite_key
                ),
            )
            runtime = replace(self.runtime, favorites=favorites)
            self._save_runtime_locked(runtime)
            runtime_data = state_to_dict(self.runtime)
            self._append_log_locked(
                "runtime_favorite_added",
                "info",
                "favorite location saved",
                layer="runtime",
                source="service.runtime",
                details={"previous_count": len(previous), "next_count": len(favorites)},
            )
        return {"ok": True, "favorites": runtime_data["favorites"], "runtime": runtime_data}

    def remove_favorite_location(self, payload: dict[str, Any]) -> dict[str, Any]:
        favorite = self._favorite_from_payload(payload)
        favorite_key = self._favorite_key(favorite)

        with self.lock:
            previous = state_to_dict(self.runtime)["favorites"]
            favorites = tuple(
                item
                for item in self.runtime.favorites
                if self._favorite_key(item) != favorite_key
            )
            runtime = replace(self.runtime, favorites=favorites)
            self._save_runtime_locked(runtime)
            runtime_data = state_to_dict(self.runtime)
            self._append_log_locked(
                "runtime_favorite_removed",
                "info",
                "favorite location removed",
                layer="runtime",
                source="service.runtime",
                details={"previous_count": len(previous), "next_count": len(favorites)},
            )
        return {"ok": True, "favorites": runtime_data["favorites"], "runtime": runtime_data}

    def update_mode(self, mode: Any) -> dict[str, Any]:
        if mode not in ("clamp", "shift"):
            raise ValueError("mode must be clamp or shift")
        with self.lock:
            previous = self.runtime.target.mode
            target = replace(self.runtime.target, mode=mode)
            runtime = replace(self.runtime, target=target)
            self._save_runtime_locked(runtime)
            runtime_data = state_to_dict(self.runtime)
            target_data = runtime_data["target"]
            self._append_log_locked(
                "runtime_mode_updated",
                "info",
                "mode updated",
                layer="runtime",
                source="service.runtime",
                details={"previous": previous, "next": mode},
            )
        return {"ok": True, "target": target_data, "runtime": runtime_data}

    def update_enabled(self, enabled: Any) -> dict[str, Any]:
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be boolean")
        with self.lock:
            previous = self.runtime.enabled
            runtime = replace(self.runtime, enabled=enabled)
            self._save_runtime_locked(runtime)
            runtime_data = state_to_dict(self.runtime)
            self._append_log_locked(
                "runtime_enabled_updated",
                "info",
                "runtime enabled updated",
                layer="runtime",
                source="service.runtime",
                details={"previous": previous, "next": enabled},
            )
        return {"ok": True, "enabled": enabled, "runtime": runtime_data}

    def update_proxy_enabled(self, enabled: Any) -> dict[str, Any]:
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be boolean")
        with self.lock:
            previous = self.runtime.proxy_enabled
            if previous == enabled:
                runtime_data = state_to_dict(self.runtime)
                self._append_log_locked(
                    "proxy_enabled_unchanged",
                    "info",
                    "proxy session state unchanged",
                    layer="runtime",
                    source="service.runtime",
                    details={"enabled": enabled, "session_id": self.runtime.session_id},
                )
                return {"ok": True, "proxy_enabled": enabled, "runtime": runtime_data}

            if enabled:
                session_id = self.runtime.session_id + 1
                runtime = replace(
                    self.runtime,
                    proxy_enabled=True,
                    session_id=session_id,
                    session_started_at=time.time(),
                )
                self._save_runtime_locked(runtime)
                self._reset_session_data_locked()
                self._append_log_locked(
                    "proxy_session_started",
                    "success",
                    "proxy session started",
                    layer="runtime",
                    source="service.runtime",
                    details={"previous": previous, "next": enabled, "session_id": session_id},
                )
            else:
                runtime = replace(self.runtime, proxy_enabled=False)
                self._save_runtime_locked(runtime)
                self._append_log_locked(
                    "proxy_session_stopped",
                    "warning",
                    "proxy session stopped",
                    layer="runtime",
                    source="service.runtime",
                    details={"previous": previous, "next": enabled, "session_id": self.runtime.session_id},
                )
            runtime_data = state_to_dict(self.runtime)
        return {"ok": True, "proxy_enabled": enabled, "runtime": runtime_data}

    def reset_runtime_state(self) -> dict[str, Any]:
        with self.lock:
            previous = state_to_dict(self.runtime)
            self._save_runtime_locked(
                RuntimeState(
                    proxy_enabled=self.runtime.proxy_enabled,
                    session_id=self.runtime.session_id,
                    session_started_at=self.runtime.session_started_at,
                )
            )
            self._append_log_locked(
                "runtime_reset",
                "warning",
                "runtime state reset",
                layer="runtime",
                source="service.runtime",
                details={"previous": previous, "next": state_to_dict(self.runtime)},
            )
        return self.snapshot_status()

    def ca_cert_path(self) -> Path:
        with self.lock:
            confdir = self.confdir
        return Path(confdir) / "mitmproxy-ca-cert.cer"

    def generate_ca(self, regenerate: bool = False) -> dict[str, Any]:
        with self.lock:
            confdir = Path(self.confdir)
        basename = "mitmproxy"
        ca_files = [
            confdir / f"{basename}-ca.pem",
            confdir / f"{basename}-ca.p12",
            confdir / f"{basename}-ca-cert.pem",
            confdir / f"{basename}-ca-cert.cer",
            confdir / f"{basename}-ca-cert.p12",
            confdir / f"{basename}-dhparam.pem",
        ]
        existing = [path for path in ca_files if path.exists()]
        if existing and not regenerate:
            self.record_log(
                "ca_exists",
                "info",
                "CA certificate already exists",
                layer="ca",
                source="service.ca",
                details={"confdir": str(confdir), "files": len(existing)},
            )
            return {
                "ok": True,
                "generated": False,
                "restart_required": False,
                "ca": self.snapshot_status()["ca"],
            }

        log_type = "ca_regenerate_started" if regenerate else "ca_generate_started"
        self.record_log(
            log_type,
            "warning" if regenerate else "info",
            "CA regeneration started" if regenerate else "CA generation started",
            layer="ca",
            source="service.ca",
            details={"confdir": str(confdir), "existing_files": len(existing)},
        )
        try:
            if regenerate:
                for path in existing:
                    path.unlink()
            certs.CertStore.create_store(
                confdir,
                basename,
                key_size=2048,
                organization="GSLOC-PROXY",
                cn="GSLOC-PROXY",
            )
        except Exception as exc:
            self.record_log(
                "ca_generate_error",
                "error",
                f"CA generation failed: {type(exc).__name__}",
                layer="ca",
                source="service.ca",
                details={"error": str(exc), "confdir": str(confdir)},
            )
            raise
        self.record_log(
            "ca_generated",
            "success",
            "CA certificate generated",
            layer="ca",
            source="service.ca",
            details={"confdir": str(confdir), "restart_required": True},
        )
        return {
            "ok": True,
            "generated": True,
            "restart_required": True,
            "ca": self.snapshot_status()["ca"],
        }

    def request_restart(self) -> None:
        from mitmproxy import ctx

        ctx.master.commands.call("gsloc.restart")

    def snapshot_logs(self, limit: int = 100) -> dict[str, Any]:
        safe_limit = max(1, min(int(limit), 1000))
        with self.lock:
            logs = list(self.logs)[-safe_limit:]
        return {
            "logs": logs,
            "limit": safe_limit,
            "count": len(logs),
            "level": self.log_level,
        }

    def _record_patch(
        self,
        key: str,
        patch_payload: dict[str, Any],
        level: str,
        message: str,
        *,
        host: str | None = None,
        path: str | None = None,
        status: int | None = None,
    ) -> None:
        with self.lock:
            self.stats[key] += 1
            self.last_patch = patch_payload
            self._append_log_locked(
                key,
                level,
                message,
                layer="rewrite",
                source="addon.response",
                host=host,
                path=path,
                status=status,
                details=patch_payload,
            )

    def _append_log_locked(
        self,
        log_type: str,
        level: str,
        message: str,
        *,
        layer: str | None = None,
        source: str | None = None,
        host: str | None = None,
        path: str | None = None,
        status: int | None = None,
        client: str | None = None,
        method: str | None = None,
        details: dict[str, Any] | None = None,
        emit_terminal: bool = True,
    ) -> dict[str, Any]:
        normalized_level = normalize_log_level(level)
        if not should_emit_log(normalized_level, self.log_level):
            return {}

        record: dict[str, Any] = {
            "id": self.next_log_id,
            "ts": time.time(),
            "session_id": self.runtime.session_id,
            "logger": "gsloc-proxy",
            "type": log_type,
            "level": normalized_level,
            "message": message,
        }
        self.next_log_id += 1
        if layer is not None:
            record["layer"] = layer
        if source is not None:
            record["source"] = source
        if host is not None:
            record["host"] = host
        if path is not None:
            record["path"] = path
        if status is not None:
            record["status"] = status
        if client is not None:
            record["client"] = client
        if method is not None:
            record["method"] = method
        if details:
            record["details"] = details
        self.logs.append(record)
        if emit_terminal:
            self._emit_terminal_log_locked(record)
        self._emit_file_log_locked(record)
        return record

    def _emit_terminal_log_locked(self, record: dict[str, Any]) -> None:
        if self.terminal_sink is None:
            return
        if not should_emit_log(str(record.get("level") or "info"), self.terminal_log_level):
            return
        self.terminal_sink(str(record.get("level") or "info"), format_log_record(record))

    def _emit_file_log_locked(self, record: dict[str, Any]) -> None:
        if self.file_sink is None:
            return
        self.file_sink.emit(record)

    def close(self) -> None:
        with self.lock:
            if self.file_sink is not None:
                self.file_sink.close()
                self.file_sink = None

    @staticmethod
    def _empty_stats() -> dict[str, int]:
        return {
            "request_total": 0,
            "pass_through_total": 0,
            "reject_total": 0,
            "patch_success": 0,
            "patch_noop": 0,
            "patch_error": 0,
        }

    def _reset_session_data_locked(self) -> None:
        self.stats = self._empty_stats()
        self.logs.clear()
        self.next_log_id = 1
        self.last_patch = None

    def _save_runtime_locked(self, runtime: RuntimeState) -> None:
        save_state(runtime, self.state_path)
        self.runtime = runtime

    @staticmethod
    def _number_in_range(value: Any, name: str, minimum: float, maximum: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be a number") from exc
        if not math.isfinite(number):
            raise ValueError(f"{name} must be finite")
        if number < minimum or number > maximum:
            raise ValueError(f"{name} must be between {minimum:g} and {maximum:g}")
        return number

    def _favorite_from_payload(self, payload: dict[str, Any]) -> FavoriteLocation:
        lat = self._number_in_range(payload.get("lat"), "lat", -90, 90)
        lng = self._number_in_range(payload.get("lng"), "lng", -180, 180)
        scale = self._number_in_range(payload.get("scale", 1), "scale", 0, 10)
        name = "" if payload.get("name") is None else str(payload.get("name")).strip()
        return FavoriteLocation(lat=lat, lng=lng, name=name, scale=scale)

    @staticmethod
    def _favorite_key(favorite: FavoriteLocation) -> tuple[float, float, str]:
        return (round(favorite.lat, 8), round(favorite.lng, 8), favorite.name)

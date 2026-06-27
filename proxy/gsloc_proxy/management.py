from __future__ import annotations

import json
import mimetypes
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from .auth import (
    AuthManager,
    auth_payload,
    auth_status_for_denial,
    make_clear_session_cookie,
    make_session_cookie,
    session_token_from_cookie_header,
)


class ManagementHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address, RequestHandlerClass, service, static_dir: Path, auth: AuthManager):
        super().__init__(server_address, RequestHandlerClass)
        self.service = service
        self.static_dir = static_dir
        self.auth = auth


class ManagementServer:
    def __init__(self, service, host: str, port: int, static_dir: Path, auth: AuthManager) -> None:
        self.host = host
        self.port = port
        self.httpd = ManagementHTTPServer((host, port), ManagementHandler, service, static_dir, auth)
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="gsloc-management", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)


class ManagementHandler(BaseHTTPRequestHandler):
    server: ManagementHTTPServer

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/auth/status":
            self.send_json(self.auth_response_payload())
        elif path in ("/api/status", "/status"):
            if not self.require_auth():
                return
            self.send_json(self.server.service.snapshot_status())
        elif path in ("/api/metrics", "/metrics"):
            if not self.require_auth():
                return
            self.send_json(self.server.service.snapshot_status()["stats"])
        elif path == "/api/logs":
            if not self.require_auth():
                return
            query = parse_qs(urlparse(self.path).query)
            try:
                limit = int(query.get("limit", ["100"])[0])
            except ValueError:
                limit = 100
            self.send_json(self.server.service.snapshot_logs(limit=limit))
        elif path == "/ca.cer":
            if not self.require_auth():
                return
            self.send_ca(head_only=False)
        else:
            self.send_static(path, head_only=False)

    def do_HEAD(self) -> None:
        path = urlparse(self.path).path
        if path == "/ca.cer":
            if not self.require_auth():
                return
            self.send_ca(head_only=True)
        else:
            self.send_static(path, head_only=True)

    def do_PUT(self) -> None:
        self.handle_runtime_mutation()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/auth/login":
            self.handle_login()
        elif path == "/api/auth/logout":
            self.handle_logout()
        else:
            self.handle_runtime_mutation()

    def handle_runtime_mutation(self) -> None:
        path = urlparse(self.path).path
        if not self.require_auth(require_csrf=True):
            return
        try:
            payload = self.read_json_body()
            if path == "/api/runtime/target":
                result = self.server.service.update_target(payload)
                self.send_json(result)
                self.record_management_log(
                    "management_runtime_mutation",
                    "info",
                    "runtime target mutation accepted",
                    status=HTTPStatus.OK,
                    details={"endpoint": path},
                )
            elif path == "/api/runtime/favorites":
                result = self.server.service.add_favorite_location(payload)
                self.send_json(result)
                self.record_management_log(
                    "management_runtime_mutation",
                    "info",
                    "runtime favorite location accepted",
                    status=HTTPStatus.OK,
                    details={"endpoint": path},
                )
            elif path == "/api/runtime/mode":
                result = self.server.service.update_mode(payload.get("mode"))
                self.send_json(result)
                self.record_management_log(
                    "management_runtime_mutation",
                    "info",
                    "runtime mode mutation accepted",
                    status=HTTPStatus.OK,
                    details={"endpoint": path, "mode": payload.get("mode")},
                )
            elif path == "/api/runtime/enabled":
                result = self.server.service.update_enabled(payload.get("enabled"))
                self.send_json(result)
                self.record_management_log(
                    "management_runtime_mutation",
                    "info",
                    "runtime enabled mutation accepted",
                    status=HTTPStatus.OK,
                    details={"endpoint": path, "enabled": payload.get("enabled")},
                )
            elif path == "/api/runtime/proxy-enabled":
                result = self.server.service.update_proxy_enabled(payload.get("enabled"))
                self.send_json(result)
                self.record_management_log(
                    "management_runtime_mutation",
                    "info",
                    "runtime proxy session mutation accepted",
                    status=HTTPStatus.OK,
                    details={"endpoint": path, "enabled": payload.get("enabled")},
                )
            elif path == "/api/runtime/reset":
                result = self.server.service.reset_runtime_state()
                self.send_json(result)
                self.record_management_log(
                    "management_runtime_mutation",
                    "warning",
                    "runtime reset accepted",
                    status=HTTPStatus.OK,
                    details={"endpoint": path},
                )
            elif path == "/api/ca/generate":
                regenerate = bool(payload.get("regenerate", False))
                result = self.server.service.generate_ca(regenerate=regenerate)
                self.send_json(result)
                self.record_management_log(
                    "management_ca_generate",
                    "warning" if regenerate else "info",
                    "CA generation requested",
                    status=HTTPStatus.OK,
                    details={"endpoint": path, "regenerate": regenerate, "restart_required": result.get("restart_required")},
                )
                if result.get("restart_required"):
                    threading.Timer(0.2, self.server.service.request_restart).start()
            else:
                self.send_json({"ok": False, "error": "not found"}, status=HTTPStatus.NOT_FOUND)
                self.record_management_log(
                    "management_not_found",
                    "warning",
                    "management endpoint not found",
                    status=HTTPStatus.NOT_FOUND,
                    details={"endpoint": path},
                )
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            self.record_management_log(
                "management_bad_request",
                "warning",
                str(exc),
                status=HTTPStatus.BAD_REQUEST,
                details={"endpoint": path},
            )
        except Exception as exc:
            self.send_json(
                {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            self.record_management_log(
                "management_error",
                "error",
                f"management request failed: {type(exc).__name__}",
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
                details={"endpoint": path, "error": str(exc)},
            )

    def handle_login(self) -> None:
        try:
            payload = self.read_json_body()
            result = self.server.auth.login(payload.get("username"), payload.get("password"))
            if result is None:
                self.send_json({"ok": False, "error": "invalid username or password"}, status=HTTPStatus.UNAUTHORIZED)
                self.record_management_log(
                    "management_login_failed",
                    "warning",
                    "management login failed",
                    status=HTTPStatus.UNAUTHORIZED,
                    details={"user": payload.get("username")},
                )
                return

            token, session = result
            self.send_json(
                {"ok": True, **auth_payload(self.server.auth.config, session)},
                headers={"Set-Cookie": make_session_cookie(token, session.expires_at)},
            )
            self.record_management_log(
                "management_login",
                "info",
                "management login accepted",
                status=HTTPStatus.OK,
                details={"user": session.user, "auth_required": self.server.auth.config.enabled},
            )
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self.send_json(
                {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def handle_logout(self) -> None:
        token = session_token_from_cookie_header(self.headers.get("Cookie"))
        session_info = self.server.auth.session_for_cookie_header(self.headers.get("Cookie"))
        if session_info is not None:
            _, session = session_info
            if not self.server.auth.verify_csrf(session, self.headers.get("X-CSRF-Token")):
                self.send_json({"ok": False, "error": "invalid csrf token"}, status=HTTPStatus.FORBIDDEN)
                return
        self.server.auth.logout(token)
        self.send_json(
            {"ok": True, **auth_payload(self.server.auth.config)},
            headers={"Set-Cookie": make_clear_session_cookie()},
        )
        self.record_management_log(
            "management_logout",
            "info",
            "management logout accepted",
            status=HTTPStatus.OK,
        )

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:5173")
        self.send_header("Access-Control-Allow-Methods", "GET, PUT, POST, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-CSRF-Token")
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.end_headers()

    def read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("content-length") or 0)
        if length <= 0:
            return {}
        if length > 1024 * 1024:
            raise ValueError("request body too large")
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("invalid JSON body") from exc
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def send_json(
        self,
        payload: Any,
        status: int | HTTPStatus = HTTPStatus.OK,
        headers: dict[str, str] | None = None,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if self.is_dev_origin():
            self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:5173")
            self.send_header("Access-Control-Allow-Credentials", "true")
        if headers:
            for name, value in headers.items():
                self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def send_ca(self, head_only: bool) -> None:
        path = self.server.service.ca_cert_path()
        if not path.exists() or not path.is_file():
            self.record_management_log(
                "management_ca_download",
                "warning",
                "CA certificate download failed: not found",
                status=HTTPStatus.NOT_FOUND,
                details={"ca_path": str(path), "head_only": head_only},
            )
            self.send_error(HTTPStatus.NOT_FOUND, "CA certificate not found")
            return
        self.send_file(path, "application/x-x509-ca-cert", head_only=head_only)
        self.record_management_log(
            "management_ca_download",
            "info",
            "CA certificate downloaded",
            status=HTTPStatus.OK,
            details={"ca_path": str(path), "head_only": head_only},
        )

    def send_static(self, request_path: str, head_only: bool) -> None:
        static_dir = self.server.static_dir.resolve()
        index_path = static_dir / "index.html"
        if not static_dir.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "static files not built")
            return

        relative = unquote(request_path).split("?", 1)[0].lstrip("/")
        candidate = (static_dir / (relative or "index.html")).resolve()
        if candidate.is_dir():
            candidate = candidate / "index.html"

        if static_dir != candidate and static_dir not in candidate.parents:
            self.send_error(HTTPStatus.FORBIDDEN, "forbidden")
            return

        if not candidate.exists() or not candidate.is_file():
            if index_path.exists() and index_path.is_file():
                candidate = index_path
            else:
                self.send_error(HTTPStatus.NOT_FOUND, "not found")
                return

        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        self.send_file(candidate, content_type, head_only=head_only)

    def send_file(self, path: Path, content_type: str, head_only: bool) -> None:
        data = b"" if head_only else path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(path.stat().st_size))
        self.end_headers()
        if not head_only:
            self.wfile.write(data)

    def require_auth(self, *, require_csrf: bool = False) -> bool:
        if not self.server.auth.is_enabled():
            return True
        session_info = self.server.auth.session_for_cookie_header(self.headers.get("Cookie"))
        if session_info is None:
            payload, status = auth_status_for_denial()
            self.send_json(payload, status=status)
            self.record_management_log(
                "management_unauthorized",
                "warning",
                "management request unauthorized",
                status=status,
                details={"endpoint": urlparse(self.path).path},
            )
            return False
        if require_csrf:
            _, session = session_info
            if not self.server.auth.verify_csrf(session, self.headers.get("X-CSRF-Token")):
                self.send_json({"ok": False, "error": "invalid csrf token"}, status=HTTPStatus.FORBIDDEN)
                self.record_management_log(
                    "management_csrf_denied",
                    "warning",
                    "management request failed csrf validation",
                    status=HTTPStatus.FORBIDDEN,
                    details={"endpoint": urlparse(self.path).path},
                )
                return False
        return True

    def auth_response_payload(self) -> dict[str, Any]:
        session_info = self.server.auth.session_for_cookie_header(self.headers.get("Cookie"))
        session = session_info[1] if session_info is not None else None
        return auth_payload(self.server.auth.config, session)

    def is_dev_origin(self) -> bool:
        return self.headers.get("Origin") == "http://127.0.0.1:5173"

    def record_management_log(
        self,
        log_type: str,
        level: str,
        message: str,
        *,
        status: int | HTTPStatus | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        client = self.client_address[0] if self.client_address else None
        self.server.service.record_log(
            log_type,
            level,
            message,
            layer="management",
            source="management.api",
            path=urlparse(self.path).path,
            status=int(status) if status is not None else None,
            client=client,
            method=self.command,
            details=details,
        )

    def log_message(self, format: str, *args: Any) -> None:
        return


def start_management_server(service, host: str, port: int, static_dir: Path, auth: AuthManager) -> ManagementServer:
    server = ManagementServer(service, host, port, static_dir, auth)
    server.start()
    return server

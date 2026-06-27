from __future__ import annotations

import json
import mimetypes
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse


class ManagementHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address, RequestHandlerClass, service, static_dir: Path):
        super().__init__(server_address, RequestHandlerClass)
        self.service = service
        self.static_dir = static_dir


class ManagementServer:
    def __init__(self, service, host: str, port: int, static_dir: Path) -> None:
        self.host = host
        self.port = port
        self.httpd = ManagementHTTPServer((host, port), ManagementHandler, service, static_dir)
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
        if path in ("/api/status", "/status"):
            self.send_json(self.server.service.snapshot_status())
        elif path in ("/api/metrics", "/metrics"):
            self.send_json(self.server.service.snapshot_status()["stats"])
        elif path == "/api/logs":
            query = parse_qs(urlparse(self.path).query)
            try:
                limit = int(query.get("limit", ["100"])[0])
            except ValueError:
                limit = 100
            self.send_json(self.server.service.snapshot_events(limit=limit))
        elif path == "/ca.cer":
            self.send_ca(head_only=False)
        else:
            self.send_static(path, head_only=False)

    def do_HEAD(self) -> None:
        path = urlparse(self.path).path
        if path == "/ca.cer":
            self.send_ca(head_only=True)
        else:
            self.send_static(path, head_only=True)

    def do_PUT(self) -> None:
        self.handle_runtime_mutation()

    def do_POST(self) -> None:
        self.handle_runtime_mutation()

    def handle_runtime_mutation(self) -> None:
        path = urlparse(self.path).path
        try:
            payload = self.read_json_body()
            if path == "/api/runtime/target":
                result = self.server.service.update_target(payload)
                self.send_json(result)
                self.record_management_event(
                    "management_runtime_mutation",
                    "info",
                    "runtime target mutation accepted",
                    status=HTTPStatus.OK,
                    details={"endpoint": path},
                )
            elif path == "/api/runtime/favorites":
                result = self.server.service.add_favorite_location(payload)
                self.send_json(result)
                self.record_management_event(
                    "management_runtime_mutation",
                    "info",
                    "runtime favorite location accepted",
                    status=HTTPStatus.OK,
                    details={"endpoint": path},
                )
            elif path == "/api/runtime/mode":
                result = self.server.service.update_mode(payload.get("mode"))
                self.send_json(result)
                self.record_management_event(
                    "management_runtime_mutation",
                    "info",
                    "runtime mode mutation accepted",
                    status=HTTPStatus.OK,
                    details={"endpoint": path, "mode": payload.get("mode")},
                )
            elif path == "/api/runtime/enabled":
                result = self.server.service.update_enabled(payload.get("enabled"))
                self.send_json(result)
                self.record_management_event(
                    "management_runtime_mutation",
                    "info",
                    "runtime enabled mutation accepted",
                    status=HTTPStatus.OK,
                    details={"endpoint": path, "enabled": payload.get("enabled")},
                )
            elif path == "/api/runtime/reset":
                result = self.server.service.reset_runtime_state()
                self.send_json(result)
                self.record_management_event(
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
                self.record_management_event(
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
                self.record_management_event(
                    "management_not_found",
                    "warning",
                    "management endpoint not found",
                    status=HTTPStatus.NOT_FOUND,
                    details={"endpoint": path},
                )
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            self.record_management_event(
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
            self.record_management_event(
                "management_error",
                "error",
                f"management request failed: {type(exc).__name__}",
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
                details={"endpoint": path, "error": str(exc)},
            )

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:5173")
        self.send_header("Access-Control-Allow-Methods", "GET, PUT, POST, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
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

    def send_json(self, payload: Any, status: int | HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_ca(self, head_only: bool) -> None:
        path = self.server.service.ca_cert_path()
        if not path.exists() or not path.is_file():
            self.record_management_event(
                "management_ca_download",
                "warning",
                "CA certificate download failed: not found",
                status=HTTPStatus.NOT_FOUND,
                details={"ca_path": str(path), "head_only": head_only},
            )
            self.send_error(HTTPStatus.NOT_FOUND, "CA certificate not found")
            return
        self.send_file(path, "application/x-x509-ca-cert", head_only=head_only)
        self.record_management_event(
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

    def record_management_event(
        self,
        event_type: str,
        level: str,
        message: str,
        *,
        status: int | HTTPStatus | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        client = self.client_address[0] if self.client_address else None
        self.server.service.record_event(
            event_type,
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


def start_management_server(service, host: str, port: int, static_dir: Path) -> ManagementServer:
    server = ManagementServer(service, host, port, static_dir)
    server.start()
    return server

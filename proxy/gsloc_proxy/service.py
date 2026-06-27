from __future__ import annotations

import math
import threading
import time
from collections import deque
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from mitmproxy import certs

from .config import load_policy, policy_to_dict
from .models import FavoriteLocation, ProxyPolicy, ProxySettings, RuntimeState, TargetState
from .state import load_state, save_state, state_to_dict


class GslocProxyService:
    def __init__(self, state_path: Path, policy_path: Path, confdir: Path) -> None:
        self.state_path = state_path
        self.policy_path = policy_path
        self.confdir = confdir
        self.lock = threading.RLock()
        self.runtime: RuntimeState = load_state(state_path)
        self.policy: ProxyPolicy = load_policy(policy_path)
        self.stats = {
            "request_total": 0,
            "pass_through_total": 0,
            "reject_total": 0,
            "patch_success": 0,
            "patch_noop": 0,
            "patch_error": 0,
        }
        self.events = deque(maxlen=1000)
        self.next_event_id = 1
        self.last_patch: dict[str, Any] | None = None

    def reload(self, state_path: Path, policy_path: Path, confdir: Path) -> None:
        runtime = load_state(state_path)
        policy = load_policy(policy_path)
        with self.lock:
            self.state_path = state_path
            self.policy_path = policy_path
            self.confdir = confdir
            self.runtime = runtime
            self.policy = policy

    def settings(self) -> ProxySettings:
        with self.lock:
            return ProxySettings(runtime=self.runtime, policy=self.policy)

    def record_event(
        self,
        event_type: str,
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
    ) -> None:
        with self.lock:
            self._append_event_locked(
                event_type,
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
            self._append_event_locked(
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
            self._append_event_locked(
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
            self._append_event_locked(
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
            self._append_event_locked(
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
            log_count = len(self.events)
            latest_log_id = self.events[-1]["id"] if self.events else None
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
            self._append_event_locked(
                "runtime_target_updated",
                "info",
                "target updated",
                layer="runtime",
                source="service.runtime",
                details={"previous": previous, "next": target_data},
            )
        return {"ok": True, "target": target_data, "runtime": runtime_data}

    def add_favorite_location(self, payload: dict[str, Any]) -> dict[str, Any]:
        lat = self._number_in_range(payload.get("lat"), "lat", -90, 90)
        lng = self._number_in_range(payload.get("lng"), "lng", -180, 180)
        scale = self._number_in_range(payload.get("scale", 1), "scale", 0, 10)
        name = "" if payload.get("name") is None else str(payload.get("name")).strip()
        favorite = FavoriteLocation(lat=lat, lng=lng, name=name, scale=scale)
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
            self._append_event_locked(
                "runtime_favorite_added",
                "info",
                "favorite location saved",
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
            self._append_event_locked(
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
            self._append_event_locked(
                "runtime_enabled_updated",
                "info",
                "runtime enabled updated",
                layer="runtime",
                source="service.runtime",
                details={"previous": previous, "next": enabled},
            )
        return {"ok": True, "enabled": enabled, "runtime": runtime_data}

    def reset_runtime_state(self) -> dict[str, Any]:
        with self.lock:
            previous = state_to_dict(self.runtime)
            self._save_runtime_locked(RuntimeState())
            self._append_event_locked(
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
            self.record_event(
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

        event_type = "ca_regenerate_started" if regenerate else "ca_generate_started"
        self.record_event(
            event_type,
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
            self.record_event(
                "ca_generate_error",
                "error",
                f"CA generation failed: {type(exc).__name__}",
                layer="ca",
                source="service.ca",
                details={"error": str(exc), "confdir": str(confdir)},
            )
            raise
        self.record_event(
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

    def snapshot_events(self, limit: int = 100) -> dict[str, Any]:
        safe_limit = max(1, min(int(limit), 1000))
        with self.lock:
            events = list(self.events)[-safe_limit:]
        return {
            "events": events,
            "limit": safe_limit,
            "count": len(events),
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
            self._append_event_locked(
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

    def _append_event_locked(
        self,
        event_type: str,
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
    ) -> dict[str, Any]:
        event: dict[str, Any] = {
            "id": self.next_event_id,
            "ts": time.time(),
            "type": event_type,
            "level": level,
            "message": message,
        }
        self.next_event_id += 1
        if layer is not None:
            event["layer"] = layer
        if source is not None:
            event["source"] = source
        if host is not None:
            event["host"] = host
        if path is not None:
            event["path"] = path
        if status is not None:
            event["status"] = status
        if client is not None:
            event["client"] = client
        if method is not None:
            event["method"] = method
        if details:
            event["details"] = details
        self.events.append(event)
        return event

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

    @staticmethod
    def _favorite_key(favorite: FavoriteLocation) -> tuple[float, float, str]:
        return (round(favorite.lat, 8), round(favorite.lng, 8), favorite.name)

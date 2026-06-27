from __future__ import annotations

import json
import math
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from .models import FavoriteLocation, RuntimeState, TargetState


DEFAULT_STATE_PATH = Path("/etc/gsloc-proxy/state.json")


def resolve_state_path(path: str | os.PathLike[str] | None = None) -> Path:
    return Path(
        path
        or os.environ.get("GSLOC_STATE_PATH")
        or DEFAULT_STATE_PATH
    )


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"state JSON must be an object: {path}")
    return data


def load_state(path: str | os.PathLike[str] | None = None) -> RuntimeState:
    state_path = resolve_state_path(path)
    raw = _load_json(state_path)
    target_raw = raw.get("target") or {}
    favorites_raw = raw.get("favorites") or []
    if not isinstance(favorites_raw, list):
        favorites_raw = []

    return RuntimeState(
        proxy_enabled=bool(raw.get("proxy_enabled", True)),
        session_id=_positive_int(raw.get("session_id", 1), "session_id"),
        session_started_at=_optional_number(
            raw.get("session_started_at", time.time()),
            "session_started_at",
        ),
        enabled=bool(raw.get("enabled", True)),
        target=TargetState(
            lat=_number(target_raw.get("lat", 0.0), "target.lat"),
            lng=_number(target_raw.get("lng", 0.0), "target.lng"),
            name=str(target_raw.get("name", "Authorized Test Location")),
            mode=str(target_raw.get("mode", "clamp")),
            scale=_number(target_raw.get("scale", 1.0), "target.scale"),
        ),
        favorites=tuple(
            favorite
            for favorite in (
                _favorite_from_raw(item, index)
                for index, item in enumerate(favorites_raw)
            )
            if favorite is not None
        ),
    )


def state_to_dict(state: RuntimeState) -> dict[str, Any]:
    return {
        "proxy_enabled": state.proxy_enabled,
        "session_id": state.session_id,
        "session_started_at": state.session_started_at,
        "enabled": state.enabled,
        "target": {
            "lat": state.target.lat,
            "lng": state.target.lng,
            "name": state.target.name,
            "mode": state.target.mode,
            "scale": state.target.scale,
        },
        "favorites": [
            {
                "lat": favorite.lat,
                "lng": favorite.lng,
                "name": favorite.name,
                "scale": favorite.scale,
            }
            for favorite in state.favorites
        ],
    }


def save_state(state: RuntimeState, path: str | os.PathLike[str]) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=state_path.parent,
            prefix=f".{state_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as f:
            tmp_path = Path(f.name)
            json.dump(state_to_dict(state), f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp_path, state_path)
        tmp_path = None
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def _number(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _optional_number(value: Any, name: str) -> float | None:
    if value is None:
        return None
    return _number(value, name)


def _positive_int(value: Any, name: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    return max(1, number)


def _favorite_from_raw(value: Any, index: int) -> FavoriteLocation | None:
    if not isinstance(value, dict):
        return None
    return FavoriteLocation(
        lat=_number(value.get("lat"), f"favorites[{index}].lat"),
        lng=_number(value.get("lng"), f"favorites[{index}].lng"),
        name=str(value.get("name", "")),
        scale=_number(value.get("scale", 1.0), f"favorites[{index}].scale"),
    )

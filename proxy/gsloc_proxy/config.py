from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .models import AllowRule, FailurePolicy, LoggingPolicy, ProxyPolicy


DEFAULT_POLICY_PATH = Path("/etc/gsloc-proxy/policy.json")


def resolve_policy_path(path: str | os.PathLike[str] | None = None) -> Path:
    return Path(path or os.environ.get("GSLOC_POLICY_PATH") or DEFAULT_POLICY_PATH)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"policy JSON must be an object: {path}")
    return data


def load_policy(path: str | os.PathLike[str] | None = None) -> ProxyPolicy:
    policy_path = resolve_policy_path(path)
    raw = _load_json(policy_path)

    allow_raw = raw.get(
        "allow",
        [
            {
                "host": "gs-loc-cn.apple.com",
                "paths": ["/clls/wloc"],
                "pass_through_other_paths": True,
            }
        ],
    )
    if not isinstance(allow_raw, list):
        raise ValueError("policy.allow must be an array")

    failure_raw = raw.get("failure") or {}
    logging_raw = raw.get("logging") or {}

    return ProxyPolicy(
        allow=tuple(_load_allow_rule(item) for item in allow_raw),
        failure=FailurePolicy(
            patch_error=str(failure_raw.get("patch_error", "pass_through")),
        ),
        logging=LoggingPolicy(
            sample_limit=int(logging_raw.get("sample_limit", 5)),
        ),
    )


def policy_to_dict(policy: ProxyPolicy) -> dict[str, Any]:
    return {
        "allow": [
            {
                "host": rule.host,
                "paths": list(rule.paths),
                "pass_through_other_paths": rule.pass_through_other_paths,
            }
            for rule in policy.allow
        ],
        "failure": {
            "patch_error": policy.failure.patch_error,
        },
        "logging": {
            "sample_limit": policy.logging.sample_limit,
        },
    }


def _load_allow_rule(raw: Any) -> AllowRule:
    if not isinstance(raw, dict):
        raise ValueError("policy.allow entries must be objects")
    paths = raw.get("paths", ["/clls/wloc"])
    if not isinstance(paths, list):
        raise ValueError("policy.allow[].paths must be an array")
    return AllowRule(
        host=str(raw.get("host", "gs-loc-cn.apple.com")),
        paths=tuple(str(path) for path in paths),
        pass_through_other_paths=bool(raw.get("pass_through_other_paths", True)),
    )

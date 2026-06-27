from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TargetState:
    lat = 0.0
    lng = 0.0
    name = "Authorized Test Location"
    mode: str = "clamp"
    scale: float = 1.0


@dataclass(frozen=True)
class FavoriteLocation:
    lat: float
    lng: float
    name: str = ""
    scale: float = 1.0


@dataclass(frozen=True)
class RuntimeState:
    enabled: bool = True
    target: TargetState = TargetState()
    favorites: tuple[FavoriteLocation, ...] = ()


@dataclass(frozen=True)
class AllowRule:
    host: str = "gs-loc-cn.apple.com"
    paths: tuple[str, ...] = ("/clls/wloc",)
    pass_through_other_paths: bool = True


@dataclass(frozen=True)
class FailurePolicy:
    patch_error: str = "pass_through"


@dataclass(frozen=True)
class LoggingPolicy:
    sample_limit: int = 5


@dataclass(frozen=True)
class ProxyPolicy:
    allow: tuple[AllowRule, ...] = (AllowRule(),)
    failure: FailurePolicy = FailurePolicy()
    logging: LoggingPolicy = LoggingPolicy()


@dataclass(frozen=True)
class ProxySettings:
    runtime: RuntimeState = RuntimeState()
    policy: ProxyPolicy = ProxyPolicy()

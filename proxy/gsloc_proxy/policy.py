from __future__ import annotations

from mitmproxy import http

from .models import AllowRule, ProxyPolicy, ProxySettings


def matching_rule(flow: http.HTTPFlow, policy: ProxyPolicy) -> AllowRule | None:
    host = flow.request.pretty_host or flow.request.host or ""
    for rule in policy.allow:
        if host.lower() == rule.host.lower():
            return rule
    return None


def path_matches(flow: http.HTTPFlow, rule: AllowRule) -> bool:
    path = flow.request.path or ""
    return any(path.startswith(allowed) for allowed in rule.paths)


def describe_request_decision(flow: http.HTTPFlow, settings: ProxySettings) -> dict[str, object]:
    rule = matching_rule(flow, settings.policy)
    host = flow.request.pretty_host or flow.request.host or ""
    path = flow.request.path or ""
    if not settings.runtime.proxy_enabled:
        return {
            "action": "reject",
            "reason": "proxy_disabled",
            "host": host,
            "path": path,
        }
    if rule is None:
        return {
            "action": "reject",
            "reason": "host_not_allowed",
            "host": host,
            "path": path,
        }
    details: dict[str, object] = {
        "host": host,
        "path": path,
        "rule_host": rule.host,
        "allowed_paths": list(rule.paths),
        "pass_through_other_paths": rule.pass_through_other_paths,
    }
    if path_matches(flow, rule):
        return {**details, "action": "patch_target", "reason": "path_allowed"}
    if rule.pass_through_other_paths:
        return {**details, "action": "pass_through", "reason": "path_pass_through"}
    return {**details, "action": "reject", "reason": "path_not_allowed"}


def describe_patch_decision(flow: http.HTTPFlow, settings: ProxySettings) -> dict[str, object]:
    request_decision = describe_request_decision(flow, settings)
    details = dict(request_decision)
    if not settings.runtime.proxy_enabled:
        return {**details, "action": "skip", "reason": "proxy_disabled"}
    if not settings.runtime.enabled:
        return {**details, "action": "skip", "reason": "runtime_disabled"}
    if not flow.response:
        return {**details, "action": "skip", "reason": "no_response"}
    if not flow.response.raw_content:
        return {**details, "action": "skip", "reason": "empty_response_body"}
    if request_decision.get("action") != "patch_target":
        return {**details, "action": "skip", "reason": "not_patch_target"}
    return {**details, "action": "patch", "reason": "patch_target"}


def is_patch_target(flow: http.HTTPFlow, settings: ProxySettings) -> bool:
    rule = matching_rule(flow, settings.policy)
    return rule is not None and path_matches(flow, rule)


def should_patch(flow: http.HTTPFlow, settings: ProxySettings) -> bool:
    if not settings.runtime.proxy_enabled:
        return False
    if not settings.runtime.enabled:
        return False
    if not flow.response or not flow.response.raw_content:
        return False
    return is_patch_target(flow, settings)


def should_reject_request(flow: http.HTTPFlow, settings: ProxySettings) -> bool:
    # mitmproxy regular mode may receive only traffic that the client routed here.
    # Keep non-allowed traffic from accidentally using this service as a generic proxy.
    if not settings.runtime.proxy_enabled:
        return True
    rule = matching_rule(flow, settings.policy)
    if rule is None:
        return True
    if path_matches(flow, rule):
        return False
    return not rule.pass_through_other_paths

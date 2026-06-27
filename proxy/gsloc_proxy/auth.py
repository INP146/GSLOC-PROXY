from __future__ import annotations

import hmac
import os
import secrets
import threading
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.cookies import SimpleCookie
from typing import Any


SESSION_COOKIE_NAME = "gsloc_session"
SESSION_TTL_SECONDS = 12 * 60 * 60


@dataclass(frozen=True)
class AuthConfig:
    username: str = "admin"
    password: str = ""
    enabled: bool = False


@dataclass(frozen=True)
class AuthSession:
    user: str
    csrf_token: str
    expires_at: float


def load_auth_config(username: str | None = None, password: str | None = None) -> AuthConfig:
    resolved_username = username or os.environ.get("GSLOC_MANAGE_USER") or "admin"
    resolved_password = password if password is not None else os.environ.get("GSLOC_MANAGE_PASSWORD", "")
    return AuthConfig(
        username=resolved_username,
        password=resolved_password,
        enabled=bool(resolved_password),
    )


class AuthManager:
    def __init__(self, config: AuthConfig) -> None:
        self.config = config
        self.sessions: dict[str, AuthSession] = {}
        self.lock = threading.RLock()

    def is_enabled(self) -> bool:
        return self.config.enabled

    def login(self, username: Any, password: Any) -> tuple[str, AuthSession] | None:
        if not self.is_enabled():
            return self._create_session(self.config.username)
        if not isinstance(username, str) or not isinstance(password, str):
            return None
        if not secrets.compare_digest(username, self.config.username):
            return None
        if not secrets.compare_digest(password, self.config.password):
            return None
        return self._create_session(username)

    def logout(self, token: str | None) -> None:
        if token:
            with self.lock:
                self.sessions.pop(token, None)

    def session_for_cookie_header(self, cookie_header: str | None) -> tuple[str, AuthSession] | None:
        token = session_token_from_cookie_header(cookie_header)
        if not token:
            return None
        with self.lock:
            session = self.sessions.get(token)
            now = time.time()
            if session is None:
                return None
            if session.expires_at <= now:
                self.sessions.pop(token, None)
                return None
            return token, session

    def verify_csrf(self, session: AuthSession, token: str | None) -> bool:
        return bool(token and hmac.compare_digest(token, session.csrf_token))

    def _create_session(self, username: str) -> tuple[str, AuthSession]:
        with self.lock:
            self._prune_expired()
            token = secrets.token_urlsafe(32)
            session = AuthSession(
                user=username,
                csrf_token=secrets.token_urlsafe(32),
                expires_at=time.time() + SESSION_TTL_SECONDS,
            )
            self.sessions[token] = session
            return token, session

    def _prune_expired(self) -> None:
        now = time.time()
        expired = [token for token, session in self.sessions.items() if session.expires_at <= now]
        for token in expired:
            self.sessions.pop(token, None)


def session_token_from_cookie_header(cookie_header: str | None) -> str | None:
    if not cookie_header:
        return None
    cookie = SimpleCookie()
    try:
        cookie.load(cookie_header)
    except Exception:
        return None
    morsel = cookie.get(SESSION_COOKIE_NAME)
    return morsel.value if morsel is not None else None


def make_session_cookie(token: str, expires_at: float) -> str:
    max_age = max(0, int(expires_at - time.time()))
    return (
        f"{SESSION_COOKIE_NAME}={token}; "
        f"Max-Age={max_age}; Path=/; HttpOnly; SameSite=Strict"
    )


def make_clear_session_cookie() -> str:
    return f"{SESSION_COOKIE_NAME}=; Max-Age=0; Path=/; HttpOnly; SameSite=Strict"


def auth_payload(config: AuthConfig, session: AuthSession | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "auth_required": config.enabled,
        "authenticated": session is not None,
        "user": session.user if session is not None else None,
    }
    if session is not None:
        payload["csrf_token"] = session.csrf_token
        payload["expires_at"] = session.expires_at
    return payload


def auth_status_for_denial() -> tuple[dict[str, Any], HTTPStatus]:
    return {"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED

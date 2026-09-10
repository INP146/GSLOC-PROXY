from __future__ import annotations

import unittest
from unittest.mock import patch

from gsloc_proxy.auth import (
    AuthConfig,
    AuthManager,
    SESSION_COOKIE_NAME,
    SESSION_TTL_SECONDS,
    make_clear_session_cookie,
    make_session_cookie,
    session_token_from_cookie_header,
)


class SessionCookieTests(unittest.TestCase):
    def test_extracts_session_token_among_other_cookies(self) -> None:
        header = f"theme=dark; {SESSION_COOKIE_NAME}=session-token; locale=zh-CN"

        self.assertEqual(session_token_from_cookie_header(header), "session-token")

    def test_returns_none_for_missing_or_malformed_cookie(self) -> None:
        self.assertIsNone(session_token_from_cookie_header(None))
        self.assertIsNone(session_token_from_cookie_header("theme=dark"))
        self.assertIsNone(session_token_from_cookie_header("broken-cookie"))

    def test_session_cookie_uses_remaining_lifetime(self) -> None:
        with patch("gsloc_proxy.auth.time.time", return_value=1_000.0):
            cookie = make_session_cookie("session-token", 1_125.9)

        self.assertEqual(
            cookie,
            f"{SESSION_COOKIE_NAME}=session-token; Max-Age=125; "
            "Path=/; HttpOnly; SameSite=Strict",
        )

    def test_session_cookie_clamps_expired_session_lifetime_to_zero(self) -> None:
        with patch("gsloc_proxy.auth.time.time", return_value=1_000.0):
            cookie = make_session_cookie("session-token", 999.0)

        self.assertEqual(
            cookie,
            f"{SESSION_COOKIE_NAME}=session-token; Max-Age=0; "
            "Path=/; HttpOnly; SameSite=Strict",
        )

    def test_clear_cookie_expires_immediately(self) -> None:
        self.assertEqual(
            make_clear_session_cookie(),
            f"{SESSION_COOKIE_NAME}=; Max-Age=0; Path=/; HttpOnly; SameSite=Strict",
        )


class AuthManagerTests(unittest.TestCase):
    def test_login_rejects_non_string_credentials(self) -> None:
        manager = AuthManager(AuthConfig(username="admin", password="secret", enabled=True))

        self.assertIsNone(manager.login(None, "secret"))
        self.assertIsNone(manager.login("admin", None))
        self.assertIsNone(manager.login(123, "secret"))
        self.assertIsNone(manager.login("admin", 123))
        self.assertEqual(manager.sessions, {})

    def test_expired_session_is_removed(self) -> None:
        manager = AuthManager(AuthConfig(username="admin", password="", enabled=False))
        with patch("gsloc_proxy.auth.time.time", return_value=500.0):
            token, session = manager.login(None, None)  # type: ignore[misc]

        self.assertEqual(session.expires_at, 500.0 + SESSION_TTL_SECONDS)
        with patch("gsloc_proxy.auth.time.time", return_value=session.expires_at):
            self.assertIsNone(
                manager.session_for_cookie_header(f"{SESSION_COOKIE_NAME}={token}")
            )
        self.assertNotIn(token, manager.sessions)

    def test_login_prunes_expired_sessions(self) -> None:
        manager = AuthManager(AuthConfig(username="admin", password="", enabled=False))
        with patch("gsloc_proxy.auth.time.time", return_value=500.0):
            expired_token, _ = manager.login(None, None)  # type: ignore[misc]

        with patch(
            "gsloc_proxy.auth.time.time",
            return_value=500.0 + SESSION_TTL_SECONDS,
        ):
            active_token, _ = manager.login(None, None)  # type: ignore[misc]

        self.assertNotIn(expired_token, manager.sessions)
        self.assertIn(active_token, manager.sessions)


if __name__ == "__main__":
    unittest.main()

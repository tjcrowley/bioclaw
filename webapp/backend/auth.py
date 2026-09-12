"""Shared-password auth for every backend route (API-05).

Single secret, not per-user accounts (see REQUIREMENTS.md AUTH-01, deferred
to v2). Checked via Authorization: Bearer header, ?password= query param,
or a `session` cookie -- the query-param/cookie fallbacks exist because a
browser WebSocket client cannot set custom headers (07-RESEARCH.md Pitfall 1).
Always compared with secrets.compare_digest (timing-safe).
"""
import os
import secrets

from fastapi import Cookie, Header, HTTPException, Query, WebSocket, WebSocketException, status


def _valid(password: str | None) -> bool:
    expected = os.environ.get("BIOCLAW_WEB_PASSWORD")
    if expected is None or password is None:
        return False
    return secrets.compare_digest(password, expected)


async def require_password(
    authorization: str | None = Header(default=None),
    password: str | None = Query(default=None),
    session: str | None = Cookie(default=None),
) -> None:
    candidate = None
    if authorization and authorization.startswith("Bearer "):
        candidate = authorization.removeprefix("Bearer ")
    candidate = candidate or password or session
    if not _valid(candidate):
        raise HTTPException(status_code=401, detail="unauthorized")


async def require_password_ws(
    websocket: WebSocket,
    password: str | None = Query(default=None),
    session: str | None = Cookie(default=None),
) -> None:
    if not _valid(password or session):
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)

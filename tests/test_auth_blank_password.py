"""Regression tests: a blank BIOCLAW_WEB_PASSWORD must never authenticate anyone.

Found during Phase 14-04. `_valid()` guarded only `expected is None`, so with
BIOCLAW_WEB_PASSWORD="" the timing-safe compare became
`secrets.compare_digest("", "")` -> True.

The reachable vector is an empty `session` cookie, not an empty `?password=`:
`candidate = candidate or password or session` returns the LAST operand when all
are falsy, so `?password=` collapses to None (rejected) while `session=""` stays
"" and reaches `_valid`. Both callers are covered below so a future refactor of
that `or` chain cannot silently reopen the hole from the other direction.
"""
import asyncio

import pytest
from fastapi import HTTPException, WebSocketException

from webapp.backend.auth import _valid, require_password, require_password_ws


@pytest.fixture
def blank_password(monkeypatch):
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "")


@pytest.fixture
def unset_password(monkeypatch):
    monkeypatch.delenv("BIOCLAW_WEB_PASSWORD", raising=False)


def test_valid_rejects_empty_candidate_when_expected_is_blank(blank_password):
    assert _valid("") is False


def test_valid_rejects_any_candidate_when_expected_is_blank(blank_password):
    assert _valid("anything") is False
    assert _valid(None) is False


def test_valid_rejects_empty_candidate_when_expected_unset(unset_password):
    assert _valid("") is False


@pytest.mark.parametrize(
    "authorization,password,session",
    [
        (None, None, ""),        # the live bypass vector: empty session cookie
        (None, "", None),
        ("Bearer ", None, None),
        ("Bearer ", "", ""),
        (None, None, None),
        (None, "guess", None),
    ],
)
def test_require_password_rejects_everything_when_blank(
    blank_password, authorization, password, session
):
    with pytest.raises(HTTPException):
        asyncio.run(
            require_password(
                authorization=authorization, password=password, session=session
            )
        )


@pytest.mark.parametrize(
    "password,session",
    [
        (None, ""),              # the live bypass vector on the WebSocket path
        ("", None),
        ("", ""),
        (None, None),
        ("guess", None),
    ],
)
def test_require_password_ws_rejects_everything_when_blank(
    blank_password, password, session
):
    with pytest.raises(WebSocketException):
        asyncio.run(
            require_password_ws(websocket=None, password=password, session=session)
        )


def test_real_password_still_authenticates(monkeypatch):
    """The fix must not break the normal path."""
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    assert _valid("testpass") is True
    asyncio.run(require_password(authorization="Bearer testpass", password=None, session=None))
    asyncio.run(require_password(authorization=None, password="testpass", session=None))
    asyncio.run(require_password(authorization=None, password=None, session="testpass"))
    asyncio.run(require_password_ws(websocket=None, password="testpass", session=None))
    with pytest.raises(HTTPException):
        asyncio.run(require_password(authorization=None, password="wrong", session=None))

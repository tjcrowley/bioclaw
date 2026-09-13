"""Pydantic request/response contracts for the webapp backend (API-01, API-02).

These are the stable shapes Plan 07-02's main.py/streaming.py/deps.py
implement against -- defined here in Wave 1 so later tasks never need to
improvise the wire format mid-implementation.
"""
from pydantic import BaseModel


class AskRequest(BaseModel):
    question: str
    session_id: str | None = None
    stream_id: str | None = None


class ToolEvent(BaseModel):
    tool_name: str
    tool_input: dict
    is_error: bool = False


class AskResponse(BaseModel):
    answer: str
    session_id: str
    citations: list = []


class SessionSummary(BaseModel):
    session_id: str
    created_at: str | None = None
    last_active_at: str | None = None
    recent_datasets: list[str] = []


class SessionListResponse(BaseModel):
    sessions: list[SessionSummary]


class UploadResponse(BaseModel):
    status: str
    dataset_id: str | None = None
    detail: str | None = None
    session_id: str | None = None


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    ok: bool

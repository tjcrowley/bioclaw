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

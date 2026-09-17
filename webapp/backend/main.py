"""FastAPI app: POST /api/ask (API-01) + WS /ws/{stream_id} (API-02) +
POST /api/upload (API-04), all password-gated (API-05). Single Uvicorn
worker only -- see webapp/backend/streaming.py's module docstring.
"""
import os as _os
import uuid
from typing import Annotated

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.staticfiles import StaticFiles

import agent.tools as agent_tools
from ingest.pipeline import ingest_10x
from webapp.backend import deps, streaming, uploads
from webapp.backend.auth import _valid, require_password, require_password_ws
from webapp.backend.schemas import (
    AskRequest,
    AskResponse,
    LoginRequest,
    LoginResponse,
    MessageRecord,
    SessionListResponse,
    SessionSummary,
    UploadResponse,
)

app = FastAPI(title="bioclaw webapp backend")


@app.post("/api/ask", dependencies=[Depends(require_password)])
async def ask(
    req: AskRequest,
    ask_question=Depends(deps.get_ask_question),
    session_memory=Depends(deps.get_session_memory),
) -> AskResponse:
    extra_hooks = []
    if req.stream_id:
        queue = streaming.get_or_create_queue(req.stream_id)
        extra_hooks.append(streaming.make_stream_hook(queue))

    answer, session_id, citations = await ask_question(
        req.question,
        session_memory=session_memory,
        session_id=req.session_id,  # was previously ignored
        extra_hooks=extra_hooks,
    )
    # Store conversation turns for HIST-01 history replay
    session_memory.touch(session_id)
    session_memory.add_message(session_id, "user", req.question)
    session_memory.add_message(session_id, "assistant", answer)
    return AskResponse(answer=answer, session_id=session_id, citations=citations)


@app.get("/api/sessions", dependencies=[Depends(require_password)])
async def list_sessions(session_memory=Depends(deps.get_session_memory)) -> SessionListResponse:
    return SessionListResponse(sessions=session_memory.list_sessions())


@app.get("/api/sessions/{session_id}", dependencies=[Depends(require_password)])
async def get_session(
    session_id: str, session_memory=Depends(deps.get_session_memory)
) -> SessionSummary:
    if not session_memory.session_exists(session_id):
        raise HTTPException(status_code=404, detail="unknown session_id")
    msgs = session_memory.get_messages(session_id)
    return SessionSummary(
        session_id=session_id,
        recent_datasets=session_memory.recent_datasets(session_id),
        messages=[MessageRecord(**m) for m in msgs],
    )


@app.post("/api/upload", dependencies=[Depends(require_password)])
async def upload_dataset(
    name: Annotated[str, Form()],
    files: Annotated[list[UploadFile], File()],
    session_id: Annotated[str | None, Form()] = None,
    session_memory=Depends(deps.get_session_memory),
) -> UploadResponse:
    try:
        staged_path = await uploads.stage(files)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    resolved_session_id = session_id or str(uuid.uuid4())
    try:
        dataset_id = ingest_10x(staged_path, name, store_root=agent_tools.STORE_ROOT)
    except Exception as exc:
        # ingest_10x can raise on a genuinely bad-but-present file (QC rejects every
        # cell, duplicate name/version race, etc.) -- report it as a conversational
        # result, not a bare 500 (08-RESEARCH.md Pitfall 5).
        return UploadResponse(
            status="error", detail=str(exc), dataset_id=None, session_id=resolved_session_id
        )
    finally:
        uploads.cleanup(staged_path)

    session_memory.touch(resolved_session_id)
    session_memory.record(resolved_session_id, dataset_id, note=f"uploaded via /api/upload: {name}")
    return UploadResponse(
        status="success", dataset_id=dataset_id, detail=None, session_id=resolved_session_id
    )


@app.websocket("/ws/{stream_id}")
async def stream_events(
    websocket: WebSocket,
    stream_id: str,
    _auth: None = Depends(require_password_ws),
) -> None:
    await websocket.accept()
    queue = streaming.get_or_create_queue(stream_id)
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        streaming.drop_queue(stream_id)


@app.post("/api/login")
async def login(req: LoginRequest, response: Response) -> LoginResponse:
    if not _valid(req.password):
        raise HTTPException(status_code=401, detail="unauthorized")
    response.set_cookie(
        key="session",
        value=req.password,
        httponly=True,
        samesite="strict",
        path="/",
    )
    return LoginResponse(ok=True)


_FRONTEND_DIR = _os.path.join(_os.path.dirname(__file__), "..", "frontend")
app.mount("/app", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")

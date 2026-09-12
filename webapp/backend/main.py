"""FastAPI app: POST /api/ask (API-01) + WS /ws/{stream_id} (API-02), both
password-gated (API-05). Single Uvicorn worker only -- see
webapp/backend/streaming.py's module docstring.
"""
from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect

from webapp.backend import deps, streaming
from webapp.backend.auth import require_password, require_password_ws
from webapp.backend.schemas import AskRequest, AskResponse

app = FastAPI(title="bioclaw webapp backend")


@app.post("/api/ask", dependencies=[Depends(require_password)])
async def ask(req: AskRequest, ask_question=Depends(deps.get_ask_question)) -> AskResponse:
    extra_hooks = []
    if req.stream_id:
        queue = streaming.get_or_create_queue(req.stream_id)
        extra_hooks.append(streaming.make_stream_hook(queue))

    answer, session_id, citations = await ask_question(
        req.question,
        extra_hooks=extra_hooks,
    )
    return AskResponse(answer=answer, session_id=session_id, citations=citations)


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

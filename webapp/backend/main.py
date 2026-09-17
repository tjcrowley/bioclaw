"""FastAPI app: POST /api/ask (API-01) + WS /ws/{stream_id} (API-02) +
POST /api/upload (API-04), GET /api/export/csv (EXPORT-01), all
password-gated (API-05). Single Uvicorn worker only -- see
webapp/backend/streaming.py's module docstring.
"""
import io
import os as _os
import uuid
import zipfile
from typing import Annotated

import pandas as pd
import scanpy as sc
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
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

import agent.tools as agent_tools
from ingest.pipeline import ingest_10x
from ingest.store import DatasetStore
from webapp.backend import deps, streaming, uploads
from webapp.backend.auth import _valid, require_password, require_password_ws
from webapp.backend.export_script import generate_analysis_script
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
    tool_events_collector: list[dict] = []

    async def _collect_tool_event(input_data, tool_use_id, context):
        """Captures tool events for history replay (HIST-01 gap closure)."""
        try:
            tool_events_collector.append({
                "tool_name": input_data.get("tool_name", ""),
                "is_error": bool(
                    isinstance(input_data.get("tool_response"), dict)
                    and input_data.get("tool_response", {}).get("is_error")
                ),
            })
        except Exception:
            pass
        return {}

    extra_hooks = [_collect_tool_event]
    if req.stream_id:
        queue = streaming.get_or_create_queue(req.stream_id)
        extra_hooks.append(streaming.make_stream_hook(queue))

    answer, session_id, citations = await ask_question(
        req.question,
        session_memory=session_memory,
        session_id=req.session_id,  # was previously ignored
        extra_hooks=extra_hooks,
    )
    # Store conversation turns for HIST-01 history replay (with citations and tool events)
    session_memory.touch(session_id)
    session_memory.add_message(session_id, "user", req.question)
    session_memory.add_message(
        session_id,
        "assistant",
        answer,
        citations=citations if citations else None,
        tool_events=tool_events_collector if tool_events_collector else None,
    )
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


@app.get("/api/export/csv", dependencies=[Depends(require_password)])
async def export_csv(dataset_id: str) -> StreamingResponse:
    """EXPORT-01: Download cluster assignments, DE table, and annotation results
    for the named dataset as a ZIP of three CSV files.

    dataset_id format: "name@version" where version is an integer (e.g. mydata@1).
    Returns a ZIP with clusters.csv, de_genes.csv, and annotations.csv.
    Gracefully handles missing leiden clustering or DE results with placeholder rows.
    """
    # Parse dataset_id format: "name@version"
    parts = dataset_id.split("@", 1)
    if len(parts) != 2:
        raise HTTPException(
            status_code=422,
            detail="dataset_id must be name@version (e.g. mydata@1)",
        )
    name, version_str = parts
    version = int(version_str) if version_str.isdigit() else None

    store = DatasetStore(root=agent_tools.STORE_ROOT)
    try:
        adata = store.load(name, version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Cluster assignments (leiden)
        if "leiden" in adata.obs.columns:
            clusters_df = adata.obs[["leiden"]].reset_index()
            clusters_df.columns = ["cell_barcode", "cluster"]
            zf.writestr("clusters.csv", clusters_df.to_csv(index=False))
        else:
            zf.writestr("clusters.csv", "cell_barcode,cluster\n(no cluster data)\n")

        # 2. DE table (rank_genes_groups)
        if "rank_genes_groups" in adata.uns:
            groups = list(adata.uns["rank_genes_groups"]["names"].dtype.names)
            de_frames = []
            for g in groups:
                df = sc.get.rank_genes_groups_df(adata, group=g)
                df.insert(0, "cluster", g)
                de_frames.append(df)
            de_csv = pd.concat(de_frames, ignore_index=True) if de_frames else pd.DataFrame()
            zf.writestr("de_genes.csv", de_csv.to_csv(index=False))
        else:
            zf.writestr(
                "de_genes.csv",
                "cluster,names,scores,pvals,pvals_adj,logfoldchanges\n(no DE data)\n",
            )

        # 3. Annotations (from adata.uns — populated when annotate() has been called)
        # NOTE: annotation/pipeline.py's annotate() returns results as a dict but does
        # NOT persist them back to the store. So adata.uns.get("annotation", {}) will
        # typically be empty. The placeholder row is the expected output for un-annotated
        # datasets. If annotation data is ever stored back to the AnnData in future, the
        # expected uns key is "annotation" with sub-keys "fm_calls" and "baseline_calls".
        ann_lines = ["cluster,method,label,confidence,ontology_term_id"]
        ann_data = adata.uns.get("annotation", {})
        for call in ann_data.get("fm_calls", []):
            ann_lines.append(
                f"{call.get('cluster', '')},fm,"
                f"{call.get('label', '')},"
                f"{call.get('confidence', '')},"
                f"{call.get('ontology_term_id', '')}"
            )
        for call in ann_data.get("baseline_calls", []):
            ann_lines.append(
                f"{call.get('cluster', '')},baseline,"
                f"{call.get('label', '')},"
                f"{call.get('confidence', '')},"
                f"{call.get('ontology_term_id', '')}"
            )
        if len(ann_lines) == 1:
            ann_lines.append("(no annotation data)")
        zf.writestr("annotations.csv", "\n".join(ann_lines) + "\n")

    buf.seek(0)
    safe_name = name.replace("/", "_").replace(" ", "_")
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}_export.zip"'
        },
    )


@app.get("/api/export/script", dependencies=[Depends(require_password)])
async def export_script(dataset_id: str) -> StreamingResponse:
    """EXPORT-02: Render a self-contained, reproducible scanpy .py script for the
    named dataset that recreates the QC thresholds, analysis parameters, random
    seed, and dataset source used in the BioClaw session.

    dataset_id format: "name@version" where version is an integer (e.g. mydata@1).
    """
    # Parse dataset_id format: "name@version"
    parts = dataset_id.split("@", 1)
    if len(parts) != 2:
        raise HTTPException(
            status_code=422,
            detail="dataset_id must be name@version (e.g. mydata@1)",
        )
    name, version_str = parts
    version = int(version_str) if version_str.isdigit() else None

    store = DatasetStore(root=agent_tools.STORE_ROOT)
    try:
        adata = store.load(name, version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Look up the source_path provenance from the registry record matching the
    # loaded version (or the latest record if no explicit version was requested).
    records = store.list(name)
    source_path = None
    if records:
        if version is not None:
            matches = [r for r in records if r["version"] == version]
            record = matches[0] if matches else records[-1]
        else:
            record = records[-1]
        source_path = record.get("source_path")

    script = generate_analysis_script(adata, source_path, dataset_id)

    safe_name = name.replace("/", "_").replace(" ", "_")
    return StreamingResponse(
        io.BytesIO(script.encode()),
        media_type="text/x-python",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}_analysis.py"'
        },
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

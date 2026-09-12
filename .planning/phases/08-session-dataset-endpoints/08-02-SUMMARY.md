---
phase: 08-session-dataset-endpoints
plan: 02
subsystem: api
tags: [fastapi, multipart-upload, ingest, session-memory]

# Dependency graph
requires:
  - phase: 08-session-dataset-endpoints
    provides: "Plan 08-01's SessionMemory.touch()/record()/recent_datasets(), deps.get_session_memory() DI factory, UploadResponse schema, session_id flowing end-to-end through ask_question()/POST /api/ask"
provides:
  - "webapp/backend/uploads.py: stage()/cleanup() multipart staging helper distinguishing .h5/.h5ad single-file uploads from the real 3-file .mtx (10x MEX) trio, raising a clean ValueError on any wrong shape"
  - "POST /api/upload: password-gated endpoint accepting name + files (+ optional session_id) Form/File fields, invoking the real ingest_10x() pipeline against agent.tools.STORE_ROOT, and recording the resulting dataset_id into SessionMemory"
  - "A successful upload's dataset_id is recalled by the very next /api/ask question in the same session"
affects: [08-03, webapp-frontend]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Multipart staging-then-pipeline pattern: uploaded bytes are always written to a real tempfile/tempdir path before touching any pipeline function that expects a filesystem path (never bytes), with cleanup() in a finally block"
    - "Read agent.tools.STORE_ROOT as a module-attribute lookup at call time (agent_tools.STORE_ROOT), never copied into a local/module-level variable in a consumer module, so monkeypatch.setattr(agent_tools, \"STORE_ROOT\", ...) in tests reliably takes effect"
    - "Pipeline exceptions on a well-formed-but-bad upload are returned as a conversational status=\"error\" response body, not raised as a bare 500; only a structurally wrong upload (bad file count/names) is a raised HTTPException(422)"

key-files:
  created:
    - webapp/backend/uploads.py
    - tests/test_webapp_upload.py
  modified:
    - webapp/backend/main.py

key-decisions:
  - "uploads.py's stage()/cleanup() implemented exactly per the plan's provided code -- single-file suffix check first (len(files)==1 branch), then exact 3-name-set equality check for the .mtx trio; no deviation needed"
  - "main.py's upload_dataset() references agent_tools.STORE_ROOT inline in the function body (not imported as a bare name or copied to a local), matching the plan's explicit Pitfall-3 guidance so the test suite's monkeypatch.setattr(agent_tools, \"STORE_ROOT\", ...) works"

patterns-established:
  - "New multipart endpoints reuse the same dependencies=[Depends(require_password)] + Depends(deps.get_*) DI shape as the existing POST /api/ask and GET /api/sessions* routes"

requirements-completed: [API-04]

# Metrics
duration: ~6min
completed: 2026-09-12
---

# Phase 8 Plan 2: Dataset Upload Endpoint Summary

**POST /api/upload accepting a single .h5/.h5ad file or the real 3-file .mtx (10x MEX) trio, staged to a filesystem path and run through the real ingest_10x() pipeline against agent.tools.STORE_ROOT, with the resulting dataset_id recorded into SessionMemory and recalled by the next question in the same session**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-09-12T14:02:35Z (approx, from prior commit timestamp)
- **Completed:** 2026-09-12T14:05:56Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- New `webapp/backend/uploads.py` staging helper distinguishes a single `.h5`/`.h5ad` file from the real 3-file `.mtx` (10x MEX) trio (`matrix.mtx.gz`, `barcodes.tsv.gz`, `features.tsv.gz`), rejecting any wrong shape with a clean `ValueError` before scanpy ever sees the files
- New `POST /api/upload`, password-gated, wires `uploads.stage()` -> `ingest_10x()` (against `agent.tools.STORE_ROOT`, never a hardcoded `"data"`) -> `SessionMemory.record()`
- Malformed uploads (wrong file count/names) return `422`; a well-formed-but-pipeline-rejected upload (e.g. QC rejects every cell) returns a conversational `status="error"` body instead of an opaque `500`
- A successful upload's `dataset_id` is recalled by the very next `/api/ask` call in the same `session_id`, verified end to end with a fake `ask_question` double that reads `SessionMemory.recent_datasets()`

## Task Commits

Each task was committed atomically:

1. **Task 1: Multipart staging helper (webapp/backend/uploads.py)** - `53bb608` (feat, tdd)
2. **Task 2: Wire POST /api/upload into main.py** - `dc1feb1` (feat)

**Plan metadata:** (pending) `docs(08-02): complete plan`

_Note: Task 1 was `tdd="true"` but the plan's own action block provided both implementation and tests together (no separate RED-only failing-test commit); tests and implementation landed in the same commit, matching Plan 08-01's Task 1-2 precedent._

## Files Created/Modified
- `webapp/backend/uploads.py` - New: `stage()`/`cleanup()` multipart staging helper (single-file vs. 3-file-trio validation, tempfile/tempdir write)
- `webapp/backend/main.py` - Added `POST /api/upload` route: stage -> ingest_10x(store_root=agent_tools.STORE_ROOT) -> SessionMemory.touch()+record()
- `tests/test_webapp_upload.py` - New: 4 staging-only unit tests (Task 1) + 6 full endpoint tests via `TestClient` (Task 2), 10 total

## Decisions Made
None beyond what the plan specified -- both tasks implemented exactly per the plan's provided `<action>` code blocks (staging module, endpoint handler, all 10 tests). No architectural deviations.

## Deviations from Plan

None - plan executed exactly as written. All code and tests match the plan's `<action>` blocks verbatim; every pre-existing test in the full suite continued to pass unmodified.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- API-04 ("upload a dataset as part of the conversation flow") is now closed and structurally verified by tests, including the cross-call session-memory recall path
- `POST /api/upload` writes to the exact same `store_root` `agent.tools`'s MCP tools read from, so a dataset uploaded via the web UI is immediately usable by the agent in the same conversation -- no separate re-ingest step needed
- Full fast suite: 193 passed, 5 deselected (`live_llm`/`bio_fm_smoke`/`vcc_data` markers) -- no regression across ingest/QC, analysis, agent, annotation, perturbation, QA, or the full webapp backend
- Plan 08-03 (if any remaining Phase 8 work) can build directly on this endpoint; no known blockers

---
*Phase: 08-session-dataset-endpoints*
*Completed: 2026-09-12*

## Self-Check: PASSED

All 3 created/modified files and the SUMMARY.md itself confirmed present on disk; both task commits (53bb608, dc1feb1) confirmed present in git log.

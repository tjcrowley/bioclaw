---
phase: 8
slug: session-dataset-endpoints
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-09-12
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >= 8 (existing dev dependency, unchanged) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) — no new markers needed; reuses `live_llm` only if an optional Phase 8 end-to-end checkpoint test is added |
| **Quick run command** | `pytest tests/test_webapp_backend.py tests/test_webapp_upload.py tests/test_agent_memory.py tests/test_qa_session.py -m "not live_llm" -x` |
| **Full suite command** | `pytest tests/ -m "not live_llm and not bio_fm_smoke and not vcc_data"` |
| **Estimated runtime** | ~10-15 seconds (fast tier, dependency-overridden — no real API key) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_webapp_backend.py tests/test_webapp_upload.py tests/test_agent_memory.py tests/test_qa_session.py -m "not live_llm" -x`
- **After every plan wave:** Run `pytest tests/ -m "not live_llm and not bio_fm_smoke and not vcc_data"`
- **Before `/gsd:verify-work`:** Full suite must be green; if a `live_llm`-marked Phase 8 checkpoint test is added (recommended, mirroring Phase 7's 07-03 pattern — real upload, real follow-up question, human-confirmed resume behavior), run it manually with a real `ANTHROPIC_API_KEY`
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 08-0x | TBD | TBD | API-03 (session_id plumbing) | unit | `pytest tests/test_qa_session.py::test_ask_question_forwards_session_id tests/test_webapp_backend.py::test_ask_resumes_existing_session_id -x` | ❌ W0 | ⬜ pending |
| 08-0x | TBD | TBD | API-03 (touch/list) | unit | `pytest tests/test_agent_memory.py::test_touch_creates_listable_session tests/test_agent_memory.py::test_list_sessions_orders_by_last_active -x` | ❌ W0 | ⬜ pending |
| 08-0x | TBD | TBD | API-03 (list endpoint) | unit | `pytest tests/test_webapp_backend.py::test_list_sessions_returns_metadata tests/test_webapp_backend.py::test_list_sessions_rejected_without_password -x` | ❌ W0 | ⬜ pending |
| 08-0x | TBD | TBD | API-03 (resume) | unit | `pytest tests/test_webapp_backend.py::test_resume_recalls_prior_dataset_reference -x` | ❌ W0 | ⬜ pending |
| 08-0x | TBD | TBD | API-04 (upload `.h5`) | unit | `pytest tests/test_webapp_upload.py::test_upload_h5_returns_dataset_id -x` | ❌ W0 | ⬜ pending |
| 08-0x | TBD | TBD | API-04 (upload `.mtx` trio) | unit | `pytest tests/test_webapp_upload.py::test_upload_mtx_trio_returns_dataset_id -x` | ❌ W0 | ⬜ pending |
| 08-0x | TBD | TBD | API-04 (upload validation) | unit | `pytest tests/test_webapp_upload.py::test_upload_rejects_incomplete_mtx_set -x` | ❌ W0 | ⬜ pending |
| 08-0x | TBD | TBD | API-04 (conversation flow) | unit | `pytest tests/test_webapp_upload.py::test_upload_result_recalled_in_next_question -x` | ❌ W0 | ⬜ pending |
| 08-0x | TBD | TBD | API-04 (store_root consistency) | unit | `pytest tests/test_webapp_upload.py::test_upload_uses_agent_tools_store_root -x` | ❌ W0 | ⬜ pending |
| 08-0x | TBD | TBD | API-03/API-04 (auth) | unit | `pytest tests/test_webapp_backend.py::test_list_sessions_rejected_without_password tests/test_webapp_upload.py::test_upload_rejected_without_password -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Exact task IDs assigned by the planner; this row set enumerates required coverage per phase requirement.*

---

## Wave 0 Requirements

- [ ] `qa/session.py::ask_question()` — add `session_id: str | None = None` param, forward to `run_session()` (currently dropped — session_id plumbing gap blocks resume)
- [ ] `webapp/backend/main.py::ask()` — read and forward `req.session_id` (currently silently dropped)
- [ ] `agent/memory.py::SessionMemory` — add `sessions` table + `touch()`/`list_sessions()`/`session_exists()` methods (additive; existing `session_memory` table/tests untouched)
- [ ] `agent/session.py::run_session()` — add one `session_memory.touch(session_id)` call so every session is listable regardless of tool-call activity
- [ ] `webapp/backend/deps.py` — add `get_session_memory()` overridable factory (mirrors `get_ask_question()`)
- [ ] `webapp/backend/schemas.py` — add `SessionSummary`, `SessionListResponse`, `UploadResponse` Pydantic models
- [ ] `webapp/backend/uploads.py` — new module: multipart staging helper (`.h5`/`.h5ad` single file vs. `.mtx` 3-file trio validation + tempfile write + cleanup)
- [ ] `webapp/backend/main.py` — add `GET /api/sessions`, `GET /api/sessions/{session_id}`, `POST /api/upload` routes, all password-gated
- [ ] `tests/test_agent_memory.py` — add touch/list_sessions/session_exists tests (existing file, additive)
- [ ] `tests/test_qa_session.py` — add session_id-forwarding test (existing file, additive)
- [ ] `tests/test_webapp_backend.py` — update `_fake_ask_question` signature to accept `session_id`; add session-list/resume tests (existing file, additive)
- [ ] `tests/test_webapp_upload.py` — new file: upload endpoint fast-tier tests
- [ ] No new pip/uv dependency install needed — `python-multipart` already present via `fastapi[standard]` (confirmed installed, v0.0.32)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real upload + real follow-up question against the actual Claude API, confirming human-perceived resume behavior | API-03, API-04 | Requires a real `ANTHROPIC_API_KEY` and live model call; too slow/costly for the fast/CI tier | If a `live_llm`-marked Phase 8 checkpoint test is added, run it manually with `ANTHROPIC_API_KEY` set locally; upload a real `.h5ad`/`.mtx` fixture, then ask a follow-up question in the same session and confirm the dataset context is recalled |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

---
phase: 9
slug: frontend-chat-ui
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-09-12
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >= 8 (existing dev dependency, unchanged) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) — no new markers needed for fast-tier tests |
| **Quick run command** | `uv run --extra web pytest tests/test_webapp_frontend.py -m "not live_llm" -x` |
| **Full suite command** | `uv run --extra web pytest tests/ -x -q -m "not live_llm and not bio_fm_smoke and not vcc_data"` |
| **Estimated runtime** | ~10-15 seconds (static file and endpoint tests, no LLM calls) |

---

## Sampling Rate

- **After every task commit:** Run `uv run --extra web pytest tests/test_webapp_frontend.py -m "not live_llm" -x`
- **After every plan wave:** Run `uv run --extra web pytest tests/ -x -q -m "not live_llm and not bio_fm_smoke and not vcc_data"`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 1 | UI-06, UI-07 | unit | `pytest tests/test_webapp_frontend.py::test_login_page_served tests/test_webapp_frontend.py::test_login_sets_cookie tests/test_webapp_frontend.py::test_login_rejects_bad_password -x` | ❌ W0 | ⬜ pending |
| 09-01-02 | 01 | 1 | UI-06, UI-07 | unit | `pytest tests/test_webapp_frontend.py::test_html_structure tests/test_webapp_frontend.py::test_static_js_files_served tests/test_webapp_frontend.py::test_css_design_tokens -x` | ❌ W0 | ⬜ pending |
| 09-02-01 | 02 | 2 | UI-02 | unit | `pytest tests/test_webapp_frontend.py::test_api_js_exports -x` | ❌ W0 | ⬜ pending |
| 09-03-01 | 03 | 2 | UI-01, UI-02 | unit | `pytest tests/test_webapp_frontend.py::test_chat_js_exports -x` | ❌ W0 | ⬜ pending |
| 09-04-01 | 04 | 3 | UI-03, UI-04, UI-05 | unit | `pytest tests/test_webapp_frontend.py::test_citations_js_exports tests/test_webapp_frontend.py::test_sessions_js_exports -x` | ❌ W0 | ⬜ pending |
| 09-05-01 | 05 | 4 | UI-01..07 | integration | `uv run --extra web pytest tests/ -x -q -m "not live_llm and not bio_fm_smoke and not vcc_data"` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `webapp/frontend/` directory — new; create in Plan 09-01 Task 1
- [ ] `webapp/frontend/index.html` — app shell (login overlay + chat layout) created in Plan 09-01
- [ ] `webapp/frontend/style.css` — dark theme CSS created in Plan 09-01
- [ ] `webapp/frontend/main.js` — entry + login flow created in Plan 09-01
- [ ] `webapp/frontend/api.js` — API client module created in Plan 09-02
- [ ] `webapp/frontend/chat.js` — chat thread component created in Plan 09-03
- [ ] `webapp/frontend/citations.js` — citation renderer created in Plan 09-04
- [ ] `webapp/frontend/sessions.js` — session sidebar created in Plan 09-04
- [ ] `webapp/backend/schemas.py` — add `LoginRequest`, `LoginResponse` (additive; existing schemas untouched)
- [ ] `webapp/backend/main.py` — add `POST /api/login` route + `StaticFiles` mount (additive; existing routes untouched)
- [ ] `tests/test_webapp_frontend.py` — new fast-tier test file; all assertions are content/endpoint checks, no browser automation
- [ ] No new `uv add` dependency needed — `fastapi.staticfiles.StaticFiles` is included in `fastapi[standard]` already installed

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual dark theme + sidebar+panel layout matches OpenClaw UX | UI-07 | CSS design token presence is auto-checked; actual visual fidelity requires human eye | Open browser to http://localhost:8000/app; compare sidebar+main-panel layout and dark theme against OpenClaw web UI |
| Login overlay appears before auth; chat appears after | UI-06 | DOM rendering is browser-side; Python TestClient tests verify HTML structure only | In a fresh browser (no existing cookie), navigate to /app; confirm login overlay; submit correct password; confirm chat UI appears |
| Live tool-call activity events stream inline during a question | UI-02 | Requires live WS + real backend question | Ask a question that triggers tool calls (e.g., "analyze the pilot dataset"); watch activity view populate in real time |
| Citation click shows audit log detail overlay | UI-03 | Requires real answer with resolved citations | After asking a question, click a citation tag; verify overlay shows tool name + JSON record |
| Session resume loads prior context | UI-04 | Requires prior session in SessionMemory | After completing a conversation, start a new tab, resume prior session via sidebar, ask a follow-up using dataset name from prior session |
| Upload drag-and-drop works + result appears in thread | UI-05 | Browser file drag-drop cannot be automated without Playwright | Drag a .h5ad file onto the composer; confirm ingest result appears in thread |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

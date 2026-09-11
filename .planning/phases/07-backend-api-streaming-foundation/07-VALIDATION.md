---
phase: 7
slug: backend-api-streaming-foundation
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-09-11
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >= 8 (already a dev dependency; no new test framework needed) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) — reuses existing `live_llm` marker, no new markers needed |
| **Quick run command** | `pytest tests/test_webapp_backend.py -m "not live_llm" -x` |
| **Full suite command** | `pytest tests/ -m "not live_llm and not bio_fm_smoke and not vcc_data"` |
| **Estimated runtime** | ~10 seconds (fast tier, dependency-overridden — no real API key) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_webapp_backend.py -m "not live_llm" -x`
- **After every plan wave:** Run `pytest tests/ -m "not live_llm and not bio_fm_smoke and not vcc_data"`
- **Before `/gsd:verify-work`:** Full suite must be green, plus the one `live_llm`-marked webapp integration test run manually with a real `ANTHROPIC_API_KEY` (mirrors Phase 6's 06-03 human-verify checkpoint pattern)
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 07-01 | 01 | 0 | Wave 0 | scaffold | `uv add "fastapi[standard]" --optional web` | ❌ W0 | ⬜ pending |
| 07-0x | TBD | TBD | API-01 | unit (dependency-overridden) | `pytest tests/test_webapp_backend.py::test_ask_returns_answer -x` | ❌ W0 | ⬜ pending |
| 07-0x | TBD | TBD | API-02 | unit (dependency-overridden, hooks driven manually) | `pytest tests/test_webapp_backend.py::test_ask_streams_tool_events -x` | ❌ W0 | ⬜ pending |
| 07-0x | TBD | TBD | API-05 | unit | `pytest tests/test_webapp_backend.py::test_ask_rejected_without_password tests/test_webapp_backend.py::test_ws_rejected_without_password -x` | ❌ W0 | ⬜ pending |
| 07-0x | TBD | TBD | API-01/02 (true e2e) | live_llm smoke | `pytest tests/test_webapp_integration.py -m live_llm -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Exact task IDs assigned by the planner; this row set enumerates required coverage per phase requirement.*

---

## Wave 0 Requirements

- [ ] `webapp/backend/__init__.py`, `main.py`, `auth.py`, `streaming.py`, `deps.py`, `schemas.py` — new package, does not exist yet
- [ ] `tests/test_webapp_backend.py` — fast-tier tests (dependency_overrides, no real API key)
- [ ] `tests/test_webapp_integration.py` — single `live_llm`-marked end-to-end test
- [ ] Additive `extra_hooks` parameter on `agent/session.py::build_options()`/`run_session()` and `qa/session.py::ask_question()` — backward-compatible; existing tests (`tests/test_agent_session_wiring.py`, `tests/test_qa_session.py`) must still pass unmodified (default `extra_hooks=None` preserves current behavior)
- [ ] `fastapi[standard]` install as a new `web` optional-dependencies group: `uv add "fastapi[standard]" --optional web` — not yet installed in `.venv`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real end-to-end ask + live tool-call streaming against the actual Claude API | API-01, API-02 | Requires a real `ANTHROPIC_API_KEY` and live model call; too slow/costly for the fast/CI tier | Run `pytest tests/test_webapp_integration.py -m live_llm -x` with `ANTHROPIC_API_KEY` set locally; confirm the WS client received at least one tool-call event before the final answer arrives |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

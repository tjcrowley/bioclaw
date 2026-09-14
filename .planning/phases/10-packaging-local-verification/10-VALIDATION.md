---
phase: 10
slug: packaging-local-verification
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-09-13
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (installed as `dev` dependency group) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run --extra web pytest tests/test_webapp_frontend.py tests/test_webapp_backend.py -x -q` |
| **Full suite command** | `uv run --extra web pytest tests/ -x -q -m "not live_llm and not bio_fm_smoke and not vcc_data"` |
| **Estimated runtime** | ~30s (full suite), ~5s (quick) |

---

## Sampling Rate

- **After every task commit:** Run `uv run --extra web pytest tests/test_webapp_frontend.py tests/test_webapp_backend.py -x -q`
- **After every plan wave:** Run `uv run --extra web pytest tests/ -x -q -m "not live_llm and not bio_fm_smoke and not vcc_data"` — must stay at 208+ passed, 0 failed, no regressions
- **Before `/gsd:verify-work`:** Full suite must be green, plus the clean-checkout dry run transcript captured, plus Darren's combined manual checkpoint approved
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 0 | PKG-01 | unit | `pytest tests/test_webapp_frontend.py::test_webapp_has_no_openclaw_dependency -x` | ❌ W0 | ⬜ pending |
| 10-0X-0X | TBD | TBD | PKG-01 | static (already covered) | `pytest tests/test_webapp_backend.py -k dependencies -x` | ✅ (verified in 07-VERIFICATION.md) | ⬜ pending |
| 10-0X-0X | TBD | TBD | PKG-02 | manual / smoke | Clean-checkout dry run (fresh clone, `uv sync`, single documented command) | manual-only | ⬜ pending |
| 10-0X-0X | TBD | TBD | PKG-02 | manual (human-verify checkpoint) | Browser walkthrough: login, chat Q&A, streaming, citations, session resume, upload→ingest in one continuous session | manual-only | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_webapp_frontend.py::test_webapp_has_no_openclaw_dependency` (or a new small module) — covers PKG-01's durability gap (currently only manually verified once, not automated)

*No new fixtures needed — reuse `analyzable_mtx_dir` and existing `tests/conftest.py` fixtures already established since Phase 3. No framework install gaps — pytest, fastapi, uvicorn, and the `web` extra are all already installed and working.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|--------------------|
| Single command boots full app from a truly clean checkout | PKG-02 | Requires a fresh filesystem clone + fresh `uv sync` — not expressible as a fast repeatable automated command | Clone the repo to a scratch directory, run only the documented setup + run command, confirm the server starts and `/app` loads with no undocumented extra steps |
| Full v1.1 feature set works together end-to-end in one session | PKG-02 | Explicitly a human-verify UX confirmation per the phase's own success-criteria wording ("confirms every v1.1 capability works together"); each capability already has independent fast-tier API/JS contract coverage, but the combined live flow is not mechanically testable as a single fast command | Browser walkthrough: log in, ask a question, watch live tool activity, click a citation, list/resume a session, upload a dataset and confirm ingest triggers — all in one continuous session |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

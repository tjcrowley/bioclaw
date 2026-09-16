---
phase: 11
slug: quick-wins-history-replay-h5ad-upload-csv-export
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-09-16
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml or pytest.ini |
| **Quick run command** | `pytest tests/test_agent_memory.py tests/test_webapp_export.py -x -q` |
| **Full suite command** | `pytest -x -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_agent_memory.py tests/test_webapp_export.py -x -q`
- **After every plan wave:** Run `pytest -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 11-01-01 | 01 | 0 | HIST-01 | unit stub | `pytest tests/test_agent_memory.py -x -q` | ❌ W0 | ⬜ pending |
| 11-01-02 | 01 | 1 | HIST-01 | unit | `pytest tests/test_agent_memory.py::test_wal_mode -x -q` | ❌ W0 | ⬜ pending |
| 11-01-03 | 01 | 1 | HIST-01 | unit | `pytest tests/test_agent_memory.py::test_add_message -x -q` | ❌ W0 | ⬜ pending |
| 11-01-04 | 01 | 1 | HIST-01 | unit | `pytest tests/test_agent_memory.py::test_content_cap -x -q` | ❌ W0 | ⬜ pending |
| 11-01-05 | 01 | 2 | HIST-01 | integration | `pytest tests/test_webapp_history.py -x -q` | ❌ W0 | ⬜ pending |
| 11-02-01 | 02 | 0 | DATA-02 | unit stub | `pytest tests/test_webapp_upload.py -x -q` | ❌ W0 | ⬜ pending |
| 11-02-02 | 02 | 1 | DATA-02 | integration | `pytest tests/test_webapp_upload.py::test_h5ad_upload -x -q` | ❌ W0 | ⬜ pending |
| 11-03-01 | 03 | 0 | EXPORT-01 | unit stub | `pytest tests/test_webapp_export.py -x -q` | ❌ W0 | ⬜ pending |
| 11-03-02 | 03 | 1 | EXPORT-01 | unit | `pytest tests/test_webapp_export.py::test_csv_export_endpoint -x -q` | ❌ W0 | ⬜ pending |
| 11-03-03 | 03 | 2 | EXPORT-01 | integration | `pytest tests/test_webapp_export.py::test_csv_zip_contents -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_agent_memory.py` — stubs for HIST-01 (WAL mode, add_message, content cap, retrieval)
- [ ] `tests/test_webapp_history.py` — stubs for HIST-01 API + JS resume path
- [ ] `tests/test_webapp_upload.py` — stubs for DATA-02 h5ad upload
- [ ] `tests/test_webapp_export.py` — stubs for EXPORT-01 CSV export endpoint
- [ ] `tests/conftest.py` — add `tiny_h5ad_file` pytest fixture

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| UI download button triggers browser Save dialog | EXPORT-01 | Browser file download API requires human observation | Navigate to active session, click download control, verify Save dialog appears with .zip filename |
| Resumed session shows full conversation thread in chat UI | HIST-01 | React rendering requires visual confirmation | Resume a session with prior messages, verify all turns visible (not placeholder) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

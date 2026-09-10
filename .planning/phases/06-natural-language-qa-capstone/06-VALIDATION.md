---
phase: 06
slug: natural-language-qa-capstone
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-09-10
---

# Phase 06 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` (existing) |
| **Quick run command** | `uv run pytest tests/ -x -q --ignore=tests/test_vcc_smoke.py` |
| **Full suite command** | `uv run pytest tests/ -q --ignore=tests/test_vcc_smoke.py` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q --ignore=tests/test_vcc_smoke.py`
- **After every plan wave:** Run `uv run pytest tests/ -q --ignore=tests/test_vcc_smoke.py`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | QA-02 | unit | `uv run pytest tests/test_qa_interpreter.py -x -q` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | QA-02 | unit | `uv run pytest tests/test_qa_interpreter.py -x -q` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 2 | QA-03 | unit | `uv run pytest tests/test_qa_interpreter.py -x -q` | ❌ W0 | ⬜ pending |
| 06-03-01 | 03 | 3 | QA-01 | integration | `uv run pytest tests/test_qa_integration.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_qa_interpreter.py` — stubs for QA-02 (citation extraction/verification) and QA-03 (uncertainty surfacing)
- [ ] `tests/test_qa_integration.py` — stubs for QA-01 (end-to-end NL Q&A)

*Existing `tests/conftest.py` and `perturbation_adata` fixture cover phase needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| NL answer reads naturally and is interpretable to a researcher | QA-01 | Readability is subjective | Read `answer_text` from integration test output |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

---
phase: 4
slug: bio-fm-cell-type-annotation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-09-05
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (already configured, unchanged from Phase 1-3) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `pythonpath=["."]`) |
| **Quick run command** | `uv run pytest tests/test_annotation_baseline.py tests/test_annotation_pipeline.py tests/test_agent_tools.py -k annotate -x` |
| **Full suite command** | `uv run pytest tests/ -q -m "not live_llm and not bio_fm_smoke"` |
| **Estimated runtime** | ~30 seconds (fast tier, excludes real scGPT inference) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_annotation_baseline.py tests/test_annotation_pipeline.py tests/test_agent_tools.py -k annotate -x`
- **After every plan wave:** Run `uv run pytest tests/ -q -m "not live_llm and not bio_fm_smoke"`
- **Before `/gsd:verify-work`:** Full fast-tier suite must be green, AND at least one manual `bio_fm_smoke` run must be demonstrated against the isolated scGPT environment with latency measured (closes Pitfall 2 / STATE.md's compute-sizing blocker with real evidence).
- **Max feedback latency:** 30 seconds (fast tier)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-xx | 01 | 0 | Wave 0 infra | n/a | package skeleton + isolation env spike | ❌ W0 | ⬜ pending |
| 04-02-xx | 02 | 1 | ANNOT-02 | unit | `uv run pytest tests/test_annotation_baseline.py -x` | ❌ W0 | ⬜ pending |
| 04-03-xx | 03 | 1 | ANNOT-01 (tool wiring, mocked FM) | unit | `uv run pytest tests/test_agent_tools.py -k annotate -x` | ❌ W0 | ⬜ pending |
| 04-04-xx | 04 | 1/2 | ANNOT-01 (real inference smoke) | integration/smoke | `uv run pytest tests/test_bio_fm_integration.py -m bio_fm_smoke -x` | ❌ W0 | ⬜ pending |
| 04-05-xx | 05 | 2 | ANNOT-03 | unit | `uv run pytest tests/test_annotation_pipeline.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*(Exact plan/task numbering to be finalized by gsd-planner; this table reflects the requirement→test mapping from 04-RESEARCH.md's Validation Architecture section.)*

---

## Wave 0 Requirements

- [ ] `annotation/` package skeleton (mirrors `analysis/`'s existing shape: `__init__.py`, `baseline.py`, `fm_client.py`, `reference.py`, `summary.py`, `pipeline.py`)
- [ ] Isolated scGPT environment (subprocess-invokable or standalone-MCP-server-invokable — resolve Open Question 3 first; scGPT's dependency pins — `scvi-tools<1.0`, unpinned `torchtext`, `orbax<0.1.8` — must NOT land in the main project venv)
- [ ] A small, static, pre-built reference embedding index sourced from `cellxgene-census` (resolve Open Question 4: scope/size)
- [ ] `tests/test_annotation_baseline.py`, `tests/test_annotation_pipeline.py` — new files, unit-tested against a synthetic clustered fixture (likely reusable/extending `structured_adata` from `tests/test_fixtures.py`, per Phase 2's own precedent)
- [ ] `tests/test_bio_fm_integration.py` — new file, new `bio_fm_smoke` pytest marker registered in `pyproject.toml` (mirrors the existing `live_llm` marker's registration pattern)
- [ ] Framework install: `uv add decoupler` (main venv only); scGPT installed only into the isolated environment, never the root `pyproject.toml`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real scGPT inference latency/plausibility on the isolated environment | ANNOT-01 | Requires downloading/running an actual pretrained FM checkpoint; too slow/heavy for default CI (analogous to Phase 3's `live_llm` exclusion) | Run `uv run pytest tests/test_bio_fm_integration.py -m bio_fm_smoke -x` manually after building the isolated env; record wall-clock latency against Pitfall 2's unverified benchmark estimate |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s (fast tier)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

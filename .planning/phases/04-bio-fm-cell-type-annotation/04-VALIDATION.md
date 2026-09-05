---
phase: 4
slug: bio-fm-cell-type-annotation
status: approved
nyquist_compliant: true
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
| 04-01 T1: install decoupler + register bio_fm_smoke marker | 01 | 0 | infra | n/a | `uv run python -c "import decoupler"` | ❌ W0 | ⬜ pending |
| 04-01 T2: annotation/ skeleton + AnnotationCall/AnnotationSummary | 01 | 0 | infra (ANNOT-03 contracts) | unit | package import check | ❌ W0 | ⬜ pending |
| 04-02 T1: baseline_annotate() decoupler ORA baseline | 02 | 1 | ANNOT-02 | unit | `uv run pytest tests/test_annotation_baseline.py -x` | ❌ W0 | ⬜ pending |
| 04-03 T1: bio_fm_worker/ isolated env + run_scgpt_embed.py | 03 | 1 | ANNOT-01 | n/a (isolated venv, no fast-tier test) | `bio_fm_worker/.venv/bin/python -c "..."` | ❌ W0 | ⬜ pending |
| 04-03 T2: annotation/fm_client.py subprocess shim | 03 | 1 | ANNOT-01 (tool wiring, mocked FM) | unit | `uv run pytest tests/test_annotation_fm_client.py -x` | ❌ W0 | ⬜ pending |
| 04-04 T1: annotation/pipeline.py annotate() composition | 04 | 2 | ANNOT-01, ANNOT-02, ANNOT-03 | unit | `uv run pytest tests/test_annotation_pipeline.py -x` | ❌ W0 | ⬜ pending |
| 04-04 T2: annotate_cell_type_tool + agent/server.py registration | 04 | 2 | ANNOT-01 | unit | `uv run pytest tests/test_agent_tools.py -k annotate -x` | ❌ W0 | ⬜ pending |
| 04-05 T1: build_reference_index() cellxgene-census subsample | 05 | 3 | ANNOT-03 | script/manual | run + inspect reference.h5ad | ❌ W0 | ⬜ pending |
| 04-05 T2: acquire scGPT checkpoint + write bio_fm_smoke test | 05 | 3 | ANNOT-01 | integration/smoke (written, not required green) | `uv run pytest tests/test_bio_fm_integration.py -m bio_fm_smoke -x` | ❌ W0 | ⬜ pending |
| 04-05 T3: real end-to-end smoke verification (checkpoint:human-verify, blocking) | 05 | 3 | ANNOT-01, ANNOT-03 | manual | same command, human-reported outcome | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*(Table finalized against the 5 real PLAN.md files after gsd-planner + gsd-plan-checker; verdict PASS 2026-09-05.)*

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

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s (fast tier)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-09-05 (gsd-plan-checker verdict: PASS, independent Dimension 8 check confirmed)

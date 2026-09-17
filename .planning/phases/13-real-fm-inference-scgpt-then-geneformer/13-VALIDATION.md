---
phase: 13
slug: real-fm-inference-scgpt-then-geneformer
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-09-17
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/ -q -m "not live_llm and not bio_fm_smoke and not vcc_data and not census_data"` (confirmed green: 252 passed, 7 deselected, 23.8s) |
| **Full suite command** | `uv run pytest tests/ -q` (includes marker-gated real-checkpoint/network tests; not run in CI) |
| **Estimated runtime** | ~24 seconds (quick) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -q -m "not live_llm and not bio_fm_smoke and not vcc_data and not census_data"`
- **After every plan wave:** Run the same quick command (smoke-marked tests are inherently manual/checkpoint-gated, not part of automated wave verification, matching Phase 4's and Phase 5's own precedent)
- **Before `/gsd:verify-work`:** Full suite must be green; `checkpoint:human-verify` steps required for both the scGPT confidence-metric re-verification and the Geneformer real-checkpoint smoke test
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 13-XX-01 | TBD | 0 | FM-01 | unit | `uv run pytest tests/test_annotation_fm_client.py -x` (extend with new k-NN vote-fraction unit test) | ❌ W0 | ⬜ pending |
| 13-XX-02 | TBD | 0 | FM-01 | smoke (excluded from fast tier) | `uv run pytest tests/test_bio_fm_integration.py -m bio_fm_smoke -x -v` | ✅ exists | ⬜ pending |
| 13-XX-03 | TBD | 0 | FM-02 | unit | `uv run pytest tests/test_perturbation_geneformer_client.py -x` (new file, mocked-subprocess pattern) | ❌ W0 | ⬜ pending |
| 13-XX-04 | TBD | 0 | FM-02 | smoke (new marker `geneformer_smoke`), `checkpoint:human-verify` gate | `uv run pytest tests/test_geneformer_integration.py -m geneformer_smoke -x -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_annotation_fm_client.py` — add a new unit test isolating the k-NN vote-fraction math (pure numpy, no subprocess) so it's covered by the fast tier even though the full integration remains `bio_fm_smoke`-gated
- [ ] New `geneformer_worker/` package skeleton + Python 3.10 `.venv` — does not exist yet
- [ ] New `perturbation/geneformer_client.py` (or equivalently named) subprocess shim — mirror `annotation/fm_client.py`'s structure and its mocked-subprocess unit test pattern (`tests/test_annotation_fm_client.py`)
- [ ] New pytest marker `geneformer_smoke` (or reuse `bio_fm_smoke` if the planner decides one marker covering both real-FM-checkpoint tests is preferable) registered in `pyproject.toml`'s `markers` list
- [ ] New dataclass(es) for Geneformer's ranked-gene-by-cosine-shift output shape in `perturbation/summary.py` (or a new module)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real, unmocked scGPT annotation with new k-NN vote-fraction confidence | FM-01 | Requires real model checkpoint + GPU/CPU inference time; gitignored checkpoint not reproducible on clean checkout | `uv run pytest tests/test_bio_fm_integration.py -m bio_fm_smoke -x -v`, inspect confidence values are in `[0,1]` and plausible |
| Real, unmocked four-step Geneformer pipeline (tokenize → extract embeddings → perturb → rank by cosine shift) | FM-02 | Requires real Geneformer checkpoint download + Ensembl-ID-mapped dataset; not reproducible on clean checkout | `uv run pytest tests/test_geneformer_integration.py -m geneformer_smoke -x -v`, inspect ranked gene list is non-empty and distinct from linear model output |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-09-17

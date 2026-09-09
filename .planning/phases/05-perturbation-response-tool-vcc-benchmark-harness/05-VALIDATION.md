---
phase: 5
slug: perturbation-response-tool-vcc-benchmark-harness
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-09-08
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=8 (already configured) |
| **Config file** | `pyproject.toml` (existing `testpaths = ["tests"]`, `markers` list) |
| **Quick run command** | `uv run pytest -m "not live_llm and not bio_fm_smoke and not vcc_data" -q` |
| **Full suite command** | `uv run pytest -q` (requires VCC dataset downloaded/cached locally for `vcc_data`-marked tests) |
| **Estimated runtime** | ~30s (fast suite, synthetic fixtures only) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -m "not live_llm and not bio_fm_smoke and not vcc_data" -q`
- **After every plan wave:** Run `uv run pytest -q` excluding only `vcc_data` (requires local VCC data cache)
- **Before `/gsd:verify-work`:** Full suite green, including a `vcc_data`-marked smoke run against the real downloaded VCC split
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 0 | Wave 0 infra | unit | `uv run pytest tests/test_perturbation_model.py -x` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 0 | PERT-01 | unit | `uv run pytest tests/test_perturbation_model.py -x` | ❌ W0 | ⬜ pending |
| 05-02-01 | 02 | 1 | PERT-02 | unit | `uv run pytest tests/test_perturbation_baseline.py -x` | ❌ W0 | ⬜ pending |
| 05-03-01 | 03 | 1 | VCC-01 | unit | `uv run pytest tests/test_loaders.py -k h5ad -x` | ❌ W0 | ⬜ pending |
| 05-04-01 | 04 | 2 | VCC-02 | integration | `uv run pytest tests/test_vcc_eval.py -x` | ❌ W0 | ⬜ pending |
| 05-05-01 | 05 | 2 | VCC-03 | integration | `uv run pytest tests/test_vcc_report.py -x` | ❌ W0 | ⬜ pending |
| 05-06-01 | 06 | 3 | phase gate smoke | smoke, marked `vcc_data` | `uv run pytest -m vcc_data -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_perturbation_model.py` — stubs for PERT-01 (synthetic control/perturbed fixture, no real VCC download needed)
- [ ] `tests/test_perturbation_baseline.py` — stubs for PERT-02
- [ ] Extend `tests/test_loaders.py` — stubs for VCC-01 (`.h5ad` branch)
- [ ] `tests/test_vcc_eval.py` — stubs for VCC-02 (small synthetic pred/real AnnData with hand-verifiable PDS/DES/MAE)
- [ ] `tests/test_vcc_report.py` — stubs for VCC-03
- [ ] New pytest marker: add `vcc_data: requires the downloaded VCC public dataset, excluded from fast/CI runs` to `pyproject.toml`'s `markers` list, mirroring the existing `bio_fm_smoke` pattern
- [ ] Framework install: `uv pip install "cell-eval>=0.8.2"` — not yet in `pyproject.toml` dependencies

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real VCC public dataset download + full-scale benchmark run | VCC-01, VCC-02, VCC-03 | Requires a one-time authenticated GCS download (multi-GB, "Requester Pays" billing beyond free tier) — not something to fire on every CI run | Download VCC training/validation/test splits from `gs://arc-institute-virtual-cell-atlas/virtual-cell-challenge/`, run `pytest -m vcc_data -x -v -s`, actively poll the process (do not trust background completion silently) |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved by gsd-plan-checker 2026-09-08 (see plan verification: `## VERIFICATION PASSED`, all 6 plans, requirement coverage confirmed)

---
phase: 2
slug: analysis-tool-layer
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-09-04
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (already configured) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `pythonpath=["."]`) |
| **Quick run command** | `uv run pytest tests/test_analysis.py -x` |
| **Full suite command** | `uv run pytest tests/ -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_analysis.py -x`
- **After every plan wave:** Run `uv run pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 0 | (infra) | unit | `uv run pytest tests/test_analysis.py -x` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 1 | ANLYS-01 | unit | `uv run pytest tests/test_analysis.py -k preprocess -x` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 1 | ANLYS-02 | unit | `uv run pytest tests/test_analysis.py -k cluster -x` | ❌ W0 | ⬜ pending |
| 02-04-01 | 04 | 1 | ANLYS-03 | unit | `uv run pytest tests/test_analysis.py -k differential -x` | ❌ W0 | ⬜ pending |
| 02-05-01 | 05 | 1 | ANLYS-04 | unit | `uv run pytest tests/test_analysis.py -k summary -x` | ❌ W0 | ⬜ pending |
| 02-06-01 | 06 | 2 | (integration) | integration | `uv run pytest tests/test_analysis_pipeline.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_analysis.py` — stubs for ANLYS-01/02/03/04
- [ ] `tests/test_analysis_pipeline.py` — stub for store-composed integration + checksum-preservation property
- [ ] New `conftest.py` fixture: a synthetic `AnnData` with ~150-300 cells / ~60-100 genes and two well-separated pseudo-populations, large enough to reliably produce ≥2 stable Leiden clusters and a non-trivial DE result at default `resolution=1.0`/`n_neighbors=15` — the existing `synthetic_adata` fixture (20 genes × 50 cells) is too small for this phase
- [ ] `uv add "igraph>=0.10.8"` — required before any `flavor="igraph"` Leiden call can import successfully

---

## Manual-Only Verifications

*None — all phase behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-09-04

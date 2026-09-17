---
phase: 12
slug: agent-data-access-script-export
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-09-16
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/ -m "not live_llm and not bio_fm_smoke and not vcc_data and not census_data" -q` |
| **Full suite command** | `uv run pytest tests/ -m "not live_llm and not bio_fm_smoke and not vcc_data" -q` |
| **Estimated runtime** | ~30 seconds (fast suite; census_data smoke excluded) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -m "not live_llm and not bio_fm_smoke and not vcc_data and not census_data" -q`
- **After every plan wave:** Run `uv run pytest tests/ -m "not live_llm and not bio_fm_smoke and not vcc_data" -q`
- **Before `/gsd:verify-work`:** Full fast suite green + `census_data` smoke test green on a network-capable machine
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 12-01-01 | 01 | 1 | DATA-01 | unit | `uv run pytest tests/test_census_tool.py -x` | ❌ W0 | ⬜ pending |
| 12-01-02 | 01 | 1 | DATA-01 | unit | `uv run pytest tests/test_census_tool.py::test_census_fetch_runs_in_thread -x` | ❌ W0 | ⬜ pending |
| 12-01-03 | 01 | 1 | DATA-01 | unit | `uv run pytest tests/test_census_tool.py::test_fetched_dataset_loadable -x` | ❌ W0 | ⬜ pending |
| 12-01-04 | 01 | 1 | DATA-01 | unit | `uv run pytest tests/test_census_tool.py::test_tool_registered -x` | ❌ W0 | ⬜ pending |
| 12-01-05 | 01 | 1 | DATA-01 | census_data (network) | `uv run pytest tests/test_census_smoke.py -m census_data -x` | ❌ W0 | ⬜ pending |
| 12-03-01 | 03 | 2 | EXPORT-02 | unit | `uv run pytest tests/test_webapp_script_export.py::test_export_script_returns_py -x` | ❌ W0 | ⬜ pending |
| 12-03-02 | 03 | 2 | EXPORT-02 | unit | `uv run pytest tests/test_webapp_script_export.py::test_script_contains_qc_thresholds -x` | ❌ W0 | ⬜ pending |
| 12-03-03 | 03 | 2 | EXPORT-02 | unit | `uv run pytest tests/test_webapp_script_export.py::test_script_contains_random_state -x` | ❌ W0 | ⬜ pending |
| 12-03-04 | 03 | 2 | EXPORT-02 | unit | `uv run pytest tests/test_webapp_script_export.py::test_script_census_source -x` | ❌ W0 | ⬜ pending |
| 12-03-05 | 03 | 2 | EXPORT-02 | unit | `uv run pytest tests/test_webapp_script_export.py::test_script_export_requires_auth -x` | ❌ W0 | ⬜ pending |
| 12-03-06 | 03 | 2 | EXPORT-02 | unit | `uv run pytest tests/test_webapp_script_export.py::test_script_no_analysis_graceful -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_census_tool.py` — DATA-01 unit tests with mocked census (mock `cellxgene_census.open_soma` and `cellxgene_census.get_anndata`)
- [ ] `tests/test_census_smoke.py` — DATA-01 real network round-trip test (`@pytest.mark.census_data`)
- [ ] `tests/test_webapp_script_export.py` — EXPORT-02 unit tests using `TestClient` + `analyzable_mtx_dir` fixture
- [ ] `pyproject.toml` — register `census_data` pytest marker (follows existing `vcc_data` marker pattern)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real cellxgene-census network fetch returns live data | DATA-01 | Requires live network + census backend availability; excluded from CI fast suite | On a network-capable machine: `uv run pytest tests/test_census_smoke.py -m census_data -x` — expect ≥1 cell AnnData |
| Exported `.py` script runs end-to-end and reproduces analysis | EXPORT-02 | Full scanpy re-run requires environment + data; unit tests assert script *content* not execution | Download script from `GET /api/export/script`, run `python <script>.py` in a scanpy env, confirm it reproduces QC + analysis |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

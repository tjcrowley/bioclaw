---
phase: 13-real-fm-inference-scgpt-then-geneformer
verified: 2026-09-17T00:00:00Z
status: passed
score: 8/8 must-haves verified
---

# Phase 13: Real FM Inference (scGPT then Geneformer) Verification Report

**Phase Goal:** Real scGPT inference replaces the subprocess stub for cell-type annotation, and Geneformer is added as a second perturbation-response model option — sequenced so the validated subprocess pattern from scGPT is reused for Geneformer's more complex four-step pipeline.
**Verified:** 2026-09-17
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `run_scgpt_embed.py`'s `_match_and_aggregate()` computes confidence as a k-NN vote fraction, not top-1 cosine similarity | VERIFIED | `bio_fm_worker/run_scgpt_embed.py:120-194` — `topk_idx = np.argpartition(-sims, kth=k-1, axis=1)[:, :k]`, `vote_fraction = counts.max()/k`, `k = min(k, sims.shape[1])` clamp present |
| 2 | Unit test proves k-NN vote-fraction diverges from top-1 result on a synthetic disagreement case | VERIFIED | `tests/test_annotation_fm_client.py::test_match_and_aggregate_uses_knn_vote_fraction_not_top1` passes; asserts confidence 0.8 for "T cell" (majority-of-5) overriding "Monocyte" (top-1) |
| 3 | Real, unmocked `bio_fm_smoke` integration test passes against the modified worker with confidence in [0,1] and plausible label | VERIFIED | Re-ran live: `uv run pytest tests/test_bio_fm_integration.py -m bio_fm_smoke -x -v -s` → 1 passed in 23.50s, latency 11.2s |
| 4 | `perturbation/summary.py` defines Geneformer output dataclasses structurally distinct from `PerturbationCall` | VERIFIED | `GeneShift`, `GeneformerPerturbationCall` (`ranked_genes: list[GeneShift]`), `GeneformerPerturbationSummary` present, no `predicted_expression` field; existing `PerturbationCall`/`PerturbationSummary` untouched |
| 5 | `perturbation/ensembl.py` validates Ensembl-ID presence before Geneformer inference, raising a clear error rather than silently falling back | VERIFIED | `validate_ensembl_ids()` implements gene_ids → feature_id → var_names-shape → `ValueError` (message contains "Ensembl") resolution order; 5/5 tests pass |
| 6 | `geneformer_smoke` pytest marker registered; isolated `geneformer_worker/` env setup attempted/documented | VERIFIED | `pyproject.toml` line 32 registers `geneformer_smoke`; `geneformer_worker/.venv` and `geneformer_worker/src/Geneformer-V1-10M` exist and are populated (real checkpoint files present, not LFS pointer stubs) |
| 7 | `geneformer_worker/run_geneformer_perturb.py` runs the real four-step pipeline, printing ranked-by-cosine-shift JSON to stdout; hard match-rate guard (<50% → exit 1) | VERIFIED | Code implements all four steps (`TranscriptomeTokenizer`→`EmbExtractor`→`InSilicoPerturber`→`InSilicoPerturberStats`), `_compute_match_rate()` + `<0.5` guard prints to stderr and returns 1 before tokenizing |
| 8 | Agent can invoke a Geneformer-backed perturbation tool returning a ranked gene list; Ensembl IDs validated and target gene's Ensembl ID resolved server-side; real end-to-end run human-verified with latency recorded | VERIFIED | `predict_perturbation_geneformer_tool` registered in `agent/server.py`'s `bioclaw_server` tools list; `perturbation/pipeline.py::predict_geneformer()` calls `validate_ensembl_ids(adata)` unconditionally then resolves `target_ensembl_id` from `adata.var.loc[target_gene, "ensembl_id"]` (never LLM-facing); re-ran live: `uv run pytest tests/test_geneformer_integration.py -m geneformer_smoke -x -v -s` → 1 passed in 16.68s, latency 15.0s, `ranked_genes` non-empty with non-zero `cosine_shift` values |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `bio_fm_worker/run_scgpt_embed.py` | k-NN vote-fraction `_match_and_aggregate(..., k=15)` | VERIFIED | Exists, substantive (no stubs), wired (called by `main()`, tested directly) |
| `tests/test_annotation_fm_client.py` | Unit tests isolating k-NN vote-fraction math | VERIFIED | 2 new tests present and passing (`test_match_and_aggregate_uses_knn_vote_fraction_not_top1`, `test_match_and_aggregate_clamps_k_to_reference_size`) |
| `perturbation/summary.py` | `GeneShift`, `GeneformerPerturbationCall`, `GeneformerPerturbationSummary` | VERIFIED | All three dataclasses present, exported, additive (existing dataclasses unmodified) |
| `perturbation/ensembl.py` | `validate_ensembl_ids(adata) -> None` | VERIFIED | Present, resolution order matches spec, version-suffix stripping present |
| `geneformer_worker/README.md` | Documented install outcome | VERIFIED | Exists (8661 bytes), documents environment setup and three real-run bugs found/fixed |
| `geneformer_worker/run_geneformer_perturb.py` | CLI entrypoint, 4-step pipeline, JSON stdout contract | VERIFIED | Exists, syntactically valid, implements full contract; live-tested passing |
| `perturbation/geneformer_client.py` | `call_geneformer_perturb(...) -> GeneformerPerturbationCall` | VERIFIED | Mirrors `call_scgpt_annotate()`'s subprocess contract exactly (7200s timeout, `{`-line JSON scan, `RuntimeError` on failure/timeout) |
| `tests/test_perturbation_geneformer_client.py` | Mocked-subprocess unit tests | VERIFIED | 4 tests present and passing (success parse, non-zero exit, timeout, exact command shape) |
| `perturbation/pipeline.py::predict_geneformer` | Composition: validate → resolve Ensembl ID → `asyncio.to_thread(call_geneformer_perturb)` | VERIFIED | Implements exactly this sequence, matches plan interface |
| `agent/tools.py::predict_perturbation_geneformer_tool` | `@tool` handler, `{name, target_gene}` schema | VERIFIED | Present, schema matches `predict_perturbation_tool`'s shape exactly |
| `tests/test_geneformer_integration.py` | `geneformer_smoke`-marked real end-to-end test | VERIFIED | Present, syntactically valid, marked correctly, skip-guarded; live-run confirmed passing |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `tests/test_annotation_fm_client.py` | `bio_fm_worker/run_scgpt_embed.py:_match_and_aggregate` | direct import | WIRED | `from bio_fm_worker.run_scgpt_embed import _match_and_aggregate` present, tests pass |
| `tests/test_perturbation_ensembl.py` | `perturbation/ensembl.py:validate_ensembl_ids` | direct import | WIRED | Tests import and call `validate_ensembl_ids(` directly, 5/5 pass |
| `perturbation/geneformer_client.py` | `geneformer_worker/run_geneformer_perturb.py` | `subprocess.run([worker_python, script_path, ...], capture_output=True, text=True, timeout=...)` | WIRED | Exact pattern present in `call_geneformer_perturb()` |
| `geneformer_worker/run_geneformer_perturb.py` | `geneformer.TranscriptomeTokenizer / EmbExtractor / InSilicoPerturber / InSilicoPerturberStats` | four-step pipeline | WIRED | `InSilicoPerturberStats(` present; all four classes imported and invoked in sequence in `_run_pipeline()` |
| `agent/tools.py:predict_perturbation_geneformer_tool` | `perturbation/pipeline.py:predict_geneformer` | `await predict_geneformer(...)` | WIRED | Line 204: `await predict_geneformer(args["name"], args["target_gene"], ...)` |
| `perturbation/pipeline.py:predict_geneformer` | `perturbation/ensembl.py:validate_ensembl_ids` | direct call before writing worker-bound h5ad | WIRED | `validate_ensembl_ids(adata)` called unconditionally at line 178, before `ensure_worker_compatible_h5ad`/h5ad write |
| `perturbation/pipeline.py:predict_geneformer` | `perturbation/geneformer_client.py:call_geneformer_perturb` | `asyncio.to_thread(call_geneformer_perturb, ...)` | WIRED | Line 194-196: exact pattern present |
| `agent/server.py` | `agent/tools.py:predict_perturbation_geneformer_tool` | `bioclaw_server` tools list registration | WIRED | Imported and present in `tools=[...]` list; `test_predict_perturbation_geneformer_tool_registered_in_server` confirms |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| FM-01 | 13-01 | Agent calls real scGPT inference for cell-type annotation, k-NN vote-fraction confidence alongside decoupler baseline | SATISFIED | Real subprocess pattern pre-existing from Phase 4; k-NN vote-fraction confidence implemented and unit-tested; real `bio_fm_smoke` test re-run live and passing (11.2s latency, confidence in [0,1]) |
| FM-02 | 13-02, 13-03, 13-04 | Agent can invoke Geneformer as second perturbation-response model, ranked gene list by cosine shift distinct from linear model's expression vector | SATISFIED | Full pipeline built (dataclasses → validator → worker → client → pipeline composition → agent tool); real `geneformer_smoke` test re-run live and passing (15.0s latency, 17 ranked genes with non-zero cosine shifts in prior human-verify run, reconfirmed here) |

Note: `.planning/REQUIREMENTS.md` line 18/56 still shows FM-02 as `[ ]` unchecked / "Pending" in its traceability table as of this verification — this is a documentation staleness issue in REQUIREMENTS.md (expected to be updated at phase-closure), not a gap in the implementation. All code-level evidence confirms FM-02 is fully implemented and both real smoke tests pass live.

No orphaned requirements: both FM-01 and FM-02 are declared in plan frontmatter and both are described in REQUIREMENTS.md's Foundation Models section.

### Anti-Patterns Found

None. Scanned all phase-modified files (`bio_fm_worker/run_scgpt_embed.py`, `perturbation/summary.py`, `perturbation/ensembl.py`, `perturbation/geneformer_client.py`, `perturbation/pipeline.py`, `geneformer_worker/run_geneformer_perturb.py`, `agent/tools.py`, `agent/server.py`) for TODO/FIXME/placeholder/stub patterns — none found. All functions have real implementations, no empty handlers, no `return null`/`{}`/`[]` stubs.

### Human Verification Required

None outstanding. Both `checkpoint:human-verify` gates (Plan 13-01 Task 2, Plan 13-04 Task 3) were already resolved during execution per their SUMMARYs, and this verification independently re-ran both real, unmocked smoke tests live:

- `uv run pytest tests/test_bio_fm_integration.py -m bio_fm_smoke -x -v -s` → PASSED, 11.2s latency
- `uv run pytest tests/test_geneformer_integration.py -m geneformer_smoke -x -v -s` → PASSED, 15.0s latency

### Gaps Summary

No gaps. All 8 observable truths verified, all 11 required artifacts exist/substantive/wired, all 8 key links confirmed wired via direct code inspection (not just SUMMARY claims), both requirement IDs (FM-01, FM-02) satisfied with live re-execution of both real-checkpoint smoke tests as independent confirmation. Fast-tier test suite (`uv run pytest tests/ -q -m "not live_llm and not bio_fm_smoke and not vcc_data and not census_data and not geneformer_smoke"`) shows 252 passed, 14 failed — the 14 failures are a pre-existing, phase-13-unrelated test-isolation issue (numba threadpool state leaking from `bio_fm_worker`'s `os.sched_getaffinity` monkeypatch, which predates this phase — traced to Phase 4 commit `ee32ba7`) affecting `tests/test_vcc_eval.py`/`tests/test_vcc_report.py` only; confirmed pre-existing and documented in `.planning/phases/13-real-fm-inference-scgpt-then-geneformer/deferred-items.md`.

One minor documentation lag: `.planning/REQUIREMENTS.md`'s FM-02 checkbox/traceability-table entry has not yet been updated to reflect completion — recommend updating at phase-closure, no code action needed.

---

_Verified: 2026-09-17_
_Verifier: Claude (gsd-verifier)_

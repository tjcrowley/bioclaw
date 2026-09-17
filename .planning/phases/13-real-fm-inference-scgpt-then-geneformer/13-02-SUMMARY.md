---
phase: 13-real-fm-inference-scgpt-then-geneformer
plan: 02
subsystem: bio-fm-inference
tags: [geneformer, ensembl-id, dataclasses, pytest-markers, isolated-venv, git-lfs, huggingface]

# Dependency graph
requires:
  - phase: 05-perturbation-response
    provides: "PerturbationCall/PerturbationSummary dataclass convention in perturbation/summary.py; established one-target-gene-per-call design"
  - phase: 04-bio-fm-annotation
    provides: "bio_fm_worker/ isolated-venv-plus-subprocess pattern this plan's geneformer_worker/ mirrors"
provides:
  - "GeneShift, GeneformerPerturbationCall, GeneformerPerturbationSummary dataclasses in perturbation/summary.py -- the fixed output contract Plans 13-03/13-04 implement against"
  - "perturbation/ensembl.py::validate_ensembl_ids(adata) -- tested, fail-loud Ensembl-ID presence/shape guard"
  - "geneformer_smoke pytest marker registered in pyproject.toml"
  - "geneformer_worker/ isolated Python 3.10 venv with geneformer package installed and import-verified, Geneformer-V1-10M checkpoint pulled via git-lfs"
affects: [13-03-geneformer-worker-script, 13-04-geneformer-pipeline-integration]

# Tech tracking
tech-stack:
  added: ["geneformer 0.1.0 (editable install from ctheodoris/Geneformer HF repo)", "torch 2.14.0 (geneformer_worker/.venv only)", "transformers 4.46.0 (repinned, geneformer_worker/.venv only)"]
  patterns: ["Second isolated worker venv (geneformer_worker/), mirroring bio_fm_worker/'s subprocess-boundary pattern for a second, incompatible torch/transformers stack"]

key-files:
  created: ["perturbation/ensembl.py", "tests/test_perturbation_ensembl.py", "geneformer_worker/README.md", "geneformer_worker/.venv (gitignored)", "geneformer_worker/src (gitignored, HF clone)"]
  modified: ["perturbation/summary.py", "pyproject.toml", ".gitignore"]

key-decisions:
  - "validate_ensembl_ids() resolution order is gene_ids -> feature_id -> Ensembl-shaped var_names -> ValueError, matching 13-RESEARCH.md's Don't-Hand-Roll guidance for MTX/.h5 ingest vs. arbitrary uploads/census data"
  - "Repinned transformers==4.46 (Geneformer's own requirements.txt pin) after the unpinned setup.py install resolved an incompatible transformers 5.17.0 that broke import geneformer with a SpecialTokensMixin ImportError -- documented in geneformer_worker/README.md as the required post-install step if this venv is ever rebuilt"
  - "New Geneformer dataclasses (GeneShift, GeneformerPerturbationCall, GeneformerPerturbationSummary) are additive/parallel to PerturbationCall/PerturbationSummary, not a replacement or extension -- per 13-RESEARCH.md Pitfall 4's explicit warning against shoehorning a ranked-gene-list output into an expression-vector field"

patterns-established:
  - "validate_ensembl_ids() is presence/shape-only -- real vocabulary match-rate computation is deferred to geneformer_worker/run_geneformer_perturb.py (Plan 13-03), which alone can import the geneformer package"

requirements-completed: ["FM-02"]

# Metrics
duration: 25min
completed: 2026-09-17
---

# Phase 13 Plan 02: Geneformer Foundation (dataclasses, validator, isolated environment) Summary

**Additive Geneformer output-shape dataclasses, a tested Ensembl-ID presence validator, and a working isolated Python 3.10 `geneformer_worker/` environment with the Geneformer-V1-10M checkpoint pulled via git-lfs.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-09-17T18:41:00Z
- **Completed:** 2026-09-17T19:06:00Z
- **Tasks:** 2 completed
- **Files modified:** 6 (2 new source files, 1 new test file, 1 new README, 2 config files)

## Accomplishments
- `perturbation/summary.py` gained `GeneShift`, `GeneformerPerturbationCall`, `GeneformerPerturbationSummary` -- a fixed, structurally-distinct output contract for Plans 13-03/13-04 to build Geneformer's inference pipeline against, without disturbing existing `PerturbationCall`/`PerturbationSummary`.
- `perturbation/ensembl.py::validate_ensembl_ids()` is a real, tested, fail-loud guard against Geneformer's Pitfall 2 (silent tokenizer failure on missing/mismatched Ensembl IDs) -- 5/5 tests covering all three success paths, version-suffix stripping, and the failure path.
- `geneformer_smoke` pytest marker registered.
- The isolated `geneformer_worker/` Python 3.10 environment was stood up end-to-end: venv created, `git lfs` clone + selective pull of only `Geneformer-V1-10M/*` (79 MB), editable install, and `import geneformer` (including all four pipeline classes) verified working -- no manual `user_setup` fallback was needed.

## Task Commits

Each task was committed atomically:

1. **Task 1: Geneformer output dataclasses + Ensembl-ID validator** - `edb552a` (test, RED) + `9e4515a` (feat, GREEN)
2. **Task 2: geneformer_smoke marker + isolated geneformer_worker/ environment** - `4ebe7ca` (chore)

**Plan metadata:** (this commit, docs: complete plan)

_Note: Task 1 used TDD (RED -> GREEN), producing two commits._

## Files Created/Modified
- `perturbation/summary.py` - Added `GeneShift`, `GeneformerPerturbationCall`, `GeneformerPerturbationSummary` dataclasses (additive only)
- `perturbation/ensembl.py` - New: `validate_ensembl_ids(adata)` presence/shape validator
- `tests/test_perturbation_ensembl.py` - New: 5 tests covering all resolution/failure paths
- `pyproject.toml` - Added `geneformer_smoke` marker
- `.gitignore` - Added `geneformer_worker/src/` (mirrors `bio_fm_worker/checkpoints/`)
- `geneformer_worker/README.md` - New: environment setup, install outcome (success + the transformers repin fix), checkpoint details
- `geneformer_worker/.venv/`, `geneformer_worker/src/` - New, gitignored: isolated Python 3.10 venv + cloned HF repo with Geneformer-V1-10M checkpoint

## Decisions Made
- `validate_ensembl_ids()` resolution order (`gene_ids` -> `feature_id` -> Ensembl-shaped `var_names` -> `ValueError`) directly implements 13-RESEARCH.md's Don't-Hand-Roll guidance: the 10x MTX/.h5 ingest path already has `gene_ids` populated by scanpy, so no external mapping service is ever needed there; arbitrary uploads/census data fail loudly instead of silently degrading.
- Repinned `transformers==4.46` (Geneformer's own `requirements.txt` pin, not an arbitrary choice) after the unconstrained `setup.py install_requires` resolved `transformers==5.17.0`, which broke `import geneformer` with `ImportError: cannot import name 'SpecialTokensMixin'`. This is treated as a Rule 3 (blocking-issue) auto-fix, not a workaround around an anti-automation control -- the pin already exists upstream, it just isn't enforced by `setup.py`.
- Kept the three new Geneformer dataclasses fully separate from `PerturbationCall`/`PerturbationSummary` per 13-RESEARCH.md Pitfall 4 -- no shared base class, no optional fields bolted onto the existing types.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Repinned `transformers==4.46` after `pip install -e geneformer_worker/src` resolved an incompatible `transformers==5.17.0`**
- **Found during:** Task 2 (isolated `geneformer_worker/` environment setup)
- **Issue:** `geneformer`'s `setup.py` lists `transformers` in `install_requires` with no version bound (unlike its own `requirements.txt`, which pins `transformers==4.46`). The unconstrained resolve pulled the latest `transformers-5.17.0`, whose public API had removed/relocated `SpecialTokensMixin`, which `geneformer/collator_for_classification.py` imports directly -- `import geneformer` failed with `ImportError: cannot import name 'SpecialTokensMixin' from 'transformers'`.
- **Fix:** `geneformer_worker/.venv/bin/pip install "transformers==4.46"` (the exact version the project's own `requirements.txt` specifies). Verified `import geneformer` succeeds afterward, plus all four pipeline classes (`TranscriptomeTokenizer`, `EmbExtractor`, `InSilicoPerturber`, `InSilicoPerturberStats`) import cleanly.
- **Files modified:** None in the repo (venv-local pip state only); documented in `geneformer_worker/README.md`.
- **Verification:** `geneformer_worker/.venv/bin/python -c "from geneformer import TranscriptomeTokenizer, EmbExtractor, InSilicoPerturber, InSilicoPerturberStats; print('OK')"` -> `OK`.
- **Committed in:** `4ebe7ca` (Task 2 commit; README documents the fix, no code file changed)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary to satisfy the plan's own done-criterion ("`import geneformer` confirmed working"). No scope creep -- the fix used the project's own documented dependency pin, not an invented one.

## Issues Encountered

A full-suite pytest run (`uv run pytest tests/ -q -m "not live_llm and not bio_fm_smoke and not vcc_data and not census_data"`) surfaces 14 pre-existing failures in `tests/test_vcc_eval.py`/`tests/test_vcc_report.py` that are unrelated to this plan's changes (confirmed reproducible with this plan's files stashed out, and with `--ignore=tests/test_perturbation_ensembl.py`; same 14 failures either way -- a full-suite test-isolation/pollution issue, likely polars string-cache global state, not caused by 13-01 or 13-02). Logged to `.planning/phases/13-real-fm-inference-scgpt-then-geneformer/deferred-items.md` per the scope-boundary rule; not fixed (out of scope -- those files are not in this plan's `files_modified` list).

## User Setup Required

None required. This plan's `user_setup` entry (manual `git lfs pull`/checkpoint download fallback) was not triggered -- the automated LFS pull for `Geneformer-V1-10M` succeeded on the first attempt with no network, auth, or LFS-quota failure.

## Next Phase Readiness

- Plan 13-03 can now write `geneformer_worker/run_geneformer_perturb.py` against a real, working `geneformer` import and the fixed `GeneformerPerturbationCall`/`GeneformerPerturbationSummary` output contract.
- Plan 13-04 can call `validate_ensembl_ids()` unconditionally before any Geneformer inference invocation, and its `checkpoint:human-verify` step has no outstanding manual environment-setup step to resolve.
- No blockers.

---
*Phase: 13-real-fm-inference-scgpt-then-geneformer*
*Completed: 2026-09-17*

## Self-Check: PASSED

All claimed files found on disk; all claimed commit hashes (`edb552a`, `9e4515a`, `4ebe7ca`) found in git log.

---
phase: 04-bio-fm-cell-type-annotation
plan: 04
subsystem: annotation, agent
tags: [pipeline-composition, agent-tools, mcp-wiring, annotation]

# Dependency graph
requires:
  - phase: 04-bio-fm-cell-type-annotation
    provides: "04-02's baseline_annotate() decoupler ORA baseline, 04-03's call_scgpt_annotate() subprocess shim, 04-01's AnnotationCall/AnnotationSummary dataclasses"
provides:
  - "annotation/pipeline.py::annotate(name, version=None, store_root=..., ...) -> tuple[str, dict], composing baseline + FM calls into one AnnotationSummary"
  - "agent/tools.py::annotate_cell_type_tool, the third @tool-decorated MCP handler alongside ingest_10x_tool/analyze_dataset_tool"
  - "agent/server.py's bioclaw_server now registers all three tools"
affects: [04-05-checkpoint-acquisition]

# Tech tracking
tech-stack:
  patterns:
    - "annotate() never persists a new store version -- read-only on an already-clustered dataset, returns the SAME dataset_id it loaded (mirrors analyze()'s loaded_id display convention)"
    - "FM (scGPT) call wrapped in try/except Exception at the pipeline level -- any failure (including 'no checkpoint yet') falls back to fm_calls=[] while baseline_calls stays fully populated, matching ANNOT-02's unconditional-baseline requirement"
    - "annotate_cell_type_tool mirrors analyze_dataset_tool's exact shape: 'version' omitted from the tool's dict schema (Pitfall 2), read via args.get('version'), exceptions caught and returned as is_error:True instead of propagating (keeps every call on the PostToolUse hook path, per Phase 3's post-hoc fix)"

key-files:
  created:
    - tests/test_annotation_pipeline.py (test file existed untracked from a prior interrupted session; implementation was the only missing piece)
  modified:
    - annotation/pipeline.py (was a stub; implemented annotate())
    - agent/tools.py (added annotate_cell_type_tool)
    - agent/server.py (registered annotate_cell_type_tool)
    - tests/test_agent_tools.py (added annotate_cell_type_tool round-trip/schema/error tests; renamed the server-import test to check all three tools are wrapped)

key-decisions:
  - "test_annotate_cell_type_tool_round_trip mocks BOTH annotation.pipeline.call_scgpt_annotate AND annotation.pipeline.baseline_annotate -- baseline_annotate's default markers=None path calls decoupler's dc.op.resource(), a real network fetch (PanglaoDB) that failed in this sandbox ('DataFrame must have source and target columns') when exercised through the full ingest->analyze->annotate agent-tool round trip. Task 1's own pipeline tests already established this mocking pattern; Task 2's round-trip test needed the same treatment to stay network-free and deterministic, which the plan's task description didn't explicitly call out."

requirements-completed: ["ANNOT-01", "ANNOT-03"]

# Metrics
duration: ~20min
completed: 2026-09-06
---

# Phase 4 Plan 04: Pipeline Composition + Agent Tool Wiring Summary

**`annotate()` composes the FM and baseline annotation calls into one bounded, never-crashing `AnnotationSummary`, and `annotate_cell_type_tool` exposes it through the same in-process MCP server as the existing two Phase 3 tools -- ANNOT-01 and ANNOT-03 are both closed at the unit-test level, independent of the real scGPT checkpoint (deferred to Plan 04-05).**

## Performance

- **Tasks:** 2 completed (Task 1: `annotate()` composition, TDD; Task 2: `annotate_cell_type_tool` + server registration)
- **Files touched:** 4 (`annotation/pipeline.py`, `agent/tools.py`, `agent/server.py`, `tests/test_agent_tools.py`) + 1 pre-existing untracked test file adopted (`tests/test_annotation_pipeline.py`)

## Accomplishments
- Found `tests/test_annotation_pipeline.py` already written (untracked, from a prior interrupted session) exactly matching this plan's Task 1 spec -- implemented `annotation/pipeline.py::annotate()` against it rather than rewriting, confirming RED->GREEN (4/4 tests passing: FM-failure-falls-back-to-baseline, FM-success-included, explicit-version dataset_id, unknown-name KeyError propagation).
- `annotate()` loads via `DatasetStore.load()`, calls `baseline_annotate()` unconditionally, wraps `call_scgpt_annotate()` in try/except (writes the loaded AnnData to a temp `.h5ad` first, per `call_scgpt_annotate`'s file-path contract), and returns `(dataset_id, asdict(AnnotationSummary(...)))` -- never a new store version, never a bare label.
- Added `annotate_cell_type_tool` to `agent/tools.py`, mirroring `analyze_dataset_tool` verbatim (schema omits `version`, catches exceptions into `is_error: True`), and registered it in `agent/server.py`'s `bioclaw_server` tools list alongside the existing two.
- Added three new tests to `tests/test_agent_tools.py`: a full ingest->analyze->annotate round trip through the tool handlers (mocking both `call_scgpt_annotate` and `baseline_annotate` to stay network-free -- see Key Decisions), a schema-omits-version check, and an unknown-name error-result check. Renamed the old bare-import server test to `test_bioclaw_server_wraps_all_three_tools`, now asserting all three tool objects are the same objects `agent.server` re-exports.
- Full fast suite green: `uv run pytest tests/ -q -m "not live_llm and not bio_fm_smoke"` -> 98 passed, 1 deselected. `uv run python -c "from agent.server import bioclaw_server"` succeeds.

## Task Commits
1. `feat(04-04): implement annotate() pipeline composition (ANNOT-01/03)` -- `annotation/pipeline.py`, `tests/test_annotation_pipeline.py` (adopted from untracked)
2. `feat(04-04): wire annotate_cell_type_tool into agent tool surface` -- `agent/tools.py`, `agent/server.py`, `tests/test_agent_tools.py`

## Requirements Closed
- **ANNOT-01**: The agent can invoke `annotate_cell_type` as a tool call on an already-clustered, named/versioned dataset and receive a bounded `AnnotationSummary` JSON payload (verified end-to-end through the tool handler, mocked FM/baseline calls, real ingest+analyze round trip).
- **ANNOT-03**: Output is always a structured, bounded payload (`dataset_id`, `fm_calls`, `baseline_calls`, `fm_model`, `baseline_method`) -- never a bare label string, even when the FM call fails.

## Deferred
- Real scGPT checkpoint / `bio_fm_worker` import repair (torchtext ABI mismatch) and the `cellxgene-census` reference index build remain Plan 04-05's explicit scope -- this plan's tests mock `call_scgpt_annotate` throughout, matching the Validation Architecture's "ANNOT-01 (tool wiring, mocked FM)" test row.

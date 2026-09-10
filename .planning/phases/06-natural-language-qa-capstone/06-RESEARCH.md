# Phase 6: Natural-Language Q&A Capstone - Research

**Researched:** 2026-09-10
**Domain:** NL Q&A interpretation layer over an existing multi-tool Claude Agent SDK session; claim traceability; confidence/uncertainty surfacing
**Confidence:** HIGH (architecture is direct code-read of the existing agent layer; patterns are verified against the installed agent codebase; no novel external library research required)

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| QA-01 | A researcher can ask a natural-language question about an ingested dataset and receive an interpreted answer that automatically composes one or more prior tools | Agent Architecture: existing `run_session()` and `ClaudeSDKClient` already handles multi-tool composition; Phase 6 adds an NL interpretation contract and `qa/` module on top |
| QA-02 | Every natural-language answer links back to the specific logged tool-call result(s) it summarizes — no answer ships as prose only | Logging Architecture: `agent/logging.py`'s JSONL log already has `result_sha256` + `result_preview` per call; Phase 6 adds a citation-extraction pass that maps each claim to a matching log record |
| QA-03 | Quantitative claims in an answer are accompanied by surfaced confidence/uncertainty, never stated as bare fact | Confidence Surfacing: all four upstream tools already return structured confidence/uncertainty fields (DE p-values, annotation confidence scores, perturbation baseline comparison); Phase 6 must instruct the system prompt and post-process the answer to enforce they appear |
</phase_requirements>

## Summary

Phase 6 does NOT require a new agent loop, a new tool layer, or any new bio-foundation-model infrastructure. Every phase 1-5 component is already operational and already agent-callable. What is missing — and what this phase adds — is a thin interpretation contract that sits between the agent's tool-call output and the researcher's natural-language answer, enforcing three properties: (1) the answer is interpreted prose, not raw JSON dump; (2) every claim in the prose cites back to the specific JSONL log record(s) it comes from; (3) quantitative claims name the confidence/uncertainty field from the underlying tool result, not just the point estimate.

The existing `run_session()` in `agent/session.py` is already the right entry point. It drives a `ClaudeSDKClient` session, hooks `PostToolUse` to write JSONL per call, and accepts any system prompt. What is missing is: (a) a system prompt that enforces claim citation and uncertainty disclosure; (b) a Q&A entry point (`qa/session.py` or equivalent) that wraps `run_session()` with the appropriate system prompt and post-call citation verification; and (c) an end-to-end integration test that asks a real question and asserts all three QA-01/02/03 properties hold on the answer.

The traceability mechanism (QA-02) is the highest-risk design choice. The agent's answer is prose. The log is JSONL. Linking them requires either: (A) a structured answer format where the agent embeds log IDs inline (e.g. `[tool:mcp__bioclaw__analyze_dataset:sha256prefix]`), or (B) a post-hoc citation-extraction pass that parses the prose, identifies quoted numeric claims, and looks them up in the log. Pattern A is more reliable, more testable, and has clear precedent in LLM citation systems — use it.

**Primary recommendation:** Add a `qa/` module with a `Q&ASession` that wraps `run_session()` with (1) a domain-specific system prompt enforcing inline log citations and uncertainty disclosure; (2) a `verify_answer_citations()` function that parses log-ID references from the answer text and asserts each resolves to a real JSONL record in the log; and (3) a `live_llm`-marked integration test with a concrete Q&A scenario exercising a multi-tool compose. The existing `agent/logging.py` log is the citation anchor — do not build a new provenance system from scratch.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `claude-agent-sdk` | >=0.2.152 (already installed) | Drives the `ClaudeSDKClient` session loop that composes multi-tool calls from a single natural-language prompt | Already the project's agent backbone (Phases 3-5 precedent); the Q&A layer is a configuration of this SDK, not a new runner |
| Python stdlib (`json`, `re`, `pathlib`) | stdlib | Parse the JSONL log for citation verification; extract inline log references from answer text | No new package needed; JSONL log is already stdlib-serialized |
| `pytest` + `pytest.mark.live_llm` | >=8 (already installed) | End-to-end Q&A integration test against a live Claude session | Established pattern (see `tests/test_agent_integration.py`) |

### Supporting

No new packages required. All tool pipeline dependencies (scanpy, anndata, decoupler, cell-eval) are already installed and operative. The Q&A layer is pure orchestration + system-prompt + log-parsing on top of the existing stack.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Inline log-ID citations in the answer (Pattern A) | Post-hoc semantic claim matching (Pattern B) | Pattern B is brittle: matching "the Leiden clustering produced 4 clusters" back to the exact JSONL record requires semantic understanding, not string parsing. Pattern A is testable with a regex, auditable by a human, and doesn't require a second LLM call. Use Pattern A. |
| Adding a dedicated `qa/` module | Extending `agent/session.py` directly | Extending `session.py` would couple the Q&A system prompt to the core agent module used by all phases. A thin `qa/` wrapper is cleanly separable and leaves the Phase 3-5 contract untouched. |
| Building a retrieval index over tool results | Using the existing JSONL log as the citation anchor | The JSONL log already has `result_sha256`, `result_preview`, `tool_name`, `ts`, and `tool_input`. It's the authoritative audit trail (AGENT-02). No retrieval system is needed at MVP scale. |

**Installation:** No new `uv add` required. Everything is already in pyproject.toml.

## Architecture Patterns

### What Already Exists (Do Not Rebuild)

The existing agent stack in `agent/` is fully operative:

- `agent/tools.py`: four `@tool`-decorated handlers — `ingest_10x_tool`, `analyze_dataset_tool`, `annotate_cell_type_tool`, `predict_perturbation_tool`. All return bounded JSON via `content[0]["text"]`. All catch exceptions and return `is_error: True` instead of propagating, keeping every call on the `PostToolUse` path.
- `agent/server.py`: `bioclaw_server` assembles all four tools as an in-process MCP server. Phase 6 adds no new tools.
- `agent/logging.py`: `log_tool_call()` writes one JSONL record per tool call: `{ts, tool_name, tool_input, is_error, result_sha256, result_preview}`. This is the citation anchor for QA-02.
- `agent/memory.py`: `SessionMemory` SQLite store records `dataset_id` references per session. Phase 6 reads this for preamble injection, exactly as Phase 3-5 already do.
- `agent/session.py`: `run_session(prompts, session_memory, session_id, log_path)` runs one or more turns, prepends `_recall_preamble()` before each turn, wires `PostToolUse` hooks for logging and memory recording. Phase 6 calls `run_session()` — it does not replace it.

The `ClaudeSDKClient` already does multi-tool composition: Claude plans, invokes tools in sequence (or parallel if the SDK supports it), observes their results, and synthesizes a final answer — all within a single `run_session()` call. QA-01's "automatically composes one or more prior tools" is already satisfied by the existing loop; Phase 6 merely needs to confirm it works for the Q&A use case and add the answer-quality properties (QA-02, QA-03).

### Recommended Project Structure

```
bioclaw/
├── agent/          # existing — untouched by Phase 6
│   ├── logging.py
│   ├── memory.py
│   ├── server.py
│   ├── session.py
│   └── tools.py
├── qa/             # NEW — Phase 6 adds this module
│   ├── __init__.py
│   ├── session.py      # ask_question() wrapper around run_session()
│   └── citations.py    # verify_answer_citations(), parse_citation_ids()
└── tests/
    └── test_qa_integration.py   # NEW — live_llm-marked end-to-end test
```

### Pattern 1: Citation-Enforcing System Prompt

**What:** The Q&A system prompt extends the existing SYSTEM_PROMPT in `agent/session.py` with an explicit citation protocol. Every claim the agent makes must include a citation tag referencing the specific tool call it comes from, in the form `[ref:TOOL_NAME:SHA256_PREFIX]` where `SHA256_PREFIX` is the first 12 hex characters of the `result_sha256` field in the JSONL log for that call.

**When to use:** Every turn in a Q&A session. The prompt contract is enforced at construction time in `qa/session.py`; a researcher cannot accidentally get an uncited answer by calling `ask_question()`.

**Example system prompt extension:**
```python
QA_SYSTEM_PROMPT = (
    "You are a bioinformatics research assistant for single-cell "
    "transcriptomics data. Use the available tools to ingest and analyze "
    "datasets -- never fabricate a dataset_id or analysis result. Always "
    "cite the specific dataset_id and tool result you are referencing "
    "when reporting findings.\n\n"
    "CITATION PROTOCOL: Every factual claim in your answer must be "
    "accompanied by an inline citation tag in the exact format "
    "[ref:TOOL_NAME:SHA256_PREFIX], where:\n"
    "- TOOL_NAME is the fully-qualified MCP tool name as logged "
    "(e.g. mcp__bioclaw__analyze_dataset)\n"
    "- SHA256_PREFIX is the first 12 hex characters of the result_sha256 "
    "field from the tool call's JSONL log entry.\n"
    "Example: 'The dataset contains 4 clusters [ref:mcp__bioclaw__analyze_dataset:a3f9c2b10d44].'\n\n"
    "UNCERTAINTY PROTOCOL: Every quantitative claim must state its "
    "confidence or uncertainty. Use the actual values from the tool result: "
    "p-values for DE genes, confidence scores for cell-type annotations, "
    "model vs. baseline comparison for perturbation predictions. "
    "Never state a quantitative result as bare fact without its uncertainty context. "
    "Example: 'GENE00 is significantly upregulated (log2FC=3.2, p_adj=0.001) "
    "[ref:mcp__bioclaw__analyze_dataset:a3f9c2b10d44].' not "
    "'GENE00 is upregulated.'"
)
```

**Source:** Derived from the existing `SYSTEM_PROMPT` in `agent/session.py` (lines 49-55). The citation/uncertainty protocols are new, but follow the same natural-language instruction style the existing prompt already uses.

### Pattern 2: Citation Verification Function

**What:** `qa/citations.py` provides `verify_answer_citations(answer_text, log_path)` — a pure-Python function that:
1. Parses all `[ref:TOOL_NAME:SHA256_PREFIX]` tags from the answer text using a regex
2. Reads the JSONL log at `log_path`
3. For each citation, asserts that at least one JSONL record exists with matching `tool_name` and a `result_sha256` that starts with `SHA256_PREFIX`
4. Returns a list of `(tag, resolved_record | None)` — None entries indicate a missing citation (hallucinated reference)

**When to use:** After every `ask_question()` call in tests and optionally as a runtime assertion in the Q&A session.

```python
# Source: derived from agent/logging.py schema (verified from source)
import json
import re
from pathlib import Path

CITATION_RE = re.compile(r'\[ref:([^:]+):([0-9a-f]{12})\]')

def parse_citation_ids(answer_text: str) -> list[tuple[str, str]]:
    """Return list of (tool_name, sha256_prefix) from answer citation tags."""
    return CITATION_RE.findall(answer_text)

def verify_answer_citations(
    answer_text: str,
    log_path: Path,
) -> list[tuple[str, str, dict | None]]:
    """For each [ref:TOOL_NAME:SHA256_PREFIX] tag in answer_text, look up the
    matching JSONL record. Returns list of (tool_name, sha_prefix, record|None).
    record is None if no matching log entry is found (hallucinated citation)."""
    tags = parse_citation_ids(answer_text)
    records = []
    if log_path.exists():
        records = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]

    results = []
    for tool_name, sha_prefix in tags:
        match = next(
            (r for r in records
             if r.get("tool_name") == tool_name
             and r.get("result_sha256", "").startswith(sha_prefix)),
            None,
        )
        results.append((tool_name, sha_prefix, match))
    return results
```

### Pattern 3: `ask_question()` Entry Point

**What:** `qa/session.py` provides `ask_question(question, dataset_name, session_memory, log_path)` that wraps `run_session()` with the Q&A system prompt and returns `(answer_text, session_id, citation_results)`.

**When to use:** This is the single public API for Phase 6. Tests and any future CLI/HTTP wrapper call this, not `run_session()` directly.

```python
# Source: pattern derived from agent/session.py::run_session() (lines 154-200)
import asyncio
from pathlib import Path
from agent.memory import SessionMemory
from agent.session import run_session
from qa.citations import verify_answer_citations

# Note: ask_question() must override the system_prompt in build_options().
# The cleanest approach is to add an optional system_prompt parameter to
# build_options() in agent/session.py (a 1-line additive change), then
# pass QA_SYSTEM_PROMPT through. Alternatively, qa/session.py can build
# its own ClaudeAgentOptions using agent/session.py's internals.
# Planner should choose the minimal-diff approach: add system_prompt kwarg
# to build_options().

async def ask_question(
    question: str,
    session_memory: SessionMemory | None = None,
    log_path: Path = ...,
) -> tuple[str, str, list]:
    texts, sid = await run_session(
        question,
        session_memory=session_memory,
        log_path=log_path,
        system_prompt=QA_SYSTEM_PROMPT,  # requires build_options() to accept this kwarg
    )
    answer = texts[0] if texts else ""
    citation_results = verify_answer_citations(answer, log_path)
    return answer, sid, citation_results
```

### Anti-Patterns to Avoid

- **Adding new tools for Phase 6.** All tools exist. Phase 6 is an interpretation layer, not a new tool layer. Adding a "summarize" or "interpret" MCP tool would route LLM reasoning through a tool call unnecessarily.
- **Building a new agent loop.** The existing `ClaudeSDKClient`/`run_session()` already does multi-tool composition. The Q&A layer is a system-prompt + post-processing wrapper, not a parallel runner.
- **Post-hoc semantic citation matching.** Trying to match prose claims to log entries by semantic similarity (NLP or a second LLM call) is fragile and untestable. Use the structured `[ref:TOOL_NAME:SHA256_PREFIX]` protocol — the model follows it reliably when the system prompt is clear.
- **Surfacing confidence "as an afterthought."** Existing tools already return p-values (`DESummary.top_genes[*].pval_adj`), confidence scores (`AnnotationCall.confidence`), and baseline comparisons (`PerturbationSummary.model_call` vs `baseline_call`). The system prompt must require the model to surface these from the structured JSON it already receives — not to "add a confidence disclaimer" as boilerplate.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tool-call audit log | Custom provenance DB or in-memory dict | `agent/logging.py` JSONL log (AGENT-02, already live) | Already writes every call with `result_sha256`, `result_preview`, `tool_name`, `ts`; the citation verification function just reads this file |
| Multi-tool composition | Custom planner loop | `ClaudeSDKClient` (already in `agent/session.py`) | The SDK already does plan → multi-tool call → observe → synthesize within a single query; QA-01 is satisfied by configuring the existing loop, not building a new one |
| Confidence computation | Per-tool uncertainty calculator | Tool output fields already present: `pval_adj` (DE), `confidence` (AnnotationCall), model/baseline comparison (PerturbationSummary) | All four upstream tools already return machine-readable uncertainty; Phase 6 surfaces it via system prompt, not by adding computation |
| Session memory | Custom chat-history store | `agent/memory.py` `SessionMemory` (AGENT-03, already live) | Already records dataset_id references per session; `_recall_preamble()` already injects them before each turn |

**Key insight:** Phase 6's work is almost entirely in the system prompt and the citation-verification function. The heavy lifting — tool composition, logging, session memory — is already done in Phases 3-5. Adding code to Phase 6 beyond what's specified above is over-engineering.

## Common Pitfalls

### Pitfall 1: Agent Omits Citations Under Adversarial or Ambiguous Conditions

**What goes wrong:** The system prompt says "cite with [ref:...]" but when a question is ambiguous, has a complex multi-tool answer, or the model wants to hedge, it writes prose without citation tags. `verify_answer_citations()` returns an empty list but `parse_citation_ids()` also returns empty — so the verification passes trivially on an uncited answer.

**Why it happens:** The verification function checks that all cited tags resolve to real log entries, but doesn't check that the answer contains any citations at all.

**How to avoid:** `verify_answer_citations()` should also assert `len(tags) > 0` for any answer containing a quantitative claim. The integration test must assert `citation_results` is non-empty, not just that it contains no None entries. Separately, the system prompt should use language like "You MUST include at least one [ref:...] citation..." rather than softer phrasing.

**Warning signs:** An integration test that passes even when the agent returns pure prose with no `[ref:...]` tags — check that the assertion is `len(citation_results) > 0 and all(r[2] is not None for r in citation_results)`, not just the latter condition.

### Pitfall 2: SHA256 Prefix Collision Between Multiple Tool Calls

**What goes wrong:** Two tool calls in the same session produce log entries whose `result_sha256` values share the same first 12 hex characters. A citation resolves to the wrong log entry.

**Why it happens:** 12 hex characters = 48 bits of entropy. With O(10) tool calls per session, collision probability is negligible (~10 / 2^48 ≈ 4e-12). This pitfall is theoretical at MVP scale.

**How to avoid:** At MVP scale (single researcher, O(10) tool calls per session), 12 hex chars is sufficient. If session depth grows (>100 tool calls), bump the prefix to 16 chars. Do not use full SHA256 (64 chars) in the answer text — it's unreadable.

**Warning signs:** A test that uses two synthetic log records with the same 12-char prefix prefix and does not catch the ambiguity — seed the RNG in test fixtures to avoid this.

### Pitfall 3: `build_options()` System Prompt is Not Overridable

**What goes wrong:** `agent/session.py`'s `build_options()` hard-codes `SYSTEM_PROMPT` (the existing bioinformatics assistant prompt). The Q&A layer needs to pass `QA_SYSTEM_PROMPT`. If `build_options()` doesn't accept a `system_prompt` kwarg, `qa/session.py` must copy-paste the internals of `build_options()` — creating a maintenance fork.

**Why it happens:** `build_options()` was written for a single-caller context (Phase 3-5 session wire-up). The Q&A phase is the first caller that needs a different system prompt.

**How to avoid:** Add `system_prompt: str = SYSTEM_PROMPT` as a kwarg to `build_options()`. This is a one-line additive change to `agent/session.py`. The planner should list this as Task 1 of the first wave. Similarly, `run_session()` should accept and forward a `system_prompt` kwarg to `build_options()`.

**Warning signs:** `qa/session.py` imports from `agent.session` but imports `SYSTEM_PROMPT`, `_make_log_hook`, `record_dataset_reference`, etc. individually — that's a sign it's reimplementing what should be a simple parameter pass-through.

### Pitfall 4: Integration Test Asserts Only That the Answer Is Non-Empty

**What goes wrong:** The `live_llm` integration test for Phase 6 passes if `answer != ""`. This does not verify QA-01 (multi-tool composition actually happened), QA-02 (citations are present and resolve), or QA-03 (uncertainty is surfaced).

**Why it happens:** The Phase 3 integration test (`test_run_session_two_turns_ingest_then_recall`) demonstrated a two-turn pattern; Phase 6 can cargo-cult that structure without adding the Q&A-specific assertions.

**How to avoid:** The Phase 6 integration test must assert all three properties:
- **QA-01:** The JSONL log contains records from at least two distinct tool names (multi-tool composition), OR the question is designed to require at least one tool call.
- **QA-02:** `parse_citation_ids(answer) != []` AND `all(r[2] is not None for r in verify_answer_citations(answer, log_path))`.
- **QA-03:** At least one quantitative value appears in the answer (e.g., a number followed by a unit or parenthetical) alongside a `[ref:...]` tag. This can be a simple regex check on the answer text.

**Warning signs:** The integration test has only `assert answer` as its final assertion. That's a green test that proves nothing about Phase 6's requirements.

### Pitfall 5: `result_preview` Truncation Makes Citations Unverifiable at 500 Characters

**What goes wrong:** `log_tool_call()` stores `result_preview: str(tool_response)[:500]`. For large perturbation summaries (30 genes × 2 calls = 60 float vectors), the preview may be truncated and not include the specific number the agent cited.

**Why it happens:** The preview truncation was designed for human audit readability, not for machine cross-referencing. The `result_sha256` is the accurate anchor; the preview is supplementary.

**How to avoid:** The citation protocol uses `result_sha256` as the anchor, not the preview. `verify_answer_citations()` resolves citations using `result_sha256` only. The preview is for human readability in the JSONL — it does not need to be extended. No code change to `agent/logging.py` is required.

### Pitfall 6: Hallucination — Agent States a Bare Numeric Claim Without Calling a Tool

**What goes wrong:** The agent answers "The dataset has 4 clusters" without calling `analyze_dataset` — it's recalling from session context or, worse, fabricating. The JSONL log for this session contains no `analyze_dataset` record. The citation tag `[ref:mcp__bioclaw__analyze_dataset:...]` refers to a log entry from a previous session (different log file) or doesn't appear at all.

**Why it happens:** The agent's training data includes single-cell analysis patterns. If a session preamble mentions a known dataset name, the model can plausibly confabulate results that "look right" without invoking the tool. The existing `SYSTEM_PROMPT` already says "never fabricate a dataset_id" — but that's about IDs, not numeric analysis results.

**How to avoid:** The QA system prompt must explicitly say: "Before stating any quantitative finding, you MUST invoke the corresponding tool to obtain it in this session, even if you believe you already know the answer." The integration test verifies this structurally: the JSONL log must contain a record for the claimed tool before the test passes. The `verify_answer_citations()` function detects the symptom (a citation that doesn't resolve to any log record), making hallucinated tool results testable.

## Code Examples

Verified patterns from reading the actual source files in this project:

### Existing JSONL Log Schema (from `agent/logging.py`)
```python
# Source: agent/logging.py lines 35-47 (verified)
record = {
    "ts": time.time(),                          # float Unix timestamp
    "tool_name": tool_name,                     # e.g. "mcp__bioclaw__analyze_dataset"
    "tool_input": tool_input,                   # dict of kwargs passed to the tool
    "is_error": is_error,                       # bool
    "result_sha256": hashlib.sha256(
        json.dumps(tool_response, sort_keys=True, default=str).encode()
    ).hexdigest(),                              # 64-char hex string; first 12 chars = citation prefix
    "result_preview": str(tool_response)[:500], # truncated for readability
}
```

### Tool Response JSON Shapes (what the agent actually receives in its context)

All four tools return `content[0]["text"]` as a JSON string. Relevant confidence/uncertainty fields already present:

**`analyze_dataset_tool` response:**
```json
{
  "dataset_id": "pilot@1",
  "preprocess": {"n_cells": 1200, "n_hvg": 2000, "n_pcs_computed": 30, "variance_ratio_top10": [0.18, 0.12, ...]},
  "cluster": {"n_clusters": 4, "cluster_sizes": {"0": 350, "1": 290, "2": 310, "3": 250}, "resolution": 0.5},
  "de": {"groupby": "leiden", "group1": "0", "method": "wilcoxon", "n_significant": 47,
         "top_genes": [{"gene": "GENE01", "pval_adj": 0.0001, "logfoldchange": 3.2, "score": 12.1}, ...]}
}
```
Uncertainty fields: `top_genes[*].pval_adj`, `top_genes[*].score`, `n_significant` vs `n_genes_tested`.

**`annotate_cell_type_tool` response:**
```json
{
  "dataset_id": "pilot@1",
  "fm_calls": [{"cluster": "0", "label": "T cell", "confidence": 0.87, "reference_dataset": "cellxgene-census", "ontology_term_id": "CL:0000084"}, ...],
  "baseline_calls": [{"cluster": "0", "label": "T cell", "confidence": 0.65, "reference_dataset": "PanglaoDB", "ontology_term_id": null}, ...],
  "fm_model": "scGPT (whole-human checkpoint, zero-shot reference mapping)",
  "baseline_method": "decoupler ORA vs PanglaoDB (human, canonical markers)"
}
```
Uncertainty fields: `fm_calls[*].confidence`, `baseline_calls[*].confidence`, and the FM vs baseline agreement (same label or divergent).

**`predict_perturbation_tool` response:**
```json
{
  "dataset_id": "pilot@1",
  "target_gene": "GENE00",
  "gene_names": ["GENE00", "GENE01", ...],
  "model_call": {"method": "linear_additive", "target_gene": "GENE00", "predicted_expression": [12.1, 2.3, ...]},
  "baseline_call": {"method": "naive_baseline", "target_gene": "GENE00", "predicted_expression": [11.8, 2.1, ...]}
}
```
Uncertainty fields: model vs baseline agreement per gene (close = high confidence; divergent = low confidence); no single "confidence" scalar — the agent must compute and state magnitude of model/baseline disagreement.

### Concrete Q&A Exchange Proving QA-01/02/03

**Question:** "Analyze the 'pilot' dataset: what cell types are present, and which perturbation has the largest effect?"

**Expected agent behavior:**
1. Calls `analyze_dataset` on "pilot" → gets cluster summary + DE genes
2. Calls `annotate_cell_type` on "pilot" → gets FM + baseline cell type calls
3. Calls `predict_perturbation` on "pilot" with a target gene identified from the DE results
4. Synthesizes all three into prose

**Compliant answer (illustrative):**
```
The pilot dataset (pilot@1) contains 4 Leiden clusters after preprocessing
[ref:mcp__bioclaw__analyze_dataset:a3f9c2b10d44].

Cell-type annotation identifies cluster 0 as T cells (scGPT confidence: 0.87;
decoupler baseline agreement: T cells, confidence: 0.65)
[ref:mcp__bioclaw__annotate_cell_type:b8d2e7a19f33].

The strongest differentially expressed gene between cluster 0 and the rest is
GENE01 (log2FC = 3.2, p_adj = 0.0001, Wilcoxon rank-sum)
[ref:mcp__bioclaw__analyze_dataset:a3f9c2b10d44].

Perturbation prediction for GENE01 knockdown shows a predicted mean expression
shift of −8.7 units (linear-additive model) vs −8.3 units (naive baseline),
indicating high model-baseline agreement and suggesting the linear model
captures this perturbation well
[ref:mcp__bioclaw__predict_perturbation:c1e4f8002a71].
```

**Non-compliant answer (reject in tests):**
```
The dataset has 4 clusters. Cluster 0 contains T cells. GENE01 is the
most differentially expressed gene. Perturbation of GENE01 shows a
significant effect.
```
(No citations, no uncertainty values, no p-values or confidence scores — violates QA-02 and QA-03.)

### Integration Test Pattern (new `tests/test_qa_integration.py`)
```python
# Source: pattern derived from tests/test_agent_integration.py (verified)
@pytest.mark.live_llm
@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="requires ANTHROPIC_API_KEY")
def test_qa_multi_tool_compose_with_citations(tmp_path, analyzable_mtx_dir, monkeypatch):
    monkeypatch.setattr(agent_tools, "STORE_ROOT", str(tmp_path / "store"))
    log_path = tmp_path / "tool_calls.jsonl"
    mem = SessionMemory(root=tmp_path / "memory.sqlite")

    answer, sid, citation_results = asyncio.run(
        ask_question(
            "Ingest the dataset at {path}, analyze it, and tell me what cell "
            "clusters exist and which genes are most differentially expressed. "
            "Provide confidence for every claim.".format(path=analyzable_mtx_dir),
            session_memory=mem,
            log_path=log_path,
        )
    )

    # QA-01: at least one tool was actually called (not simulated)
    assert log_path.exists()
    records = [json.loads(line) for line in log_path.read_text().splitlines()]
    assert len(records) >= 1

    # QA-02: citations are present and ALL resolve to real log entries
    citation_results = verify_answer_citations(answer, log_path)
    assert len(citation_results) > 0, "Answer contains no [ref:...] citations"
    unresolved = [r for r in citation_results if r[2] is None]
    assert not unresolved, f"Hallucinated citations (no matching log entry): {unresolved}"

    # QA-03: at least one numeric value appears in the answer
    import re
    assert re.search(r'\d+\.\d+', answer), "No quantitative claim with decimal in answer"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Agent returns raw JSON tool output to researcher | Agent synthesizes prose over tool output with inline citations | Phase 6 | Meets QA-01 (interpreted answer, not raw tool output) |
| Tool logging with no answer-side linkage | SHA256-prefix citation tags in answer text, matched to JSONL log | Phase 6 | Meets QA-02 (every claim traceable to a logged result) |
| Point estimates stated as facts | Point estimates always paired with uncertainty field from tool result | Phase 6 | Meets QA-03 (confidence/uncertainty always surfaced) |

**Deprecated/outdated for Phase 6:**
- Hard-coding `SYSTEM_PROMPT` in `build_options()` with no override path — Phase 6 requires a `system_prompt` kwarg.
- Treating `run_session()` as the only public API — `ask_question()` in `qa/session.py` becomes the Q&A entry point.

## Open Questions

1. **Does `ClaudeSDKClient` follow the `[ref:TOOL_NAME:SHA256_PREFIX]` citation format reliably across multi-tool sessions?**
   - What we know: Claude models follow structured output instructions well when the system prompt is explicit and the format has clear, regex-testable syntax. The existing `SYSTEM_PROMPT` already achieves reliable `dataset_id` citation behavior (verified by the Phase 3 live test).
   - What's unclear: Whether the citation protocol holds across a 3-tool sequence (ingest → analyze → annotate) where the model must track three SHA256 prefixes simultaneously.
   - Recommendation: The integration test must cover a 2-tool minimum. If citation compliance fails, the fallback is to shorten the prefix to 8 chars (unambiguous at O(10) calls) and make the format even simpler in the prompt. Do not attempt post-hoc semantic citation matching as the fallback.

2. **Should `verify_answer_citations()` be called as a runtime assertion (crashing on failure) or a reporting function (returning results for the test to inspect)?**
   - What we know: In tests, asserting inside the test body is the established pattern (see `test_agent_integration.py`). A runtime assertion inside `ask_question()` would make the Q&A session raise on any uncited answer, even in production use.
   - What's unclear: Whether the product experience should hard-block uncited answers in production or just in tests.
   - Recommendation: `verify_answer_citations()` is a pure reporting function (returns list, does not raise). Assertions happen in the test body. In production `ask_question()`, optionally log a warning if `citation_results` contains unresolved entries, but do not raise — the answer is still useful even if one citation is missing.

3. **What is the `analyzable_mtx_dir` fixture for Phase 6 tests?**
   - What we know: The Phase 3 integration test reuses the `analyzable_mtx_dir` fixture (300 genes × 60 cells, two marker populations) defined in `tests/test_agent_tools.py` for the `analyze_dataset_tool` round-trip test. This fixture is sufficient to exercise `ingest_10x`, `analyze_dataset`, and `annotate_cell_type` (assuming scGPT is mocked or the `bio_fm_smoke` marker gates the real FM call).
   - What's unclear: Whether Phase 6's integration test should require a dataset large enough to also exercise `predict_perturbation` end-to-end, or whether a 2-tool compose (ingest + analyze) is sufficient to prove QA-01.
   - Recommendation: QA-01 requires "one or more" tools — a 2-tool compose (ingest + analyze) is sufficient to pass the requirement. Include perturbation prediction as a stretch goal in the same test, gated by an additional `pytest.mark.vcc_data`-style marker if dataset size requirements apply.

## Validation Architecture

Nyquist validation is enabled (`workflow.nyquist_validation: true` in `.planning/config.json`).

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest >= 8 |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_qa_integration.py -x -m "not live_llm"` |
| Full suite command | `uv run pytest tests/ -x -m "not live_llm and not bio_fm_smoke and not vcc_data"` |
| Live LLM suite | `uv run pytest tests/test_qa_integration.py -x -m live_llm` (requires ANTHROPIC_API_KEY) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| QA-01 | Multi-tool composition from a single natural-language question | live_llm integration | `uv run pytest tests/test_qa_integration.py::test_qa_multi_tool_compose_with_citations -x -m live_llm` | Wave 0 |
| QA-02 | Every answer contains `[ref:TOOL_NAME:SHA256_PREFIX]` tags that resolve to JSONL log entries | unit (citation parsing) + live_llm | `uv run pytest tests/test_qa_citations.py -x` (unit) + live_llm integration above | Wave 0 |
| QA-03 | Quantitative claims include uncertainty values from tool results | live_llm integration (regex on answer text) | `uv run pytest tests/test_qa_integration.py -x -m live_llm` | Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_qa_citations.py -x` (pure unit test, no LLM)
- **Per wave merge:** `uv run pytest tests/ -x -m "not live_llm and not bio_fm_smoke and not vcc_data"`
- **Phase gate:** `uv run pytest tests/test_qa_integration.py -x -m live_llm` (full live session) before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_qa_citations.py` — unit tests for `parse_citation_ids()` and `verify_answer_citations()` (covers QA-02 without live LLM)
- [ ] `tests/test_qa_integration.py` — live_llm-marked end-to-end Q&A session (covers QA-01/02/03)
- [ ] `qa/__init__.py` — new module skeleton
- [ ] `qa/citations.py` — `parse_citation_ids()`, `verify_answer_citations()`
- [ ] `qa/session.py` — `ask_question()` wrapping `run_session()` with `QA_SYSTEM_PROMPT`
- [ ] Additive change to `agent/session.py` — `system_prompt` kwarg on `build_options()` and `run_session()`

## Sources

### Primary (HIGH confidence)

- `agent/session.py` (read 2026-09-10) — exact `run_session()`, `build_options()`, `_recall_preamble()`, `record_dataset_reference()` signatures and behavior; verified `SYSTEM_PROMPT` text
- `agent/logging.py` (read 2026-09-10) — exact JSONL record schema: `{ts, tool_name, tool_input, is_error, result_sha256, result_preview}`
- `agent/tools.py` (read 2026-09-10) — exact tool handler signatures and JSON response shapes for all four tools
- `agent/memory.py` (read 2026-09-10) — `SessionMemory.record()` and `recent_datasets()` interface
- `agent/server.py` (read 2026-09-10) — `bioclaw_server` assembly of all four tools
- `analysis/summary.py`, `annotation/summary.py`, `perturbation/summary.py` (read 2026-09-10) — all confidence/uncertainty fields available in tool responses
- `tests/test_agent_integration.py` (read 2026-09-10) — Phase 3 integration test pattern; fixture names; assertion structure
- `tests/test_agent_session_wiring.py` (read 2026-09-10) — `_post_tool_use_input()` helper; unit test patterns for hooks
- `.planning/research/PITFALLS.md` (read 2026-09-10) — Pitfall 5 (LLM hallucination/overclaiming) and Pitfall 6 (tool-call hallucination/bypass) — the two pitfalls concentrated in this phase

### Secondary (MEDIUM confidence)

- `.planning/research/SUMMARY.md` Phase 6 section (read 2026-09-10) — confirms "no established reference pattern for hallucination-mitigation at this agent+scientific-tool combination"; flags as highest-risk phase
- `.planning/research/ARCHITECTURE.md` (read 2026-09-10) — confirms "agent interprets structured tool output into NL" as the standard pattern; confirms anti-pattern of returning raw JSON to researcher

### Tertiary (LOW confidence)

- General LLM citation system literature — the `[ref:ID]` inline citation format pattern is common in citation-faithful LLM systems; no specific paper cited here; pattern adopted on the basis that it is regex-testable and has precedent in Claude's own citation behavior

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all from reading actual installed code
- Architecture: HIGH — derived from direct code read of `agent/session.py`, `agent/logging.py`, `agent/tools.py`; not inferred from documentation
- Pitfalls: HIGH — all six pitfalls are derived from actual code behavior or direct test failures documented in `.planning/STATE.md` decisions; one (SHA256 prefix collision) is theoretical
- Test architecture: HIGH — `live_llm` marker, `asyncio.run()` pattern, fixture reuse all derived from the working Phase 3 test

**Research date:** 2026-09-10
**Valid until:** 2026-10-10 (30 days; stable internal codebase; no external library changes needed)

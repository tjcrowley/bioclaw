"""Q&A session entry point (Phase 6 Wave 2, QA-01/02/03).

`ask_question()` is the single public Q&A API for Phase 6. It wraps
`agent.session.run_session()` with `QA_SYSTEM_PROMPT` (adding the citation +
uncertainty + anti-hallucination protocols on top of the existing
bioinformatics-assistant `SYSTEM_PROMPT`), and post-processes the returned
answer through `qa.citations.verify_answer_citations()` to resolve every
`[ref:TOOL_NAME:SHA256_PREFIX]` tag against the JSONL tool-call log.

Contract (returned tuple):
    (answer_text: str, session_id: str, citation_results: list)

`citation_results` is `list[tuple[str, str, dict | None]]` — one entry per
citation tag in `answer_text`. A `None` third element indicates a
hallucinated citation (no matching JSONL record).

Notes:
- `verify_answer_citations()` is a reporting function; a citation with a
  `None` record does NOT raise here. Test suites (Plan 06-03) assert on the
  returned list to decide whether QA-02/QA-03 held for a given answer.
- Empty `texts` from `run_session()` (SDK returned nothing usable) yields
  `answer_text=""`, and `verify_answer_citations()` is still called (which
  returns `[]` for an empty answer -- consistent behavior at the boundary).
"""

from pathlib import Path

from agent.memory import SessionMemory
from agent.session import run_session
from qa.citations import verify_answer_citations

QA_SYSTEM_PROMPT = (
    "You are a bioinformatics research assistant for single-cell "
    "transcriptomics data. Use the available tools to ingest and analyze "
    "datasets -- never fabricate a dataset_id or analysis result. Always "
    "cite the specific dataset_id and tool result you are referencing "
    "when reporting findings.\n\n"
    "CITATION PROTOCOL: Every factual claim in your answer MUST be "
    "accompanied by an inline citation tag in the exact format "
    "[ref:TOOL_NAME:SHA256_PREFIX], where:\n"
    "- TOOL_NAME is the fully-qualified MCP tool name as logged "
    "(e.g. mcp__bioclaw__analyze_dataset)\n"
    "- SHA256_PREFIX is the first 12 lowercase hex characters of the "
    "result_sha256 field from the tool call's JSONL log entry.\n"
    "Example: 'The dataset contains 4 clusters "
    "[ref:mcp__bioclaw__analyze_dataset:a3f9c2b10d44].'\n"
    "You MUST include at least one [ref:...] citation in your answer. "
    "Answers with zero citation tags will be treated as unsupported.\n\n"
    "UNCERTAINTY PROTOCOL: Every quantitative claim MUST state its "
    "confidence or uncertainty using the actual values from the tool result. "
    "Specifically:\n"
    "- For differentially-expressed genes (analyze_dataset): report the "
    "adjusted p-value (pval_adj) and log-fold change (logfoldchange) from "
    "top_genes, and note n_significant when summarizing.\n"
    "- For cell-type annotations (annotate_cell_type): report the "
    "confidence score from fm_calls / baseline_calls for each label.\n"
    "- For perturbation predictions (predict_perturbation): compare "
    "model_call.predicted_expression against baseline_call.predicted_expression "
    "and surface the delta -- never state the model prediction as a bare "
    "fact without its baseline comparison.\n"
    "Never state a quantitative result as bare fact without its uncertainty "
    "context. Example: 'GENE00 is significantly upregulated (log2FC=3.2, "
    "p_adj=0.001) [ref:mcp__bioclaw__analyze_dataset:a3f9c2b10d44].' NOT "
    "'GENE00 is upregulated.'\n\n"
    "ANTI-HALLUCINATION PROTOCOL: Before stating any quantitative finding, "
    "you MUST invoke the corresponding tool to obtain it in this session, "
    "even if you believe you already know the answer from pretraining. Do "
    "not report gene lists, cluster counts, cell-type labels, or "
    "perturbation predictions unless a tool call in THIS session produced "
    "them and you cite that call's [ref:TOOL_NAME:SHA256_PREFIX] tag."
)


async def ask_question(
    question: str,
    session_memory: SessionMemory | None = None,
    log_path: Path = Path("tool_calls.jsonl"),
) -> tuple[str, str, list]:
    """Ask a natural-language question against the bioclaw tool server.

    Wraps `run_session()` with `QA_SYSTEM_PROMPT` (enforcing the citation +
    uncertainty + anti-hallucination protocols), then resolves every
    citation tag in the returned answer against the JSONL log at `log_path`.

    Parameters
    ----------
    question:
        The researcher's natural-language question.
    session_memory:
        Optional `SessionMemory` for cross-turn dataset-reference recall.
        `run_session()` creates a fresh one if omitted.
    log_path:
        Path to the JSONL tool-call log (also passed to `run_session()`'s
        PostToolUse logging hook, so citations resolve against the log
        this call itself writes).

    Returns
    -------
    (answer_text, session_id, citation_results)
        - answer_text: the final assistant text (first element of
          `run_session()`'s texts list, or "" if empty).
        - session_id: our process-local session id from `run_session()`.
        - citation_results: `verify_answer_citations(answer_text, log_path)`
          -- list[(tool_name, sha_prefix, record_or_None)]. A `None` record
          indicates a hallucinated/unresolvable citation; callers (tests)
          decide the policy for treating those.
    """
    texts, session_id = await run_session(
        question,
        session_memory=session_memory,
        log_path=log_path,
        system_prompt=QA_SYSTEM_PROMPT,
    )
    answer = texts[0] if texts else ""
    citation_results = verify_answer_citations(answer, log_path)
    return answer, session_id, citation_results

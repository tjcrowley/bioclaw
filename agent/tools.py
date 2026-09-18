"""AGENT-01 tool-calling surface: thin `@tool`-decorated async handlers
wrapping Phase 1/2's `ingest_10x`/`analyze` entrypoints verbatim -- no
reimplemented pipeline logic.

Per 03-RESEARCH.md Pitfall 1, the in-process `@tool` decorator only
forwards `content`/`is_error` from a handler's return dict --
`structuredContent` is silently dropped -- so both handlers here serialize
their bounded-dataclass result as a single JSON `text` content block
instead.

Per 03-RESEARCH.md Pitfall 2, `analyze_dataset_tool`'s optional `version`
parameter is intentionally omitted from the tool's dict schema (every key
in a dict schema is treated as required) and read via `args.get("version")`
in the handler body.

Both handlers catch exceptions raised by `ingest_10x`/`analyze` (e.g.
`KeyError` from an unknown dataset name, `RuntimeError` from a
counts-integrity failure) and return a normal `is_error: True` result
instead of letting them propagate. Contrary to 03-RESEARCH.md Pitfall 3's
original assumption, an uncaught handler exception does NOT surface as a
`PostToolUse` hook event with `tool_response.is_error` set -- the installed
`claude_agent_sdk` dispatches it as a distinct `PostToolUseFailure` event
(`PostToolUseFailureHookInput`, carrying `error: str`, no `tool_response`)
that `agent/session.py`'s hooks never subscribed to. Left uncaught, a failed
tool call is invisible to AGENT-02's audit log and to
`record_dataset_reference`. Catching here keeps every call -- success or
failure -- on the `PostToolUse` path those hooks are wired to.
"""

import json
import os
from typing import Any

from claude_agent_sdk import tool

from analysis.pipeline import AnalysisConfig, analyze
from annotation.pipeline import annotate
from ingest.census import fetch_census_dataset
from ingest.pipeline import ingest_10x
from perturbation.pipeline import predict as predict_perturbation
from perturbation.pipeline import predict_geneformer

# Module-level constant, set once at import time (overridable via the
# BIOCLAW_STORE_ROOT env var, or directly in tests via
# `monkeypatch.setattr(agent.tools, "STORE_ROOT", ...)`). Deliberately never
# read from LLM-controlled `args` -- the agent cannot redirect where
# datasets get written by asking for it in a prompt.
STORE_ROOT = os.environ.get("BIOCLAW_STORE_ROOT", "data")


@tool(
    "ingest_10x",
    "Ingest a 10x Genomics .mtx directory or .h5 file into the versioned "
    "dataset store, running standard QC. Returns the new dataset_id.",
    {"path": str, "name": str},
)
async def ingest_10x_tool(args: dict[str, Any]) -> dict[str, Any]:
    try:
        dataset_id = ingest_10x(args["path"], args["name"], store_root=STORE_ROOT)
    except Exception as exc:
        return {"content": [{"type": "text", "text": str(exc)}], "is_error": True}
    return {
        "content": [{"type": "text", "text": json.dumps({"dataset_id": dataset_id})}],
        "is_error": False,
    }


@tool(
    "analyze_dataset",
    "Run preprocess -> cluster -> (optional) differential expression on a "
    "named/versioned dataset from the store. Optionally pass 'version' "
    "(int) to analyze a specific version instead of the latest. Clustering "
    "always runs; differential expression only runs if 'run_de' is true, "
    "since the specific comparison (which cluster label vs. which "
    "reference) can never be guessed -- it requires 'de_groupby' (the "
    "cluster column, e.g. 'leiden') and 'de_group1' (the specific cluster "
    "label to test, e.g. '0'), both discoverable from a prior call's "
    "'cluster' summary. 'de_group2' optionally names a specific reference "
    "cluster (defaults to 'rest' of the clustering). To get DE results: "
    "call this tool once to see the cluster labels, then call it again "
    "with 'run_de' true and those labels. Returns a bounded summary, "
    "never raw matrices.",
    {"name": str},  # 'version'/'run_de'/'de_*' intentionally omitted -- optional, see Pitfall 2
)
async def analyze_dataset_tool(args: dict[str, Any]) -> dict[str, Any]:
    version = args.get("version")
    config = AnalysisConfig(
        run_de=args.get("run_de", False),
        de_groupby=args.get("de_groupby"),
        de_group1=args.get("de_group1"),
        de_group2=args.get("de_group2"),
        de_n_genes=args.get("de_n_genes", 25),
    )
    try:
        new_id, summary = analyze(
            args["name"], version=version, config=config, store_root=STORE_ROOT
        )
    except Exception as exc:
        return {"content": [{"type": "text", "text": str(exc)}], "is_error": True}
    return {
        "content": [
            {"type": "text", "text": json.dumps({"dataset_id": new_id, **summary})}
        ],
        "is_error": False,
    }


@tool(
    "annotate_cell_type",
    "Run bio-FM-backed (scGPT) cell-type annotation on a named/versioned, "
    "already-clustered dataset from the store, always paired with a "
    "decoupler marker-gene statistical baseline. Returns per-cluster calls "
    "from both methods, each with confidence, reference dataset, and Cell "
    "Ontology (CL) metadata -- never a bare label.",
    {"name": str},  # 'version' intentionally omitted -- optional, see Pitfall 2
)
async def annotate_cell_type_tool(args: dict[str, Any]) -> dict[str, Any]:
    version = args.get("version")
    try:
        dataset_id, summary = annotate(args["name"], version=version, store_root=STORE_ROOT)
    except Exception as exc:
        return {"content": [{"type": "text", "text": str(exc)}], "is_error": True}
    return {
        "content": [
            {"type": "text", "text": json.dumps({"dataset_id": dataset_id, **summary})}
        ],
        "is_error": False,
    }


@tool(
    "fetch_census_dataset",
    "Fetch a real public single-cell dataset from cellxgene-census by "
    "organism + obs_value_filter (no file upload); ingests it into the "
    "versioned dataset store and returns a dataset_id the other tools can "
    "analyze. 'organism' is passed separately, e.g. 'Homo sapiens' or "
    "'Mus musculus'. 'obs_value_filter' is a TileDB-SOMA filter expression "
    "over obs columns tissue_general, assay, cell_type, disease, and "
    "is_primary_data, e.g. \"tissue_general == 'lung' and is_primary_data "
    "== True\". Always require is_primary_data == True and a specific "
    "tissue in the filter to keep the result small.",
    {"organism": str, "obs_value_filter": str, "name": str},
    # 'census_version' intentionally omitted -- optional, see Pitfall 2
)
async def fetch_census_dataset_tool(args: dict[str, Any]) -> dict[str, Any]:
    try:
        dataset_id = await fetch_census_dataset(
            args["organism"],
            args["obs_value_filter"],
            args["name"],
            census_version=args.get("census_version", "stable"),
            store_root=STORE_ROOT,
        )
    except Exception as exc:
        return {"content": [{"type": "text", "text": str(exc)}], "is_error": True}
    return {
        "content": [{"type": "text", "text": json.dumps({"dataset_id": dataset_id})}],
        "is_error": False,
    }


@tool(
    "predict_perturbation",
    "Predict post-perturbation gene expression for a named dataset and target gene, "
    "always returning BOTH a linear-additive model prediction and Arc Institute's "
    "naive perturbation-mean baseline -- the two calls are never separated. "
    "Optionally pass 'version' (int) to operate on a specific dataset version "
    "instead of the latest.",
    {"name": str, "target_gene": str},  # 'version' intentionally omitted -- optional
)
async def predict_perturbation_tool(args: dict[str, Any]) -> dict[str, Any]:
    version = args.get("version")
    try:
        dataset_id, summary = predict_perturbation(
            args["name"],
            args["target_gene"],
            version=version,
            store_root=STORE_ROOT,
        )
    except Exception as exc:
        return {"content": [{"type": "text", "text": str(exc)}], "is_error": True}
    return {
        "content": [
            {"type": "text", "text": json.dumps({"dataset_id": dataset_id, **summary})}
        ],
        "is_error": False,
    }


@tool(
    "predict_perturbation_geneformer",
    "Predict post-perturbation effects for a named dataset and target gene using "
    "Geneformer's in-silico perturbation (four-step pipeline: tokenize, embed, perturb, "
    "aggregate). Returns a ranked list of genes by cosine-shift magnitude -- distinct from "
    "predict_perturbation's expression-vector output. Requires Ensembl-ID-mapped gene "
    "identifiers in the dataset (validated automatically; raises a clear error if absent). "
    "Can take a long time on CPU -- this is a separate, explicitly-invoked tool, not run "
    "unconditionally alongside predict_perturbation. Optionally pass 'version' (int).",
    {"name": str, "target_gene": str},  # 'version' intentionally omitted -- optional
)
async def predict_perturbation_geneformer_tool(args: dict[str, Any]) -> dict[str, Any]:
    version = args.get("version")
    try:
        dataset_id, summary = await predict_geneformer(
            args["name"], args["target_gene"], version=version, store_root=STORE_ROOT
        )
    except Exception as exc:
        return {"content": [{"type": "text", "text": str(exc)}], "is_error": True}
    return {
        "content": [
            {"type": "text", "text": json.dumps({"dataset_id": dataset_id, **summary})}
        ],
        "is_error": False,
    }

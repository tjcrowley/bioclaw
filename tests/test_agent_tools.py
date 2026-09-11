"""Tests for agent/tools.py: ingest_10x_tool/analyze_dataset_tool @tool
handlers, called directly as plain async functions (bypassing the SDK/LLM
entirely, per 03-RESEARCH.md Pitfall 4).

Note: `@tool`-decorated functions become `claude_agent_sdk.SdkMcpTool`
instances, not directly callable -- the actual async handler lives on
`.handler`. Tests invoke `<tool>.handler(args)`; `agent/server.py` (Task 2)
passes the `SdkMcpTool` instances themselves to `create_sdk_mcp_server`.

`tiny_mtx_dir` (18 genes) is used for the plain ingest test, matching the
plan's spec. It is deliberately NOT reused for the ingest->analyze round
trip: `ingest.qc.QCConfig`'s default `min_genes_per_cell=200` filters every
cell out of an 18-gene dataset (no cell can ever have >=200 detected genes
when there are only 18 genes total), and `ingest_10x_tool`'s schema
intentionally doesn't expose `qc_config` as a tool-input override (Phase 1's
own `tests/test_pipeline.py` always overrides `qc_config` for this exact
reason when running the full pipeline on `tiny_mtx_dir`). The round-trip
test below builds its own larger, real-structure 10x MEX directory
(`analyzable_mtx_dir`, 300 genes x 60 cells, two marker-gene pseudo
populations) that survives default QC and produces genuine cluster
structure, so `analyze_dataset_tool` is exercised with real default
settings end to end.
"""

import asyncio
import json

import agent.tools as agent_tools
from agent.tools import (
    analyze_dataset_tool,
    annotate_cell_type_tool,
    ingest_10x_tool,
    predict_perturbation_tool,
)


def test_ingest_10x_tool_returns_dataset_id(tmp_path, tiny_mtx_dir, monkeypatch):
    monkeypatch.setattr(agent_tools, "STORE_ROOT", str(tmp_path))

    result = asyncio.run(
        ingest_10x_tool.handler({"path": str(tiny_mtx_dir), "name": "pilot"})
    )

    assert result["is_error"] is False
    assert len(result["content"]) == 1
    block = result["content"][0]
    assert block["type"] == "text"
    payload = json.loads(block["text"])
    assert payload == {"dataset_id": "pilot@1"}


def test_analyze_dataset_tool_round_trip(tmp_path, analyzable_mtx_dir, monkeypatch):
    monkeypatch.setattr(agent_tools, "STORE_ROOT", str(tmp_path))

    asyncio.run(
        ingest_10x_tool.handler({"path": str(analyzable_mtx_dir), "name": "pilot"})
    )

    result = asyncio.run(analyze_dataset_tool.handler({"name": "pilot"}))

    assert result["is_error"] is False
    payload = json.loads(result["content"][0]["text"])
    assert payload["dataset_id"] == "pilot@2"
    assert set(["preprocess", "cluster", "de"]) <= set(payload.keys())
    assert payload["de"] is None


def test_analyze_dataset_tool_schema_omits_version():
    schema = analyze_dataset_tool.input_schema
    assert "version" not in schema
    assert "name" in schema


def test_analyze_dataset_tool_unknown_name_returns_error_result(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_tools, "STORE_ROOT", str(tmp_path))

    result = asyncio.run(analyze_dataset_tool.handler({"name": "does-not-exist"}))

    assert result["is_error"] is True


def test_annotate_cell_type_tool_round_trip(tmp_path, analyzable_mtx_dir, monkeypatch):
    monkeypatch.setattr(agent_tools, "STORE_ROOT", str(tmp_path))

    asyncio.run(
        ingest_10x_tool.handler({"path": str(analyzable_mtx_dir), "name": "pilot"})
    )
    asyncio.run(analyze_dataset_tool.handler({"name": "pilot"}))

    import annotation.pipeline as annotation_pipeline
    from annotation.summary import AnnotationCall

    canned_fm_calls = [
        AnnotationCall(
            cluster="0",
            label="T cell",
            confidence=0.91,
            reference_dataset="cellxgene-census: tissue=blood, n=3000",
            ontology_term_id="CL:0000084",
        )
    ]
    canned_baseline_calls = [
        AnnotationCall(
            cluster="0",
            label="PopA",
            confidence=0.9,
            reference_dataset="decoupler ORA vs PanglaoDB (human, canonical markers)",
            ontology_term_id=None,
        ),
        AnnotationCall(
            cluster="1",
            label="PopB",
            confidence=0.85,
            reference_dataset="decoupler ORA vs PanglaoDB (human, canonical markers)",
            ontology_term_id=None,
        ),
    ]
    monkeypatch.setattr(
        annotation_pipeline, "call_scgpt_annotate", lambda *a, **k: canned_fm_calls
    )
    monkeypatch.setattr(
        annotation_pipeline,
        "baseline_annotate",
        lambda *a, **k: canned_baseline_calls,
    )

    result = asyncio.run(annotate_cell_type_tool.handler({"name": "pilot"}))

    assert result["is_error"] is False
    payload = json.loads(result["content"][0]["text"])
    assert set(["dataset_id", "fm_calls", "baseline_calls", "fm_model", "baseline_method"]) <= set(
        payload.keys()
    )


def test_annotate_cell_type_tool_schema_omits_version():
    schema = annotate_cell_type_tool.input_schema
    assert "version" not in schema
    assert "name" in schema


def test_annotate_cell_type_tool_unknown_name_returns_error_result(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_tools, "STORE_ROOT", str(tmp_path))

    result = asyncio.run(annotate_cell_type_tool.handler({"name": "does-not-exist"}))

    assert result["is_error"] is True


def test_predict_perturbation_tool_round_trip(tmp_path, perturbation_adata, monkeypatch):
    """predict_perturbation_tool round-trip test, mirroring test_annotate_cell_type_tool_round_trip.

    Design: persist perturbation_adata directly into the store via DatasetStore.save()
    rather than going through ingest_10x/QC -- perturbation_adata already has correct
    target_gene labels and does not need the full ingest pipeline.  This is documented
    here as an intentional choice matching the pipeline test above.

    Asserts: is_error is False and JSON payload contains both model_call and baseline_call.
    """
    from ingest.store import DatasetStore

    monkeypatch.setattr(agent_tools, "STORE_ROOT", str(tmp_path))
    store = DatasetStore(root=tmp_path)
    store.save("pert-pilot", perturbation_adata)

    result = asyncio.run(
        predict_perturbation_tool.handler({"name": "pert-pilot", "target_gene": "GENE00"})
    )

    assert result["is_error"] is False
    payload = json.loads(result["content"][0]["text"])
    assert "model_call" in payload, "predict_perturbation_tool must return model_call"
    assert "baseline_call" in payload, "predict_perturbation_tool must return baseline_call"
    assert payload["model_call"] is not None
    assert payload["baseline_call"] is not None


def test_predict_perturbation_tool_unknown_name_returns_error_result(tmp_path, monkeypatch):
    """predict_perturbation_tool returns is_error=True for unknown dataset names."""
    monkeypatch.setattr(agent_tools, "STORE_ROOT", str(tmp_path))

    result = asyncio.run(
        predict_perturbation_tool.handler(
            {"name": "does-not-exist", "target_gene": "GENE00"}
        )
    )

    assert result["is_error"] is True


def test_predict_perturbation_tool_schema_omits_version():
    """predict_perturbation_tool's schema lists name and target_gene but not version."""
    schema = predict_perturbation_tool.input_schema
    assert "name" in schema
    assert "target_gene" in schema
    assert "version" not in schema


def test_bioclaw_server_wraps_all_four_tools():
    import agent.server as agent_server

    assert agent_server.ingest_10x_tool is ingest_10x_tool
    assert agent_server.analyze_dataset_tool is analyze_dataset_tool
    assert agent_server.annotate_cell_type_tool is annotate_cell_type_tool
    assert agent_server.predict_perturbation_tool is predict_perturbation_tool
    assert agent_server.bioclaw_server["name"] == "bioclaw"

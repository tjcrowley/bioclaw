"""Tests for annotation/fm_client.py: call_scgpt_annotate(), the subprocess
shim to the isolated bio_fm_worker/ scGPT environment (ANNOT-01).

All tests monkeypatch subprocess.run -- no real subprocess is ever
launched and the isolated bio_fm_worker/.venv does not need to exist or
have scgpt actually installed for this suite to pass.

Also includes tests for bio_fm_worker/run_scgpt_embed.py::_match_and_aggregate()
(FM-01), imported directly -- this module only needs numpy at import time
(anndata/scgpt are imported lazily inside other functions), so it imports
cleanly from the main venv without requiring the isolated bio_fm_worker/.venv.
"""

import json
import subprocess
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from annotation import fm_client
from annotation.fm_client import call_scgpt_annotate
from annotation.summary import AnnotationCall
from bio_fm_worker.run_scgpt_embed import _match_and_aggregate


def _completed_process(returncode, stdout="", stderr=""):
    return subprocess.CompletedProcess(
        args=["fake"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_call_scgpt_annotate_parses_success_json(monkeypatch):
    canned_stdout = json.dumps(
        [
            {
                "cluster": "0",
                "label": "T cell",
                "confidence": 0.91,
                "reference_dataset": "cellxgene-census: tissue=blood, n=3000",
                "ontology_term_id": "CL:0000084",
            }
        ]
    )

    def fake_run(*args, **kwargs):
        return _completed_process(0, stdout=canned_stdout)

    monkeypatch.setattr(fm_client.subprocess, "run", fake_run)

    calls = call_scgpt_annotate("query.h5ad", "reference.h5ad")

    assert calls == [
        AnnotationCall(
            cluster="0",
            label="T cell",
            confidence=0.91,
            reference_dataset="cellxgene-census: tissue=blood, n=3000",
            ontology_term_id="CL:0000084",
        )
    ]


def test_call_scgpt_annotate_raises_runtime_error_on_nonzero_exit(monkeypatch):
    def fake_run(*args, **kwargs):
        return _completed_process(1, stdout="", stderr="model checkpoint not found")

    monkeypatch.setattr(fm_client.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="model checkpoint not found"):
        call_scgpt_annotate("query.h5ad", "reference.h5ad")


def test_call_scgpt_annotate_raises_runtime_error_on_timeout(monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="fake", timeout=kwargs.get("timeout"))

    monkeypatch.setattr(fm_client.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="timeout"):
        call_scgpt_annotate("query.h5ad", "reference.h5ad", timeout=5.0)


def test_call_scgpt_annotate_builds_expected_command(monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return _completed_process(0, stdout="[]")

    monkeypatch.setattr(fm_client.subprocess, "run", fake_run)

    call_scgpt_annotate(
        "query.h5ad",
        "reference.h5ad",
        worker_python="bio_fm_worker/.venv/bin/python",
        script_path="bio_fm_worker/run_scgpt_embed.py",
        model_dir="bio_fm_worker/checkpoints/scGPT_human",
    )

    assert captured["cmd"] == [
        "bio_fm_worker/.venv/bin/python",
        "bio_fm_worker/run_scgpt_embed.py",
        "--query",
        "query.h5ad",
        "--reference",
        "reference.h5ad",
        "--model-dir",
        "bio_fm_worker/checkpoints/scGPT_human",
    ]
    assert captured["kwargs"]["capture_output"] is True
    assert captured["kwargs"]["text"] is True


def _make_reference():
    embed = np.array(
        [
            [0.99, 0.01],  # idx0: single nearest neighbor by cosine similarity
            [0.90, 0.10],  # idx1
            [0.85, 0.15],  # idx2
            [0.80, 0.20],  # idx3
            [0.75, 0.25],  # idx4
            [0.00, 1.00],  # idx5: orthogonal, excluded from top-5
        ]
    )
    obs = pd.DataFrame(
        {
            "cell_type": [
                "Monocyte",
                "T cell",
                "T cell",
                "T cell",
                "T cell",
                "Monocyte",
            ],
            "cell_type_ontology_term_id": [
                "CL:MONO",
                "CL:TCELL",
                "CL:TCELL",
                "CL:TCELL",
                "CL:TCELL",
                "CL:MONO",
            ],
        }
    )
    reference = SimpleNamespace(obs=obs)
    return reference, embed


def test_match_and_aggregate_uses_knn_vote_fraction_not_top1():
    reference, reference_embed = _make_reference()
    query = SimpleNamespace(obs=pd.DataFrame({"leiden": ["0"]}))
    query_embed = np.array([[1.0, 0.0]])

    calls = _match_and_aggregate(
        query, query_embed, reference, reference_embed, "test-reference", k=5
    )

    assert calls == [
        {
            "cluster": "0",
            "label": "T cell",
            "confidence": 0.8,
            "reference_dataset": "test-reference",
            "ontology_term_id": "CL:TCELL",
        }
    ]


def test_match_and_aggregate_clamps_k_to_reference_size():
    reference = SimpleNamespace(
        obs=pd.DataFrame(
            {
                "cell_type": ["T cell", "T cell"],
                "cell_type_ontology_term_id": ["CL:TCELL", "CL:TCELL"],
            }
        )
    )
    reference_embed = np.array([[0.9, 0.1], [0.8, 0.2]])
    query = SimpleNamespace(obs=pd.DataFrame({"leiden": ["0"]}))
    query_embed = np.array([[1.0, 0.0]])

    calls = _match_and_aggregate(
        query, query_embed, reference, reference_embed, "test-reference"
    )

    assert len(calls) == 1
    assert calls[0]["confidence"] == 1.0

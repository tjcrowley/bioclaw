"""Tests for annotation/fm_client.py: call_scgpt_annotate(), the subprocess
shim to the isolated bio_fm_worker/ scGPT environment (ANNOT-01).

All tests monkeypatch subprocess.run -- no real subprocess is ever
launched and the isolated bio_fm_worker/.venv does not need to exist or
have scgpt actually installed for this suite to pass.
"""

import json
import subprocess

import pytest

from annotation import fm_client
from annotation.fm_client import call_scgpt_annotate
from annotation.summary import AnnotationCall


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

"""Tests for perturbation/geneformer_client.py: call_geneformer_perturb(), the
subprocess shim to the isolated geneformer_worker/ environment (FM-02).

All tests monkeypatch subprocess.run -- no real subprocess is ever launched
and the isolated geneformer_worker/.venv does not need to exist or have
geneformer actually installed for this suite to pass. Mirrors
tests/test_annotation_fm_client.py's exact pattern for call_scgpt_annotate().
"""

import json
import subprocess

import pytest

from perturbation import geneformer_client
from perturbation.geneformer_client import call_geneformer_perturb
from perturbation.summary import GeneformerPerturbationCall, GeneShift


def _completed_process(returncode, stdout="", stderr=""):
    return subprocess.CompletedProcess(
        args=["fake"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_call_geneformer_perturb_parses_success_json(monkeypatch):
    canned_stdout = json.dumps(
        {
            "target_gene": "GATA1",
            "target_ensembl_id": "ENSG00000102145",
            "match_rate": 0.92,
            "ranked_genes": [
                {"gene": "KLF1", "ensembl_id": "ENSG00000105610", "cosine_shift": -0.41},
                {"gene": "TAL1", "ensembl_id": "ENSG00000162367", "cosine_shift": 0.12},
            ],
        }
    )

    def fake_run(*args, **kwargs):
        return _completed_process(0, stdout=canned_stdout)

    monkeypatch.setattr(geneformer_client.subprocess, "run", fake_run)

    call = call_geneformer_perturb("query.h5ad", "GATA1", "ENSG00000102145")

    assert call == GeneformerPerturbationCall(
        method="geneformer",
        target_gene="GATA1",
        target_ensembl_id="ENSG00000102145",
        match_rate=0.92,
        ranked_genes=[
            GeneShift(gene="KLF1", ensembl_id="ENSG00000105610", cosine_shift=-0.41),
            GeneShift(gene="TAL1", ensembl_id="ENSG00000162367", cosine_shift=0.12),
        ],
    )


def test_call_geneformer_perturb_raises_runtime_error_on_nonzero_exit(monkeypatch):
    def fake_run(*args, **kwargs):
        return _completed_process(
            1, stdout="", stderr="match_rate 0.31 below 0.5 threshold"
        )

    monkeypatch.setattr(geneformer_client.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="match_rate 0.31 below 0.5 threshold"):
        call_geneformer_perturb("query.h5ad", "GATA1", "ENSG00000102145")


def test_call_geneformer_perturb_raises_runtime_error_on_timeout(monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="fake", timeout=kwargs.get("timeout"))

    monkeypatch.setattr(geneformer_client.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="timeout"):
        call_geneformer_perturb(
            "query.h5ad", "GATA1", "ENSG00000102145", timeout=5.0
        )


def test_call_geneformer_perturb_builds_expected_command(monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return _completed_process(
            0,
            stdout=json.dumps(
                {
                    "target_gene": "GATA1",
                    "target_ensembl_id": "ENSG00000102145",
                    "match_rate": 0.92,
                    "ranked_genes": [],
                }
            ),
        )

    monkeypatch.setattr(geneformer_client.subprocess, "run", fake_run)

    call_geneformer_perturb(
        "query.h5ad",
        "GATA1",
        "ENSG00000102145",
        worker_python="geneformer_worker/.venv/bin/python",
        script_path="geneformer_worker/run_geneformer_perturb.py",
        model_dir="geneformer_worker/src/Geneformer-V1-10M",
    )

    assert captured["cmd"] == [
        "geneformer_worker/.venv/bin/python",
        "geneformer_worker/run_geneformer_perturb.py",
        "--query",
        "query.h5ad",
        "--target-gene",
        "GATA1",
        "--target-ensembl-id",
        "ENSG00000102145",
        "--model-dir",
        "geneformer_worker/src/Geneformer-V1-10M",
    ]
    assert captured["kwargs"]["capture_output"] is True
    assert captured["kwargs"]["text"] is True

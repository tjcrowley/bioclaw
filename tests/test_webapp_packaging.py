"""Packaging/local-verification regression tests (PKG-01, PKG-02).

Promotes the one-off manual "no OpenClaw import" grep (recorded in
.planning/phases/09-frontend-chat-ui/09-VERIFICATION.md) into a permanent,
always-run automated check, and smoke-tests the demo dataset generator
script used by Plan 10-02's manual upload-flow verification.
"""

import pathlib

WEBAPP_DIR = pathlib.Path(__file__).resolve().parent.parent / "webapp"


def test_webapp_has_no_openclaw_dependency():
    """PKG-01: webapp/ must have zero code/runtime dependency on the sibling
    OpenClaw project (the actual OpenClaw agent product at
    ~/.openclaw/workspace) -- NOT on bioclaw's own agent/qa/ingest packages,
    which webapp is intentionally supposed to import directly.
    """
    offending = []
    for path in WEBAPP_DIR.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in (".py", ".js", ".html", ".css"):
            continue
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(errors="ignore").lower()
        if "openclaw" in text:
            offending.append(str(path))
    assert not offending, f"Found OpenClaw references in: {offending}"


def test_make_sample_dataset_writes_valid_10x_dir(tmp_path):
    from scripts.make_sample_dataset import generate_sample_dataset

    out_dir = tmp_path / "demo_10x"
    generate_sample_dataset(out_dir)

    for fname in ("matrix.mtx.gz", "barcodes.tsv.gz", "features.tsv.gz"):
        assert (out_dir / fname).exists(), f"missing {fname}"

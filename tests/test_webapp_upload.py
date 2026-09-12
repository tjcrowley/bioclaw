"""Fast-tier tests for webapp/backend/uploads.py and POST /api/upload (API-04)."""
import asyncio
import io

from fastapi import UploadFile

from webapp.backend import uploads


def _upload(name: str, content: bytes = b"data") -> UploadFile:
    return UploadFile(file=io.BytesIO(content), filename=name)


def test_stage_single_h5_file_stages_to_tempfile():
    f = _upload("sample.h5")
    path = asyncio.run(uploads.stage([f]))
    try:
        assert path.name == "sample.h5"
        assert path.read_bytes() == b"data"
    finally:
        uploads.cleanup(path)


def test_stage_rejects_bad_single_suffix():
    f = _upload("sample.txt")
    try:
        asyncio.run(uploads.stage([f]))
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_stage_mtx_trio_stages_all_three():
    files = [_upload(n) for n in ["matrix.mtx.gz", "barcodes.tsv.gz", "features.tsv.gz"]]
    path = asyncio.run(uploads.stage(files))
    try:
        assert path.is_dir()
        assert {p.name for p in path.iterdir()} == {
            "matrix.mtx.gz", "barcodes.tsv.gz", "features.tsv.gz",
        }
    finally:
        uploads.cleanup(path)


def test_stage_rejects_incomplete_mtx_trio():
    files = [_upload("matrix.mtx.gz"), _upload("barcodes.tsv.gz")]
    try:
        asyncio.run(uploads.stage(files))
        assert False, "expected ValueError"
    except ValueError:
        pass

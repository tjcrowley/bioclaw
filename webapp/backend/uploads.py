"""Multipart upload staging helper (API-04).

Real 10x MEX (`.mtx`) format is three separate gzipped files
(matrix.mtx.gz, barcodes.tsv.gz, features.tsv.gz), not one -- scanpy's
sc.read_10x_mtx reads a directory and expects exactly these names.
A .h5/.h5ad upload is a single file. This module stages uploaded bytes
onto a real filesystem path/directory (ingest_10x() takes a path, not
bytes) and validates the file-count/name shape before ever touching
scanpy, so a wrong upload gets a clean ValueError instead of a scanpy
FileNotFoundError deep in a traceback.
"""
import shutil
import tempfile
from pathlib import Path

from fastapi import UploadFile

_MTX_NAMES = {"matrix.mtx.gz", "barcodes.tsv.gz", "features.tsv.gz"}
_SINGLE_FILE_SUFFIXES = (".h5", ".h5ad")


async def stage(files: list[UploadFile]) -> Path:
    """Writes uploaded file(s) to a fresh temp path/dir and returns it.
    Raises ValueError for a shape FastAPI itself cannot reject (wrong file
    count/names) -- callers should turn this into a 422, not let it propagate."""
    if len(files) == 1:
        f = files[0]
        suffix = Path(f.filename or "").suffix
        if suffix not in _SINGLE_FILE_SUFFIXES:
            raise ValueError(
                f"Single-file upload must be .h5 or .h5ad, got {f.filename!r}. "
                "A .mtx (10x MEX) dataset requires 3 files: "
                "matrix.mtx.gz, barcodes.tsv.gz, features.tsv.gz."
            )
        tmp = Path(tempfile.mkdtemp()) / f.filename
        with tmp.open("wb") as out:
            shutil.copyfileobj(f.file, out)
        return tmp

    names = {f.filename for f in files}
    if names != _MTX_NAMES:
        raise ValueError(
            f"3-file upload must be exactly {sorted(_MTX_NAMES)}, got {sorted(n for n in names if n)}"
        )
    tmp_dir = Path(tempfile.mkdtemp())
    for f in files:
        with (tmp_dir / f.filename).open("wb") as out:
            shutil.copyfileobj(f.file, out)
    return tmp_dir


def cleanup(path: Path) -> None:
    root = path if path.is_dir() else path.parent
    shutil.rmtree(root, ignore_errors=True)

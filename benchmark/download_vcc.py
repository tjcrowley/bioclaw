"""Scripted VCC public dataset download -- Phase 5, Plan 05-06.

Downloads one or more splits of the Arc Institute Virtual Cell Challenge public
dataset from the Google Cloud Storage (GCS) bucket into a local cache directory.

Downloads use ``gcsfs`` (installed via ``uv add gcsfs``) for authenticated
streaming reads from GCS, rather than shelling out to ``gcloud``/``gsutil``
(which are not guaranteed to be installed in every environment).  ``gcsfs``
uses Application Default Credentials (ADC) if available; if not, it falls
back to anonymous access.  Anonymous access will succeed for reading metadata
(listing bucket contents) but WILL FAIL with a Requester Pays error or 403
when actually downloading data, because the bucket is subject to Requester
Pays.

---------------------------------------------------------------------
ONE-TIME SETUP STEPS (human, not automated)
---------------------------------------------------------------------

Step 1 — Subscribe to the dataset on GCP Marketplace (free tier):
  Open https://console.cloud.google.com/marketplace/product/bigquery-public-data/arc-institute
  Click "Subscribe" (or "Enroll").  Select the GCP project you will use to
  download data.  Up to 2 TB/month is free, but ONLY for a subscribed project.

Step 2 — Authenticate gcloud:
  gcloud auth login
  gcloud auth application-default login
  gcloud config set project <YOUR_SUBSCRIBED_PROJECT_ID>

Step 3 — Re-run the download:
  uv run python -c "
  from benchmark.download_vcc import download_vcc_split
  path = download_vcc_split('validation', billing_project='<YOUR_PROJECT_ID>')
  print('Downloaded to:', path)
  "

Step 4 — After the validation split is confirmed, download training:
  uv run python -c "
  from benchmark.download_vcc import download_vcc_split
  path = download_vcc_split('train', billing_project='<YOUR_PROJECT_ID>')
  print('Downloaded to:', path)
  "

---------------------------------------------------------------------
REQUESTER PAYS BILLING NOTE (per 05-RESEARCH.md Pitfall 7)
---------------------------------------------------------------------

This bucket (gs://arc-institute-virtual-cell-atlas/) uses Requester Pays.
The 2 TB/month free tier requires subscribing on GCP Marketplace *before*
making any requests.  ``billing_project`` must match the project ID used
during subscription.  If you are charged unexpectedly:
  1. Subscribe to the dataset on Marketplace immediately (stops future charges).
  2. File a ticket with Google Cloud Support to request a billing adjustment
     for charges made before subscription.

---------------------------------------------------------------------
BUCKET STRUCTURE (verified 2026-09-09 from the official VCC README)
---------------------------------------------------------------------

gs://arc-institute-virtual-cell-atlas/virtual-cell-challenge/2025/
  train/
    adata_Training.h5ad     (~10-30 GB — download last)
    pert_counts_Training.csv
  validation/
    adata_Validation.h5ad   (smallest split — start here)
  test/
    (contents not listed in public README — will be discovered at download time)

---------------------------------------------------------------------
LOCAL CACHE STRUCTURE
---------------------------------------------------------------------

data/vcc_raw/
  validation/
    adata_Validation.h5ad
  train/
    adata_Training.h5ad
    pert_counts_Training.csv
  test/
    (contents mirrored from bucket)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bucket constants (verified from official VCC README, 2026-09-09)
# ---------------------------------------------------------------------------

_VCC_BUCKET = "arc-institute-virtual-cell-atlas"
_VCC_PREFIX = "virtual-cell-challenge/2025"

# Known file manifests per split (from official VCC README and tutorial notebook).
# The test split's file list is not published; it will be discovered at runtime
# by listing the bucket prefix.
_SPLIT_MANIFESTS: dict[str, list[str]] = {
    "validation": ["adata_Validation.h5ad"],
    "train": ["adata_Training.h5ad", "pert_counts_Training.csv"],
    # "test" is intentionally omitted -- discovered at runtime (see _list_split_files)
}

_DEFAULT_OUT_DIR = "data/vcc_raw"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def download_vcc_split(
    split: str,
    out_dir: str | Path = _DEFAULT_OUT_DIR,
    billing_project: str | None = None,
) -> Path | None:
    """Download one split of the VCC public dataset from GCS into a local cache.

    Uses ``gcsfs`` for authenticated GCS access.  Authentication must be
    established before calling this function (see module docstring for setup
    steps).

    Args:
        split: One of ``"train"``, ``"validation"``, or ``"test"``.  The
            validation split is the smallest and recommended as the first
            download to verify auth/billing are working.
        out_dir: Local directory in which to cache the downloaded split.
            The split's files will be written to ``{out_dir}/{split}/``.
            Defaults to ``"data/vcc_raw"``.
        billing_project: GCP project ID to use for Requester Pays billing.
            **Must** match the project subscribed to the dataset on GCP
            Marketplace.  If ``None``, the function attempts to infer it
            from the ``GCLOUD_PROJECT`` / ``GOOGLE_CLOUD_PROJECT``
            environment variables (standard ADC conventions), then falls
            back to an anonymous/unauthenticated attempt, which WILL fail
            for this bucket.

    Returns:
        The local ``Path`` to the downloaded split directory if successful,
        or ``None`` if the download failed (error is printed + logged).

    Raises:
        Nothing -- all errors are caught, logged, and returned as ``None``
        so Task 3's checkpoint can report the exact failure without
        crashing the calling test suite.
    """
    try:
        return _download_split_inner(split, Path(out_dir), billing_project)
    except Exception as exc:
        _log_failure(split, exc)
        return None


# ---------------------------------------------------------------------------
# Internal implementation
# ---------------------------------------------------------------------------

def _resolve_billing_project(billing_project: str | None) -> str | None:
    """Resolve billing project from argument or environment variables."""
    if billing_project:
        return billing_project
    for env_var in ("GCLOUD_PROJECT", "GOOGLE_CLOUD_PROJECT", "BILLING_PROJECT"):
        val = os.environ.get(env_var)
        if val:
            logger.info("Using billing project from env var %s: %s", env_var, val)
            return val
    return None


def _make_gcs_filesystem(billing_project: str | None):
    """Instantiate a gcsfs.GCSFileSystem with appropriate auth settings.

    Does NOT fall back to anonymous access.  Anonymous access to this Requester
    Pays bucket will either fail with a 403, or (worse) stream a corrupt error
    response body to disk without raising a Python exception.  In either case
    the result is useless.  Authentication is required.

    Raises RuntimeError if no credentials are available.
    """
    import gcsfs

    kwargs: dict = {}
    if billing_project:
        kwargs["requester_pays"] = billing_project

    # Check if Application Default Credentials (ADC) are available before
    # attempting to create the filesystem.  gcsfs uses google-auth under the
    # hood; if GOOGLE_APPLICATION_CREDENTIALS is set, it will be found.
    import os
    has_creds = (
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") is not None
        or os.environ.get("CLOUDSDK_CONFIG") is not None
    )

    # gcsfs also discovers credentials from well-known ADC paths
    try:
        import google.auth
        creds, _ = google.auth.default()
        has_creds = True
    except Exception:
        pass

    if not has_creds:
        raise RuntimeError(
            "No Google Cloud credentials found.  "
            "This bucket (gs://arc-institute-virtual-cell-atlas/) uses Requester Pays "
            "and requires authenticated access.\n"
            "Setup steps:\n"
            "  1. Install gcloud CLI: https://cloud.google.com/sdk/docs/install\n"
            "  2. Run: gcloud auth login\n"
            "  3. Run: gcloud auth application-default login\n"
            "  4. Run: gcloud config set project <YOUR_SUBSCRIBED_PROJECT_ID>\n"
            "  5. Subscribe at: "
            "https://console.cloud.google.com/marketplace/product/bigquery-public-data/arc-institute\n"
            "  6. Re-run this download with billing_project='<YOUR_PROJECT_ID>'"
        )

    fs = gcsfs.GCSFileSystem(**kwargs)
    logger.info("GCS filesystem created (authenticated via ADC).")
    return fs


def _list_split_files(fs, split: str) -> list[str]:
    """List blob names within the split prefix on GCS.

    Uses the known manifest if available, otherwise discovers by listing.
    Returns a list of blob names relative to the bucket root.
    """
    prefix = f"{_VCC_BUCKET}/{_VCC_PREFIX}/{split}/"
    if split in _SPLIT_MANIFESTS:
        # Use the documented manifest (avoids a listing call that may itself
        # require billing for Requester Pays)
        return [
            f"{prefix}{filename}"
            for filename in _SPLIT_MANIFESTS[split]
        ]
    # Discover files at runtime (test split, or unknown future splits)
    logger.info("Listing GCS prefix %s (split not in known manifest)", prefix)
    try:
        blobs = fs.ls(prefix)
        # Filter to actual files (not sub-prefixes)
        return [b for b in blobs if not b.endswith("/")]
    except Exception as exc:
        raise RuntimeError(
            f"Could not list GCS prefix {prefix!r}: {exc}. "
            "This is often a Requester Pays or auth error. "
            "See module docstring for setup steps."
        ) from exc


def _verify_h5ad(local_path: Path) -> None:
    """Verify that a downloaded .h5ad file is a valid HDF5 file.

    gcsfs can write a partial or error-response body to disk without raising
    an exception (e.g., when anonymous access to a Requester Pays bucket
    returns a 403 error page that happens to be large).  This check catches
    corrupt downloads early and raises RuntimeError with a descriptive message.
    """
    import h5py

    try:
        with h5py.File(local_path, "r") as f:
            _ = list(f.keys())  # Minimal read to confirm valid HDF5 structure
    except Exception as exc:
        local_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Downloaded file {local_path} is not a valid HDF5/h5ad file: {exc}\n"
            "This usually means the download was incomplete or returned an auth error "
            "body (e.g., a 403 HTML page written to disk by gcsfs). "
            "Verify that billing_project is set and matches your GCP Marketplace "
            "subscription, then re-run the download."
        ) from exc


def _download_blob(fs, gcs_blob: str, local_path: Path) -> None:
    """Download a single GCS blob to a local path, skipping if already present and valid."""
    if local_path.exists():
        # For h5ad files, verify the existing file is valid before skipping
        if local_path.suffix == ".h5ad":
            try:
                _verify_h5ad(local_path)
                local_size = local_path.stat().st_size
                logger.info(
                    "Skipping %s (already exists and is valid at %s, %d bytes)",
                    gcs_blob, local_path, local_size,
                )
                return
            except RuntimeError:
                logger.warning(
                    "Existing file %s is invalid; re-downloading.", local_path
                )
                # File has already been deleted by _verify_h5ad; fall through to download
        else:
            local_size = local_path.stat().st_size
            logger.info(
                "Skipping %s (already exists at %s, %d bytes)",
                gcs_blob, local_path, local_size,
            )
            return

    local_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading gs://%s -> %s", gcs_blob, local_path)
    print(f"  Downloading gs://{gcs_blob} -> {local_path} ...")

    try:
        gcs_url = gcs_blob if gcs_blob.startswith("gs://") else f"gs://{gcs_blob}"
        fs.get(gcs_url, str(local_path))
        size_mb = local_path.stat().st_size / (1024 * 1024)
        print(f"  Done: {size_mb:.1f} MB")
        logger.info("Downloaded %s (%.1f MB)", local_path, size_mb)
    except Exception as exc:
        # Clean up any partial download
        if local_path.exists():
            local_path.unlink()
        raise RuntimeError(
            f"Download failed for gs://{gcs_blob}: {type(exc).__name__}: {exc}\n"
            "Common causes:\n"
            "  - Not authenticated: run `gcloud auth application-default login`\n"
            "  - Requester Pays: set billing_project to your subscribed GCP project ID\n"
            "  - Not subscribed: subscribe at "
            "https://console.cloud.google.com/marketplace/product/bigquery-public-data/arc-institute"
        ) from exc

    # Verify .h5ad integrity after download
    if local_path.suffix == ".h5ad":
        _verify_h5ad(local_path)


def _download_split_inner(
    split: str, out_dir: Path, billing_project: str | None
) -> Path:
    """Inner implementation -- exceptions propagate to download_vcc_split's handler."""
    billing_project = _resolve_billing_project(billing_project)

    print(f"\n=== VCC download: split={split!r}, billing_project={billing_project!r} ===")
    if not billing_project:
        print(
            "WARNING: No billing project set. This WILL fail for the Requester Pays "
            "bucket unless you have already subscribed and ADC is configured."
        )

    fs = _make_gcs_filesystem(billing_project)
    split_dir = out_dir / split
    split_dir.mkdir(parents=True, exist_ok=True)

    blobs = _list_split_files(fs, split)
    if not blobs:
        raise RuntimeError(
            f"No files found for split {split!r} under "
            f"gs://{_VCC_BUCKET}/{_VCC_PREFIX}/{split}/. "
            "The bucket structure may have changed; check the VCC README."
        )

    print(f"  Found {len(blobs)} file(s) to download for split {split!r}:")
    for blob in blobs:
        filename = blob.split("/")[-1]
        local_path = split_dir / filename
        _download_blob(fs, blob, local_path)

    print(f"  All files for split {split!r} are in {split_dir}")
    return split_dir


def _log_failure(split: str, exc: Exception) -> None:
    """Print and log a descriptive failure message."""
    msg = (
        f"\n=== VCC download FAILED: split={split!r} ===\n"
        f"Error: {type(exc).__name__}: {exc}\n"
        "\nTo complete the download manually:\n"
        "  1. Run: gcloud auth login\n"
        "  2. Run: gcloud auth application-default login\n"
        "  3. Run: gcloud config set project <YOUR_SUBSCRIBED_PROJECT_ID>\n"
        "  4. Subscribe at:\n"
        "     https://console.cloud.google.com/marketplace/product/bigquery-public-data/arc-institute\n"
        "  5. Re-run:\n"
        "     uv run python -c \"\n"
        "     from benchmark.download_vcc import download_vcc_split\n"
        "     download_vcc_split('validation', billing_project='<YOUR_PROJECT_ID>')\n"
        "     \"\n"
        "\nSee benchmark/download_vcc.py module docstring for full setup steps.\n"
    )
    print(msg)
    logger.error("VCC download failed for split=%r: %s: %s", split, type(exc).__name__, exc)

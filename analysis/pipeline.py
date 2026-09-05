"""Single coarse-grained Phase 2 entrypoint (ANLYS-01/02/03/04).

Wires analysis/preprocess.py -> analysis/cluster.py -> (optional)
analysis/diffexp.py into one call, on top of Phase 1's DatasetStore: load a
named/versioned dataset, run the analysis, verify the raw-counts contract
survived, save the result as a new store version, and return a bounded
summary. Mirrors `ingest/pipeline.py::ingest_10x`.

Per 02-RESEARCH.md Pitfall 6, the Phase 1 counts-layer write-lock does NOT
survive a `write_h5ad`/`read_h5ad` round-trip -- only the checksum
comparison in `ingest.contract.verify_counts_integrity()` remains as a
detection mechanism once a dataset is store-loaded. This is the load-bearing
call site for that check: it must run both immediately after `store.load()`
and immediately before `store.save()`.

Per Open Question 1, `AnalysisConfig` (logged into `adata.uns['analysis']`)
mirrors the `QCConfig`/`adata.uns['qc']` pattern Phase 1 established for
QC-02.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path

from ingest import contract
from ingest.store import DatasetStore

from analysis.cluster import cluster
from analysis.diffexp import differential_expression
from analysis.preprocess import preprocess


@dataclass
class AnalysisConfig:
    """Explicit, overridable analysis parameters -- never hard-coded.
    Logged verbatim (via `asdict`) into `adata.uns['analysis']`.
    """

    target_sum: float | None = None
    n_top_genes: int = 2000
    n_pcs: int = 50
    resolution: float = 1.0
    n_neighbors: int = 15
    random_state: int = 0
    run_de: bool = False
    de_groupby: str | None = None
    de_group1: str | None = None
    de_group2: str | None = None
    de_n_genes: int = 25


def analyze(
    name: str,
    version: int | None = None,
    config: AnalysisConfig | None = None,
    store_root: str | Path = "data",
) -> tuple[str, dict]:
    """Loads `name`/`version` from the `DatasetStore` at `store_root`, runs
    preprocess -> cluster -> (optional) differential_expression, verifies
    the raw-counts contract survived both immediately after load and
    immediately before save, saves the result as a new store version, and
    returns `(new_dataset_id, summary_dict)`.

    `summary_dict` is `{"preprocess": dict, "cluster": dict, "de": dict |
    None}` -- each a bounded `dataclasses.asdict` of the respective
    Phase 2 summary dataclass, with `dataset_id` patched to the new
    version's id. Never a raw matrix or per-cell array.

    Raises `KeyError` if `name`/`version` isn't found in the store
    (propagated from `DatasetStore.load`, not swallowed). Raises
    `RuntimeError` if the raw-counts contract fails integrity verification
    at either checkpoint. Raises `ValueError` if `config.run_de` is set but
    `de_groupby`/`de_group1` aren't both provided.
    """
    config = config or AnalysisConfig()
    store = DatasetStore(root=store_root)
    adata = store.load(name, version)

    loaded_id = f"{name}@{version if version is not None else '(latest)'}"
    if not contract.verify_counts_integrity(adata):
        raise RuntimeError(
            f"Raw-counts integrity check failed immediately after loading "
            f"{loaded_id!r} from the store -- layers['counts'] does not "
            f"match its load-time checksum."
        )

    adata, preprocess_summary = preprocess(
        adata,
        target_sum=config.target_sum,
        n_top_genes=config.n_top_genes,
        n_pcs=config.n_pcs,
        random_state=config.random_state,
    )
    adata, cluster_summary = cluster(
        adata,
        resolution=config.resolution,
        n_neighbors=config.n_neighbors,
        random_state=config.random_state,
    )

    de_summary = None
    if config.run_de:
        missing = [
            field_name
            for field_name, value in (
                ("de_groupby", config.de_groupby),
                ("de_group1", config.de_group1),
            )
            if value is None
        ]
        if missing:
            raise ValueError(
                f"config.run_de is True but required field(s) "
                f"{missing} are unset -- analyze() never guesses an "
                f"implicit DE comparison."
            )
        adata, de_summary = differential_expression(
            adata,
            groupby=config.de_groupby,
            group1=config.de_group1,
            group2=config.de_group2,
            n_genes=config.de_n_genes,
        )

    adata.uns["analysis"] = asdict(config)

    if not contract.verify_counts_integrity(adata):
        raise RuntimeError(
            f"Raw-counts integrity check failed immediately before saving "
            f"{name!r} back to the store -- the analysis pipeline itself "
            f"corrupted layers['counts']."
        )

    new_version = store.save(name, adata)
    new_id = f"{name}@{new_version}"

    preprocess_summary = replace(preprocess_summary, dataset_id=new_id)
    cluster_summary = replace(cluster_summary, dataset_id=new_id)
    if de_summary is not None:
        de_summary = replace(de_summary, dataset_id=new_id)

    summary = {
        "preprocess": asdict(preprocess_summary),
        "cluster": asdict(cluster_summary),
        "de": asdict(de_summary) if de_summary is not None else None,
    }

    return new_id, summary

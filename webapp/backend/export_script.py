"""EXPORT-02: Pure script renderer for reproducible scanpy analysis scripts.

generate_analysis_script() reads stored parameters from adata.uns['qc'] and
adata.uns['analysis'], plus the dataset provenance string (source_path), and
renders a self-contained .py script that faithfully reproduces the pipeline.

No bioclaw imports appear in generated scripts — they are fully self-contained.
"""

from __future__ import annotations

from datetime import datetime, timezone

from anndata import AnnData


def generate_analysis_script(
    adata: AnnData,
    source_path: str | None,
    dataset_id: str,
) -> str:
    """Render a reproducible scanpy script for the given dataset.

    Reads adata.uns['qc']['config'] for QC thresholds and adata.uns['analysis']
    for analysis parameters.  Branches on source_path to emit either a
    cellxgene-census fetch block or a sc.read_h5ad() call.

    Returns a str that is a complete, runnable Python script.  Never raises on
    a dataset that has no analysis block — instead emits a comment.
    """
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ── Determine source type ─────────────────────────────────────────────────
    is_census = bool(source_path and source_path.startswith("cellxgene-census:"))

    # ── Parse census provenance string if needed ──────────────────────────────
    census_version = ""
    organism = ""
    obs_value_filter = ""
    if is_census and source_path:
        # Format: "cellxgene-census:{census_version}:{organism}:{obs_value_filter}"
        parts = source_path.split(":", 3)
        # parts[0] = "cellxgene-census"
        census_version = parts[1] if len(parts) > 1 else "stable"
        organism = parts[2] if len(parts) > 2 else ""
        obs_value_filter = parts[3] if len(parts) > 3 else ""

    # ── Read QC config ────────────────────────────────────────────────────────
    qc_uns = adata.uns.get("qc") or {}
    qc_cfg = qc_uns.get("config") or {}
    min_genes_per_cell = qc_cfg.get("min_genes_per_cell", 200)
    min_cells_per_gene = qc_cfg.get("min_cells_per_gene", 3)
    max_pct_mt = qc_cfg.get("max_pct_mt", 20.0)
    doublet_action = qc_cfg.get("doublet_action", "flag")

    # ── Read analysis config ──────────────────────────────────────────────────
    an = adata.uns.get("analysis")

    # ── Build script sections ─────────────────────────────────────────────────
    lines: list[str] = []

    # 1. Comment header
    lines += [
        f"# BioClaw reproducible analysis script",
        f"# Dataset:   {dataset_id}",
        f"# Generated: {ts}",
        f"#",
        f"# This script reproduces the QC thresholds, analysis parameters, and",
        f"# random seed used in the BioClaw session for this dataset.",
        f"# It is self-contained — no bioclaw modules are required.",
        "",
    ]

    # 2. Imports
    lines.append("import scanpy as sc")
    if is_census:
        lines.append("import cellxgene_census")
    lines.append("")

    # 3. Fetch / load block
    if is_census:
        lines += [
            f'with cellxgene_census.open_soma(census_version="{census_version}") as census:',
            f'    adata = cellxgene_census.get_anndata(',
            f'        census=census,',
            f'        organism="{organism}",',
            f'        obs_value_filter="{obs_value_filter}",',
            f'    )',
        ]
    else:
        safe_path = source_path or ""
        lines.append(f'adata = sc.read_h5ad("{safe_path}")')
    lines.append("")

    # 4. QC block
    lines += [
        "# ── QC filtering ─────────────────────────────────────────────────────────────",
        f"sc.pp.filter_cells(adata, min_genes={min_genes_per_cell})",
        f"sc.pp.filter_genes(adata, min_cells={min_cells_per_gene})",
    ]

    if max_pct_mt is not None:
        lines += [
            "",
            "# Mitochondrial filtering",
            "adata.var['mt'] = adata.var_names.str.upper().str.startswith('MT-')",
            "sc.pp.calculate_qc_metrics(adata, qc_vars=['mt'], percent_top=None, log1p=False, inplace=True)",
            f"adata = adata[adata.obs['pct_counts_mt'] <= {max_pct_mt}].copy()",
        ]

    if doublet_action in ("flag", "filter"):
        lines += [
            "",
            "# Doublet detection (Scrublet)",
            "sc.pp.scrublet(adata)",
        ]
        if doublet_action == "filter":
            lines.append("adata = adata[~adata.obs['predicted_doublet']].copy()")

    lines.append("")

    # 5. Analysis block
    lines.append(
        "# ── Analysis ─────────────────────────────────────────────────────────────────"
    )
    if an is None:
        lines += [
            "# No analysis was run in this session — add your analysis steps here.",
        ]
    else:
        target_sum = an.get("target_sum")
        n_top_genes = an.get("n_top_genes", 2000)
        n_pcs = an.get("n_pcs", 50)
        resolution = an.get("resolution", 1.0)
        n_neighbors = an.get("n_neighbors", 15)
        random_state = an.get("random_state", 0)

        target_sum_arg = f"target_sum={target_sum}" if target_sum is not None else "target_sum=None"

        lines += [
            f"sc.pp.normalize_total(adata, {target_sum_arg})",
            "sc.pp.log1p(adata)",
            f"sc.pp.highly_variable_genes(adata, n_top_genes={n_top_genes})",
            "adata = adata[:, adata.var.highly_variable].copy()",
            f"sc.pp.pca(adata, n_comps={n_pcs}, random_state={random_state})",
            f"sc.pp.neighbors(adata, n_neighbors={n_neighbors}, random_state={random_state})",
            f'sc.tl.leiden(adata, resolution={resolution}, flavor="igraph", n_iterations=2, directed=False, random_state={random_state})',
            f"sc.tl.umap(adata, random_state={random_state})",
        ]

    lines.append("")
    return "\n".join(lines)

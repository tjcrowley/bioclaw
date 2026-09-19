# Milestone context: Declarative domain panels (self-extension tier 1)

Intake for `/gsd:new-milestone`. Written 2026-09-18. Scope deliberately
limited to **tier 1 only** of the self-extension spectrum recorded in
README.md — no code generation, no repository credential, no agent-authored
pull requests.

## What the user asked for

A researcher who wants a domain-specific pipeline (the stated examples were
**cardiac** and **cancer**) should be able to describe what they need and get
it, without hand-writing a new tool and without waiting on a repo change.

## Why tier 1 and not tier 3

The originating request imagined BioClaw orchestrating a coding model to clone
the repo, build a new pipeline, and open PRs. That is tier 3 and is out of
scope here. The reason is not risk-aversion but sequencing: **most of the
cardiac/cancer demand is domain knowledge, not new algorithms.** A cardiac
subtype panel is a set of marker genes; a tumor/normal split is a marker set
plus a grouping. Both compose Phase 1–2 primitives that already exist. Tier 1
delivers that as *data*, and is also the artifact tier 3 would be generating —
so it has to exist first regardless.

Tier 3 remains recorded in README.md as unscheduled, with its boundaries
(PRs-only, fork-scoped credential, CI gate, sandboxed build, PR provenance,
and the conflict with the Phase 16 appliance threat model) already written
down for whenever it is picked up.

## Grounding: the seam already exists

This milestone is mostly plumbing, not new science. `annotation/baseline.py`'s
`baseline_annotate()` already takes the exact input a user panel is:

```python
def baseline_annotate(
    adata, groupby="leiden",
    markers: pd.DataFrame | None = None,      # <- decoupler-shaped source/target long format
    resource_name: str = "PanglaoDB",
)
```

When `markers` is supplied, no network call is made and `dc.op.resource()` is
bypassed entirely. A custom panel is a `source`/`target` DataFrame. The
function-level seam is done; everything around it is missing.

## What is actually missing

1. **Persistence.** Panels are user-created, so they must live under `/app/state`
   to survive `docker compose down` (Phase 14: only the `bioclaw-state` volume
   persists). Nothing in the repo currently writes user content there besides
   the dataset store, memory DB, and tool log.
2. **A panel format and validator.** See silent-failure traps below — this is
   the bulk of the real work.
3. **An agent surface.** The agent cannot use a panel it does not know exists:
   some combination of a list/describe tool and an annotate-with-panel path.
4. **Provenance plumbing** so ANNOT-03 metadata stays truthful (see defect below).

## Known defects and traps this milestone must handle

Found by reading `annotation/baseline.py` against this use case. All four are
latent today because only unit tests pass `markers` directly.

1. **`reference_dataset` is mislabeled when a custom panel is used.** The field
   is built as `f"decoupler ORA vs {resource_name} ..."`, and `resource_name`
   still defaults to `"PanglaoDB"` even when `markers` is supplied and
   PanglaoDB was never fetched. A cardiac-panel result would be reported as
   "decoupler ORA vs PanglaoDB". This is an ANNOT-03 provenance violation and
   should be fixed as part of this milestone, not worked around.
2. **Small panels vanish silently.** `dc.mt.ora` drops sources with fewer than
   `tmin` targets (decoupler's default is 5). A 3-gene cardiomyocyte subtype
   panel produces no error and no result — it is simply absent from the output.
   Panel validation must reject or loudly warn below the threshold.
3. **Small panels are diluted on large datasets.** `n_up` is 10% of `n_vars`,
   so only the top decile of the pseudobulk profile counts as "observed". Panel
   genes outside it never score. Needs documenting at minimum; possibly a
   panel-size-aware `n_up`.
4. **Unresolved gene symbols disappear.** Panel genes absent from
   `adata.var_names` contribute nothing, with no diagnostic. Given this
   project's history with silent data failures (the `gene_dictionaries_30m`
   pickle, the synthetic `GENE003` symbols), symbol resolution must be
   reported — "matched 34/40 panel genes" — not inferred from a bad score.

## Decisions needed during requirements

- **Ontology terms.** `ontology_term_id` is `None` on every baseline call, and
  `annotation/summary.py` documents that as permanent and intentional. Should a
  user panel be allowed to declare Cell Ontology terms, or does it inherit the
  documented `None`? ANNOT-03 pushes toward allowing it; consistency with the
  existing baseline contract pushes the other way.
- **Statistical baseline rule.** If a panel becomes a *primary* annotation path
  rather than the baseline, what plays the baseline role for it? A panel
  annotation cannot be its own comparison.
- **Authoring surface.** File dropped into a state directory, an upload
  endpoint, or agent-assisted authoring from a conversation. The last is
  closest to the original ask and should be evaluated, noting it generates
  *data*, not code, and so stays inside tier 1.
- **Scope of "panel".** Marker sets only, or also saved grouping/QC parameter
  presets? Marker sets alone are the defensible minimum.

## Explicitly out of scope

- Any code generation, `git` operation, or repository credential
- New foundation models or new worker interpreters
- Anything requiring changes to the three-interpreter Docker layout

## Version collision to resolve

`ROADMAP.md` already assigns **v1.3** to Edge Appliance (Phases 15–16,
roadmap-only, unplanned). This milestone is smaller and has a nearer-term
payoff, so it is probably v1.3 with Edge Appliance renumbered to v1.4 — but
that is a user decision at workflow step 3, not an assumption to bake in.

## Precondition

**Do not start this milestone until Phase 14 closes.** `/gsd:new-milestone`
step 5 overwrites STATE.md's `## Current Position`, which currently holds the
in-flight 14-05 position and its pending blocking human-verify gate.

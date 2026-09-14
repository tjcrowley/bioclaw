# bioclaw Web UI

A local-only chat front end for the bioclaw agent: a FastAPI backend and a
vanilla-JS frontend, both living in this directory, with no import or
runtime dependency on the sibling OpenClaw project (enforced by the
automated `tests/test_webapp_packaging.py::test_webapp_has_no_openclaw_dependency`
regression test).

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) installed.
- An `ANTHROPIC_API_KEY` (the agent calls Claude).
- A `BIOCLAW_WEB_PASSWORD` value of your choosing (any non-empty string —
  this is a single shared-password gate for local use, not a per-user
  account system).

## Setup (one-time, from a clean checkout)

```bash
uv sync --extra web
```

## Run (every time)

```bash
BIOCLAW_WEB_PASSWORD=<your-chosen-password> \
ANTHROPIC_API_KEY=<your-anthropic-api-key> \
uv run --extra web uvicorn webapp.backend.main:app --port 8000
```

## Open the app

Open **http://localhost:8000/app** in a browser — NOT `http://localhost:8000/`.
The root path returns a bare 404 by design: `StaticFiles` is mounted at
`/app` specifically so it never shadows the `/api/*` or `/ws/*` routes.

## Hard constraint: single process only

Never add `--workers` or run this behind a multi-process supervisor.
`webapp/backend/streaming.py`'s tool-call event queues are a single-process,
in-memory registry. Running multiple workers silently breaks the live
activity view, since the WebSocket connection and the POST request that
feeds it can land on different processes with no shared queue between them.

## Generating a demo dataset for the upload flow

```bash
python scripts/make_sample_dataset.py
```

This writes a small synthetic 10x MEX-format dataset (`matrix.mtx.gz`,
`barcodes.tsv.gz`, `features.tsv.gz`) to `data/demo_10x/`, so you can
exercise the upload control without needing a private test file on hand.

## Scope note

This webapp is local-only. There is no deployment, Docker, systemd, or
hosting step in this repo, and none is required to verify the feature.

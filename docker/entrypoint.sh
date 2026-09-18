#!/bin/sh
# Fixed single-worker Uvicorn invocation. Deliberately ignores any arguments
# passed via `docker run`/compose `command:` overrides -- the in-memory
# streaming queue registry (webapp/backend/streaming.py) is single-process
# only; --workers must never change. See webapp/README.md's "Hard
# constraint: single process only" and 14-RESEARCH.md's Anti-Patterns.
set -e
exec /app/.venv/bin/uvicorn webapp.backend.main:app --host 0.0.0.0 --port 8000 --workers 1

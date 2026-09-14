# Clean-Checkout Dry Run Transcript (PKG-02, Plan 10-02 Task 1)

**Verdict: PASS**

Ran on: 2026-09-13 (local clock), macOS (darwin), from a genuinely fresh
`git worktree` at commit `ce35bc1` — no pre-existing `.venv/`, `data/`, or
`agent/logs/` reused from the warm dev checkout. Every step below is the
exact documented command from `webapp/README.md`; no undocumented steps
were required.

## 1. Create a fresh worktree

```
$ git worktree add /tmp/bioclaw-clean-check HEAD
Preparing worktree (detached HEAD ce35bc1)
HEAD is now at ce35bc1 docs(10-01): complete packaging local verification plan
```

## 2. Confirm the worktree is genuinely clean (before setup)

```
$ cd /tmp/bioclaw-clean-check && ls -la
total 1696
drwx------@  21 darren  wheel     672 Sep 13 18:18 .
drwxrwxrwt  219 root    wheel    7008 Sep 13 18:18 ..
-rw-------@   1 darren  wheel      85 Sep 13 18:18 .git
-rw-------@   1 darren  wheel     138 Sep 13 18:18 .gitignore
drwx------@   9 darren  wheel     288 Sep 13 18:18 .planning
-rw-------@   1 darren  wheel       5 Sep 13 18:18 .python-version
-rw-------@   1 darren  wheel    5755 Sep 13 18:18 CONCEPT.md
-rw-------@   1 darren  wheel    2904 Sep 13 18:18 README.md
drwx------@   8 darren  wheel     256 Sep 13 18:18 agent
drwx------@   8 darren  wheel     256 Sep 13 18:18 analysis
drwx------@   8 darren  wheel     256 Sep 13 18:18 annotation
drwx------@   6 darren  wheel     192 Sep 13 18:18 benchmark
drwx------@   4 darren  wheel     128 Sep 13 18:18 bio_fm_worker
drwx------@   8 darren  wheel     256 Sep 13 18:18 ingest
drwx------@   7 darren  wheel     224 Sep 13 18:18 perturbation
-rw-------@   1 darren  wheel     830 Sep 13 18:18 pyproject.toml
drwx------@   5 darren  wheel     160 Sep 13 18:18 qa
drwx------@   4 darren  wheel     128 Sep 13 18:18 scripts
drwx------@  36 darren  wheel    1152 Sep 13 18:18 tests
-rw-------@   1 darren  wheel  836376 Sep 13 18:18 uv.lock
drwx------@   6 darren  wheel     192 Sep 13 18:18 webapp

$ ls -la .venv
ls: .venv: No such file or directory

$ [ -d data ] && echo "data EXISTS (unexpected)" || echo "data absent (expected)"
data absent (expected)

$ ls -la agent/
total 72
drwx------@  8 darren  wheel    256 Sep 13 18:18 .
drwx------@ 21 darren  wheel    672 Sep 13 18:18 ..
-rw-------@  1 darren  wheel      0 Sep 13 18:18 __init__.py
-rw-------@  1 darren  wheel   2137 Sep 13 18:18 logging.py
-rw-------@  1 darren  wheel   4365 Sep 13 18:18 memory.py
-rw-------@  1 darren  wheel    621 Sep 13 18:18 server.py
-rw-------@  1 darren  wheel  10595 Sep 13 18:18 session.py
-rw-------@  1 darren  wheel   6654 Sep 13 18:18 tools.py
```

No `.venv/`, no `data/`, no `agent/logs/` — confirmed genuinely clean before
running any setup step.

## 3. Run the documented setup step: `uv sync --extra web`

```
$ uv sync --extra web
Using CPython 3.13.12 interpreter at: /opt/homebrew/opt/python@3.13/bin/python3.13
Creating virtual environment at: .venv
Resolved 171 packages in 1ms
Installed 166 packages in 560ms
 + adjusttext==1.4.0
 + agent-detector==2.0.0
 ... (166 packages total, including fastapi==0.141.1, uvicorn==0.52.4,
      claude-agent-sdk==0.2.152, scanpy==1.12.4, anndata==0.13.3.post0,
      cell-eval==0.8.2, cellxgene-census==1.18.0, decoupler==2.2.0, etc.)
```

Full output captured; command completed successfully with no errors, no
undocumented flags, no manual intervention.

## 4. Start the server in the background (test password, port 8001)

```
$ BIOCLAW_WEB_PASSWORD=cleancheck-test ANTHROPIC_API_KEY=dummy-not-needed-for-boot \
  uv run --extra web uvicorn webapp.backend.main:app --port 8001 &

INFO:     Started server process [62716]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8001 (Press CTRL+C to quit)
```

Note: `ANTHROPIC_API_KEY` was set to a dummy placeholder value (no real
Anthropic key was available in this execution environment). This is
sufficient for this task's scope — boot, static-file serving, and the
password-gate endpoints (`/app`, `/api/login`) never call the Anthropic
API. The backend does not validate `ANTHROPIC_API_KEY` at import or
startup time (confirmed via `grep -rn ANTHROPIC_API_KEY webapp/` — the
key is only referenced in documentation, not read by any webapp backend
module at boot). Server startup took roughly 40 seconds on this machine,
dominated by the first-time import of scanpy/anndata's dependency chain
(numba/llvmlite JIT warm-up) — this matches normal Python scientific-stack
cold-start behavior, not an application defect.

## 5. Verify the server boots and serves correctly

```
$ curl -s -o /dev/null -w '%{http_code}' http://localhost:8001/app
307

$ curl -s -D - -o /dev/null http://localhost:8001/app
HTTP/1.1 307 Temporary Redirect
location: http://localhost:8001/app/

$ curl -s -o /dev/null -w '%{http_code}' http://localhost:8001/app/
200

$ curl -s -X POST http://localhost:8001/api/login -H 'Content-Type: application/json' \
  -d '{"password":"wrong"}' -w '\nHTTP_STATUS:%{http_code}\n'
{"detail":"unauthorized"}
HTTP_STATUS:401

$ curl -s -X POST http://localhost:8001/api/login -H 'Content-Type: application/json' \
  -d '{"password":"cleancheck-test"}' -w '\nHTTP_STATUS:%{http_code}\n'
{"ok":true}
HTTP_STATUS:200
```

**Note on the `/app` result (deviation from the plan's literal expectation,
not a real bug):** the plan's Task 1 verify step expected a bare
`curl .../app` to return `200`; the actual result is `307 Temporary
Redirect` to `/app/`. This is standard Starlette/FastAPI `StaticFiles`
mount behavior — a request to the mount path without a trailing slash is
redirected to the canonical trailing-slash URL, which then serves `200`.
Confirmed this is not specific to the clean worktree: the same `307 ->
/app/` behavior was observed against the already-running warm dev
instance on port 8000. Any browser (and `curl -L`) follows the redirect
transparently and receives the real app shell with `200`. This does not
contradict PKG-02's "serves the app at http://localhost:8000/app" claim —
opening that URL in a browser works exactly as documented — so no fix to
`webapp/README.md` was needed; this is a curl-flag technicality in the
plan's own verify step, not a documentation gap or application defect.

All three substantive checks passed:
- `uv sync --extra web` succeeded from a clean checkout.
- Server boots and serves the app shell at `/app` (200 after following the
  standard StaticFiles redirect, exactly as a browser would experience it).
- Wrong password -> `401`; correct password -> `200` at `/api/login`.

## 6. Stop the background server

```
$ kill <uvicorn PID>
```

Confirmed via `ps`/`lsof -i :8001` that no process remained bound to port
8001 after the kill.

## 7. Clean up the worktree

```
$ cd /Users/darren/.openclaw/workspace/bioclaw
$ git worktree remove /tmp/bioclaw-clean-check --force
$ git worktree list
/Users/darren/.openclaw/workspace/bioclaw  ce35bc1 [main]
```

Worktree removed; no `/tmp/bioclaw-clean-check` residue.

## Summary

| Check | Expected | Actual | Result |
|---|---|---|---|
| Pre-setup state | no `.venv`/`data`/`agent/logs` | confirmed absent | PASS |
| `uv sync --extra web` | succeeds | succeeded, 166 packages installed | PASS |
| Server boot | starts, listens on :8001 | started, "Application startup complete" | PASS |
| `GET /app` | app shell served (200) | 307 -> `/app/` -> 200 (standard StaticFiles redirect; browser/`curl -L` both land on 200) | PASS (see note above) |
| `POST /api/login` wrong password | 401 | 401 | PASS |
| `POST /api/login` correct password | 200 | 200 | PASS |
| Undocumented steps required | none | none | PASS |

**Overall verdict: PASS.** The documented `webapp/README.md` command
sequence boots and serves the app from a genuinely clean checkout with no
undocumented steps. No changes to `webapp/README.md` were required.

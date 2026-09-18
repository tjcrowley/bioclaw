---
phase: 14-docker-compose-deployment
plan: 04
subsystem: docker
tags: [docker-compose, gpu-override, healthcheck, persistence, smoke-test, security]

# Dependency graph
requires:
  - phase: 14
    plan: 02
    provides: bioclaw image with baked-in ENTRYPOINT (--workers 1) and /app/state ENV paths
  - phase: 14
    plan: 01
    provides: unauthenticated GET /api/health probe
provides:
  - docker-compose.yml — single `backend` service, named volume, healthcheck, required-var guards
  - docker-compose.gpu.yml — pure override adding nvidia device reservation to the same service
  - scripts/docker_compose_smoke_test.sh — config assertions + build/up/health/down cycle
  - .env added to .gitignore
affects: [14-05-docs]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "GPU support as an `-f` override file on the same single service, never a second profile-gated service (avoids the port-8000 conflict in 14-RESEARCH.md's illustrated profiles:+extends pattern)"
    - "Compose required-variable syntax ${VAR:?msg} as a credential guard, since Compose silently converts an unset var to an empty string"
    - "Single named volume at /app/state covers all three state paths, because 14-02 relocated them under one prefix"

key-files:
  created:
    - docker-compose.yml
    - docker-compose.gpu.yml
    - scripts/docker_compose_smoke_test.sh
  modified:
    - .gitignore

key-decisions:
  - "SECURITY — deviated from the plan's literal `${ANTHROPIC_API_KEY}` / `${BIOCLAW_WEB_PASSWORD}` to the `:?` required-variable form. See the security note below; the plan's literal YAML would have shipped an auth bypass."
  - "Added .env to .gitignore before writing any .env — the plan creates a file whose documented purpose is holding a real ANTHROPIC_API_KEY, and the repo was not ignoring it."
  - "Smoke test uses POSIX [[:space:]] rather than the plan's \\s. \\s is a GNU extension; under a strict BSD grep it fails to match, which would silently turn the DOCK-01 criterion-2 assertion into a false pass."
  - "Added a second smoke-test assertion that the ${BIOCLAW_WEB_PASSWORD:?} guard is still present, so a future edit cannot quietly reintroduce the blank-password hole."
  - "Kept `env_file: .env` required (no `required: false`). Failing loudly on a missing .env is correct here — the alternative boots the stack with blank credentials."

requirements-completed: []

# Metrics
duration: ~20min
completed: 2026-09-18
---

# Phase 14 Plan 04: Compose stack, GPU override, smoke test

**`docker compose up` starts the backend from a clean checkout with only `.env` configured; GPU passthrough is an additive override on the same service; all mutable state lives in one named volume that survives `down`/`up`.**

## Security finding (deviation from plan)

The plan specified `environment: BIOCLAW_WEB_PASSWORD: ${BIOCLAW_WEB_PASSWORD}`. Compose converts an **unset** variable into an **empty string** rather than leaving it unset. `webapp/backend/auth.py::_valid` (line 16-19) rejects only `expected is None`:

```python
expected = os.environ.get("BIOCLAW_WEB_PASSWORD")
if expected is None or password is None:
    return False
return secrets.compare_digest(password, expected)
```

With `expected == ""`, `secrets.compare_digest("", "")` returns True — a request with `?password=` authenticates. Confirmed live. Because `.env.example` ships `BIOCLAW_WEB_PASSWORD=` blank and the documented flow is "copy to .env and fill in", anyone who copied it and forgot a value would have started a **wide-open instance**.

Fixed inside this plan's own artifact using `${VAR:?message}`, which makes Compose refuse to start when the variable is unset *or* empty. Verified both paths:

- No `.env` at all → `required variable ANTHROPIC_API_KEY is missing a value: set ANTHROPIC_API_KEY in .env (copy .env.example)`, exit 1
- `.env` copied verbatim from `.env.example` (blank values) → same refusal, exit 1

**The underlying `auth.py` weakness is NOT fixed** — `webapp/backend/auth.py` is not in this plan's `files_modified`. Compose can no longer trigger it, but a non-Docker run with `BIOCLAW_WEB_PASSWORD=""` exported still authenticates on an empty password. Logged in `deferred-items.md` for a follow-up plan; the real fix is `if not expected or password is None`.

## Verification

All run live against Docker Engine 29.3.1:

| Must-have truth | Result |
|---|---|
| `docker compose up` works with only `.env` | Smoke test passed end-to-end: build → up → `/api/health` → down |
| `--workers 1` not overridable via Compose | Resolved `docker compose config` contains no `command:`/`entrypoint:` |
| GPU overlay = same service, not a second one | `--services` returns exactly `backend` both base and merged; nvidia reservation merged into it |
| State persists across `down` && `up` | Marker file + `memory.sqlite` (20KB, mtime preserved) survived a full `down`/`up`; health 200 after restart |

Also confirmed the container's own healthcheck reaches `healthy` (~15s, within the 20s `start_period`) — the `python3 -c urllib.request` probe works in the slim image, which has no curl.

Fast pytest tier: 255 passed / 14 failed — unchanged baseline, all pre-existing VCC numba threadpool failures. This plan touches no Python.

## Notes for 14-05

- Docs must say **copy `.env.example` to `.env` and fill in both values** — the stack now refuses to start otherwise, by design. Document the error message so it reads as intended behavior, not a bug.
- GPU invocation: `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up`.
- The 14-03 FM image layers are not yet present; `docker compose build` currently builds the 14-02 base only.

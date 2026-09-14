# Phase 10: Packaging & Local Verification - Research

**Researched:** 2026-09-13
**Domain:** Python/uv monorepo packaging, FastAPI local process management, end-to-end manual verification methodology
**Confidence:** HIGH

## Summary

Phase 10 is not a "build new tech" phase — it is a **close-out and formalize** phase. Every piece of the v1.1 stack (backend API, WebSocket streaming, session endpoints, upload/ingest, and the full frontend) already exists, already lives inside `webapp/`, and has already been started and manually exercised by Darren multiple times across Phases 7, 8, and 9 using the exact same command:

```bash
BIOCLAW_WEB_PASSWORD=<your-password> uv run --extra web uvicorn webapp.backend.main:app --port 8000
```

with `ANTHROPIC_API_KEY` set in the environment and the browser pointed at `http://localhost:8000/app` (not `/`). This command is proven — it has been the actual vehicle for three separate `live_llm` human-verify checkpoints already. Phase 10's real work is: (1) **document** this command and its prerequisites somewhere a fresh reader would find them (currently nowhere outside `.planning/` plan files — `README.md` doesn't mention the webapp at all), (2) **harden the PKG-01 self-containment claim** from a one-time manual `grep` (done during Phase 9's verification) into a durable, automated regression test, (3) **prove the "clean checkout" claim literally** (not just "it worked on my already-warmed .venv"), and (4) run one **combined** end-to-end manual walkthrough that exercises all six v1.1 capabilities together in a single session (previous checkpoints tested subsets in isolation, phase by phase).

**Primary recommendation:** Do not introduce any new packaging mechanism (no separate `webapp/pyproject.toml`, no separate venv, no Docker). Keep the existing root-`pyproject.toml` + `web` optional-dependency-group pattern (already justified and precedented in 07-RESEARCH.md), write it up as the single documented command in `README.md`, add one automated "no OpenClaw import" test, and spend the phase's real effort on the clean-checkout dry run plus the combined manual checkpoint.

## User Constraints

No `CONTEXT.md` exists for this phase (not yet run through `/gsd:discuss-phase`). No locked decisions or discretion areas to carry forward — proceed on ROADMAP.md/REQUIREMENTS.md scope as written.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| PKG-01 | Webapp ships self-contained inside `bioclaw` repo in its own directory, own dependencies, no OpenClaw runtime/code dependency | Already substantially true today (`webapp/backend/` + `webapp/frontend/`, `fastapi[standard]` isolated as an opt-in `web` extra in root `pyproject.toml`, zero `openclaw` imports — manually confirmed in 09-VERIFICATION.md). Research finds the concrete gap: this fact is currently proven by a one-off manual `grep`, not an automated test — see Don't Hand-Roll and Pitfall 1. |
| PKG-02 | Single documented command runs the full webapp locally from a clean checkout with no undocumented setup | The exact command already exists and has been used 3+ times (`BIOCLAW_WEB_PASSWORD=... uv run --extra web uvicorn webapp.backend.main:app --port 8000`) but is documented only inside `.planning/phases/07..09/*.md`, never in `README.md`. Research finds the concrete gaps: (a) no root-level docs at all, (b) `/app` mount path (not `/`) is an easy silent-404 trap for a first-time reader, (c) "clean checkout" has never actually been tested against a directory that lacks the already-populated `.venv`/`agent/logs`/`data/` state of the dev machine — see Pitfalls 2-4 and Code Examples. |
</phase_requirements>

## Standard Stack

No new libraries are needed for this phase. The relevant tooling is already installed and pinned:

### Core
| Tool | Version (confirmed installed) | Purpose | Why Standard |
|------|-------------------------------|---------|---------------|
| `uv` | 0.11.4 | Python env/dependency manager for the whole repo | Already the project's only dependency manager (uv.lock, `uv sync`/`uv run` used throughout Phases 1-9) |
| `fastapi[standard]` | >=0.141.1 (root `pyproject.toml` `web` optional group) | Backend framework + bundles `uvicorn[standard]`, `websockets`, `httpx`, `python-multipart` | Already installed and working; verified via `.venv/bin/uvicorn --version` -> `uvicorn 0.52.4` |
| `uvicorn` | 0.52.4 (bundled via `fastapi[standard]`) | ASGI server that actually runs `webapp.backend.main:app` | Official FastAPI-recommended server; single-worker mode is a hard existing constraint (see Pitfall 3) |

### Supporting
| Tool | Purpose | When to Use |
|------|---------|-------------|
| `git worktree` or `git clone --local` | Simulate a genuinely clean checkout for PKG-02 verification | Use for the phase's "clean checkout" success-criterion check — do not just re-run in the already-warm dev directory |
| `pytest` (existing `tests/`) | Automated regression coverage | Extend, don't replace — add one new "no OpenClaw import" test into the existing `tests/test_webapp_frontend.py` or `tests/test_webapp_backend.py` module |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Root `pyproject.toml` `web` optional-dependency group (current) | Separate `webapp/pyproject.toml` + fully isolated venv, mirroring `bio_fm_worker/`'s pattern | `bio_fm_worker/`'s isolation exists **only** because `scgpt` pins conflicting/ancient transitive deps (`torch`, `scvi-tools<1.0`, `torchtext`) that must never touch the tested main stack. `fastapi`/`uvicorn` have zero such conflict (already verified in 07-RESEARCH.md: no pin conflicts, confirmed by successful `uv sync --extra web` three phases running). A separate venv here would also need to re-install the *entire* base stack anyway (scanpy, anndata, claude-agent-sdk, decoupler, cell-eval, etc.) since `webapp/backend/main.py` imports `agent.tools`, `ingest.pipeline`, and `qa.session` directly — there is no dependency subset to actually isolate. **Recommendation: do not build this.** It adds packaging complexity with zero corresponding benefit and actively risks violating "no runtime dependency on the OpenClaw codebase" in the other direction by duplicating environment state that then drifts. |
| Manual `grep` verification of "no OpenClaw import" (current, one-off, done in 09-VERIFICATION.md) | An automated pytest test in the fast-tier suite | A one-time manual check during a prior phase's checkpoint is not durable — nothing prevents a future edit from reintroducing an `openclaw` import and it going unnoticed. Promote it to a real test (see Don't Hand-Roll). |
| Docker/docker-compose for "single command" | Plain `uv run uvicorn ...` | Explicitly out of scope — REQUIREMENTS.md's Out of Scope table and the phase's hard constraint rule out any deployment tooling; Docker would also be new infrastructure this phase doesn't need since the existing single-process `uv run` command already satisfies "single documented command" without adding a new tool to learn/maintain. |

**Installation:** None required — everything is already installed. If verifying from a genuinely clean checkout, the one install step is:
```bash
uv sync --extra web
```

## Architecture Patterns

### Recommended Project Structure (already in place — verify, don't restructure)
```
bioclaw/
├── pyproject.toml          # base deps + [project.optional-dependencies] web = [fastapi[standard]]
├── webapp/
│   ├── __init__.py
│   ├── backend/
│   │   ├── main.py         # FastAPI app: /api/ask, /api/sessions, /api/upload, /ws/{id}, /api/login, StaticFiles mount at /app
│   │   ├── auth.py         # shared-password check (API-05)
│   │   ├── deps.py         # Depends()-injectable factories -> qa.session.ask_question, agent.memory.SessionMemory
│   │   ├── schemas.py       # pydantic request/response models
│   │   ├── streaming.py     # in-process asyncio.Queue registry keyed by stream_id
│   │   └── uploads.py       # multipart staging -> ingest_10x
│   └── frontend/
│       ├── index.html, style.css, main.js, api.js, chat.js, citations.js, sessions.js
├── agent/, qa/, ingest/, analysis/, annotation/, perturbation/   # core bioclaw packages -- webapp imports these directly (this is intentional and correct; it is NOT the "OpenClaw" dependency PKG-01 forbids)
└── bio_fm_worker/            # fully separate .venv (Python 3.9) -- NOT needed for Phase 10's manual walkthrough
```

**Critical clarification for the planner:** PKG-01's phrase "no runtime or code dependency on the OpenClaw codebase" refers to the **separate sibling project** at `~/.openclaw/workspace` (the actual OpenClaw agent product this project is modeled after), **not** to bioclaw's own `agent/`, `qa/`, `ingest/` packages. The webapp is *supposed* to import `qa.session.ask_question`, `agent.tools`, `agent.memory.SessionMemory`, and `ingest.pipeline.ingest_10x` directly — that's the whole point of API-01 through API-04. Do not interpret PKG-01 as requiring the webapp to vendor or duplicate those modules into `webapp/`. Phase 9's own verification already confirmed this reading (`09-VERIFICATION.md` line 28: "grep across webapp/ for any import of an openclaw package/path returned nothing").

### Pattern 1: uv optional-dependency group as the isolation boundary
**What:** Webapp-only dependencies (`fastapi[standard]`) live in `[project.optional-dependencies] web` in the root `pyproject.toml`, not the base `dependencies` list. Base installs (`uv sync` with no flags) never pull in fastapi/uvicorn; only `uv sync --extra web` or `uv run --extra web ...` does.
**When to use:** Whenever a sub-feature's dependencies don't conflict with the base stack — this is the correct uv-idiomatic pattern for "this directory has its own dependencies" in a single-package monorepo, as opposed to spinning up a second venv.
**Example:**
```toml
# Source: pyproject.toml (already in repo, verified working across Phases 7-9)
[project.optional-dependencies]
web = [
    "fastapi[standard]>=0.141.1",
]
```

### Pattern 2: Single-worker uvicorn constraint (must be preserved and documented)
**What:** `webapp/backend/streaming.py`'s tool-call event queues are a plain in-process `dict` keyed by `stream_id`. This only works correctly with exactly one Python process.
**When to use:** Always, for this app, until the queue registry is redesigned (out of scope — no such redesign is needed for local-only verification).
**Example:**
```bash
# Source: webapp/backend/streaming.py module docstring + 07-03-PLAN.md (verified 3x live)
uv run --extra web uvicorn webapp.backend.main:app --port 8000
# NEVER: uvicorn ... --workers 2   (silently breaks WS<->POST event correlation across processes)
```

### Pattern 3: StaticFiles mounted at a subpath, not root
**What:** `app.mount("/app", StaticFiles(directory=..., html=True), name="frontend")` is the **last** route registered in `main.py`, deliberately after all `/api/*` and `/ws/*` routes, so it never shadows them.
**When to use:** This is already correct and should not change. The only gap is that visiting `http://localhost:8000/` (root) returns a bare FastAPI 404, not the app — a natural first mistake for anyone following documentation loosely.
**Example (optional polish, not required):**
```python
# Source: FastAPI official docs pattern (https://fastapi.tiangolo.com/tutorial/static-files/)
from fastapi.responses import RedirectResponse

@app.get("/")
async def root_redirect():
    return RedirectResponse(url="/app")
```
This is a nice-to-have, not a requirement — PKG-02 only requires the command + documented URL to work, and `http://localhost:8000/app` already does. If added, it must not conflict with the `/app` StaticFiles mount registration order.

### Anti-Patterns to Avoid
- **Building a second venv/pyproject.toml for the webapp "just to be safe" about PKG-01:** No dependency conflict exists to justify it (unlike `bio_fm_worker/`). It would only add drift risk and packaging complexity the requirement doesn't ask for.
- **Treating `bio_fm_worker/`'s scGPT environment as a Phase 10 prerequisite:** None of Phase 10's four success criteria require cell-type annotation or perturbation prediction. Scope the manual verification's chosen research question to ingest + analyze + Q&A (e.g., "ingest this dataset and tell me how many clusters it has") so the walkthrough doesn't accidentally require the separate, fragile, Python-3.9 scGPT venv to be present and working.
- **Re-running verification only in the already-warm dev checkout:** `.venv/`, `agent/logs/`, `agent/memory.sqlite`, `data/`, and `bio_fm_worker/.venv/` are all gitignored and already exist locally. Success criterion 2 ("from a clean checkout") is not actually tested by running the command again in the same directory — see Code Examples for a real clean-checkout test method.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Verifying "no OpenClaw import" stays true forever | A one-off manual `grep` at checkpoint time (what Phase 9 did) | A permanent pytest test (e.g. `test_webapp_has_no_openclaw_dependency`) that walks `webapp/**/*.py` and `webapp/**/*.js`, asserting no line matches `openclaw` (case-insensitive) or an absolute path containing `.openclaw/workspace` outside this repo | Manual checks don't run in CI/on every future edit; a static-analysis test does, and it's a ~10-line test that's trivial to write given the existing `tests/test_webapp_frontend.py` conventions (file-content assertions are already the established pattern there) |
| Confirming "single command, no undocumented steps" | An informal claim in a SUMMARY.md (what Phases 7-9 effectively did) | An actual clean-checkout dry run (`git worktree add` or `git clone --local`) executed as a documented phase task, with its exact transcript captured in the phase's verification artifact | "It worked when I ran it" in an already-configured dev machine does not prove a fresh clone works; the whole point of PKG-02's "clean checkout" phrase is to catch exactly the kind of hidden local state (stray env vars, pre-existing `data/` or `agent/logs/` directories, an already-`uv sync`'d `.venv`) that a warm-directory re-run cannot catch |
| A packaging/deployment framework | Docker, docker-compose, Procfile, systemd unit | Nothing — plain `uv run --extra web uvicorn ...` already satisfies "single documented command," and any deployment-shaped tooling is explicitly out of scope per the phase's hard constraint | Introducing deployment machinery this phase explicitly forbids researching would violate the standing hard constraint even if well-intentioned |

**Key insight:** This phase's biggest risk is *scope creep toward deployment-adjacent tooling* (Docker, process managers, `.env` file loaders, etc.) that would feel natural for "packaging" but is explicitly out of scope. The correct scope is narrow: documentation + one regression test + one clean-checkout dry run + one combined manual checkpoint.

## Common Pitfalls

### Pitfall 1: PKG-01's "no OpenClaw dependency" claim currently rests on a one-time manual grep
**What goes wrong:** A future code change (e.g., someone imports a helper from `~/.openclaw/workspace` during a later maintenance pass) would silently violate PKG-01 with no automated signal.
**Why it happens:** The only verification so far is a manual `grep` recorded in `09-VERIFICATION.md`, not a repeatable test.
**How to avoid:** Add a fast-tier pytest test that asserts this statically (see Don't Hand-Roll table). Cheap, fast, and closes the gap permanently.
**Warning signs:** None currently, but this is the kind of check that only ever fails silently until someone happens to notice — precisely why it needs to be automated.

### Pitfall 2: The app lives at `/app`, not `/` — first-time documentation readers will hit a 404
**What goes wrong:** Someone follows "run the command, open your browser" instructions, goes to `http://localhost:8000/`, sees FastAPI's default 404 JSON, and concludes the webapp is broken.
**Why it happens:** `StaticFiles` is mounted at `/app` (correct, so it doesn't shadow `/api/*`/`/ws/*`), but nothing currently redirects `/` there.
**How to avoid:** Document the exact URL (`http://localhost:8000/app`) explicitly and prominently in whatever run instructions this phase writes. Optionally (not required) add a `GET /` -> `RedirectResponse("/app")` route as a documentation-proofing nicety.
**Warning signs:** Any verification script/checklist that says "open http://localhost:8000" without the `/app` suffix.

### Pitfall 3: `--workers` or any multi-process supervisor breaks the WebSocket<->POST correlation
**What goes wrong:** Running `uvicorn webapp.backend.main:app --workers 2` (or behind a forking process manager) puts the WS connection and its correlated `/api/ask` POST on two different OS processes with two different `asyncio` event loops. `streaming.py`'s `_QUEUES` dict is per-process, so the WS side's queue lookup returns nothing or the wrong queue — tool-call events silently vanish.
**Why it happens:** In-process, in-memory queue registry (documented as a deliberate, accepted tradeoff in `streaming.py`'s own module docstring) — appropriate for a local-only single-user tool, not multi-worker production.
**How to avoid:** The single documented command must never include `--workers`. State this explicitly (not just implicitly) in whatever documentation this phase writes, since it's exactly the kind of flag someone adds "for performance" without realizing it breaks a core feature (API-02 live streaming).
**Warning signs:** Live tool-call activity view (UI-02) silently stops updating for some requests but not others.

### Pitfall 4: "Clean checkout" is currently unverified — hidden local state could be masking a real gap
**What goes wrong:** The dev machine already has `.venv/` synced, `agent/logs/`, `data/`, `agent/memory.sqlite`, and `bio_fm_worker/.venv/` all present from prior phases. Re-running the documented command in that same directory proves nothing about a genuinely fresh clone — e.g., if `uv sync --extra web` were accidentally missing from the documented steps, the warm directory would still work fine (fastapi already installed) while a real fresh clone would fail immediately.
**Why it happens:** Every prior live-verification checkpoint (Phases 7, 8, 9) ran in the same long-lived working directory, never a fresh one.
**How to avoid:** Use `git worktree add /tmp/bioclaw-clean-check HEAD` (or `git clone --local . /tmp/bioclaw-clean-check`), `cd` into it, and run the full documented sequence from scratch: `uv sync --extra web` -> set env vars -> `uv run --extra web uvicorn ...` -> browser walkthrough. This is the only way to actually prove PKG-02's "from a clean checkout" clause.
**Warning signs:** Documentation that was never actually executed step-by-step in a directory that didn't already have `.venv`/`data`/`agent/logs` present.

### Pitfall 5: Manual verification question inadvertently requires the isolated scGPT environment
**What goes wrong:** If the chosen test question during the combined manual checkpoint asks something that causes the agent to call `annotate_cell_type_tool` (bio-FM cell-type annotation), the walkthrough now depends on `bio_fm_worker/.venv` (a separate, fragile, Python 3.9 environment with a documented history of `torch`/`torchtext` ABI breakage) being present and working — which is unrelated to and not required by any of Phase 10's four success criteria.
**Why it happens:** The agent decides which tools to call based on the natural-language question; a broad question like "tell me about this dataset" could trigger annotation or perturbation tools unpredictably.
**How to avoid:** Deliberately scope the manual-verification question(s) to only exercise ingest + analyze (e.g., "Ingest the dataset at `<path>` and tell me how many clusters it has" — this exact phrasing is already proven to work, taken verbatim from `tests/test_webapp_integration.py`'s live_llm test).
**Warning signs:** A checkpoint failing on an unrelated bio-FM dependency issue when the actual UI/packaging surface being verified has nothing to do with cell-type annotation.

## Code Examples

### The single documented command (already proven, use verbatim)
```bash
# Source: 07-03-PLAN.md, 08-03-PLAN.md, 09-05-PLAN.md (identical command used and
# live-verified in all three prior human-verify checkpoints)

# One-time setup (from a clean checkout):
uv sync --extra web

# Every run:
BIOCLAW_WEB_PASSWORD=<your-chosen-password> \
ANTHROPIC_API_KEY=<your-anthropic-api-key> \
uv run --extra web uvicorn webapp.backend.main:app --port 8000

# Then open a browser at:
#   http://localhost:8000/app
```

### Automated "no OpenClaw dependency" regression test (new, recommended for this phase)
```python
# Pattern source: tests/test_webapp_frontend.py's existing file-content-assertion
# style (e.g. test_css_design_tokens greps style.css for expected strings) --
# mirror that same pattern in the negative direction.
import pathlib

def test_webapp_has_no_openclaw_dependency():
    webapp_dir = pathlib.Path("webapp")
    offending = []
    for path in webapp_dir.rglob("*"):
        if path.suffix not in (".py", ".js", ".html", ".css"):
            continue
        text = path.read_text(errors="ignore").lower()
        if "openclaw" in text:
            offending.append(str(path))
    assert not offending, f"Found OpenClaw references in: {offending}"
```

### Clean-checkout dry run (the actual PKG-02 verification method)
```bash
# Source: standard git worktree usage, applied here as the phase's verification
# method for "from a clean checkout" (not previously done in Phases 7-9, which
# all ran in the same long-lived dev directory).
git worktree add /tmp/bioclaw-clean-check HEAD
cd /tmp/bioclaw-clean-check
uv sync --extra web
BIOCLAW_WEB_PASSWORD=testpass ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  uv run --extra web uvicorn webapp.backend.main:app --port 8000
# ... exercise in browser at http://localhost:8000/app ...
# cleanup afterward:
git worktree remove /tmp/bioclaw-clean-check
```

## State of the Art

Nothing has changed technology-wise for this phase — `fastapi[standard]` 0.141.x / `uvicorn` 0.52.4 are already installed and were the current stable versions as of Phase 7's research (Sep 2026). No version bumps, no deprecated-feature concerns, no new packaging tooling has emerged that would change the recommendation. This is a documentation-and-verification phase, not a technology-adoption phase.

## Open Questions

1. **Should `README.md` (root) or a new `webapp/README.md` be the canonical home for run instructions?**
   - What we know: `README.md` currently has zero mention of the webapp; all existing run-command documentation lives buried in `.planning/phases/*/**-PLAN.md` files, which are not meant to be end-user-facing.
   - What's unclear: Whether the planner should update root `README.md` (most discoverable, matches "single documented command" framing at the project's front door) vs. add a dedicated `webapp/README.md` (co-located with the code it documents, per the "self-contained in its own directory" spirit of PKG-01) vs. both (a one-line pointer in root README + full detail in `webapp/README.md`).
   - Recommendation: Do both — a short "Web UI" section in root `README.md` with the exact command block, linking to a more detailed `webapp/README.md` that also documents the `/app` path, the single-worker constraint, and the env-var prerequisites. This satisfies both discoverability and self-containment.

2. **Does the combined manual checkpoint need a fresh, purpose-written test dataset, or can it reuse an existing fixture path?**
   - What we know: Prior live_llm tests use `analyzable_mtx_dir` (a pytest fixture, not a standalone file), and Darren's own manual browser checkpoints in Phases 7-9 used real files he supplied himself (not documented in the repo).
   - What's unclear: Whether Phase 10 should ship a small, checked-in sample `.mtx`/`.h5` dataset specifically for manual verification/demo purposes, so "from a clean checkout" doesn't implicitly require Darren to already have a private test dataset on hand.
   - Recommendation: Check whether a small sample dataset already exists somewhere reusable (e.g. under `data/` or a fixtures directory) before assuming one needs to be created; if not, a tiny synthetic 10x-format fixture (mirroring `tests/`'s existing synthetic fixtures from Phase 1) checked into the repo would make the "clean checkout" verification fully self-contained with zero external file dependency.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x (installed as `dev` dependency group) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run --extra web pytest tests/test_webapp_frontend.py tests/test_webapp_backend.py -x -q` |
| Full suite command | `uv run --extra web pytest tests/ -x -q -m "not live_llm and not bio_fm_smoke and not vcc_data"` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|--------------------|--------------|
| PKG-01 | webapp has no OpenClaw import/runtime dependency | static-analysis unit | `pytest tests/test_webapp_frontend.py::test_webapp_has_no_openclaw_dependency -x` | ❌ Wave 0 — new test, see Code Examples |
| PKG-01 | webapp deps declared as isolated `web` optional group, base install unaffected | unit (already covered) | `pytest tests/test_webapp_backend.py -k dependencies -x` (or manual `pyproject.toml` inspection, already verified in 07-VERIFICATION.md) | ✅ (verified structurally in 07-VERIFICATION.md; no dedicated test needed — this is a static pyproject.toml fact, not runtime behavior) |
| PKG-02 | single command starts full app from clean checkout | manual / smoke | Clean-checkout dry run per Code Examples — not expressible as a <30s automated command since it requires a fresh `uv sync` and a real browser session | manual-only (justified: literally requires a fresh filesystem clone + human browser interaction) |
| PKG-02 | full v1.1 feature set works together end-to-end on that local run | manual (human-verify checkpoint) | N/A — browser walkthrough covering login, chat Q&A, streaming, citations, session resume, upload->ingest in one continuous session | manual-only (justified: this is explicitly a human-verify UI/UX confirmation per the phase's own success criteria wording, "confirms every v1.1 capability works together" — not mechanically testable as a single fast command; existing fast-tier tests already cover each capability's API/JS contract individually) |

### Sampling Rate
- **Per task commit:** `uv run --extra web pytest tests/test_webapp_frontend.py tests/test_webapp_backend.py -x -q`
- **Per wave merge:** `uv run --extra web pytest tests/ -x -q -m "not live_llm and not bio_fm_smoke and not vcc_data"` (must stay at 208+ passed, 0 failed, no regressions — this has been the standing bar since Phase 9)
- **Phase gate:** Full suite green, plus the clean-checkout dry run executed and its transcript captured, plus Darren's combined manual checkpoint approved, before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_webapp_frontend.py::test_webapp_has_no_openclaw_dependency` (or a new small module) — covers PKG-01's durability gap (currently only manually verified)
- [ ] No new fixtures needed — reuse `analyzable_mtx_dir` and existing `tests/conftest.py` fixtures already established since Phase 3

*(No framework install gaps — pytest, fastapi, uvicorn, and the `web` extra are all already installed and working.)*

## Sources

### Primary (HIGH confidence — direct codebase inspection, this repo)
- `/Users/darren/.openclaw/workspace/bioclaw/pyproject.toml` — dependency structure, `web` optional group
- `/Users/darren/.openclaw/workspace/bioclaw/webapp/backend/main.py`, `deps.py`, `auth.py` — actual route/mount/auth implementation
- `/Users/darren/.openclaw/workspace/bioclaw/webapp/frontend/index.html` — frontend structure
- `/Users/darren/.openclaw/workspace/bioclaw/.planning/phases/07-backend-api-streaming-foundation/07-RESEARCH.md` — original dependency-isolation decision and its justification (root pyproject `web` extra vs. separate venv), verified still valid
- `/Users/darren/.openclaw/workspace/bioclaw/.planning/phases/07-backend-api-streaming-foundation/07-03-PLAN.md`, `08-03-PLAN.md`, `09-05-PLAN.md` — the exact, thrice-proven run command
- `/Users/darren/.openclaw/workspace/bioclaw/.planning/phases/09-frontend-chat-ui/09-VERIFICATION.md` — existing manual grep confirming no OpenClaw imports
- `/Users/darren/.openclaw/workspace/bioclaw/tests/test_webapp_integration.py`, `test_webapp_session_upload_integration.py` — live_llm test patterns and question phrasing to reuse for Phase 10's manual checkpoint
- `/Users/darren/.openclaw/workspace/bioclaw/bio_fm_worker/README.md` — precedent for when true dependency isolation (separate venv) is actually warranted, and why it does not apply here
- Direct shell verification: `uv --version` (0.11.4), `.venv/bin/uvicorn --version` (0.52.4), `.venv/bin/fastapi --help` (CLI present but not needed — `uvicorn` invocation is the established pattern)

### Secondary (MEDIUM confidence)
- [FastAPI Static Files docs](https://fastapi.tiangolo.com/tutorial/static-files/) — confirms the `/` -> `/app` `RedirectResponse` pattern as a standard, optional polish

### Tertiary (LOW confidence)
None — this phase's research is dominated by direct, already-executed, already-live-verified evidence from this exact repository, which is stronger than any external source for a packaging/verification phase.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — nothing new is being introduced; every tool cited is already installed and has run successfully multiple times in this exact repo
- Architecture: HIGH — the self-containment and single-command patterns are already implemented and already live-verified across three prior phases, not proposed
- Pitfalls: HIGH — all five pitfalls are derived from direct code/log inspection (module docstrings, prior SUMMARY.md bug reports, actual file structure), not speculation

**Research date:** 2026-09-13
**Valid until:** Stable for the life of this milestone — no fast-moving dependency exists in this phase's scope. Re-check only if `fastapi`/`uvicorn` major-version bumps occur before Phase 10 executes.

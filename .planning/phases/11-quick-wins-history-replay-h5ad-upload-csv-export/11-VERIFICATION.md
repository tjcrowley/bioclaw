---
phase: 11-quick-wins-history-replay-h5ad-upload-csv-export
verified: 2026-09-16T12:00:00Z
status: human_needed
score: 14/14 must-haves verified
re_verification: true
re_verification_meta:
  previous_status: human_needed
  previous_score: 14/14
  gaps_closed:
    - "HIST-01 citations not stored or replayed — NOW CLOSED: citations_json column added, add_message() stores citations, get_messages() returns them, sessions.js passes msg.citations to appendMessage()"
    - "HIST-01 tool events not stored or replayed — NOW CLOSED: tool_events_json column added, _collect_tool_event hook captures events in ask(), sessions.js renders [Tools used: X] inline after assistant turns"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Browser Download Flow — Export CSV Button"
    expected: "Browser opens Save dialog. Downloaded ZIP contains clusters.csv, de_genes.csv, annotations.csv. annotations.csv contains a placeholder row since annotation pipeline does not persist results back to the store."
    why_human: "Browser file download flow (anchor-click pattern) cannot be verified programmatically. The plan 11-03 Task 3 checkpoint was marked 'approved' in docs commit 74784e3, but the verifier cannot independently confirm the browser flow."
  - test: "HIST-01 Citation Link Rendering on Replay — visual confirmation"
    expected: "After resuming a session that had citations, assistant answers display clickable citation buttons (not raw [ref:...] bracket text). The renderAnswerWithCitations() branch in chat.js fires when msg.citations is a non-empty array."
    why_human: "The JS wiring is verified (sessions.js passes msg.citations || undefined to appendMessage; chat.js has the renderAnswerWithCitations branch). The visual outcome — clickable buttons vs. raw bracket text — requires a browser session to confirm."
  - test: "HIST-01 Inline Tool Activity on Replay — visual confirmation"
    expected: "After resuming a session where a tool ran, a [Tools used: <tool_name>] system message appears inline after the assistant bubble. The tool name has the mcp__bioclaw__ prefix stripped."
    why_human: "The JS append logic is verified in sessions.js lines 73-76. Visual confirmation of the system bubble rendering requires a browser session."
---

# Phase 11: Quick Wins — History Replay, H5AD Upload, CSV Export — Verification Report

**Phase Goal:** Researchers can resume any session and see the full prior conversation, upload .h5ad files directly, and download cluster/DE/annotation results as CSV — three capabilities that are independent of each other and independent of FM and network.
**Verified:** 2026-09-16
**Status:** human_needed (automated checks all pass; three browser-visual items remain for human confirmation)
**Re-verification:** Yes — after plan 11-04 gap closure

All 242 fast-tier tests pass. The HIST-01 citations/tool-events gap identified in the initial verification has been closed by plan 11-04. Two new browser-visual items are added for human confirmation (citation link rendering and tool activity rendering on replay). The pre-existing browser download flow item remains.

---

## Re-Verification: Gap Closure Confirmation

### Gap 1 (HIST-01 citations not stored): CLOSED

**Before (11-01):** `add_message()` accepted only `role` and `content`. Citations were returned in `AskResponse` but discarded.

**After (11-04):**
- `agent/memory.py` line 50-55: `_MIGRATE_MESSAGES_CITATIONS_SQL` and `_MIGRATE_MESSAGES_TOOL_EVENTS_SQL` constants present.
- `agent/memory.py` line 69-73: Migration executed idempotently in `__init__`.
- `agent/memory.py` lines 142-169: `add_message()` accepts `citations: list | None = None` and `tool_events: list | None = None`; both serialized to JSON before storage.
- `agent/memory.py` lines 171-193: `get_messages()` selects `citations_json, tool_events_json`; deserializes to Python list or None.
- `webapp/backend/main.py` lines 53-89: `tool_events_collector` list + `_collect_tool_event` async hook captures tool calls; `add_message(..., citations=citations if citations else None, tool_events=tool_events_collector if tool_events_collector else None)` for assistant turn.
- `webapp/backend/schemas.py` lines 32-33: `MessageRecord` has `citations: list | None = None` and `tool_events: list | None = None`.

### Gap 2 (HIST-01 tool events not stored/replayed): CLOSED

- `webapp/frontend/sessions.js` line 71: `appendMessage({ role: msg.role, content: msg.content, citations: msg.citations || undefined })` — passes citations, activates `renderAnswerWithCitations()` branch.
- `webapp/frontend/sessions.js` lines 73-76: After each assistant message with non-empty `msg.tool_events`, a `[Tools used: <names>]` system message is appended inline.

### Regression Check (previously passing items): NO REGRESSIONS

All 14 originally verified truths continue to pass. The full fast-tier suite grew from 231 to 242 tests (11 new tests from 11-04: 6 unit tests in test_agent_memory.py, 5 integration tests in test_webapp_backend.py).

---

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | Resuming a session renders all prior Q&A turns in the chat thread | VERIFIED | `sessions.js` line 70-79: `for (const msg of msgs)` loop with fallback for empty sessions |
| 2  | SQLite WAL mode is enabled on every SessionMemory connection | VERIFIED | `agent/memory.py` line 77: `conn.execute("PRAGMA journal_mode=WAL")` in `_connect()` |
| 3  | Stored message content is capped at 64 KB per entry | VERIFIED | `agent/memory.py` line 158: `capped = content[:_CONTENT_CAP]` where `_CONTENT_CAP = 64 * 1024` |
| 4  | GET /api/sessions/{id} returns a `messages` array alongside `recent_datasets` | VERIFIED | `main.py` line 104-109: `msgs = session_memory.get_messages(session_id)` returned as `messages=[MessageRecord(**m) for m in msgs]` |
| 5  | POST /api/ask stores both the user question and assistant answer per turn | VERIFIED | `main.py` lines 82-89: `add_message()` called for both roles |
| 6  | Citations are stored per-assistant-message at ask time | VERIFIED | `main.py` line 87: `citations=citations if citations else None` passed to `add_message()`; 11-04 unit test `test_ask_stores_citations_with_assistant_message` passes |
| 7  | Tool events are captured and stored per-assistant-message at ask time | VERIFIED | `main.py` lines 53-68: `_collect_tool_event` hook populates `tool_events_collector`; `main.py` line 88: passed to `add_message()`; `test_ask_stores_tool_events_with_assistant_message` passes |
| 8  | GET /api/sessions/{id} returns messages with citations and tool_events fields | VERIFIED | `schemas.py` lines 32-33: `MessageRecord` has both optional fields; `test_get_session_returns_citations_in_messages` and `test_get_session_returns_tool_events_in_messages` pass |
| 9  | sessions.js passes citations to appendMessage() on replay | VERIFIED | `sessions.js` line 71: `citations: msg.citations || undefined` in replay loop |
| 10 | sessions.js renders inline tool activity markers for turns with tool calls | VERIFIED | `sessions.js` lines 73-76: `[Tools used: ${toolNames}]` system message appended when `msg.tool_events.length > 0` |
| 11 | POST /api/upload with a single .h5ad file returns status=success and a dataset_id | VERIFIED | `test_upload_h5ad_returns_dataset_id` passes; `uploads.py` line 19: `_SINGLE_FILE_SUFFIXES = (".h5", ".h5ad")` |
| 12 | The .h5ad ingest path runs through the same ingest_10x() pipeline | VERIFIED | `loaders.py` lines 85-89: `if p.suffix == ".h5ad": return sc.read_h5ad(p)` inside the loader used by `ingest_10x()` |
| 13 | GET /api/export/csv?dataset_id={name@version} returns a ZIP with clusters.csv, de_genes.csv, annotations.csv | VERIFIED | `main.py` lines 144-229: `export_csv()` endpoint builds ZIP in-memory; 9 export tests pass |
| 14 | The download button is only visible/active when a dataset is associated | VERIFIED | `main.js`: `removeAttribute('hidden')` on upload success; `setAttribute('hidden','')` on new session |

**Score:** 14/14 truths verified (automated); 3 browser-visual items flagged for human confirmation

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `agent/memory.py` | messages table; add_message() with citations/tool_events; get_messages() returns all fields; WAL mode; idempotent migration | VERIFIED | `_MIGRATE_MESSAGES_CITATIONS_SQL` + `_MIGRATE_MESSAGES_TOOL_EVENTS_SQL` at lines 50-55; migration in `__init__` lines 69-73; `add_message()` lines 142-169; `get_messages()` lines 171-193 |
| `webapp/backend/schemas.py` | MessageRecord with citations and tool_events optional fields | VERIFIED | Lines 32-33: `citations: list \| None = None` and `tool_events: list \| None = None` |
| `webapp/backend/main.py` | ask() has tool_events_collector, _collect_tool_event hook, passes citations+tool_events to add_message() | VERIFIED | Lines 53-89 confirmed; hook prepended as first extra_hook |
| `webapp/frontend/sessions.js` | resumeSession() passes msg.citations and renders [Tools used: X] inline | VERIFIED | Line 71: citations passed; lines 73-76: tool activity rendered |
| `tests/test_agent_memory.py` | 6 new citations/tool_events unit tests | VERIFIED | Lines 157-259; 23 total tests pass (6 new: citations round-trip, tool_events round-trip, defaults None, backward compat) |
| `tests/test_webapp_backend.py` | 5 new integration tests for citations/tool_events API round-trip | VERIFIED | Lines 305-420; 26 total tests pass (5 new: stores citations, stores tool_events, GET returns citations, GET returns tool_events, MessageRecord schema) |
| `webapp/backend/main.py` | GET /api/export/csv endpoint | VERIFIED | Lines 144-229; StreamingResponse + zipfile |
| `webapp/frontend/api.js` | exportCsv() using anchor-click download pattern | VERIFIED | Lines 91-101; anchor-click pattern |
| `webapp/frontend/index.html` | #download-btn element | VERIFIED | id="download-btn" hidden by default |
| `webapp/frontend/main.js` | download button wiring; __currentDatasetId tracking | VERIFIED | Wiring confirmed; exportCsv() called on click |
| `tests/test_webapp_export.py` | 9 export endpoint unit tests | VERIFIED | All 9 pass |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `main.py POST /api/ask` | `memory.py add_message()` | `add_message(session_id, 'assistant', answer, citations=..., tool_events=...)` | WIRED | Lines 83-89 of main.py confirmed |
| `main.py POST /api/ask` | `_collect_tool_event hook` | hook prepended to `extra_hooks` before ask_question() call | WIRED | Lines 55-69 confirmed; hook fires for every tool call |
| `main.py GET /api/sessions/{id}` | `memory.py get_messages()` | `msgs = session_memory.get_messages(session_id)` | WIRED | Line 104 confirmed; now returns 5-field dicts |
| `sessions.js resumeSession()` | `chat.js appendMessage()` | `appendMessage({ role, content, citations: msg.citations || undefined })` | WIRED | Line 71 confirmed; citations branch activates |
| `sessions.js resumeSession()` | inline tool activity | `appendMessage({ role: 'system', content: '[Tools used: ...]' })` | WIRED | Lines 73-76 confirmed; strips mcp__bioclaw__ prefix |
| `tests/test_webapp_backend.py` | citations/tool_events in memory | `_fake_ask_with_citations` calls hooks; asserts on get_messages() | WIRED | Lines 305-420 confirmed; all 5 tests pass |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| HIST-01 | 11-01-PLAN.md + 11-04-PLAN.md | Resuming a session renders the full prior conversation thread including all turns, inline tool activity, citations | SATISFIED | Citations stored in `citations_json` column and replayed via `msg.citations`; tool events stored in `tool_events_json` and rendered as `[Tools used: X]` system messages. 11 new tests confirm round-trip. |
| DATA-02 | 11-02-PLAN.md | Upload endpoint accepts .h5ad files routing to same ingest pipeline | SATISFIED | uploads.py, loaders.py, and two passing integration tests confirm end-to-end |
| EXPORT-01 | 11-03-PLAN.md | Researcher can download cluster assignments, DE table, and annotation results as CSV | SATISFIED | GET /api/export/csv returns ZIP with all three CSVs; 9 tests pass; browser flow human-verified per docs commit 74784e3 |

**Orphaned requirements:** None.

---

### Anti-Patterns Found

No new anti-patterns introduced by 11-04. The `tool_events_collector` catch-all `except Exception: pass` on line 65 of main.py is intentional defensive coding (tool hook failures must not abort the ask response).

---

### Test Suite Results

| Suite | Tests | Result |
|-------|-------|--------|
| tests/test_agent_memory.py | 23 (was 17; +6 from 11-04) | PASS |
| tests/test_webapp_backend.py | 26 (was 21; +5 from 11-04) | PASS |
| tests/test_webapp_upload.py | 12 | PASS |
| tests/test_webapp_export.py | 9 | PASS |
| Full fast-tier suite | 242 (was 231; +11 from 11-04) | PASS (6 deselected live/smoke tests) |

---

### Human Verification Required

#### 1. Browser Download Flow — Export CSV Button

**Test:** (1) Start the webapp. (2) Log in. (3) Upload an .h5ad or MTX dataset. (4) Confirm the "Export CSV" button appears in the main panel toolbar. (5) Click the button. (6) Verify the browser opens a Save dialog (or auto-downloads) a file ending in `_export.zip`. (7) Open the ZIP and confirm it contains clusters.csv, de_genes.csv, annotations.csv.
**Expected:** ZIP downloads with correct filename. All three CSVs present. clusters.csv has placeholder row if leiden was not run. annotations.csv always has a placeholder row.
**Why human:** The anchor-click browser download pattern cannot be verified by the automated test suite. Plan 11-03 Task 3 checkpoint was marked approved in commit 74784e3 but the verifier cannot independently confirm browser behavior.

#### 2. HIST-01 Citation Link Rendering on Replay

**Test:** (1) Ask a question that returns citations (e.g., a gene-lookup query). (2) Note that citation links are rendered as clickable buttons in the response. (3) Close and resume the session from the sidebar. (4) Observe the replayed assistant message.
**Expected:** Citation links appear as clickable buttons in the replayed assistant message — not as raw `[ref:...]` bracket text. The `renderAnswerWithCitations()` branch in chat.js should fire because `msg.citations` is passed as a non-empty array.
**Why human:** The JS wiring is verified (sessions.js line 71 passes `msg.citations || undefined`; chat.js has the `renderAnswerWithCitations` branch guarded by `citations` being truthy). The visual outcome requires a browser session to confirm.

#### 3. HIST-01 Inline Tool Activity on Replay

**Test:** (1) Ask a question that triggers a tool call (e.g., "analyze dataset X" — should call cluster_analysis or similar). (2) Close and resume the session from the sidebar. (3) Observe the area after the replayed assistant bubble.
**Expected:** A `[Tools used: <tool_name>]` system message appears inline after the assistant bubble. The tool name should have the `mcp__bioclaw__` prefix stripped (e.g., "analyze_dataset" not "mcp__bioclaw__analyze_dataset").
**Why human:** The JS append logic is verified (sessions.js lines 73-76). Visual confirmation of the system bubble rendering requires a browser session. Also confirms that `_collect_tool_event` in main.py actually fires during a live tool call (live tool calls are excluded from the fast-tier suite).

---

### Commits Verified

All phase commits present in git history (original 11-01 through 11-03, plus 11-04 gap closure):

Original phase commits:
- `4b51cd4` feat(11-01): messages table, WAL mode, add_message(), get_messages()
- `2fa432a` feat(11-01): enrich API schema and store message turns
- `5b4c4c7` feat(11-01): replace JS placeholder with history replay
- `7d5d118` test(11-02): tiny_h5ad_file fixture
- `034c46f` test(11-02): h5ad upload integration tests
- `bc48751` test(11-03): RED tests for GET /api/export/csv
- `b4bcd8e` feat(11-03): implement GET /api/export/csv endpoint
- `626024b` feat(11-03): add export CSV download button to frontend
- `74784e3` docs(11-03): human-verify checkpoint approved

Gap closure commits (11-04):
- `fa5457e` feat(11-04): extend messages table to store citations and tool_events
- `3c881f9` feat(11-04): extend MessageRecord schema and add backend integration tests for citations/tool_events
- `40e5c12` feat(11-04): wire citations and tool events through ask handler and JS session replay

---

_Verified: 2026-09-16_
_Re-verified: 2026-09-16 (after plan 11-04 gap closure)_
_Verifier: Claude (gsd-verifier)_

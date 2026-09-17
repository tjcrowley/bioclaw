---
plan: "11-04"
phase: "11"
status: complete
gap_closure: true
requirements: [HIST-01]
---

# Plan 11-04 Summary: HIST-01 Gap Closure — Citations & Tool Events in Session Replay

## What Was Built

Extended the session history replay system to store and replay citations and tool events alongside each conversation turn. Session replay now shows clickable citation links and inline tool activity markers — not just plain text.

## Key Files

### Created / Modified

- **`agent/memory.py`** — Added `citations_json` and `tool_events_json` columns to the messages table via idempotent ALTER TABLE migration. Extended `add_message()` with optional `citations` and `tool_events` params (serialized to JSON). Extended `get_messages()` to deserialize and return both fields per row.
- **`webapp/backend/schemas.py`** — Added `citations: list | None = None` and `tool_events: list | None = None` to `MessageRecord`, so `GET /api/sessions/{id}` includes both fields in the response.
- **`webapp/backend/main.py`** — Added `_collect_tool_event` hook to `ask()` that captures tool calls into a local list. Passes `citations` and `tool_events` to `add_message()` for the assistant turn.
- **`webapp/frontend/sessions.js`** — Updated `resumeSession()` replay loop to pass `msg.citations` to `appendMessage()` (activates `renderAnswerWithCitations()`) and render a `[Tools used: X, Y]` system message inline after assistant turns with tool activity.
- **`tests/test_agent_memory.py`** — 6 new unit tests: round-trip citations/tool_events, defaults (None), backward compat with legacy rows.
- **`tests/test_webapp_backend.py`** — 5 new integration tests: citations stored via ask(), tool_events stored via ask(), GET session returns both, MessageRecord schema accepts both fields.

## Commits

- `fa5457e` — feat(11-04): extend messages table to store citations and tool_events
- `3c881f9` — feat(11-04): extend MessageRecord schema and add backend integration tests for citations/tool_events
- `40e5c12` — feat(11-04): wire citations and tool events through ask handler and JS session replay

## Test Results

- `tests/test_agent_memory.py`: 23 passed (6 new)
- `tests/test_webapp_backend.py`: 26 passed (5 new)
- Full fast-tier suite: **242 passed**, 6 deselected

## Deviations

None. Implemented exactly as specified in the plan.

## Self-Check

- [x] Citations stored as JSON in `citations_json` column; deserialized on read
- [x] Tool events stored as JSON in `tool_events_json` column; deserialized on read
- [x] `add_message()` backward compat: callers without citations/tool_events still work; get_messages returns None for those rows
- [x] `GET /api/sessions/{id}` returns `citations` and `tool_events` on each MessageRecord
- [x] `resumeSession()` passes `msg.citations` to `appendMessage()` — activates citation-rendering branch
- [x] `[Tools used: X]` system message rendered inline after replayed turns with tool activity
- [x] All 242 fast-tier tests pass

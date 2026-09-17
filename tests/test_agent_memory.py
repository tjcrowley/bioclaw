"""Tests for agent/memory.py: SessionMemory record/recall store."""

import sqlite3

from agent.memory import SessionMemory


# ---------------------------------------------------------------------------
# HIST-01: messages table, WAL mode, content cap tests
# ---------------------------------------------------------------------------

def test_wal_mode_enabled(tmp_path):
    """After SessionMemory init, WAL mode must be active on any new connection."""
    SessionMemory(root=tmp_path / "m.sqlite")
    conn = sqlite3.connect(str(tmp_path / "m.sqlite"))
    row = conn.execute("PRAGMA journal_mode").fetchone()
    conn.close()
    assert row[0] == "wal"


def test_add_message_stores_and_retrieves(tmp_path):
    mem = SessionMemory(root=tmp_path / "m.sqlite")
    mem.touch("s1")
    mem.add_message("s1", "user", "hello")
    msgs = mem.get_messages("s1")
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "hello"
    assert "created_at" in msgs[0]


def test_add_message_caps_at_64kb(tmp_path):
    mem = SessionMemory(root=tmp_path / "m.sqlite")
    mem.touch("s1")
    big = "x" * (65 * 1024)
    mem.add_message("s1", "user", big)
    msgs = mem.get_messages("s1")
    assert len(msgs[0]["content"]) == 64 * 1024


def test_get_messages_returns_oldest_first(tmp_path):
    mem = SessionMemory(root=tmp_path / "m.sqlite")
    mem.touch("s1")
    mem.add_message("s1", "user", "question")
    mem.add_message("s1", "assistant", "answer")
    msgs = mem.get_messages("s1")
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"


def test_get_messages_empty_for_unknown_session(tmp_path):
    mem = SessionMemory(root=tmp_path / "m.sqlite")
    assert mem.get_messages("no-such") == []


def test_messages_isolated_by_session(tmp_path):
    mem = SessionMemory(root=tmp_path / "m.sqlite")
    mem.touch("sess-1")
    mem.touch("sess-2")
    mem.add_message("sess-1", "user", "hello from 1")
    msgs_1 = mem.get_messages("sess-1")
    msgs_2 = mem.get_messages("sess-2")
    assert len(msgs_1) == 1
    assert len(msgs_2) == 0


# ---------------------------------------------------------------------------
# Existing tests
# ---------------------------------------------------------------------------

def test_record_and_recall_most_recent_first(tmp_path):
    mem = SessionMemory(root=tmp_path / "memory.sqlite")
    mem.record("sess-1", "pilot@1", note="ingested pilot")
    mem.record("sess-1", "pilot@2", note="analyze: 3 clusters")

    assert mem.recent_datasets("sess-1") == ["pilot@2", "pilot@1"]


def test_recent_datasets_respects_limit(tmp_path):
    mem = SessionMemory(root=tmp_path / "memory.sqlite")
    mem.record("sess-1", "pilot@1", note="ingested pilot")
    mem.record("sess-1", "pilot@2", note="analyze: 3 clusters")

    assert mem.recent_datasets("sess-1", limit=1) == ["pilot@2"]


def test_session_isolation(tmp_path):
    mem = SessionMemory(root=tmp_path / "memory.sqlite")
    mem.record("sess-1", "pilot@1", note="ingested pilot")
    mem.record("sess-2", "other@1", note="ingested other")

    assert mem.recent_datasets("sess-1") == ["pilot@1"]
    assert mem.recent_datasets("sess-2") == ["other@1"]


def test_recent_datasets_missing_session_returns_empty_list(tmp_path):
    mem = SessionMemory(root=tmp_path / "memory.sqlite")
    assert mem.recent_datasets("no-such-session") == []


def test_persistence_across_new_instance(tmp_path):
    path = tmp_path / "memory.sqlite"
    mem = SessionMemory(root=path)
    mem.record("sess-1", "pilot@1", note="ingested pilot")

    reopened = SessionMemory(root=path)
    assert reopened.recent_datasets("sess-1") == ["pilot@1"]


def test_record_note_is_optional(tmp_path):
    mem = SessionMemory(root=tmp_path / "memory.sqlite")
    mem.record("sess-1", "pilot@3")

    assert mem.recent_datasets("sess-1") == ["pilot@3"]


def test_touch_creates_listable_session(tmp_path):
    mem = SessionMemory(root=tmp_path / "memory.sqlite")
    mem.touch("sess-1")
    sessions = mem.list_sessions()
    assert len(sessions) == 1
    assert sessions[0]["session_id"] == "sess-1"


def test_touch_twice_updates_not_duplicates(tmp_path):
    mem = SessionMemory(root=tmp_path / "memory.sqlite")
    mem.touch("sess-1")
    mem.touch("sess-1")
    assert len(mem.list_sessions()) == 1


def test_list_sessions_orders_by_last_active(tmp_path):
    mem = SessionMemory(root=tmp_path / "memory.sqlite")
    mem.touch("sess-1")
    mem.touch("sess-2")
    mem.touch("sess-1")  # bump sess-1 back to most-recently-active
    sessions = mem.list_sessions()
    assert sessions[0]["session_id"] == "sess-1"


def test_list_sessions_includes_recent_datasets(tmp_path):
    mem = SessionMemory(root=tmp_path / "memory.sqlite")
    mem.touch("sess-1")
    mem.record("sess-1", "pilot@1")
    sessions = mem.list_sessions()
    assert sessions[0]["recent_datasets"] == ["pilot@1"]


def test_session_exists(tmp_path):
    mem = SessionMemory(root=tmp_path / "memory.sqlite")
    assert mem.session_exists("nope") is False
    mem.touch("sess-1")
    assert mem.session_exists("sess-1") is True


# ---------------------------------------------------------------------------
# HIST-01 gap closure: citations and tool_events storage/retrieval tests
# ---------------------------------------------------------------------------

def test_add_message_stores_citations(tmp_path):
    """citations list round-trips through add_message/get_messages correctly."""
    mem = SessionMemory(root=tmp_path / "m.sqlite")
    mem.touch("s1")
    citations = [["tool", "abc123", {"k": "v"}]]
    mem.add_message("s1", "assistant", "answer", citations=citations)
    msgs = mem.get_messages("s1")
    assert len(msgs) == 1
    assert msgs[0]["citations"] == citations


def test_add_message_stores_tool_events(tmp_path):
    """tool_events list round-trips through add_message/get_messages correctly."""
    mem = SessionMemory(root=tmp_path / "m.sqlite")
    mem.touch("s1")
    tool_events = [{"tool_name": "leiden", "is_error": False}]
    mem.add_message("s1", "assistant", "answer", tool_events=tool_events)
    msgs = mem.get_messages("s1")
    assert len(msgs) == 1
    assert msgs[0]["tool_events"] == tool_events


def test_add_message_citations_default_none(tmp_path):
    """Calling add_message without citations returns citations=None, not an error."""
    mem = SessionMemory(root=tmp_path / "m.sqlite")
    mem.touch("s1")
    mem.add_message("s1", "user", "q")
    msgs = mem.get_messages("s1")
    assert len(msgs) == 1
    assert msgs[0]["citations"] is None


def test_add_message_tool_events_default_none(tmp_path):
    """Calling add_message without tool_events returns tool_events=None, not an error."""
    mem = SessionMemory(root=tmp_path / "m.sqlite")
    mem.touch("s1")
    mem.add_message("s1", "user", "q")
    msgs = mem.get_messages("s1")
    assert len(msgs) == 1
    assert msgs[0]["tool_events"] is None


def test_get_messages_parses_citations_json(tmp_path):
    """Citations stored as JSON string round-trip correctly to Python list."""
    mem = SessionMemory(root=tmp_path / "m.sqlite")
    mem.touch("s1")
    citations = [["tool_a", "sha1", {"gene": "BRCA1"}], ["tool_b", "sha2", None]]
    mem.add_message("s1", "assistant", "result", citations=citations)
    msgs = mem.get_messages("s1")
    assert msgs[0]["citations"] == citations


def test_get_messages_existing_rows_without_citations_json_column_return_none(tmp_path):
    """Backward compat: rows with NULL citations_json/tool_events_json return None without error."""
    import sqlite3
    db_path = tmp_path / "m.sqlite"
    # Create legacy-style table without citations_json/tool_events_json
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            last_active_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS session_memory (
            session_id TEXT NOT NULL,
            dataset_id TEXT NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute(
        "INSERT INTO sessions VALUES (?, ?, ?)",
        ("legacy-sess", "2024-01-01T00:00:00+00:00", "2024-01-01T00:00:00+00:00"),
    )
    conn.execute(
        "INSERT INTO messages VALUES (?, ?, ?, ?)",
        ("legacy-sess", "user", "old message", "2024-01-01T00:00:00+00:00"),
    )
    conn.commit()
    conn.close()

    # Now open with the new SessionMemory — migration should add columns idempotently
    mem = SessionMemory(root=db_path)
    msgs = mem.get_messages("legacy-sess")
    assert len(msgs) == 1
    assert msgs[0]["content"] == "old message"
    assert msgs[0]["citations"] is None
    assert msgs[0]["tool_events"] is None

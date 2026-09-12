"""Tests for agent/memory.py: SessionMemory record/recall store."""

from agent.memory import SessionMemory


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

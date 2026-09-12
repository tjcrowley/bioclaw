"""Depends()-injectable factories -- overridden in tests via
app.dependency_overrides so fast-tier tests never call the real LLM
(07-RESEARCH.md "Code Examples").
"""
from agent.memory import SessionMemory
from qa.session import ask_question


def get_ask_question():
    return ask_question


_session_memory = SessionMemory()


def get_session_memory():
    return _session_memory

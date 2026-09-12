"""Depends()-injectable factories -- overridden in tests via
app.dependency_overrides so fast-tier tests never call the real LLM
(07-RESEARCH.md "Code Examples").
"""
from qa.session import ask_question


def get_ask_question():
    return ask_question

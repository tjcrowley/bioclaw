"""Unit tests for qa/session.py (Phase 6 Wave 2, Plan 06-02).

Deterministic structural tests -- no LLM required. Assert that
QA_SYSTEM_PROMPT contains the four protocol sections the plan requires
(citation, uncertainty, anti-hallucination, mandatory citation) and that
ask_question() has the right signature and wires the right pieces
together (run_session with system_prompt=QA_SYSTEM_PROMPT, then
verify_answer_citations on the returned answer).

The live end-to-end run against a real LLM is
tests/test_qa_integration.py (Plan 06-03).
"""

import asyncio
import inspect
from pathlib import Path
from unittest.mock import AsyncMock, patch

from qa.session import QA_SYSTEM_PROMPT, ask_question


class TestQASystemPrompt:
    """QA_SYSTEM_PROMPT is a string constant with four required protocols."""

    def test_is_nonempty_string(self):
        assert isinstance(QA_SYSTEM_PROMPT, str)
        assert len(QA_SYSTEM_PROMPT) > 100  # not a stub / placeholder

    def test_citation_protocol_format(self):
        # Must reference the [ref:TOOL_NAME:SHA256_PREFIX] tag format the
        # qa/citations.py regex parses.
        assert "[ref:" in QA_SYSTEM_PROMPT
        assert "TOOL_NAME" in QA_SYSTEM_PROMPT
        assert "SHA256_PREFIX" in QA_SYSTEM_PROMPT

    def test_uncertainty_protocol_names_real_fields(self):
        # Every quantitative claim must surface the actual uncertainty field
        # from the tool result JSON -- not a generic "state your confidence"
        # instruction. Names must match the shapes documented in the plan's
        # <interfaces> block.
        low = QA_SYSTEM_PROMPT.lower()
        assert "p-value" in low or "pval_adj" in QA_SYSTEM_PROMPT or "p_adj" in QA_SYSTEM_PROMPT
        assert "confidence" in low
        assert "baseline" in low  # perturbation model-vs-baseline

    def test_anti_hallucination_instruction(self):
        # Must instruct the model to invoke the tool even when it thinks it
        # already knows the answer -- prevents pretrained-knowledge hallucination.
        low = QA_SYSTEM_PROMPT.lower()
        assert "invoke" in low or "call" in low
        assert "tool" in low

    def test_mandatory_citation_language(self):
        # "MUST" (uppercase) -- required by the plan's must_haves.truths.
        assert "MUST" in QA_SYSTEM_PROMPT
        # At least one [ref:...] citation is required in every answer.
        low = QA_SYSTEM_PROMPT.lower()
        assert "at least one" in low or "must include" in low


class TestAskQuestionSignature:
    """ask_question() is async and returns (answer, session_id, citation_results)."""

    def test_is_coroutine_function(self):
        assert inspect.iscoroutinefunction(ask_question)

    def test_has_required_parameters(self):
        sig = inspect.signature(ask_question)
        assert "question" in sig.parameters
        assert "session_memory" in sig.parameters
        assert "log_path" in sig.parameters

    def test_log_path_default_is_path(self):
        sig = inspect.signature(ask_question)
        default = sig.parameters["log_path"].default
        assert isinstance(default, Path)

    def test_session_memory_default_is_none(self):
        sig = inspect.signature(ask_question)
        assert sig.parameters["session_memory"].default is None


class TestAskQuestionWiring:
    """ask_question() wires run_session (with QA_SYSTEM_PROMPT) into
    verify_answer_citations. Mock the LLM boundary; assert on call shape.

    Uses asyncio.run() to drive the coroutine, matching the existing pattern
    in tests/test_agent_session_wiring.py (no pytest-asyncio dependency)."""

    def test_calls_run_session_with_qa_system_prompt(self, tmp_path):
        log_path = tmp_path / "tool_calls.jsonl"
        with patch("qa.session.run_session", new_callable=AsyncMock) as mock_run, \
             patch("qa.session.verify_answer_citations") as mock_verify:
            mock_run.return_value = (["answer text"], "sid-123")
            mock_verify.return_value = []

            asyncio.run(ask_question("What clusters are in DS1?", log_path=log_path))

            mock_run.assert_awaited_once()
            _, kwargs = mock_run.call_args
            assert kwargs["system_prompt"] == QA_SYSTEM_PROMPT
            assert kwargs["log_path"] == log_path

    def test_returns_answer_session_id_citation_results_tuple(self, tmp_path):
        log_path = tmp_path / "tool_calls.jsonl"
        with patch("qa.session.run_session", new_callable=AsyncMock) as mock_run, \
             patch("qa.session.verify_answer_citations") as mock_verify:
            mock_run.return_value = (["the answer"], "sid-xyz")
            mock_verify.return_value = [("mcp__bioclaw__x", "aaaaaaaaaaaa", {"tool_name": "x"})]

            result = asyncio.run(ask_question("q", log_path=log_path))

            assert isinstance(result, tuple)
            assert len(result) == 3
            answer, session_id, citation_results = result
            assert answer == "the answer"
            assert session_id == "sid-xyz"
            assert citation_results == [("mcp__bioclaw__x", "aaaaaaaaaaaa", {"tool_name": "x"})]

    def test_calls_verify_answer_citations_on_answer(self, tmp_path):
        log_path = tmp_path / "tool_calls.jsonl"
        with patch("qa.session.run_session", new_callable=AsyncMock) as mock_run, \
             patch("qa.session.verify_answer_citations") as mock_verify:
            mock_run.return_value = (["some answer"], "sid")
            mock_verify.return_value = []

            asyncio.run(ask_question("q", log_path=log_path))

            mock_verify.assert_called_once_with("some answer", log_path)

    def test_empty_texts_yields_empty_answer_string(self, tmp_path):
        # run_session can return [] on some edge cases -- ask_question must
        # not IndexError; it should fall back to "" and still call verify.
        log_path = tmp_path / "tool_calls.jsonl"
        with patch("qa.session.run_session", new_callable=AsyncMock) as mock_run, \
             patch("qa.session.verify_answer_citations") as mock_verify:
            mock_run.return_value = ([], "sid")
            mock_verify.return_value = []

            answer, sid, citations = asyncio.run(ask_question("q", log_path=log_path))

            assert answer == ""
            mock_verify.assert_called_once_with("", log_path)

    def test_ask_question_forwards_extra_hooks(self, tmp_path):
        log_path = tmp_path / "tool_calls.jsonl"

        async def dummy_hook(input_data, tool_use_id, context):
            return {}

        with patch("qa.session.run_session", new_callable=AsyncMock) as mock_run, \
             patch("qa.session.verify_answer_citations") as mock_verify:
            mock_run.return_value = (["answer"], "sid")
            mock_verify.return_value = []

            asyncio.run(
                ask_question("q", log_path=log_path, extra_hooks=[dummy_hook])
            )

            assert mock_run.call_args.kwargs["extra_hooks"] == [dummy_hook]

    def test_ask_question_forwards_session_id(self, tmp_path):
        log_path = tmp_path / "tool_calls.jsonl"
        with patch("qa.session.run_session", new_callable=AsyncMock) as mock_run, \
             patch("qa.session.verify_answer_citations") as mock_verify:
            mock_run.return_value = (["answer"], "sess-42")
            mock_verify.return_value = []

            asyncio.run(ask_question("q", session_id="sess-42", log_path=log_path))

            assert mock_run.call_args.kwargs["session_id"] == "sess-42"

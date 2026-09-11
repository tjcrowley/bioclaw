"""Live end-to-end Q&A integration test (Phase 6, QA-01/02/03).

Wave 0 scaffold: this file exists so Plan 06-03 has a concrete target to
implement against. The full body -- driving a real ClaudeSDKClient session
with the qa/session.py wrapper, asserting on inline [ref:...] citations and
verify_answer_citations() resolution -- is filled in by Plan 06-03.

Marked @pytest.mark.live_llm and skipped when ANTHROPIC_API_KEY is unset,
mirroring tests/test_agent_integration.py's Phase-3 pattern.
"""

import os

import pytest

# Import surfaces the ask_question stub exists (fails loudly if the qa/
# skeleton was not created), without invoking it -- the stub raises
# NotImplementedError, which Plan 06-03 replaces.
from qa.session import ask_question  # noqa: F401


@pytest.mark.live_llm
@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"), reason="requires ANTHROPIC_API_KEY"
)
def test_qa_multi_tool_compose_with_citations():
    """Full body implemented in Plan 06-03. This scaffold reserves the name
    and marker set so QA-01/02/03 have a concrete integration target."""
    pytest.skip("Implemented in Plan 06-03")

"""In-process MCP server assembling `agent/tools.py`'s @tool-decorated
handlers -- the single object Wave 2's `agent/session.py` wires into
`ClaudeAgentOptions(mcp_servers={"bioclaw": bioclaw_server})`.
"""

from claude_agent_sdk import create_sdk_mcp_server

from agent.tools import (
    analyze_dataset_tool,
    annotate_cell_type_tool,
    fetch_census_dataset_tool,
    ingest_10x_tool,
    predict_perturbation_geneformer_tool,
    predict_perturbation_tool,
)

bioclaw_server = create_sdk_mcp_server(
    name="bioclaw",
    version="1.0.0",
    tools=[
        ingest_10x_tool,
        analyze_dataset_tool,
        annotate_cell_type_tool,
        predict_perturbation_tool,
        predict_perturbation_geneformer_tool,
        fetch_census_dataset_tool,
    ],
)

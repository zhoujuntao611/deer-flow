import os
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
async def test_stdio_server_exposes_stable_tool_contract() -> None:
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "scholarflow_mcp.server"],
        env=dict(os.environ),
    )

    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            response = await session.list_tools()

    tools = {tool.name: tool for tool in response.tools}
    assert set(tools) == {
        "assess_claim_evidence",
        "assess_retrieved_claim_evidence",
        "extract_pdf_pages",
        "normalize_papers",
        "retrieve_claim_evidence",
        "search_literature",
        "verify_evidence_spans",
    }
    assert {"query", "max_results"} <= set(tools["search_literature"].inputSchema["properties"])
    assert "records" in tools["normalize_papers"].inputSchema["properties"]
    assert {"pages", "claims"} == set(tools["verify_evidence_spans"].inputSchema["properties"])
    assert {"pdf_base64", "document_id", "max_pages"} == set(tools["extract_pdf_pages"].inputSchema["properties"])
    assert {"pages", "claims"} == set(tools["assess_claim_evidence"].inputSchema["properties"])
    assert {"pages", "claims", "top_k"} <= set(tools["retrieve_claim_evidence"].inputSchema["properties"])
    assert {"pages", "claims", "top_k"} <= set(tools["assess_retrieved_claim_evidence"].inputSchema["properties"])

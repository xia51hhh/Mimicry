"""Regression: every exposed MCP tool MUST carry a registered description.

If `_make_description` falls back to "Mimicry: <name>", the LLM has no signal
to pick the tool. This was the gap fixed in
`05-01-mcp-cli-camoufox-gap-analysis` Phase 2; lock it here so we don't
regress when adding new `@rpc_method`s.
"""
import asyncio
import os
import sys

import pytest

# Make sidecar/ importable as the test runner uses tests/ as a subdir.
_HERE = os.path.dirname(os.path.abspath(__file__))
_SIDECAR = os.path.dirname(_HERE)
if _SIDECAR not in sys.path:
    sys.path.insert(0, _SIDECAR)


def _list_tools_sync():
    import mcp_server  # noqa: WPS433 — needs lazy import after sys.path tweak
    return asyncio.run(mcp_server.list_tools())


def test_no_fallback_descriptions():
    tools = _list_tools_sync()
    fallback = [t.name for t in tools if (t.description or "").startswith("Mimicry: ")]
    assert not fallback, (
        f"{len(fallback)} tool(s) lack a registered description and fell back "
        f"to 'Mimicry: <name>': {fallback}"
    )


def test_tool_count_minimum():
    tools = _list_tools_sync()
    assert len(tools) >= 60, (
        f"Tool count regressed to {len(tools)}; expected >= 60. Did a registry "
        "import fail silently?"
    )


def test_call_tool_unknown_returns_iserror():
    """call_tool unknown name path returns CallToolResult(isError=True)."""
    import mcp_server  # noqa: WPS433
    from mcp.types import CallToolResult

    r = asyncio.run(mcp_server.call_tool("does_not_exist_xyz", {}))
    assert isinstance(r, CallToolResult)
    assert r.isError is True
    assert r.content and r.content[0].type == "text"

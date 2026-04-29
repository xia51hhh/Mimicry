"""Mimicry MCP Server — Model Context Protocol bridge.

Maps METHOD_REGISTRY RPC methods to MCP tools so that LLM agents
(Cursor, Copilot, Claude Desktop, etc.) can drive Mimicry via the
standard MCP stdio transport.

Usage:
    python main.py --mcp          # started by CLI or directly
    mimicry --mcp                 # via entry_point
"""
from __future__ import annotations

import inspect
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# Import all RPC methods (side-effect: registers into METHOD_REGISTRY)
import browser.actions  # noqa: F401
from rpc.methods import METHOD_REGISTRY

# Methods that should NOT be exposed as MCP tools
_SKIP_METHODS = {"shutdown", "echo"}


def _build_tool_schema(name: str, fn) -> dict:
    """Build a JSON Schema 'properties' dict from function signature."""
    sig = inspect.signature(fn)
    properties = {}
    required = []
    for pname, param in sig.parameters.items():
        if pname in ("self", "cls"):
            continue
        prop: dict = {}
        annotation = param.annotation
        if annotation == inspect.Parameter.empty:
            prop["type"] = "string"
        elif annotation is str:
            prop["type"] = "string"
        elif annotation is int:
            prop["type"] = "integer"
        elif annotation is float:
            prop["type"] = "number"
        elif annotation is bool:
            prop["type"] = "boolean"
        elif annotation is dict:
            prop["type"] = "object"
        elif annotation is list:
            prop["type"] = "array"
        else:
            prop["type"] = "string"

        if param.default is inspect.Parameter.empty:
            required.append(pname)
        else:
            prop["default"] = param.default

        properties[pname] = prop

    schema = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _make_description(name: str, fn) -> str:
    """Generate a description from docstring or method name."""
    if fn.__doc__:
        return fn.__doc__.strip().split("\n")[0]
    return f"Mimicry: {name}"


app = Server("mimicry")


@app.list_tools()
async def list_tools() -> list[Tool]:
    tools = []
    for method_name, fn in METHOD_REGISTRY.items():
        if method_name in _SKIP_METHODS:
            continue
        # Convert dotted name to underscore for MCP tool naming
        tool_name = method_name.replace(".", "_")
        schema = _build_tool_schema(method_name, fn)
        tools.append(Tool(
            name=tool_name,
            description=_make_description(method_name, fn),
            inputSchema=schema,
        ))
    return tools


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    # Convert underscore back to dotted name
    method_name = name.replace("_", ".", 1) if "_" in name else name

    # Try exact match first, then try full underscore-to-dot conversion
    fn = METHOD_REGISTRY.get(method_name)
    if fn is None:
        # Try replacing all underscores
        method_name = name.replace("_", ".")
        fn = METHOD_REGISTRY.get(method_name)
    if fn is None:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown method: {name}"}))]

    try:
        result = fn(**arguments) if arguments else fn()
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, default=str))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def _run():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def run_mcp():
    """Entry point for MCP server."""
    import asyncio
    asyncio.run(_run())

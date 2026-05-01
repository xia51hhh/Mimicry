"""Mimicry MCP Server — Model Context Protocol bridge.

Maps METHOD_REGISTRY RPC methods to MCP tools so that LLM agents
(Cursor, Copilot, Claude Desktop, etc.) can drive Mimicry via the
standard MCP stdio transport.

Usage:
    python main.py --mcp          # started by CLI or directly
    mimicry --mcp                 # via entry_point
"""
from __future__ import annotations

import enum
import inspect
import json
import os
import sys
import types
import typing
from typing import Any, Union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, TextContent, Tool

# Import all RPC methods (side-effect: registers into METHOD_REGISTRY)
import browser.actions  # noqa: F401
from rpc.methods import METHOD_METADATA, METHOD_REGISTRY

# Methods that should NOT be exposed as MCP tools
_SKIP_METHODS = {"shutdown", "echo"}

# Server-level instructions surfaced to the LLM client at handshake.
_SERVER_INSTRUCTIONS = (
    "Mimicry is a workflow-first browser automation toolkit built on Camoufox. "
    "These MCP tools let an LLM (a) list and execute recorded workflow JSON, "
    "(b) drive the browser interactively to test selectors and pages, "
    "(c) author new workflow nodes, and (d) debug execution with breakpoints, "
    "step, pause/resume and runtime block injection. "
    "Three top-level RPC namespaces are exposed: `browser.*` for atomic "
    "actions across multiple isolated sessions, `workflow.*` for execute / "
    "pause / step / inject / breakpoint control, and `recording.*` for "
    "capturing user actions into workflow JSON. "
    "Most browser tools accept a `session_id` argument that defaults to "
    '"default"; pass distinct ids to keep multiple browsers isolated.'
)


# ---------------------------------------------------------------------------
# JSON-Schema generation from Python type hints
# ---------------------------------------------------------------------------

_PRIMITIVE_MAP = {
    str: {"type": "string"},
    int: {"type": "integer"},
    float: {"type": "number"},
    bool: {"type": "boolean"},
    dict: {"type": "object"},
    list: {"type": "array"},
    type(None): {"type": "null"},
    Any: {},
}


def _annotation_to_schema(annotation: Any) -> dict:
    """Convert a Python type annotation to a JSON Schema fragment."""
    if annotation is inspect.Parameter.empty or annotation is Any:
        return {"type": "string"}

    if annotation in _PRIMITIVE_MAP:
        # Copy so callers can mutate (e.g. add description) safely.
        return dict(_PRIMITIVE_MAP[annotation])

    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)

    # Optional[T] / Union[T, None] / T | None
    if origin is Union or origin is types.UnionType:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return _annotation_to_schema(non_none[0])
        # Genuine multi-type union → anyOf
        return {"anyOf": [_annotation_to_schema(a) for a in non_none]}

    # list[T] / List[T]
    if origin in (list, tuple, set, frozenset):
        if args:
            return {"type": "array", "items": _annotation_to_schema(args[0])}
        return {"type": "array"}

    # dict[K, V] / Dict[K, V]
    if origin is dict:
        if len(args) == 2:
            return {"type": "object", "additionalProperties": _annotation_to_schema(args[1])}
        return {"type": "object"}

    # Literal[...]
    if origin is typing.Literal:
        values = list(args)
        # Infer JSON type from first literal value if homogeneous strings
        if all(isinstance(v, str) for v in values):
            return {"type": "string", "enum": values}
        if all(isinstance(v, bool) for v in values):
            return {"type": "boolean", "enum": values}
        if all(isinstance(v, int) for v in values):
            return {"type": "integer", "enum": values}
        return {"enum": values}

    # Enum subclasses
    if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
        values = [m.value for m in annotation]
        return {"enum": values}

    # Unknown / custom class → fall back to string
    return {"type": "string"}


def _build_tool_schema(name: str, fn) -> dict:
    """Build a JSON Schema 'object' from function signature + metadata.

    Skips `self`/`cls`, `*args` (VAR_POSITIONAL) and `**kwargs` (VAR_KEYWORD)
    entirely — they cannot be expressed as fixed schema properties.
    """
    sig = inspect.signature(fn)
    meta = METHOD_METADATA.get(name, {})
    param_descriptions = meta.get("param_descriptions", {}) or {}
    properties: dict[str, dict] = {}
    required: list[str] = []
    for pname, param in sig.parameters.items():
        if pname in ("self", "cls"):
            continue
        # **kwargs / *args have no fixed schema shape — drop them.
        if param.kind in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL):
            continue

        prop = _annotation_to_schema(param.annotation)

        if param.default is inspect.Parameter.empty:
            required.append(pname)
        else:
            # Only emit JSON-serializable defaults; otherwise skip.
            try:
                json.dumps(param.default)
                prop["default"] = param.default
            except (TypeError, ValueError):
                pass

        if pname in param_descriptions:
            prop["description"] = param_descriptions[pname]

        properties[pname] = prop

    schema: dict = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _make_description(name: str, fn) -> str:
    """Generate a description from registered metadata, docstring, or method name."""
    meta = METHOD_METADATA.get(name, {})
    if meta.get("description"):
        return meta["description"]
    if fn.__doc__:
        return fn.__doc__.strip().split("\n")[0]
    return f"Mimicry: {name}"


# ---------------------------------------------------------------------------
# Tool name <-> RPC name bidirectional map
# ---------------------------------------------------------------------------

# Convention: dotted RPC name → tool name = replace ALL "." with "_".
# E.g. "browser.navigate" → "browser_navigate", "workflow.set_breakpoint" →
# "workflow_set_breakpoint". The reverse map is built once and used for O(1)
# dispatch in call_tool, eliminating the brittle replace heuristic.
_TOOL_NAME_TO_RPC: dict[str, str] = {}


def _rpc_to_tool_name(rpc_name: str) -> str:
    return rpc_name.replace(".", "_")


def _rebuild_name_map() -> None:
    _TOOL_NAME_TO_RPC.clear()
    for rpc_name in METHOD_REGISTRY:
        if rpc_name in _SKIP_METHODS or rpc_name.startswith("test."):
            continue
        _TOOL_NAME_TO_RPC[_rpc_to_tool_name(rpc_name)] = rpc_name


# Build at import time so call_tool can dispatch even before list_tools is hit.
_rebuild_name_map()


app = Server("mimicry", instructions=_SERVER_INSTRUCTIONS)


@app.list_tools()
async def list_tools() -> list[Tool]:
    # Refresh in case methods were registered after import.
    _rebuild_name_map()
    tools = []
    for tool_name, method_name in _TOOL_NAME_TO_RPC.items():
        fn = METHOD_REGISTRY[method_name]
        schema = _build_tool_schema(method_name, fn)
        tools.append(Tool(
            name=tool_name,
            description=_make_description(method_name, fn),
            inputSchema=schema,
        ))
    return tools


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent] | CallToolResult:
    """Dispatch an MCP tool call to the underlying RPC method.

    Returns a plain list[TextContent] on success (the SDK wraps it with
    isError=False), and a CallToolResult with isError=True on any failure
    path — unknown tool/method or exception raised by the RPC handler.
    Surfacing isError at the protocol level lets MCP clients distinguish
    failures without parsing the JSON payload.

    SDK compatibility verified against `mcp.server.lowlevel.server.Server`:
    its `@call_tool` request handler explicitly checks
    `isinstance(results, types.CallToolResult)` and forwards via
    `ServerResult(results)` without re-wrapping. Validated empirically with
    `asyncio.run(call_tool('does_not_exist', {}))` returning a
    CallToolResult(isError=True). See task 05-01-mcp-gap-followup.
    """
    def _err(message: str) -> CallToolResult:
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps({"error": message}, ensure_ascii=False))],
            isError=True,
        )

    method_name = _TOOL_NAME_TO_RPC.get(name)
    if method_name is None:
        return _err(f"Unknown tool: {name}")
    fn = METHOD_REGISTRY.get(method_name)
    if fn is None:
        return _err(f"Unknown method: {method_name}")

    try:
        result = fn(**arguments) if arguments else fn()
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, default=str))]
    except Exception as e:
        return _err(str(e))


async def _run():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def run_mcp():
    """Entry point for MCP server."""
    import asyncio
    asyncio.run(_run())

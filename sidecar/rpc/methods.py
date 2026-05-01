import platform
import time
from typing import Any, Callable

METHOD_REGISTRY: dict[str, Callable[..., Any]] = {}
# Per-method MCP metadata: tool description + per-param descriptions.
# Populated by the @rpc_method decorator. Consumed by sidecar/mcp_server.py.
METHOD_METADATA: dict[str, dict[str, Any]] = {}

_start_time = time.time()


def rpc_method(
    name: str,
    *,
    description: str | None = None,
    param_descriptions: dict[str, str] | None = None,
):
    """Register a function as both an RPC method and an MCP tool.

    Args:
        name: dotted RPC method name (e.g. "browser.launch").
        description: one-line tool description for MCP. Falls back to
            the function's first docstring line.
        param_descriptions: mapping of parameter name to a human-readable
            description shown to LLMs in the MCP inputSchema. Parameters
            not present here get no description (LLM has to guess).
    """
    def decorator(fn):
        METHOD_REGISTRY[name] = fn
        METHOD_METADATA[name] = {
            "description": description,
            "param_descriptions": param_descriptions or {},
        }
        return fn
    return decorator


@rpc_method(
    "ping",
    description="Liveness probe. Returns the literal string 'pong'. Use to verify the sidecar RPC is reachable.",
)
def ping():
    return "pong"


@rpc_method("echo")
def echo(message: str = ""):
    return message


@rpc_method(
    "system.info",
    description="Return basic sidecar runtime info: host platform, Python version, sidecar version. Use for diagnostics or version-gating client behavior.",
)
def system_info():
    return {
        "platform": platform.system(),
        "python": platform.python_version(),
        "sidecar": "0.1.0",
    }


@rpc_method(
    "heartbeat",
    description="Return current sidecar timestamp and process uptime in seconds. Use to confirm the daemon is alive and to measure session age.",
)
def heartbeat():
    return {
        "timestamp": time.time(),
        "uptime_seconds": round(time.time() - _start_time, 1),
    }

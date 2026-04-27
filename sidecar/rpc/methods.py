import platform
import time
from typing import Any, Callable

METHOD_REGISTRY: dict[str, Callable[..., Any]] = {}

_start_time = time.time()


def rpc_method(name: str):
    def decorator(fn):
        METHOD_REGISTRY[name] = fn
        return fn
    return decorator


@rpc_method("ping")
def ping():
    return "pong"


@rpc_method("echo")
def echo(message: str = ""):
    return message


@rpc_method("system.info")
def system_info():
    return {
        "platform": platform.system(),
        "python": platform.python_version(),
        "sidecar": "0.1.0",
    }


@rpc_method("heartbeat")
def heartbeat():
    return {
        "timestamp": time.time(),
        "uptime_seconds": round(time.time() - _start_time, 1),
    }

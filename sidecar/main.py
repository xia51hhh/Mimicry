import sys
import os
from pathlib import Path
from loguru import logger

# Absolute log path anchored to this file's directory.
# Prevents the sidecar from writing logs into the caller's CWD when launched
# by Tauri (which runs the sidecar with CWD=src-tauri/).
_SIDECAR_DIR = Path(__file__).resolve().parent
_LOG_DIR = _SIDECAR_DIR / "logs"
_LOG_DIR.mkdir(exist_ok=True)
_LOG_FILE = _LOG_DIR / "mimicry-sidecar.log"

logger.remove()
logger.add(sys.stderr, level="DEBUG", format="{time:HH:mm:ss} | {level:<7} | {message}")
logger.add(str(_LOG_FILE), rotation="10 MB", retention="3 days", level="DEBUG")


def main():
    mode = _detect_mode()

    if mode == "daemon":
        logger.info("Mimicry daemon starting")
        from daemon import run_daemon
        run_daemon()
    elif mode == "mcp":
        logger.info("Mimicry MCP server starting")
        from mcp_server import run_mcp
        run_mcp()
    else:
        # Default: stdio JSON-RPC (Tauri sidecar mode)
        logger.info("Mimicry sidecar starting (stdio)")
        from rpc.server import JsonRpcServer
        import browser.actions  # registers browser RPC methods
        server = JsonRpcServer()
        browser.actions.set_server(server)
        server.run()


def _detect_mode() -> str:
    """Parse --daemon / --mcp flags from argv."""
    if "--daemon" in sys.argv:
        return "daemon"
    if "--mcp" in sys.argv:
        return "mcp"
    return "stdio"


if __name__ == "__main__":
    main()

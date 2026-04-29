import sys
import json
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="DEBUG", format="{time:HH:mm:ss} | {level:<7} | {message}")
logger.add("mimicry-sidecar.log", rotation="10 MB", retention="3 days", level="DEBUG")


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

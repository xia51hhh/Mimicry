import sys
import json
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="DEBUG", format="{time:HH:mm:ss} | {level:<7} | {message}")
logger.add("mimicry-sidecar.log", rotation="10 MB", retention="3 days", level="DEBUG")


def main():
    logger.info("Mimicry sidecar starting")
    # Lazy import: browser/actions imports camoufox which is heavy
    from rpc.server import JsonRpcServer
    import browser.actions  # registers browser RPC methods
    # DSL module is deprecated (ADR-001), do not import dsl.rpc_methods
    server = JsonRpcServer()
    browser.actions.set_server(server)
    server.run()


if __name__ == "__main__":
    main()

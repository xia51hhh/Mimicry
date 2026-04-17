import sys
import json
from loguru import logger
from rpc.server import JsonRpcServer
import browser.actions  # registers browser RPC methods
import dsl.rpc_methods  # registers DSL RPC methods

logger.remove()
logger.add(sys.stderr, level="DEBUG", format="{time:HH:mm:ss} | {level:<7} | {message}")
logger.add("mimicry-sidecar.log", rotation="10 MB", retention="3 days", level="DEBUG")


def main():
    logger.info("Mimicry sidecar starting")
    server = JsonRpcServer()
    server.run()


if __name__ == "__main__":
    main()

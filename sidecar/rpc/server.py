import sys
import json
import threading
from loguru import logger
from .methods import METHOD_REGISTRY

# Methods that should run in a background thread (non-blocking)
ASYNC_METHODS = {"workflow.execute"}


class JsonRpcServer:
    def __init__(self):
        self.methods = METHOD_REGISTRY.copy()
        self._write_lock = threading.Lock()

    def handle_request(self, raw: str) -> str | None:
        try:
            req = json.loads(raw)
        except json.JSONDecodeError:
            return json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})

        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params", {})

        handler = self.methods.get(method)
        if not handler:
            return json.dumps({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {method}"}})

        if method in ASYNC_METHODS:
            # Run in background thread, respond immediately
            def _run():
                try:
                    result = handler(**params) if isinstance(params, dict) else handler(*params)
                    resp = json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result})
                except Exception as e:
                    logger.exception(f"Error in async method {method}")
                    resp = json.dumps({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32000, "message": str(e), "data": {"error_type": type(e).__name__, "method": method}}})
                self._write(resp)

            threading.Thread(target=_run, daemon=True).start()
            # Return None = no immediate response; the thread will send it
            return None

        try:
            result = handler(**params) if isinstance(params, dict) else handler(*params)
            return json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result})
        except Exception as e:
            logger.exception(f"Error in method {method}")
            return json.dumps({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32000, "message": str(e), "data": {"error_type": type(e).__name__, "method": method}}})

    def send_notification(self, method: str, params: dict | None = None):
        """Send a JSON-RPC notification (no id, no response expected)."""
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        self._write(json.dumps(msg))

    def _write(self, response: str):
        """Thread-safe stdout write."""
        with self._write_lock:
            sys.stdout.write(response + "\n")
            sys.stdout.flush()

    def run(self):
        logger.info("JSON-RPC server listening on stdio")
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            response = self.handle_request(line)
            if response is not None:
                self._write(response)

import sys
import json
from loguru import logger
from .methods import METHOD_REGISTRY


class JsonRpcServer:
    def __init__(self):
        self.methods = METHOD_REGISTRY.copy()

    def handle_request(self, raw: str) -> str:
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

        try:
            result = handler(**params) if isinstance(params, dict) else handler(*params)
            return json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result})
        except Exception as e:
            logger.exception(f"Error in method {method}")
            return json.dumps({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32000, "message": str(e)}})

    def run(self):
        logger.info("JSON-RPC server listening on stdio")
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            response = self.handle_request(line)
            sys.stdout.write(response + "\n")
            sys.stdout.flush()

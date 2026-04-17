import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rpc.server import JsonRpcServer


def test_ping():
    server = JsonRpcServer()
    req = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"})
    resp = json.loads(server.handle_request(req))
    assert resp["result"] == "pong"
    assert resp["id"] == 1


def test_echo():
    server = JsonRpcServer()
    req = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "echo", "params": {"message": "hello"}})
    resp = json.loads(server.handle_request(req))
    assert resp["result"] == "hello"


def test_method_not_found():
    server = JsonRpcServer()
    req = json.dumps({"jsonrpc": "2.0", "id": 3, "method": "nonexistent"})
    resp = json.loads(server.handle_request(req))
    assert resp["error"]["code"] == -32601


def test_parse_error():
    server = JsonRpcServer()
    resp = json.loads(server.handle_request("not json"))
    assert resp["error"]["code"] == -32700


def test_system_info():
    server = JsonRpcServer()
    req = json.dumps({"jsonrpc": "2.0", "id": 4, "method": "system.info"})
    resp = json.loads(server.handle_request(req))
    assert "platform" in resp["result"]
    assert "python" in resp["result"]
    assert resp["result"]["sidecar"] == "0.1.0"

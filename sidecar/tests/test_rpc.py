import io
import json
import sys
import os
import time
import subprocess
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rpc.server import JsonRpcServer
from rpc.methods import rpc_method


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


def test_sidecar_startup_time():
    """Sidecar should respond to ping within 2 seconds."""
    start = time.time()
    proc = subprocess.Popen(
        [sys.executable, "-u", "main.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.join(os.path.dirname(__file__), ".."),
    )
    # Send ping
    req = '{"jsonrpc":"2.0","id":1,"method":"ping"}\n'
    proc.stdin.write(req.encode())
    proc.stdin.flush()
    line = proc.stdout.readline().decode()
    elapsed = time.time() - start
    proc.kill()
    assert '"pong"' in line
    assert elapsed < 2.0, f"Startup took {elapsed:.2f}s, expected < 2s"


def test_error_response_has_structured_fields():
    """Error responses should include error_code and context."""
    @rpc_method("test.fail")
    def fail_method():
        raise ValueError("bad input")

    server = JsonRpcServer()
    raw = '{"jsonrpc":"2.0","id":1,"method":"test.fail"}'
    resp = json.loads(server.handle_request(raw))
    assert resp["error"]["code"] == -32000
    assert "bad input" in resp["error"]["message"]
    assert "error_type" in resp["error"]["data"]
    assert resp["error"]["data"]["error_type"] == "ValueError"


def test_server_send_notification():
    """Server should be able to send JSON-RPC notifications to stdout."""
    server = JsonRpcServer()
    buf = io.StringIO()
    with patch("sys.stdout", buf):
        server.send_notification("workflow.progress", {"step": 1, "total": 5, "action": "Click"})
    line = buf.getvalue().strip()
    msg = json.loads(line)
    assert msg.get("jsonrpc") == "2.0"
    assert "id" not in msg  # notifications have no id
    assert msg["method"] == "workflow.progress"
    assert msg["params"]["step"] == 1

"""Length-prefixed JSON frame protocol for daemon ↔ CLI communication.

Wire format per message:
    4 bytes (big-endian uint32) — payload length N
    N bytes — JSON payload (UTF-8)

Message types follow JSON-RPC 2.0 structure:
    Request:      {"id": "...", "method": "...", "params": {...}}
    Response:     {"id": "...", "result": {...}}
    Error:        {"id": "...", "error": {"code": int, "message": "..."}}
    Notification: {"method": "...", "params": {...}}   (no id)
"""
from __future__ import annotations

import json
import struct
import uuid
from typing import Any

HEADER_FMT = "!I"
HEADER_SIZE = struct.calcsize(HEADER_FMT)
MAX_PAYLOAD = 64 * 1024 * 1024  # 64 MiB safety limit


# ── Frame encoding / decoding ──────────────────────────────────────

def encode_frame(msg: dict) -> bytes:
    """Encode a dict into a length-prefixed JSON frame."""
    payload = json.dumps(msg, ensure_ascii=False).encode("utf-8")
    return struct.pack(HEADER_FMT, len(payload)) + payload


def read_frame(recv_fn) -> dict | None:
    """Read exactly one frame using *recv_fn(n) -> bytes*.

    *recv_fn* must return exactly *n* bytes or raise / return b''
    on disconnect.  Returns ``None`` on clean disconnect.
    """
    header = _recv_exact(recv_fn, HEADER_SIZE)
    if header is None:
        return None
    length = struct.unpack(HEADER_FMT, header)[0]
    if length > MAX_PAYLOAD:
        raise ValueError(f"Frame too large: {length} bytes")
    payload = _recv_exact(recv_fn, length)
    if payload is None:
        return None
    return json.loads(payload.decode("utf-8"))


def _recv_exact(recv_fn, n: int) -> bytes | None:
    buf = bytearray()
    while len(buf) < n:
        chunk = recv_fn(n - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)


# ── Message constructors ───────────────────────────────────────────

def make_request(method: str, params: dict | None = None) -> tuple[str, dict]:
    """Return (request_id, request_message)."""
    req_id = uuid.uuid4().hex[:12]
    msg: dict[str, Any] = {"id": req_id, "method": method}
    if params is not None:
        msg["params"] = params
    return req_id, msg


def make_response(req_id: str, result: Any) -> dict:
    return {"id": req_id, "result": result}


def make_error(req_id: str | None, code: int, message: str, data: Any = None) -> dict:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"id": req_id, "error": err}


def make_notification(method: str, params: dict | None = None) -> dict:
    msg: dict[str, Any] = {"method": method}
    if params is not None:
        msg["params"] = params
    return msg

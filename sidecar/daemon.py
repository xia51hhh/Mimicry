"""Mimicry CLI Daemon — persistent background service.

Architecture:
    IO thread   → accepts socket connections, reads frames, pushes to cmd_queue
    Main thread → pulls from cmd_queue, dispatches to METHOD_REGISTRY, sends response

This keeps Playwright on the main thread (greenlet requirement) while
allowing concurrent control commands (pause/state) via the IO thread.
"""
from __future__ import annotations

import json
import os
import queue
import signal
import socket
import struct
import sys
import threading
import time
from pathlib import Path
from typing import Any

from loguru import logger

from rpc.protocol import (
    HEADER_FMT,
    HEADER_SIZE,
    encode_frame,
    make_error,
    make_notification,
    make_response,
    read_frame,
)

# ── Socket path / port helpers ──────────────────────────────────

def _socket_path() -> str:
    return f"/tmp/mimicry-{os.getuid()}.sock"

def _pid_path() -> str:
    return f"/tmp/mimicry-daemon-{os.getuid()}.pid"

TCP_FALLBACK_PORT = 19420

def _is_windows() -> bool:
    return sys.platform == "win32"


# ── Per-client connection handler ───────────────────────────────

class _ClientConn:
    """Wraps a connected client socket for frame I/O."""

    def __init__(self, sock: socket.socket, addr):
        self.sock = sock
        self.addr = addr
        self._write_lock = threading.Lock()

    def recv(self, n: int) -> bytes:
        return self.sock.recv(n)

    def read_frame(self) -> dict | None:
        return read_frame(self.recv)

    def send_frame(self, msg: dict):
        with self._write_lock:
            try:
                self.sock.sendall(encode_frame(msg))
            except (BrokenPipeError, OSError):
                pass

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


# ── Command item passed from IO thread → main thread ───────────

class _CmdItem:
    __slots__ = ("client", "req_id", "method", "params", "result_queue")

    def __init__(self, client: _ClientConn, req_id: str | None,
                 method: str, params: dict):
        self.client = client
        self.req_id = req_id
        self.method = method
        self.params = params
        self.result_queue: queue.Queue[dict] = queue.Queue(maxsize=1)


# ── Daemon server ──────────────────────────────────────────────

# Quick-dispatch methods that are safe to run on the IO thread
# (they only read state, never touch Playwright)
_IO_SAFE_METHODS = {
    "ping", "echo", "heartbeat", "system.info",
    "workflow.pause", "workflow.unpause", "workflow.step",
    "workflow.inject", "workflow.set_breakpoint",
    "workflow.remove_breakpoint", "workflow.list_breakpoints",
    "workflow.state", "workflow.execution_status",
    "workflow.stop",
    "daemon.status",
}


class MimicryDaemon:
    """Persistent daemon that manages browser sessions and workflow execution."""

    def __init__(self):
        self._cmd_queue: queue.Queue[_CmdItem] = queue.Queue()
        self._clients: list[_ClientConn] = []
        self._clients_lock = threading.Lock()
        self._running = True
        self._server_sock: socket.socket | None = None
        self._start_time = time.time()

    # ── Lifecycle ───────────────────────────────────────────────

    def run(self):
        """Start daemon: write PID, bind socket, enter main loop."""
        self._write_pid()
        self._setup_signals()
        self._init_rpc()
        self._bind_socket()

        # IO thread accepts connections
        io_thread = threading.Thread(target=self._io_loop, daemon=True, name="daemon-io")
        io_thread.start()

        logger.info("Daemon main loop started")
        self._main_loop()

    def _init_rpc(self):
        """Import and register all RPC methods (same as main.py)."""
        import browser.actions  # noqa: F401 — registers all RPC methods
        # Register daemon-specific methods
        from rpc.methods import METHOD_REGISTRY
        self._methods = METHOD_REGISTRY

        # Add daemon.status
        self._methods["daemon.status"] = self._cmd_daemon_status

    def _cmd_daemon_status(self):
        return {
            "running": self._running,
            "uptime": round(time.time() - self._start_time, 1),
            "clients": len(self._clients),
            "pid": os.getpid(),
        }

    def _write_pid(self):
        pid_path = _pid_path()
        with open(pid_path, "w") as f:
            f.write(str(os.getpid()))
        logger.info(f"PID file: {pid_path}")

    def _setup_signals(self):
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, sig, frame):
        logger.info(f"Signal {sig} received, shutting down")
        self._running = False

    def _bind_socket(self):
        if _is_windows():
            self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_sock.bind(("127.0.0.1", TCP_FALLBACK_PORT))
            logger.info(f"Listening on TCP 127.0.0.1:{TCP_FALLBACK_PORT}")
        else:
            path = _socket_path()
            # Remove stale socket
            if os.path.exists(path):
                os.unlink(path)
            self._server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._server_sock.bind(path)
            os.chmod(path, 0o600)  # owner-only access
            logger.info(f"Listening on UDS {path}")

        self._server_sock.listen(8)
        self._server_sock.settimeout(1.0)  # allow periodic check of _running

    # ── IO thread ───────────────────────────────────────────────

    def _io_loop(self):
        """Accept connections and spawn reader threads."""
        while self._running:
            try:
                client_sock, addr = self._server_sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            client = _ClientConn(client_sock, addr)
            with self._clients_lock:
                self._clients.append(client)
            threading.Thread(
                target=self._client_reader,
                args=(client,),
                daemon=True,
                name=f"client-{addr}",
            ).start()

    def _client_reader(self, client: _ClientConn):
        """Read frames from a client and dispatch."""
        try:
            while self._running:
                msg = client.read_frame()
                if msg is None:
                    break  # client disconnected
                self._dispatch(client, msg)
        except Exception as e:
            logger.debug(f"Client error: {e}")
        finally:
            with self._clients_lock:
                if client in self._clients:
                    self._clients.remove(client)
            client.close()

    def _dispatch(self, client: _ClientConn, msg: dict):
        """Route a request to IO-safe handler or main-thread queue."""
        req_id = msg.get("id")
        method = msg.get("method", "")
        params = msg.get("params", {})

        handler = self._methods.get(method)
        if not handler:
            client.send_frame(make_error(req_id, -32601, f"Method not found: {method}"))
            return

        if method in _IO_SAFE_METHODS:
            # Execute directly on IO thread (no Playwright calls)
            try:
                result = handler(**params) if isinstance(params, dict) else handler(*params)
                client.send_frame(make_response(req_id, result))
            except Exception as e:
                client.send_frame(make_error(req_id, -32000, str(e)))
        elif method == "shutdown":
            try:
                result = {"shutdown": True}
                client.send_frame(make_response(req_id, result))
            except Exception:
                pass
            self._running = False
        else:
            # Queue for main thread (Playwright operations)
            item = _CmdItem(client, req_id, method, params)
            self._cmd_queue.put(item)
            # Wait for result from main thread
            try:
                resp = item.result_queue.get(timeout=600)
                client.send_frame(resp)
            except queue.Empty:
                client.send_frame(make_error(req_id, -32000, "Timeout waiting for execution"))

    # ── Main thread loop ────────────────────────────────────────

    def _main_loop(self):
        """Process command queue on the main thread (Playwright-safe)."""
        while self._running:
            try:
                item = self._cmd_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            handler = self._methods.get(item.method)
            if not handler:
                item.result_queue.put(make_error(item.req_id, -32601, f"Method not found: {item.method}"))
                continue

            try:
                params = item.params
                result = handler(**params) if isinstance(params, dict) else handler(*params)
                item.result_queue.put(make_response(item.req_id, result))
            except Exception as e:
                logger.exception(f"Error in {item.method}")
                item.result_queue.put(make_error(item.req_id, -32000, str(e)))

            # Broadcast notifications for long-running ops
            # (notification wiring already handled via actions.py set_server)

        self._shutdown()

    # ── Shutdown ────────────────────────────────────────────────

    def _shutdown(self):
        logger.info("Daemon shutting down...")
        # Close all clients
        with self._clients_lock:
            for c in self._clients:
                c.close()
            self._clients.clear()

        # Close server socket
        if self._server_sock:
            self._server_sock.close()

        # Clean up socket/pid files
        if not _is_windows():
            path = _socket_path()
            if os.path.exists(path):
                os.unlink(path)
        pid_path = _pid_path()
        if os.path.exists(pid_path):
            os.unlink(pid_path)

        # Destroy browser sessions
        try:
            from browser.actions import _mgr
            _mgr.destroy_all()
        except Exception:
            pass

        logger.info("Daemon stopped")


# ── Notification bridge ─────────────────────────────────────────

class _DaemonNotifier:
    """Replaces JsonRpcServer for notification delivery over sockets."""

    def __init__(self, daemon: MimicryDaemon):
        self._daemon = daemon

    def send_notification(self, method: str, params: dict | None = None):
        msg = make_notification(method, params)
        with self._daemon._clients_lock:
            for client in list(self._daemon._clients):
                client.send_frame(msg)


# ── Entry point ─────────────────────────────────────────────────

def run_daemon():
    """Start the Mimicry daemon process."""
    daemon = MimicryDaemon()

    # Wire up notifications so actions.py can push events to clients
    notifier = _DaemonNotifier(daemon)
    import browser.actions
    browser.actions.set_server(notifier)

    daemon.run()


def is_daemon_running() -> bool:
    """Check if a daemon is already running."""
    pid_path = _pid_path()
    if not os.path.exists(pid_path):
        return False
    try:
        with open(pid_path) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)  # check process exists
        return True
    except (ValueError, ProcessLookupError, PermissionError):
        # Stale PID file
        try:
            os.unlink(pid_path)
        except OSError:
            pass
        return False


def get_daemon_pid() -> int | None:
    """Return the daemon PID or None."""
    pid_path = _pid_path()
    if not os.path.exists(pid_path):
        return None
    try:
        with open(pid_path) as f:
            return int(f.read().strip())
    except (ValueError, OSError):
        return None


def connect_daemon() -> socket.socket | None:
    """Connect to the running daemon.  Returns socket or None."""
    try:
        if _is_windows():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(("127.0.0.1", TCP_FALLBACK_PORT))
        else:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(_socket_path())
        return sock
    except (ConnectionRefusedError, FileNotFoundError, OSError):
        return None

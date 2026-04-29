"""Shared execution control state for the WorkflowExecutor.

Provides pause/resume, step-mode, breakpoints, and an inject queue
that the daemon (or any RPC caller) can manipulate while a workflow
is executing on the main thread.

Thread-safety: the executor reads these fields on the main thread;
the daemon IO thread writes them.  ``threading.Event`` is already
thread-safe.  ``inject_queue`` is guarded by ``_lock``.
"""
from __future__ import annotations

import threading
from typing import Any


class ExecutorState:
    """Mutable control state shared between executor and daemon."""

    def __init__(self):
        # set = running, clear = paused
        self.pause_event = threading.Event()
        self.pause_event.set()  # start in running state

        self._lock = threading.Lock()
        self._inject_queue: list[dict] = []
        self._breakpoints: set[str] = set()
        self.step_mode: bool = False
        self.steps_remaining: int = 0  # for step(N)
        self.current_node_id: str | None = None
        self.current_action: str | None = None

    # ── Pause / Resume ──────────────────────────────────────────

    def pause(self):
        self.pause_event.clear()

    def resume(self):
        self.step_mode = False
        self.pause_event.set()

    @property
    def paused(self) -> bool:
        return not self.pause_event.is_set()

    def wait_if_paused(self, timeout: float | None = None) -> bool:
        """Block until resumed.  Returns False if timed out."""
        return self.pause_event.wait(timeout=timeout)

    # ── Step mode ───────────────────────────────────────────────

    def step(self, count: int = 1):
        """Resume for *count* nodes, then auto-pause again."""
        self.step_mode = True
        self.steps_remaining = max(1, count)
        self.pause_event.set()

    def step_tick(self):
        """Called after each node executes in step mode."""
        if not self.step_mode:
            return
        self.steps_remaining -= 1
        if self.steps_remaining <= 0:
            self.pause_event.clear()

    # ── Breakpoints ─────────────────────────────────────────────

    def add_breakpoint(self, node_id: str):
        with self._lock:
            self._breakpoints.add(node_id)

    def remove_breakpoint(self, node_id: str):
        with self._lock:
            self._breakpoints.discard(node_id)

    def list_breakpoints(self) -> list[str]:
        with self._lock:
            return sorted(self._breakpoints)

    def hit_breakpoint(self, node_id: str) -> bool:
        with self._lock:
            return node_id in self._breakpoints

    # ── Inject queue ────────────────────────────────────────────

    def inject(self, block: dict):
        with self._lock:
            self._inject_queue.append(block)

    def drain_inject_queue(self) -> list[dict]:
        with self._lock:
            items = list(self._inject_queue)
            self._inject_queue.clear()
            return items

    @property
    def inject_queue_size(self) -> int:
        with self._lock:
            return len(self._inject_queue)

    # ── Snapshot ────────────────────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-serialisable snapshot of the control state."""
        return {
            "paused": self.paused,
            "step_mode": self.step_mode,
            "steps_remaining": self.steps_remaining,
            "current_node_id": self.current_node_id,
            "current_action": self.current_action,
            "breakpoints": self.list_breakpoints(),
            "inject_queue_size": self.inject_queue_size,
        }

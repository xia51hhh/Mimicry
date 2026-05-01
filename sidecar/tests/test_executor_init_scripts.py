"""Regression test for the launch-first init_scripts blocker.

Scenario: workflow has top-level `init_scripts` AND its first node is
`browser.launch`. The executor calls `controller.register_init_scripts(...)`
before any node runs; at that point `_context is None`, so
`_apply_init_script_to_context` early-returns. Without the launch-time flush
fix, the scripts never reach Playwright.

Two layers of test:
1. Executor-level: confirms `register_init_scripts` IS called before
   the first node executes. (Already true pre-fix; locks orchestration.)
2. Controller-level: confirms `launch()` flushes the pre-registered
   scripts to the new context's `add_init_script`. (THE blocker fix.)
"""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SIDECAR = os.path.dirname(_HERE)
if _SIDECAR not in sys.path:
    sys.path.insert(0, _SIDECAR)


# ---------------------------------------------------------------------------
# Layer 1 — executor calls register_init_scripts before nodes run
# ---------------------------------------------------------------------------


def test_executor_registers_init_scripts_before_first_node():
    from engine.executor import WorkflowExecutor

    ctrl = MagicMock()
    call_order: list[str] = []
    ctrl.register_init_scripts.side_effect = (
        lambda scripts: call_order.append("register_init_scripts")
    )

    executor = WorkflowExecutor(ctrl, humanize=False)
    workflow = {
        "init_scripts": ["window.x = 1;"],
        "nodes": [
            # Use a no-op-ish action — the executor will skip unknown actions
            # but the init_scripts registration runs unconditionally before
            # the node loop starts, which is what we're locking here.
            {"kind": "action", "action": "browser.launch", "data": {}, "settings": {}},
        ],
    }
    executor.execute(workflow)

    ctrl.register_init_scripts.assert_called_once()
    args, _ = ctrl.register_init_scripts.call_args
    assert args[0] == ["window.x = 1;"]
    # Registered as the very first controller interaction.
    assert call_order == ["register_init_scripts"]


# ---------------------------------------------------------------------------
# Layer 2 — BrowserController.launch() flushes pre-registered init_scripts
# (THE blocker — without this, scripts registered before launch are lost)
# ---------------------------------------------------------------------------


def _make_fake_camoufox(fake_context):
    """Build a class compatible with `with Camoufox(...) as ctx_or_browser`."""
    class _FakeCamoufox:
        def __init__(self, **_kw):
            self._ctx = fake_context

        def __enter__(self):
            return self._ctx

        def __exit__(self, *a):
            return False

    return _FakeCamoufox


def test_launch_flushes_pre_registered_init_scripts():
    from browser.controller import BrowserController

    ctrl = BrowserController()
    # Register before launch — at this point _context is None.
    ctrl.register_init_scripts(["window.preregistered = 1;", {"name": "named", "script": "window.named=2;"}])
    # Sanity: registry has them, but nothing applied yet.
    assert "init_1" in ctrl._init_scripts
    assert "named" in ctrl._init_scripts

    fake_context = MagicMock()
    fake_context.pages = []
    fake_context.new_page.return_value = MagicMock()
    fake_context.contexts = [fake_context]  # so _context property resolves

    # Make the fake context behave as both context and browser:
    # - persistent path: ctx_or_browser IS the context (pages, new_page)
    # - _context property: needs `_browser.contexts[0]` for non-persistent
    # We use persistent_context=True via profile.user_data_dir so
    # `self._browser = ctx_or_browser` and `_context` returns it directly.
    profile = {"user_data_dir": "/tmp/does-not-matter-mocked"}

    with patch.dict("sys.modules"):
        import types as _types
        fake_module = _types.ModuleType("camoufox.sync_api")
        fake_module.Camoufox = _make_fake_camoufox(fake_context)
        sys.modules["camoufox.sync_api"] = fake_module

        # Bypass sub-bits that touch real OS / browser
        with patch.object(BrowserController, "_inject_stealth_scripts", lambda self: None), \
             patch.object(BrowserController, "_register_page", lambda self, p: MagicMock()), \
             patch.object(BrowserController, "_get_screen_size", lambda: (1920, 1080)):
            ctrl.launch(headless=True, profile=profile)

    # The two init scripts must have been pushed onto the new context.
    applied_bodies = [c.args[0] for c in fake_context.add_init_script.call_args_list]
    assert "window.preregistered = 1;" in applied_bodies, (
        f"Pre-registered (string) init script was not flushed at launch. "
        f"Got calls: {applied_bodies}"
    )
    assert "window.named=2;" in applied_bodies, (
        f"Pre-registered (named) init script was not flushed at launch. "
        f"Got calls: {applied_bodies}"
    )

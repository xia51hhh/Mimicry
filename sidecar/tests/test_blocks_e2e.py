"""End-to-end block functionality test with real Camoufox browser.

Requires a running display server and Camoufox installed.
Skipped automatically in CI via the 'e2e' marker (see conftest.py).
"""
import os
import pytest
from browser.controller import BrowserController
from engine.executor import WorkflowExecutor


pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def browser():
    ctrl = BrowserController()
    ctrl.launch(headless=False)
    yield ctrl
    ctrl.close()


@pytest.fixture(scope="module")
def executor(browser):
    return WorkflowExecutor(browser)


class TestNavigationBlocks:
    def test_navigate_and_get_url(self, executor):
        r = executor.execute({
            "name": "t1", "nodes": [
                {"id": "1", "type": "action", "action": "Navigate", "url": "https://example.com"},
                {"id": "2", "type": "action", "action": "GetURL", "into": "$url"},
            ], "edges": [{"source": "1", "target": "2"}]
        })
        assert r["success"]
        assert "example.com" in r["variables"].get("$url", "")

    def test_go_back_forward_reload(self, executor):
        r = executor.execute({
            "name": "t4", "nodes": [
                {"id": "1", "type": "action", "action": "Navigate", "url": "https://example.com"},
                {"id": "2", "type": "action", "action": "GoBack"},
                {"id": "3", "type": "action", "action": "GoForward"},
                {"id": "4", "type": "action", "action": "Reload"},
            ], "edges": [
                {"source": "1", "target": "2"}, {"source": "2", "target": "3"},
                {"source": "3", "target": "4"},
            ]
        })
        assert r["success"]


class TestDataExtraction:
    def test_wait_get_text_set_variable(self, executor):
        r = executor.execute({
            "name": "t2", "nodes": [
                {"id": "1", "type": "action", "action": "Wait", "selector": "h1", "timeout": "3s"},
                {"id": "2", "type": "action", "action": "GetText", "selector": "h1", "into": "$h1"},
                {"id": "3", "type": "action", "action": "SetVariable", "variable": "$custom", "value": "hello"},
            ], "edges": [{"source": "1", "target": "2"}, {"source": "2", "target": "3"}]
        })
        assert r["success"]
        assert r["variables"].get("$h1") == "Example Domain"
        assert r["variables"].get("$custom") == "hello"

    def test_get_attribute(self, executor):
        r = executor.execute({
            "name": "t11", "nodes": [
                {"id": "1", "type": "action", "action": "Navigate", "url": "https://example.com"},
                {"id": "2", "type": "action", "action": "GetAttribute", "selector": "a", "attrName": "href", "into": "$href"},
            ], "edges": [{"source": "1", "target": "2"}]
        })
        assert r["success"]
        assert r["variables"].get("$href") is not None

    def test_element_exists_true_and_false(self, executor):
        r = executor.execute({
            "name": "t9", "nodes": [
                {"id": "1", "type": "action", "action": "Navigate", "url": "https://example.com"},
                {"id": "2", "type": "action", "action": "ElementExists", "selector": "h1", "into": "$exists"},
                {"id": "3", "type": "action", "action": "ElementExists", "selector": "#nonexistent_xyz_999", "into": "$notexists"},
            ], "edges": [{"source": "1", "target": "2"}, {"source": "2", "target": "3"}]
        })
        assert r["success"]
        assert r["variables"].get("$exists") is True
        assert r["variables"].get("$notexists") is False


class TestScriptAndMisc:
    def test_run_script_delay_log(self, executor):
        r = executor.execute({
            "name": "t3", "nodes": [
                {"id": "1", "type": "action", "action": "Navigate", "url": "https://example.com"},
                {"id": "2", "type": "action", "action": "RunScript", "script": "document.querySelectorAll('p').length", "into": "$pCount"},
                {"id": "3", "type": "action", "action": "Delay", "duration": "0.3s"},
                {"id": "4", "type": "action", "action": "Log", "parts": ["paragraph count"]},
            ], "edges": [{"source": "1", "target": "2"}, {"source": "2", "target": "3"}, {"source": "3", "target": "4"}]
        })
        assert r["success"]
        assert r["variables"].get("$pCount") is not None

    def test_screenshot(self, executor):
        os.makedirs("tests/screenshots", exist_ok=True)
        r = executor.execute({
            "name": "t7", "nodes": [
                {"id": "1", "type": "action", "action": "Screenshot", "filename": "tests/screenshots/e2e_test.png"},
            ], "edges": []
        })
        assert r["success"]

    def test_comment_noop(self, executor):
        r = executor.execute({
            "name": "t14", "nodes": [
                {"id": "1", "type": "action", "action": "Comment"},
            ], "edges": []
        })
        assert r["success"]

    def test_hover_and_focus(self, executor):
        r = executor.execute({
            "name": "t12", "nodes": [
                {"id": "1", "type": "action", "action": "Navigate", "url": "https://example.com"},
                {"id": "2", "type": "action", "action": "Hover", "selector": "a"},
                {"id": "3", "type": "action", "action": "Focus", "selector": "a"},
            ], "edges": [{"source": "1", "target": "2"}, {"source": "2", "target": "3"}]
        })
        assert r["success"]


class TestControlFlow:
    def test_condition_true_branch(self, executor):
        r = executor.execute({
            "name": "t5", "nodes": [
                {"id": "1", "type": "action", "action": "SetVariable", "variable": "$x", "value": "10"},
                {"id": "2", "type": "condition", "condition": 'equals("$x","10")', "children": [
                    {"id": "3", "type": "action", "action": "SetVariable", "variable": "$branch", "value": "true_branch"}
                ], "elseChildren": [
                    {"id": "4", "type": "action", "action": "SetVariable", "variable": "$branch", "value": "false_branch"}
                ]},
            ], "edges": [{"source": "1", "target": "2"}]
        })
        assert r["success"]
        assert r["variables"].get("$branch") == "true_branch"

    def test_loop_count(self, executor):
        r = executor.execute({
            "name": "t6", "nodes": [
                {"id": "1", "type": "action", "action": "SetVariable", "variable": "$sum", "value": "0"},
                {"id": "2", "type": "loop", "loopType": "count", "count": 3, "variable": "$i", "children": [
                    {"id": "3", "type": "action", "action": "SetVariable", "variable": "$sum", "value": "loop_ran"}
                ]},
            ], "edges": [{"source": "1", "target": "2"}]
        })
        assert r["success"]
        assert r["variables"].get("$sum") == "loop_ran"
        assert r["variables"].get("$i") == 2


class TestCookies:
    def test_cookie_set_get_delete(self, executor):
        r = executor.execute({
            "name": "t8", "nodes": [
                {"id": "1", "type": "action", "action": "Navigate", "url": "https://example.com"},
                {"id": "2", "type": "action", "action": "Cookie", "operation": "set",
                 "cookies": [{"name": "test_cookie", "value": "mimicry123", "url": "https://example.com"}]},
                {"id": "3", "type": "action", "action": "Cookie", "operation": "get", "name": "test_cookie", "into": "$cookie"},
                {"id": "4", "type": "action", "action": "Cookie", "operation": "delete", "name": "test_cookie"},
            ], "edges": [{"source": "1", "target": "2"}, {"source": "2", "target": "3"}, {"source": "3", "target": "4"}]
        })
        assert r["success"]


class TestPageState:
    def test_wait_for_page(self, executor):
        r = executor.execute({
            "name": "t10", "nodes": [
                {"id": "1", "type": "action", "action": "Navigate", "url": "https://example.com"},
                {"id": "2", "type": "action", "action": "WaitForPage", "state": "load", "timeout": 5000},
            ], "edges": [{"source": "1", "target": "2"}]
        })
        assert r["success"]

    def test_export_json(self, executor):
        os.makedirs("tests/screenshots", exist_ok=True)
        r = executor.execute({
            "name": "t13", "nodes": [
                {"id": "1", "type": "action", "action": "SetVariable", "variable": "$data", "value": "export_test"},
                {"id": "2", "type": "action", "action": "Export", "format": "json", "path": "tests/screenshots/export_test.json"},
            ], "edges": [{"source": "1", "target": "2"}]
        })
        assert r["success"]

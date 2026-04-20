"""End-to-end block functionality test with real Camoufox browser."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from browser.controller import BrowserController
from engine.executor import WorkflowExecutor

ctrl = BrowserController()
ctrl.launch(headless=False)
exe = WorkflowExecutor(ctrl)
results = []

def run_test(name, workflow):
    r = exe.execute(workflow)
    status = "PASS" if r["success"] else f"FAIL: {r.get('error','')}"
    results.append((name, status, r))
    print(f"  [{status}] {name}")
    return r

print("=" * 60)
print("COMPREHENSIVE BLOCK E2E TEST")
print("=" * 60)

# T1: Navigate + GetURL
r = run_test("Navigate + GetURL", {
    "name": "t1", "nodes": [
        {"id": "1", "type": "action", "action": "Navigate", "url": "https://example.com"},
        {"id": "2", "type": "action", "action": "GetURL", "into": "$url"},
    ], "edges": [{"source": "1", "target": "2"}]
})
assert "example.com" in r["variables"].get("$url", ""), f"URL mismatch: {r['variables']}"

# T2: Wait + GetText + SetVariable
r = run_test("Wait + GetText + SetVariable", {
    "name": "t2", "nodes": [
        {"id": "1", "type": "action", "action": "Wait", "selector": "h1", "timeout": "3s"},
        {"id": "2", "type": "action", "action": "GetText", "selector": "h1", "into": "$h1"},
        {"id": "3", "type": "action", "action": "SetVariable", "variable": "$custom", "value": "hello"},
    ], "edges": [{"source": "1", "target": "2"}, {"source": "2", "target": "3"}]
})
assert r["variables"].get("$h1") == "Example Domain"
assert r["variables"].get("$custom") == "hello"

# T3: RunScript + Delay + Log
r = run_test("RunScript + Delay + Log", {
    "name": "t3", "nodes": [
        {"id": "1", "type": "action", "action": "RunScript", "script": "document.querySelectorAll('p').length", "into": "$pCount"},
        {"id": "2", "type": "action", "action": "Delay", "duration": "0.3s"},
        {"id": "3", "type": "action", "action": "Log", "parts": ["paragraph count"]},
    ], "edges": [{"source": "1", "target": "2"}, {"source": "2", "target": "3"}]
})
assert r["variables"].get("$pCount") is not None

# T4: Click + GoBack + GoForward + Reload
r = run_test("Click + GoBack + GoForward + Reload", {
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

# T5: Condition (true branch)
r = run_test("Condition (true branch)", {
    "name": "t5", "nodes": [
        {"id": "1", "type": "action", "action": "SetVariable", "variable": "$x", "value": "10"},
        {"id": "2", "type": "condition", "condition": 'equals("$x","10")', "children": [
            {"id": "3", "type": "action", "action": "SetVariable", "variable": "$branch", "value": "true_branch"}
        ], "elseChildren": [
            {"id": "4", "type": "action", "action": "SetVariable", "variable": "$branch", "value": "false_branch"}
        ]},
    ], "edges": [{"source": "1", "target": "2"}]
})
assert r["variables"].get("$branch") == "true_branch"

# T6: Loop count
r = run_test("Loop count (3 iterations)", {
    "name": "t6", "nodes": [
        {"id": "1", "type": "action", "action": "SetVariable", "variable": "$sum", "value": "0"},
        {"id": "2", "type": "loop", "loopType": "count", "count": 3, "variable": "$i", "children": [
            {"id": "3", "type": "action", "action": "SetVariable", "variable": "$sum", "value": "loop_ran"}
        ]},
    ], "edges": [{"source": "1", "target": "2"}]
})
assert r["variables"].get("$sum") == "loop_ran"
assert r["variables"].get("$i") == 2  # last iteration index

# T7: Screenshot
os.makedirs("tests/screenshots", exist_ok=True)
r = run_test("Screenshot", {
    "name": "t7", "nodes": [
        {"id": "1", "type": "action", "action": "Screenshot", "filename": "tests/screenshots/e2e_test.png"},
    ], "edges": []
})
assert os.path.exists("tests/screenshots/e2e_test.png")

# T8: Cookie set + get + delete
r = run_test("Cookie set/get/delete", {
    "name": "t8", "nodes": [
        {"id": "1", "type": "action", "action": "Cookie", "operation": "set",
         "cookies": [{"name": "test_cookie", "value": "mimicry123", "url": "https://example.com"}]},
        {"id": "2", "type": "action", "action": "Cookie", "operation": "get", "name": "test_cookie", "into": "$cookie"},
        {"id": "3", "type": "action", "action": "Cookie", "operation": "delete", "name": "test_cookie"},
    ], "edges": [{"source": "1", "target": "2"}, {"source": "2", "target": "3"}]
})

# T9: ElementExists (true + false)
r = run_test("ElementExists (true + false)", {
    "name": "t9", "nodes": [
        {"id": "1", "type": "action", "action": "ElementExists", "selector": "h1", "into": "$exists"},
        {"id": "2", "type": "action", "action": "ElementExists", "selector": "#nonexistent_xyz_999", "into": "$notexists"},
    ], "edges": [{"source": "1", "target": "2"}]
})
assert r["variables"].get("$exists") is True
assert r["variables"].get("$notexists") is False

# T10: WaitForPage
r = run_test("WaitForPage", {
    "name": "t10", "nodes": [
        {"id": "1", "type": "action", "action": "WaitForPage", "state": "load", "timeout": 5000},
    ], "edges": []
})

# T11: GetAttribute
r = run_test("GetAttribute", {
    "name": "t11", "nodes": [
        {"id": "1", "type": "action", "action": "Navigate", "url": "https://example.com"},
        {"id": "2", "type": "action", "action": "GetAttribute", "selector": "a", "attrName": "href", "into": "$href"},
    ], "edges": [{"source": "1", "target": "2"}]
})
assert r["variables"].get("$href") is not None

# T12: Hover + Focus
r = run_test("Hover + Focus", {
    "name": "t12", "nodes": [
        {"id": "1", "type": "action", "action": "Hover", "selector": "a"},
        {"id": "2", "type": "action", "action": "Focus", "selector": "a"},
    ], "edges": [{"source": "1", "target": "2"}]
})

# T13: Export (JSON)
r = run_test("Export to JSON", {
    "name": "t13", "nodes": [
        {"id": "1", "type": "action", "action": "SetVariable", "variable": "$data", "value": "export_test"},
        {"id": "2", "type": "action", "action": "Export", "format": "json", "path": "tests/screenshots/export_test.json"},
    ], "edges": [{"source": "1", "target": "2"}]
})
assert os.path.exists("tests/screenshots/export_test.json")

# T14: Comment (no-op)
r = run_test("Comment (no-op)", {
    "name": "t14", "nodes": [
        {"id": "1", "type": "action", "action": "Comment"},
    ], "edges": []
})

ctrl.close()

print()
print("=" * 60)
passed = sum(1 for _, s, _ in results if s == "PASS")
total = len(results)
print(f"RESULTS: {passed}/{total} PASSED")
for name, status, _ in results:
    print(f"  {status:6s} | {name}")
print("=" * 60)

"""Generate demo workflow JSON files."""
import json
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))


def make_demo(engine_url, search_sel, engine_name):
    return {
        "name": f"Demo: {engine_name}搜索GitHub → 进入Mimicry仓库",
        "nodes": [
            {"id": "n1", "kind": "action", "action": "open", "data": {"url": engine_url}},
            {"id": "n2", "kind": "action", "action": "wait_for_page", "data": {"state": "domcontentloaded", "timeout": 30000}},
            {"id": "n3", "kind": "action", "action": "wait", "data": {"selector": search_sel, "timeout": "10s"}},
            {"id": "n4", "kind": "action", "action": "type", "data": {"selector": search_sel, "value": "github"}},
            {"id": "n5", "kind": "action", "action": "press_key", "data": {"selector": search_sel, "key": "Enter"}},
            {"id": "n6", "kind": "action", "action": "wait_for_page", "data": {"state": "domcontentloaded", "timeout": 30000}},
            {"id": "n7", "kind": "action", "action": "wait", "data": {"selector": "a[href*='github.com']", "timeout": "10s"}},
            {"id": "n8", "kind": "action", "action": "click", "data": {"selector": "a[href*='github.com']"}},
            {"id": "n9", "kind": "action", "action": "wait_for_page", "data": {"state": "domcontentloaded", "timeout": 30000}},
            {"id": "n10", "kind": "action", "action": "open", "data": {"url": "https://github.com/xia51hhh/Mimicry"}},
            {"id": "n11", "kind": "action", "action": "wait_for_page", "data": {"state": "domcontentloaded", "timeout": 30000}},
            {"id": "n12", "kind": "action", "action": "wait", "data": {"selector": "article, [data-testid='repository-container'], .repository-content, .Box-body, main", "timeout": "10s"}},
            {"id": "n13", "kind": "action", "action": "screenshot", "data": {"path": f"tests/screenshots/demo_{engine_name.lower()}_github.png"}},
        ],
    }


# Bing - use humanize:false to avoid click interception by header overlay
bing = make_demo("https://www.bing.com", "textarea#sb_form_q", "Bing")
bing["nodes"][3] = {"id": "n4", "kind": "action", "action": "type", "data": {"selector": "textarea#sb_form_q", "value": "github", "humanize": False}}
bing["nodes"][6] = {"id": "n7", "kind": "action", "action": "wait", "data": {"selector": "li.b_algo h2 a", "timeout": "10s"}}
bing["nodes"][7] = {"id": "n8", "kind": "action", "action": "click", "data": {"selector": "li.b_algo h2 a"}}

# Google - use multiple fallback selectors for result headings
google = make_demo("https://www.google.com", "textarea[name='q']", "Google")
google["nodes"][6] = {"id": "n7", "kind": "action", "action": "wait", "data": {"selector": "#rso h3, #search h3, .g h3", "timeout": "15s"}}
google["nodes"][7] = {"id": "n8", "kind": "action", "action": "click", "data": {"selector": "#rso h3, #search h3, .g h3"}}

# DuckDuckGo - use result title link selector
ddg = make_demo("https://duckduckgo.com", "input[name='q']", "DuckDuckGo")
ddg["nodes"][6] = {"id": "n7", "kind": "action", "action": "wait", "data": {"selector": "a[data-testid='result-title-a'][href*='github.com']", "timeout": "10s"}}
ddg["nodes"][7] = {"id": "n8", "kind": "action", "action": "click", "data": {"selector": "a[data-testid='result-title-a'][href*='github.com']"}}

for fname, data in [
    ("demo_bing_github.json", bing),
    ("demo_google_github.json", google),
    ("demo_duckduckgo_github.json", ddg),
]:
    with open(fname, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Wrote {fname}")

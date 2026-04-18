"""Compiler: AST <-> workflow JSON for the Mimicry Pseudocode DSL."""
from __future__ import annotations
import uuid
from . import ast_nodes as ast
from engine.action_map import to_frontend, to_backend


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _node_to_json(node: ast.Node) -> dict:
    """Convert a single AST node to a workflow JSON node."""
    match node:
        case ast.Open(url=url):
            return {"id": _uid(), "type": "action", "action": "open", "url": url}
        case ast.Back():
            return {"id": _uid(), "type": "action", "action": "back"}
        case ast.Forward():
            return {"id": _uid(), "type": "action", "action": "forward"}
        case ast.Reload():
            return {"id": _uid(), "type": "action", "action": "reload"}
        case ast.Click(selector=s):
            return {"id": _uid(), "type": "action", "action": "click", "selector": s}
        case ast.DblClick(selector=s):
            return {"id": _uid(), "type": "action", "action": "dblclick", "selector": s}
        case ast.Type(selector=s, text=t):
            return {"id": _uid(), "type": "action", "action": "type", "selector": s, "value": t}
        case ast.Clear(selector=s):
            return {"id": _uid(), "type": "action", "action": "clear", "selector": s}
        case ast.Select(selector=s, value=v):
            return {"id": _uid(), "type": "action", "action": "select", "selector": s, "value": v}
        case ast.Hover(selector=s):
            return {"id": _uid(), "type": "action", "action": "hover", "selector": s}
        case ast.Scroll(selector=s, direction=d, amount=a):
            return {"id": _uid(), "type": "action", "action": "scroll", "selector": s, "direction": d, "amount": a}
        case ast.Focus(selector=s):
            return {"id": _uid(), "type": "action", "action": "focus", "selector": s}
        case ast.Wait(selector=s, url_contains=u, time=t, timeout=to):
            w: dict = {"id": _uid(), "type": "action", "action": "wait", "timeout": to}
            if s:
                w["selector"] = s
            if u:
                w["url_contains"] = u
            if t:
                w["time"] = t
            return w
        case ast.Extract(mode=m, selector=s, attr_name=an, into=i):
            action_name = "extract_text" if m == "text" else "extract_attr" if m == "attribute" else "extract_table"
            e: dict = {"id": _uid(), "type": "action", "action": action_name, "selector": s, "into": i}
            if an:
                e["attrName"] = an
            return e
        case ast.SetVar(name=n, value=v):
            return {"id": _uid(), "type": "action", "action": "set", "variable": n, "value": v}
        case ast.If(condition=c, body=body, else_body=eb):
            node_json: dict = {
                "id": _uid(), "type": "condition", "condition": c,
                "children": [_node_to_json(n) for n in body],
            }
            if eb:
                node_json["elseChildren"] = [_node_to_json(n) for n in eb]
            return node_json
        case ast.Loop(loop_type=lt, items_selector=items, count=cnt,
                      while_condition=wc, variable=var, max=mx, body=body):
            l: dict = {
                "id": _uid(), "type": "loop", "loopType": lt,
                "children": [_node_to_json(n) for n in body],
            }
            if items:
                l["selector"] = items
            if cnt is not None:
                l["count"] = cnt
            if wc:
                l["whileCondition"] = wc
            if var:
                l["variable"] = var
            if mx is not None:
                l["max"] = mx
            return l
        case ast.Screenshot(filename=f):
            return {"id": _uid(), "type": "action", "action": "screenshot", "filename": f}
        case ast.Log(parts=p):
            return {"id": _uid(), "type": "action", "action": "log", "parts": p}
        case ast.Sleep(duration=d):
            return {"id": _uid(), "type": "action", "action": "sleep", "duration": d}
        case ast.Fail(message=m):
            return {"id": _uid(), "type": "action", "action": "fail", "message": m}
        case ast.PressKey(selector=s, key=k):
            return {"id": _uid(), "type": "action", "action": "press_key", "selector": s, "key": k}
        case ast.NewTab(url=u):
            n = {"id": _uid(), "type": "action", "action": "new_tab"}
            if u:
                n["url"] = u
            return n
        case ast.SwitchTab(tab_index=i):
            return {"id": _uid(), "type": "action", "action": "switch_tab", "tabIndex": i}
        case ast.CloseTab(tab_index=i):
            n = {"id": _uid(), "type": "action", "action": "close_tab"}
            if i is not None:
                n["tabIndex"] = i
            return n
        case ast.GetURL(into=i):
            return {"id": _uid(), "type": "action", "action": "get_url", "into": i}
        case ast.Export(format=f, path=p):
            return {"id": _uid(), "type": "action", "action": "export", "format": f, "path": p}
        case ast.RunScript(script=s, into=i):
            n = {"id": _uid(), "type": "action", "action": "run_script", "script": s}
            if i:
                n["into"] = i
            return n
        case ast.HttpRequest(url=u, method=m, body=b, into=i):
            n = {"id": _uid(), "type": "action", "action": "http_request", "url": u, "method": m}
            if b:
                n["body"] = b
            if i:
                n["into"] = i
            return n
        case ast.Comment(text=t):
            return {"id": _uid(), "type": "action", "action": "comment", "text": t}
        case ast.HandleDialog(dialog_action=a, text=t):
            n = {"id": _uid(), "type": "action", "action": "handle_dialog", "dialogAction": a}
            if t:
                n["text"] = t
            return n
        case ast.UploadFile(selector=s, file_path=p):
            return {"id": _uid(), "type": "action", "action": "upload_file", "selector": s, "filePath": p}
        case _:
            raise ValueError(f"Unknown AST node: {type(node).__name__}")


def compile_to_json(workflow: ast.Workflow) -> dict:
    """Convert a Workflow AST to the JSON format used by frontend (PascalCase actions)."""
    nodes = [_node_to_json(n) for n in workflow.body]
    # Convert backend action names to frontend PascalCase
    _convert_nodes_to_frontend(nodes)
    return {
        "name": workflow.name,
        "nodes": nodes,
    }


def _convert_nodes_to_frontend(nodes: list[dict]) -> None:
    """In-place convert action names from backend to frontend PascalCase."""
    for node in nodes:
        if "action" in node:
            node["action"] = to_frontend(node["action"])
        if "children" in node:
            _convert_nodes_to_frontend(node["children"])
        if "elseChildren" in node:
            _convert_nodes_to_frontend(node["elseChildren"])


# ── Decompiler: JSON → Pseudocode ──────────────────────────────

def _indent(text: str, level: int) -> str:
    return "  " * level + text


def _json_to_pseudo(node: dict, level: int = 1) -> list[str]:
    """Convert a single JSON node back to pseudocode lines."""
    lines: list[str] = []
    ntype = node.get("type", "action")
    action = to_backend(node.get("action", ""))

    if ntype == "condition":
        lines.append(_indent(f'IF {node["condition"]} {{', level))
        for child in node.get("children", []):
            lines.extend(_json_to_pseudo(child, level + 1))
        if node.get("elseChildren"):
            lines.append(_indent("} ELSE {", level))
            for child in node["elseChildren"]:
                lines.extend(_json_to_pseudo(child, level + 1))
        lines.append(_indent("}", level))
        return lines

    if ntype == "loop":
        lt = node.get("loopType", "items")
        parts = ["LOOP"]
        if lt == "items":
            parts.append(f'items="{node.get("selector", "")}"')
        elif lt == "count":
            parts.append(f'count={node.get("count", 1)}')
        elif lt == "while":
            parts.append(f'while={node.get("whileCondition", "")}')
        if node.get("variable"):
            parts.append(f'as={node["variable"]}')
        if node.get("max"):
            parts.append(f'max={node["max"]}')
        parts.append("{")
        lines.append(_indent(" ".join(parts), level))
        for child in node.get("children", []):
            lines.extend(_json_to_pseudo(child, level + 1))
        lines.append(_indent("}", level))
        return lines

    # Action nodes
    match action:
        case "open":
            lines.append(_indent(f'OPEN "{node.get("url", "")}"', level))
        case "back":
            lines.append(_indent("BACK", level))
        case "forward":
            lines.append(_indent("FORWARD", level))
        case "reload":
            lines.append(_indent("RELOAD", level))
        case "click":
            lines.append(_indent(f'CLICK "{node.get("selector", "")}"', level))
        case "dblclick":
            lines.append(_indent(f'DBLCLICK "{node.get("selector", "")}"', level))
        case "type":
            lines.append(_indent(f'TYPE "{node.get("selector", "")}" "{node.get("value", "")}"', level))
        case "clear":
            lines.append(_indent(f'CLEAR "{node.get("selector", "")}"', level))
        case "select":
            lines.append(_indent(f'SELECT "{node.get("selector", "")}" "{node.get("value", "")}"', level))
        case "hover":
            lines.append(_indent(f'HOVER "{node.get("selector", "")}"', level))
        case "scroll":
            s = f'SCROLL "{node.get("selector", "window")}"'
            if node.get("direction"):
                s += f' direction={node["direction"]}'
            if node.get("amount"):
                s += f' amount={node["amount"]}'
            lines.append(_indent(s, level))
        case "focus":
            lines.append(_indent(f'FOCUS "{node.get("selector", "")}"', level))
        case "wait":
            parts = ["WAIT"]
            if node.get("selector"):
                parts.append(f'selector="{node["selector"]}"')
            if node.get("url_contains"):
                parts.append(f'url_contains="{node["url_contains"]}"')
            if node.get("time"):
                parts.append(f'time={node["time"]}')
            if node.get("timeout", "5s") != "5s":
                parts.append(f'timeout={node["timeout"]}')
            lines.append(_indent(" ".join(parts), level))
        case "extract" | "extract_text" | "extract_attr" | "extract_table":
            mode = node.get("extractMode", "text")
            if action == "extract_text":
                mode = "text"
            elif action == "extract_attr":
                mode = "attr"
            elif action == "extract_table":
                mode = "table"
            sel = node.get("selector", "")
            parts = ["EXTRACT"]
            if mode == "text":
                parts.append(f'text="{sel}"')
            elif mode == "attr":
                parts.append(f'attr="{sel}" name="{node.get("attrName", "")}"')
            elif mode == "table":
                parts.append(f'table="{sel}"')
            elif mode == "count":
                parts.append(f'count="{sel}"')
            parts.append(f'into={node.get("into", "$var")}')
            lines.append(_indent(" ".join(parts), level))
        case "set":
            val = node.get("value", "")
            if isinstance(val, str):
                lines.append(_indent(f'SET {node.get("variable", "$var")} = "{val}"', level))
            else:
                lines.append(_indent(f'SET {node.get("variable", "$var")} = {val}', level))
        case "screenshot":
            lines.append(_indent(f'SCREENSHOT "{node.get("filename", "screenshot.png")}"', level))
        case "log":
            parts_str = " ".join(
                f'"{p}"' if not p.startswith("$") else p
                for p in node.get("parts", [])
            )
            lines.append(_indent(f"LOG {parts_str}", level))
        case "sleep":
            lines.append(_indent(f'SLEEP {node.get("duration", "1s")}', level))
        case "fail":
            lines.append(_indent(f'FAIL "{node.get("message", "")}"', level))
        case "press_key":
            lines.append(_indent(f'PRESS_KEY "{node.get("selector", "")}" "{node.get("key", "")}"', level))
        case "new_tab":
            url = node.get("url", "")
            lines.append(_indent(f'NEW_TAB "{url}"' if url else "NEW_TAB", level))
        case "switch_tab":
            lines.append(_indent(f'SWITCH_TAB {node.get("tabIndex", 0)}', level))
        case "close_tab":
            idx = node.get("tabIndex")
            lines.append(_indent(f'CLOSE_TAB {idx}' if idx is not None else "CLOSE_TAB", level))
        case "get_url":
            lines.append(_indent(f'GET_URL into={node.get("into", "$url")}', level))
        case "export":
            lines.append(_indent(f'EXPORT format={node.get("format", "json")} path="{node.get("path", "")}"', level))
        case "run_script":
            s = f'RUN_SCRIPT "{node.get("script", "")}"'
            if node.get("into"):
                s += f' into={node["into"]}'
            lines.append(_indent(s, level))
        case "http_request":
            s = f'HTTP_REQUEST "{node.get("url", "")}" method={node.get("method", "GET")}'
            if node.get("body"):
                s += f' body="{node["body"]}"'
            if node.get("into"):
                s += f' into={node["into"]}'
            lines.append(_indent(s, level))
        case "comment":
            lines.append(_indent(f'COMMENT "{node.get("text", "")}"', level))
        case "handle_dialog":
            s = f'HANDLE_DIALOG action={node.get("dialogAction", "accept")}'
            if node.get("text"):
                s += f' text="{node["text"]}"'
            lines.append(_indent(s, level))
        case "upload_file":
            lines.append(_indent(f'UPLOAD_FILE "{node.get("selector", "")}" "{node.get("filePath", "")}"', level))
        case _:
            lines.append(_indent(f'# Unknown action: {action}', level))
    return lines


def decompile_from_json(workflow_json: dict) -> str:
    """Convert workflow JSON back to pseudocode string."""
    name = workflow_json.get("name", "Untitled")
    lines = [f'WORKFLOW "{name}" {{']
    for node in workflow_json.get("nodes", []):
        lines.extend(_json_to_pseudo(node))
    lines.append("}")
    return "\n".join(lines)

"""Compiler: AST <-> workflow JSON for the Mimicry Pseudocode DSL."""
from __future__ import annotations
import uuid
from . import ast_nodes as ast


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
            e: dict = {"id": _uid(), "type": "action", "action": "extract", "extractMode": m, "selector": s, "into": i}
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
        case _:
            raise ValueError(f"Unknown AST node: {type(node).__name__}")


def compile_to_json(workflow: ast.Workflow) -> dict:
    """Convert a Workflow AST to the JSON format used by frontend."""
    nodes = [_node_to_json(n) for n in workflow.body]
    return {
        "name": workflow.name,
        "nodes": nodes,
    }


# ── Decompiler: JSON → Pseudocode ──────────────────────────────

def _indent(text: str, level: int) -> str:
    return "  " * level + text


def _json_to_pseudo(node: dict, level: int = 1) -> list[str]:
    """Convert a single JSON node back to pseudocode lines."""
    lines: list[str] = []
    ntype = node.get("type", "action")
    action = node.get("action", "")

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
            lines.append(_indent(f'OPEN "{node["url"]}"', level))
        case "back":
            lines.append(_indent("BACK", level))
        case "forward":
            lines.append(_indent("FORWARD", level))
        case "reload":
            lines.append(_indent("RELOAD", level))
        case "click":
            lines.append(_indent(f'CLICK "{node["selector"]}"', level))
        case "dblclick":
            lines.append(_indent(f'DBLCLICK "{node["selector"]}"', level))
        case "type":
            lines.append(_indent(f'TYPE "{node["selector"]}" "{node.get("value", "")}"', level))
        case "clear":
            lines.append(_indent(f'CLEAR "{node["selector"]}"', level))
        case "select":
            lines.append(_indent(f'SELECT "{node["selector"]}" "{node.get("value", "")}"', level))
        case "hover":
            lines.append(_indent(f'HOVER "{node["selector"]}"', level))
        case "scroll":
            s = f'SCROLL "{node["selector"]}"'
            if node.get("direction"):
                s += f' direction={node["direction"]}'
            if node.get("amount"):
                s += f' amount={node["amount"]}'
            lines.append(_indent(s, level))
        case "focus":
            lines.append(_indent(f'FOCUS "{node["selector"]}"', level))
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
        case "extract":
            mode = node.get("extractMode", "text")
            parts = ["EXTRACT"]
            if mode == "text":
                parts.append(f'text="{node["selector"]}"')
            elif mode == "attr":
                parts.append(f'attr="{node["selector"]}" name="{node.get("attrName", "")}"')
            elif mode == "count":
                parts.append(f'count="{node["selector"]}"')
            parts.append(f'into={node.get("into", "$var")}')
            lines.append(_indent(" ".join(parts), level))
        case "set":
            val = node.get("value", "")
            if isinstance(val, str):
                lines.append(_indent(f'SET {node["variable"]} = "{val}"', level))
            else:
                lines.append(_indent(f'SET {node["variable"]} = {val}', level))
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

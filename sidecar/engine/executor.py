"""Workflow execution engine: runs workflow JSON via Camoufox."""
from __future__ import annotations
import json
import re
import time
import urllib.request
import urllib.error
from loguru import logger
from browser.controller import BrowserController
from engine.action_map import to_backend


class ExecutionContext:
    """Holds variables and state during workflow execution."""

    def __init__(self):
        self.variables: dict[str, any] = {}
        self.step_index: int = 0
        self.total_steps: int = 0
        self.running: bool = False
        self.error: str | None = None

    def set_var(self, name: str, value):
        self.variables[name] = value

    def get_var(self, name: str, default=None):
        return self.variables.get(name, default)

    def resolve(self, value: str) -> str:
        """Replace $var references in a string with their values."""
        if not isinstance(value, str):
            return value
        def replacer(m):
            var_name = m.group(0)
            return str(self.variables.get(var_name, var_name))
        return re.sub(r'\$\w+', replacer, value)

    def status(self) -> dict:
        return {
            "running": self.running,
            "step": self.step_index,
            "total": self.total_steps,
            "error": self.error,
            "variables": dict(self.variables),
        }


def _parse_duration(s: str) -> float:
    """Parse duration string like '2s', '500ms', '1.5s' to seconds."""
    s = s.strip().lower()
    if s.endswith("ms"):
        return float(s[:-2]) / 1000
    if s.endswith("s"):
        return float(s[:-1])
    return float(s)


class WorkflowExecutor:
    def __init__(self, controller: BrowserController):
        self._controller = controller
        self._ctx = ExecutionContext()

    @property
    def context(self) -> ExecutionContext:
        return self._ctx

    def execute(self, workflow_json: dict) -> dict:
        """Execute a workflow from JSON. Returns execution result."""
        nodes = workflow_json.get("nodes", [])
        self._ctx = ExecutionContext()
        self._ctx.total_steps = self._count_nodes(nodes)
        self._ctx.running = True
        logger.info(f"Executing workflow: {workflow_json.get('name', 'unnamed')} ({len(nodes)} top-level nodes)")

        try:
            self._execute_nodes(nodes)
            self._ctx.running = False
            logger.info("Workflow completed successfully")
            return {"success": True, **self._ctx.status()}
        except Exception as e:
            self._ctx.error = str(e)
            self._ctx.running = False
            logger.error(f"Workflow failed: {e}")
            return {"success": False, **self._ctx.status()}

    def stop(self):
        self._ctx.running = False

    def _count_nodes(self, nodes: list[dict]) -> int:
        count = 0
        for n in nodes:
            count += 1
            count += self._count_nodes(n.get("children", []))
            count += self._count_nodes(n.get("elseChildren", []))
        return count

    def _execute_nodes(self, nodes: list[dict]):
        for node in nodes:
            if not self._ctx.running:
                return
            self._execute_node(node)
            self._ctx.step_index += 1

    def _execute_node(self, node: dict):
        ntype = node.get("type", "action")
        action = node.get("action", "")
        logger.debug(f"Step {self._ctx.step_index}: {ntype}/{action}")

        match ntype:
            case "action":
                self._execute_action(node)
            case "condition":
                self._execute_condition(node)
            case "loop":
                self._execute_loop(node)

    def _execute_action(self, node: dict):
        action = to_backend(node.get("action", ""))
        ctrl = self._controller
        ctx = self._ctx

        match action:
            case "open":
                ctrl.navigate(ctx.resolve(node["url"]))
            case "back":
                ctrl.go_back()
            case "forward":
                ctrl.go_forward()
            case "reload":
                ctrl.reload()
            case "click":
                ctrl.click(ctx.resolve(node["selector"]))
            case "dblclick":
                ctrl.dblclick(ctx.resolve(node["selector"]))
            case "type":
                ctrl.type_text(ctx.resolve(node["selector"]), ctx.resolve(node.get("value", "")))
            case "clear":
                ctrl.clear(ctx.resolve(node["selector"]))
            case "select":
                ctrl.select_option(ctx.resolve(node["selector"]), ctx.resolve(node.get("value", "")))
            case "hover":
                ctrl.hover(ctx.resolve(node["selector"]))
            case "scroll":
                sel = ctx.resolve(node.get("selector", "window"))
                ctrl.scroll(sel, node.get("direction", "down"), node.get("amount", 300))
            case "focus":
                ctrl.focus(ctx.resolve(node["selector"]))
            case "press_key":
                sel = ctx.resolve(node.get("selector", "body"))
                ctrl.press_key(sel, ctx.resolve(node["key"]))
            case "wait":
                if node.get("selector"):
                    timeout = _parse_duration(node.get("timeout", "5s")) * 1000
                    ctrl.wait_for(ctx.resolve(node["selector"]), timeout=int(timeout))
                elif node.get("url_contains"):
                    target = ctx.resolve(node["url_contains"])
                    timeout = _parse_duration(node.get("timeout", "10s"))
                    deadline = time.time() + timeout
                    while time.time() < deadline:
                        if target in ctrl.get_url():
                            break
                        time.sleep(0.2)
                elif node.get("time"):
                    time.sleep(_parse_duration(node["time"]))
            case "extract_text":
                sel = ctx.resolve(node["selector"])
                into = node.get("into", "$_result")
                ctx.set_var(into, ctrl.get_element_text(sel))
            case "extract_attr":
                sel = ctx.resolve(node["selector"])
                into = node.get("into", "$_result")
                ctx.set_var(into, ctrl.get_element_attribute(sel, node.get("attrName", "")))
            case "extract_table":
                sel = ctx.resolve(node["selector"])
                into = node.get("into", "$_result")
                ctx.set_var(into, ctrl.extract_table(sel))
            case "get_url":
                into = node.get("into", "$_result")
                ctx.set_var(into, ctrl.get_url())
            case "set":
                ctx.set_var(node["variable"], node.get("value"))
            case "screenshot":
                ctrl.screenshot(node.get("filename", "screenshot.png"))
            case "log":
                parts = node.get("parts", [])
                resolved = [ctx.resolve(p) for p in parts]
                logger.info(f"[LOG] {' '.join(str(r) for r in resolved)}")
            case "sleep":
                time.sleep(_parse_duration(node.get("duration", "1s")))
            case "fail":
                raise RuntimeError(ctx.resolve(node.get("message", "Workflow failed")))
            case "new_tab":
                ctrl.new_tab(ctx.resolve(node.get("url", "")))
            case "switch_tab":
                ctrl.switch_tab(node.get("tabIndex", 0))
            case "close_tab":
                ctrl.close_tab(node.get("tabIndex"))
            case "handle_dialog":
                ctrl.handle_dialog(
                    accept=node.get("accept", True),
                    text=ctx.resolve(node.get("text", ""))
                )
            case "upload_file":
                ctrl.upload_file(
                    ctx.resolve(node["selector"]),
                    ctx.resolve(node["filePath"])
                )
            case "run_script":
                result = ctrl.evaluate(ctx.resolve(node["script"]))
                into = node.get("into")
                if into:
                    ctx.set_var(into, result)
            case "http_request":
                url = ctx.resolve(node["url"])
                method = node.get("method", "GET").upper()
                headers = node.get("headers", {})
                body = ctx.resolve(node["body"]) if node.get("body") else None
                try:
                    timeout_val = int(node.get("timeout", 30))
                except (ValueError, TypeError):
                    timeout_val = int(_parse_duration(str(node.get("timeout", "30s"))))
                req = urllib.request.Request(
                    url, method=method,
                    data=body.encode("utf-8") if body else None,
                    headers=headers,
                )
                try:
                    with urllib.request.urlopen(req, timeout=timeout_val) as resp:
                        resp_body = resp.read().decode("utf-8", errors="replace")
                        into = node.get("into", "$_result")
                        try:
                            ctx.set_var(into, json.loads(resp_body))
                        except json.JSONDecodeError:
                            ctx.set_var(into, resp_body)
                except urllib.error.URLError as e:
                    raise RuntimeError(f"HTTP request failed: {e}")
            case "export":
                fmt = node.get("format", "json")
                path = ctx.resolve(node.get("path", "export.json"))
                data = ctx.variables
                if fmt == "csv":
                    import csv
                    import io
                    buf = io.StringIO()
                    writer = csv.writer(buf)
                    for k, v in data.items():
                        if isinstance(v, list) and v and isinstance(v[0], list):
                            for row in v:
                                writer.writerow(row)
                        else:
                            writer.writerow([k, v])
                    with open(path, "w", encoding="utf-8", newline="") as f:
                        f.write(buf.getvalue())
                else:
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                logger.info(f"Exported to {path} ({fmt})")
            case "comment":
                pass
            case _:
                logger.warning(f"Unknown action: {action}")

    def _execute_condition(self, node: dict):
        condition = self._ctx.resolve(node.get("condition", ""))
        result = self._evaluate_condition(condition)
        if result:
            self._execute_nodes(node.get("children", []))
        else:
            self._execute_nodes(node.get("elseChildren", []))

    def _evaluate_condition(self, condition: str) -> bool:
        """Evaluate a condition string against browser state."""
        ctx = self._ctx
        ctrl = self._controller

        # exists("selector")
        m = re.match(r'exists\s*\(\s*"(.+?)"\s*\)', condition)
        if m:
            try:
                return ctrl.get_element_count(m.group(1)) > 0
            except Exception:
                return False

        # visible("selector")
        m = re.match(r'visible\s*\(\s*"(.+?)"\s*\)', condition)
        if m:
            try:
                return ctrl.evaluate(f'document.querySelector("{m.group(1)}")?.offsetParent !== null')
            except Exception:
                return False

        # url_contains("path")
        m = re.match(r'url_contains\s*\(\s*"(.+?)"\s*\)', condition)
        if m:
            return m.group(1) in ctrl.get_url()

        # text("selector") == "value"
        m = re.match(r'text\s*\(\s*"(.+?)"\s*\)\s*==\s*"(.+?)"', condition)
        if m:
            try:
                actual = ctrl.get_element_text(m.group(1))
                return actual == m.group(2)
            except Exception:
                return False

        # $var == "value" or $var == number
        m = re.match(r'(\$\w+)\s*==\s*"(.+?)"', condition)
        if m:
            return str(ctx.get_var(m.group(1), "")) == m.group(2)
        m = re.match(r'(\$\w+)\s*==\s*(\d+)', condition)
        if m:
            return ctx.get_var(m.group(1)) == int(m.group(2))

        # not condition
        if condition.startswith("not "):
            return not self._evaluate_condition(condition[4:].strip())

        logger.warning(f"Unknown condition: {condition}")
        return False

    def _execute_loop(self, node: dict):
        lt = node.get("loopType", "items")
        ctx = self._ctx

        if lt == "count":
            count = node.get("count", 1)
            var = node.get("variable")
            for i in range(count):
                if not ctx.running:
                    return
                if var:
                    ctx.set_var(var, i)
                self._execute_nodes(node.get("children", []))

        elif lt == "items":
            selector = ctx.resolve(node.get("selector", ""))
            var = node.get("variable")
            max_iter = node.get("max", 100)
            elements_count = self._controller.get_element_count(selector)
            count = min(elements_count, max_iter)
            for i in range(count):
                if not ctx.running:
                    return
                if var:
                    ctx.set_var(var, f"{selector} >> :nth-match({selector}, {i+1})")
                self._execute_nodes(node.get("children", []))

        elif lt == "while":
            cond = node.get("whileCondition", "")
            max_iter = node.get("max", 100)
            iteration = 0
            while ctx.running and iteration < max_iter:
                if not self._evaluate_condition(cond):
                    break
                self._execute_nodes(node.get("children", []))
                iteration += 1

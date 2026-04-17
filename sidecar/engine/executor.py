"""Workflow execution engine: runs workflow JSON via Camoufox."""
from __future__ import annotations
import re
import time
from loguru import logger
from browser.controller import BrowserController


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
        action = node.get("action", "")
        ctrl = self._controller
        ctx = self._ctx

        match action:
            case "open":
                ctrl.navigate(ctx.resolve(node["url"]))
            case "back":
                ctrl._page.go_back()
            case "forward":
                ctrl._page.go_forward()
            case "reload":
                ctrl._page.reload()
            case "click":
                ctrl.click(ctx.resolve(node["selector"]))
            case "dblclick":
                ctrl._page.dblclick(ctx.resolve(node["selector"]))
            case "type":
                ctrl.type_text(ctx.resolve(node["selector"]), ctx.resolve(node.get("value", "")))
            case "clear":
                ctrl._page.fill(ctx.resolve(node["selector"]), "")
            case "select":
                ctrl._page.select_option(ctx.resolve(node["selector"]), ctx.resolve(node.get("value", "")))
            case "hover":
                ctrl._page.hover(ctx.resolve(node["selector"]))
            case "scroll":
                sel = ctx.resolve(node.get("selector", "window"))
                amount = node.get("amount", 300)
                direction = node.get("direction", "down")
                dy = amount if direction == "down" else -amount
                if sel == "window":
                    ctrl._page.evaluate(f"window.scrollBy(0, {dy})")
                else:
                    ctrl._page.locator(sel).scroll_into_view_if_needed()
            case "focus":
                ctrl._page.focus(ctx.resolve(node["selector"]))
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
            case "extract":
                sel = ctx.resolve(node["selector"])
                mode = node.get("extractMode", "text")
                into = node.get("into", "$_result")
                if mode == "text":
                    val = ctrl._page.locator(sel).inner_text()
                elif mode == "attr":
                    val = ctrl._page.locator(sel).get_attribute(node.get("attrName", ""))
                elif mode == "count":
                    val = ctrl._page.locator(sel).count()
                else:
                    val = None
                ctx.set_var(into, val)
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
                return ctrl._page.locator(m.group(1)).count() > 0
            except Exception:
                return False

        # visible("selector")
        m = re.match(r'visible\s*\(\s*"(.+?)"\s*\)', condition)
        if m:
            try:
                return ctrl._page.locator(m.group(1)).is_visible()
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
                actual = ctrl._page.locator(m.group(1)).inner_text()
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
            elements = self._controller._page.locator(selector)
            count = min(elements.count(), max_iter)
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

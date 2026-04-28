"""Workflow execution engine: runs workflow JSON via Camoufox."""
from __future__ import annotations
import csv
import io
import json
import os
import re
import time
import urllib.request
import urllib.error
from typing import Any
from loguru import logger
from browser.controller import BrowserController, SessionManager
from engine.action_map import to_backend

# Sandbox directory for file outputs (screenshots, exports)
_SANDBOX_DIR = os.path.abspath(os.getcwd())


def _safe_path(raw_path: str) -> str:
    """Resolve a file path and ensure it stays within the sandbox directory."""
    resolved = os.path.abspath(raw_path)
    if not resolved.startswith(_SANDBOX_DIR + os.sep) and resolved != _SANDBOX_DIR:
        raise ValueError(f"Path traversal blocked: {raw_path!r} resolves outside sandbox")
    return resolved


class ExecutionContext:
    """Holds variables and state during workflow execution."""

    def __init__(self):
        self.variables: dict[str, Any] = {}
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

    def serialize(self) -> dict:
        return {
            "variables": dict(self.variables),
            "step_index": self.step_index,
            "total_steps": self.total_steps,
            "running": self.running,
            "error": self.error,
        }

    def deserialize(self, state: dict):
        self.variables = dict(state.get("variables", {}))
        self.step_index = state.get("step_index", 0)
        self.total_steps = state.get("total_steps", 0)
        self.running = state.get("running", False)
        self.error = state.get("error")


def _parse_duration(s) -> float:
    """Parse duration string like '2s', '500ms', '1.5s' to seconds."""
    if isinstance(s, (int, float)):
        return float(s) / 1000 if s > 100 else float(s)
    s = str(s).strip().lower()
    if s.endswith("ms"):
        return float(s[:-2]) / 1000
    if s.endswith("s"):
        return float(s[:-1])
    return float(s)


class WorkflowExecutor:
    def __init__(self, controller: BrowserController | None = None, *,
                 session_manager: SessionManager | None = None,
                 default_session_id: str = "default"):
        self._controller = controller
        self._session_manager = session_manager
        self._default_session_id = default_session_id
        self._ctx = ExecutionContext()
        self.progress_callback: callable | None = None
        self.log_callback: callable | None = None

    def _get_ctrl(self, node: dict | None = None) -> BrowserController:
        """Resolve BrowserController for a node, supporting per-node session_id."""
        sid = None
        if node:
            sid = node.get("session_id")
        if sid and self._session_manager:
            return self._session_manager.get(sid)
        if sid and not self._session_manager:
            logger.warning(f"session_id='{sid}' ignored: no SessionManager available")
        if self._controller:
            return self._controller
        if self._session_manager:
            return self._session_manager.get(self._default_session_id)
        raise RuntimeError("No browser controller available")

    @property
    def context(self) -> ExecutionContext:
        return self._ctx

    def _normalize_node(self, node: dict) -> dict:
        """Normalize canonical workflow nodes into executor shape.

        Canonical shape (from frontend):
            {id, kind, action, position, data, settings, runtime}
            - action is already snake_case
            - data contains action parameters (selector, url, etc.)
            - children/elseChildren are inside data

        Legacy shape (e.g. old recorder output, hand-written JSON):
            {type, action, selector, url, ...} — flat.

        Returns a normalized dict with: id, type, action, data, settings,
        session_id, children, elseChildren.
        """
        node_id = node.get("id", "<no-id>")

        # Canonical path: node has 'kind' field
        if "kind" in node:
            data = node.get("data") if isinstance(node.get("data"), dict) else {}
            runtime = node.get("runtime") if isinstance(node.get("runtime"), dict) else {}
            raw_action = node.get("action")
            normalized: dict = {
                "id": node.get("id"),
                "type": node["kind"],
                "data": {k: v for k, v in data.items()
                         if k not in ("children", "elseChildren")},
            }
            if raw_action:
                # action may already be snake_case; to_backend is idempotent
                normalized["action"] = to_backend(raw_action)
            settings = node.get("settings")
            if settings is not None:
                normalized["settings"] = settings
            session_id = runtime.get("sessionId")
            if session_id:
                normalized["session_id"] = session_id
            for child_key in ("children", "elseChildren"):
                children = data.get(child_key)
                if isinstance(children, list):
                    normalized[child_key] = [
                        self._normalize_node(child)
                        for child in children
                        if isinstance(child, dict)
                    ]
            return normalized

        # Legacy fallback: flat format with 'type' field
        logger.debug(f"node {node_id}: legacy format detected, normalizing")
        meta_keys = {
            "id", "kind", "type", "action", "data", "settings",
            "runtime", "session_id", "sessionId", "children", "elseChildren", "selected",
        }
        src_data = node.get("data") if isinstance(node.get("data"), dict) else {}
        runtime = node.get("runtime") if isinstance(node.get("runtime"), dict) else {}

        data: dict = dict(src_data)
        for key, value in node.items():
            if key in meta_keys:
                continue
            if key in data:
                continue
            data[key] = value

        normalized = {
            "id": node.get("id"),
            "type": node.get("type", "action"),
            "data": data,
        }

        action = node.get("action") if node.get("action") is not None else src_data.get("action")
        if action is not None:
            normalized["action"] = to_backend(action)

        settings = node.get("settings") if node.get("settings") is not None else src_data.get("settings")
        if settings is not None:
            normalized["settings"] = settings

        session_id = (
            node.get("session_id")
            or node.get("sessionId")
            or src_data.get("session_id")
            or src_data.get("sessionId")
            or runtime.get("sessionId")
        )
        if session_id:
            normalized["session_id"] = session_id

        for child_key in ("children", "elseChildren"):
            children = node.get(child_key) if node.get(child_key) is not None else src_data.get(child_key)
            if isinstance(children, list):
                normalized[child_key] = [
                    self._normalize_node(child)
                    for child in children
                    if isinstance(child, dict)
                ]

        return normalized

    def execute(self, workflow_json: dict) -> dict:
        """Execute a workflow from JSON. Returns execution result."""
        nodes = [
            self._normalize_node(n)
            for n in workflow_json.get("nodes", [])
            if isinstance(n, dict)
        ]
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

    def _emit_log(self, level: str, message: str, node_id: str | None = None):
        if self.log_callback:
            self.log_callback({
                "level": level,
                "message": message,
                "nodeId": node_id,
                "step": self._ctx.step_index,
                "timestamp": time.time(),
            })

    def resume(self, workflow_json: dict, saved_state: dict) -> dict:
        """Resume a workflow from a saved execution state."""
        nodes = [
            self._normalize_node(n)
            for n in workflow_json.get("nodes", [])
            if isinstance(n, dict)
        ]
        self._ctx = ExecutionContext()
        self._ctx.deserialize(saved_state)
        self._ctx.running = True
        resume_from = self._ctx.step_index
        self._ctx.step_index = 0

        try:
            self._execute_nodes(nodes, skip_until=resume_from)
            self._ctx.running = False
            return {"success": True, **self._ctx.status()}
        except Exception as e:
            self._ctx.error = str(e)
            self._ctx.running = False
            return {"success": False, **self._ctx.status()}

    def _count_nodes(self, nodes: list[dict]) -> int:
        count = 0
        for n in nodes:
            n = self._normalize_node(n)
            count += 1
            count += self._count_nodes(n.get("children", []))
            count += self._count_nodes(n.get("elseChildren", []))
        return count

    def _execute_nodes(self, nodes: list[dict], skip_until: int = 0):
        for _i, node in enumerate(nodes):
            node = self._normalize_node(node)
            if not self._ctx.running:
                return
            if self._ctx.step_index < skip_until:
                self._ctx.step_index += 1
                self._ctx.step_index += self._count_nodes(node.get("children", []))
                self._ctx.step_index += self._count_nodes(node.get("elseChildren", []))
                continue
            self._execute_node(node)
            self._ctx.step_index += 1

    def _execute_node(self, node: dict):
        ntype = node.get("type", "action")
        action = node.get("action", "")
        logger.debug(f"Step {self._ctx.step_index}: {ntype}/{action}")

        settings = node.get("settings", {})
        on_error = settings.get("onError", "stop")
        retry_on_fail = settings.get("retryOnFail", False)
        retry_count = settings.get("retryCount", 1) if retry_on_fail else 0
        retry_interval = settings.get("retryInterval", 1000) / 1000.0

        if settings.get("disabled", False):
            logger.debug(f"Skipping disabled node: {action}")
            return

        if self.progress_callback:
            self.progress_callback({
                "step": self._ctx.step_index,
                "total": self._ctx.total_steps,
                "action": action,
                "nodeId": node.get("id"),
                "status": "running",
            })

        last_error: Exception | None = None
        attempts = 1 + retry_count
        for attempt in range(attempts):
            try:
                self._emit_log("info", f"Executing: {action}", node.get("id"))
                match ntype:
                    case "action":
                        self._execute_action(node)
                    case "condition":
                        self._execute_condition(node)
                    case "loop":
                        self._execute_loop(node)
                self._emit_log("info", f"Completed: {action}", node.get("id"))
                return  # success
            except Exception as e:
                last_error = e
                if attempt < attempts - 1:
                    logger.warning(f"Retry {attempt+1}/{retry_count} for {action}: {e}")
                    time.sleep(retry_interval)

        # All retries exhausted
        self._emit_log("error", f"Failed: {action}: {last_error}", node.get("id"))
        match on_error:
            case "continue":
                logger.warning(f"Node {action} failed, continuing: {last_error}")
            case "stop" | _:
                raise last_error

    def _execute_action(self, node: dict):
        action = node.get("action", "")
        ctrl = self._get_ctrl(node)
        ctx = self._ctx
        data = node.get("data") or {}

        match action:
            case "open":
                ctrl.navigate(ctx.resolve(data["url"]))
            case "back":
                ctrl.go_back()
            case "forward":
                ctrl.go_forward()
            case "reload":
                ctrl.reload()
            case "click":
                ctrl.click(ctx.resolve(data["selector"]))
            case "dblclick":
                ctrl.dblclick(ctx.resolve(data["selector"]))
            case "type":
                ctrl.type_text(ctx.resolve(data["selector"]), ctx.resolve(data.get("value", "")))
            case "clear":
                ctrl.clear(ctx.resolve(data["selector"]))
            case "select":
                ctrl.select_option(ctx.resolve(data["selector"]), ctx.resolve(data.get("value", "")))
            case "hover":
                ctrl.hover(ctx.resolve(data["selector"]))
            case "scroll":
                sel = ctx.resolve(data.get("selector", "window"))
                ctrl.scroll(sel, data.get("direction", "down"), data.get("amount", 300))
            case "focus":
                ctrl.focus(ctx.resolve(data["selector"]))
            case "press_key":
                sel = ctx.resolve(data.get("selector", "body"))
                ctrl.press_key(sel, ctx.resolve(data["key"]))
            case "wait":
                if data.get("selector"):
                    timeout = _parse_duration(data.get("timeout", "5s")) * 1000
                    ctrl.wait_for(ctx.resolve(data["selector"]), timeout=int(timeout))
                elif data.get("url_contains"):
                    target = ctx.resolve(data["url_contains"])
                    timeout = _parse_duration(data.get("timeout", "10s"))
                    deadline = time.time() + timeout
                    while time.time() < deadline:
                        if target in ctrl.get_url():
                            break
                        time.sleep(0.2)
                elif data.get("time"):
                    time.sleep(_parse_duration(data["time"]))
            case "extract_text":
                sel = ctx.resolve(data["selector"])
                into = data.get("into", "$_result")
                ctx.set_var(into, ctrl.get_element_text(sel))
            case "extract_attr":
                sel = ctx.resolve(data["selector"])
                into = data.get("into", "$_result")
                ctx.set_var(into, ctrl.get_element_attribute(sel, data.get("attrName", "")))
            case "extract_table":
                sel = ctx.resolve(data["selector"])
                into = data.get("into", "$_result")
                ctx.set_var(into, ctrl.extract_table(sel))
            case "get_url":
                into = data.get("into", "$_result")
                ctx.set_var(into, ctrl.get_url())
            case "set":
                ctx.set_var(data["variable"], data.get("value"))
            case "screenshot":
                ctrl.screenshot(_safe_path(data.get("filename", "screenshot.png")))
            case "log":
                parts = data.get("parts", [])
                resolved = [ctx.resolve(p) for p in parts]
                logger.info(f"[LOG] {' '.join(str(r) for r in resolved)}")
            case "sleep":
                time.sleep(_parse_duration(data.get("duration", "1s")))
            case "fail":
                raise RuntimeError(ctx.resolve(data.get("message", "Workflow failed")))
            case "new_tab":
                ctrl.new_tab(ctx.resolve(data.get("url", "")))
            case "switch_tab":
                ctrl.switch_tab(data.get("tabIndex", 0))
            case "close_tab":
                ctrl.close_tab(data.get("tabIndex"))
            case "handle_dialog":
                ctrl.handle_dialog(
                    accept=data.get("accept", True),
                    text=ctx.resolve(data.get("text", ""))
                )
            case "upload_file":
                ctrl.upload_file(
                    ctx.resolve(data["selector"]),
                    ctx.resolve(data["filePath"])
                )
            case "run_script":
                result = ctrl.evaluate(ctx.resolve(data["script"]))
                into = data.get("into")
                if into:
                    ctx.set_var(into, result)
            case "http_request":
                url = ctx.resolve(data["url"])
                if not url.startswith(("http://", "https://")):
                    raise ValueError(f"HTTP request URL scheme not allowed: {url}")
                method = data.get("method", "GET").upper()
                headers = data.get("headers", {})
                body = ctx.resolve(data["body"]) if data.get("body") else None
                try:
                    timeout_val = int(data.get("timeout", 30))
                except (ValueError, TypeError):
                    timeout_val = int(_parse_duration(str(data.get("timeout", "30s"))))
                req = urllib.request.Request(
                    url, method=method,
                    data=body.encode("utf-8") if body else None,
                    headers=headers,
                )
                try:
                    with urllib.request.urlopen(req, timeout=timeout_val) as resp:
                        resp_body = resp.read().decode("utf-8", errors="replace")
                        into = data.get("into", "$_result")
                        try:
                            ctx.set_var(into, json.loads(resp_body))
                        except json.JSONDecodeError:
                            ctx.set_var(into, resp_body)
                except urllib.error.URLError as e:
                    raise RuntimeError(f"HTTP request failed: {e}")
            case "export":
                fmt = data.get("format", "json")
                raw_path = ctx.resolve(data.get("path", "export.json"))
                path = _safe_path(raw_path)
                exported = ctx.variables
                if fmt == "csv":
                    buf = io.StringIO()
                    writer = csv.writer(buf)
                    for k, v in exported.items():
                        if isinstance(v, list) and v and isinstance(v[0], list):
                            for row in v:
                                writer.writerow(row)
                        else:
                            writer.writerow([k, v])
                    with open(path, "w", encoding="utf-8", newline="") as f:
                        f.write(buf.getvalue())
                else:
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(exported, f, ensure_ascii=False, indent=2)
                logger.info(f"Exported to {path} ({fmt})")
            case "comment":
                pass
            case "switch_frame":
                sel = ctx.resolve(data.get("selector"))
                ctrl.switch_frame(sel)
            case "wait_for_page":
                state = data.get("state", "load")
                timeout = int(data.get("timeout", 30000))
                ctrl.wait_for_page(state, timeout=timeout)
            case "cookie":
                op = data.get("operation", "get")
                if op == "get":
                    name = ctx.resolve(data.get("name", "")) or None
                    into = data.get("into", "$_result")
                    ctx.set_var(into, ctrl.get_cookie(name))
                elif op == "set":
                    cookies = data.get("cookies", [])
                    ctrl.set_cookie(cookies)
                elif op == "delete":
                    name = ctx.resolve(data.get("name", "")) or None
                    ctrl.delete_cookie(name)
            case "element_exists":
                sel = ctx.resolve(data["selector"])
                into = data.get("into", "$_result")
                try:
                    ctx.set_var(into, ctrl.get_element_count(sel) > 0)
                except Exception:
                    ctx.set_var(into, False)
            case "handle_download":
                save_path = ctx.resolve(data.get("savePath", "download"))
                timeout = int(data.get("timeout", 30000))
                result = ctrl.handle_download(save_path, timeout=timeout)
                into = data.get("into", "$_result")
                ctx.set_var(into, result)
            case "transform":
                source_var = data.get("source", "$_result")
                into = data.get("into", "$_result")
                op = data.get("operation", "identity")
                src = ctx.get_var(source_var)
                match op:
                    case "map":
                        expr = data.get("expression", "")
                        if isinstance(src, list):
                            src = [ctx.resolve(expr.replace("$item", str(item))) for item in src]
                    case "filter":
                        expr = data.get("expression", "")
                        if isinstance(src, list):
                            src = [item for item in src if item]
                    case "sort":
                        reverse = data.get("reverse", False)
                        if isinstance(src, list):
                            src = sorted(src, reverse=reverse)
                    case "flatten":
                        if isinstance(src, list):
                            flat = []
                            for item in src:
                                if isinstance(item, list):
                                    flat.extend(item)
                                else:
                                    flat.append(item)
                            src = flat
                    case "unique":
                        if isinstance(src, list):
                            seen = set()
                            result_list = []
                            for item in src:
                                key = str(item)
                                if key not in seen:
                                    seen.add(key)
                                    result_list.append(item)
                            src = result_list
                ctx.set_var(into, src)
            case "execute_workflow":
                # Sub-workflow execution - requires workflow JSON in data
                sub_wf = data.get("workflow")
                if sub_wf:
                    sub_executor = WorkflowExecutor(
                        session_manager=self._session_manager,
                        default_session_id=self._default_session_id,
                    )
                    if not self._session_manager:
                        sub_executor._controller = ctrl
                    result = sub_executor.execute(sub_wf)
                    into = data.get("into")
                    if into:
                        ctx.set_var(into, result)
                else:
                    logger.warning("ExecuteWorkflow: no workflow provided")
            case "stop":
                logger.info("Stop node reached, halting workflow")
                ctx.running = False
            case "loop_breakpoint":
                raise _LoopBreak()
            case "wait_connections":
                # In sequential execution, this is a no-op sync point
                logger.debug("WaitConnections: sync point (sequential mode)")
            case _:
                logger.warning(f"Unknown action: {action}")

    def _execute_condition(self, node: dict):
        data = node.get("data") or {}
        condition = self._ctx.resolve(data.get("condition", ""))
        result = self._evaluate_condition(condition, node)
        if result:
            self._execute_nodes(node.get("children", []))
        else:
            self._execute_nodes(node.get("elseChildren", []))

    def _evaluate_condition(self, condition: str, node: dict | None = None) -> bool:
        """Evaluate a condition string against browser state."""
        from engine.condition_parser import evaluate_condition
        return evaluate_condition(condition, self._get_ctrl(node), self._ctx)

    def _execute_loop(self, node: dict):
        data = node.get("data") or {}
        lt = data.get("loopType", "items")
        ctx = self._ctx

        if lt == "count":
            count = data.get("count", 1)
            var = data.get("variable")
            for i in range(count):
                if not ctx.running:
                    return
                if var:
                    ctx.set_var(var, i)
                try:
                    self._execute_nodes(node.get("children", []))
                except _LoopBreak:
                    break

        elif lt == "items":
            selector = ctx.resolve(data.get("selector", ""))
            var = data.get("variable")
            max_iter = data.get("max", 100)
            elements_count = self._get_ctrl(node).get_element_count(selector)
            count = min(elements_count, max_iter)
            for i in range(count):
                if not ctx.running:
                    return
                if var:
                    ctx.set_var(var, f":nth-match({selector}, {i+1})")
                try:
                    self._execute_nodes(node.get("children", []))
                except _LoopBreak:
                    break

        elif lt == "while":
            cond = data.get("whileCondition", "")
            max_iter = data.get("max", 100)
            iteration = 0
            while ctx.running and iteration < max_iter:
                if not self._evaluate_condition(cond, node):
                    break
                try:
                    self._execute_nodes(node.get("children", []))
                except _LoopBreak:
                    break
                iteration += 1

        elif lt == "elements":
            selector = ctx.resolve(data.get("selector", ""))
            var = data.get("variable")
            max_iter = data.get("max", 100)
            elements_count = self._get_ctrl(node).get_element_count(selector)
            count = min(elements_count, max_iter)
            for i in range(count):
                if not ctx.running:
                    return
                if var:
                    ctx.set_var(var, f":nth-match({selector}, {i+1})")
                try:
                    self._execute_nodes(node.get("children", []))
                except _LoopBreak:
                    break


class _LoopBreak(Exception):
    """Internal signal for loop breakpoint."""
    pass

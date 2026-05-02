"""Workflow execution engine: runs workflow JSON via Camoufox."""
from __future__ import annotations
import csv
import io
import json
import os
import random
import re
import time
import urllib.request
import urllib.error
from typing import Any
from loguru import logger
from browser.controller import BrowserController, SessionManager
from engine.action_map import to_backend
from engine.executor_state import ExecutorState

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
    _DELAY_PROFILES: dict[str, tuple[float, float]] = {
        "click": (0.3, 1.5),
        "dblclick": (0.3, 1.5),
        "type": (0.1, 0.5),
        "open": (1.0, 3.0),
        "back": (0.8, 2.0),
        "forward": (0.8, 2.0),
        "reload": (1.0, 3.0),
        "scroll": (0.5, 2.0),
        "select": (0.3, 1.0),
        "hover": (0.2, 0.8),
    }

    def __init__(self, controller: BrowserController | None = None, *,
                 session_manager: SessionManager | None = None,
                 default_session_id: str = "default",
                 humanize: bool = True,
                 delay_multiplier: float = 1.0):
        self._controller = controller
        self._session_manager = session_manager
        self._default_session_id = default_session_id
        self._humanize = humanize
        self._delay_multiplier = max(0.0, delay_multiplier)
        self._ctx = ExecutionContext()
        self._state = ExecutorState()
        self.progress_callback: callable | None = None
        self.log_callback: callable | None = None

    def _human_delay(self, action: str):
        """Insert a random delay after an action to simulate human think time."""
        if not self._humanize or self._delay_multiplier == 0.0:
            return
        low, high = self._DELAY_PROFILES.get(action, (0.3, 1.5))
        delay = random.uniform(low, high) * self._delay_multiplier
        if random.random() < 0.1:
            delay += random.uniform(1.0, 3.0) * self._delay_multiplier
        time.sleep(delay)

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

    def _resolve_selector(self, node: dict, action_fn, *args) -> Any:
        """Execute action_fn with primary selector; on failure try fallbacks.

        action_fn receives (resolved_selector, *args) as arguments.
        node['data'] may contain 'selectorFallbacks' — a list of backup selectors.
        Returns the result of action_fn on the first successful selector.
        """
        data = node.get("data") or {}
        primary = self._ctx.resolve(data.get("selector", ""))
        try:
            return action_fn(primary, *args)
        except Exception as primary_err:
            fallbacks = data.get("selectorFallbacks", [])
            if not fallbacks:
                raise
            node_id = node.get("id", "")
            for i, fb in enumerate(fallbacks):
                resolved_fb = self._ctx.resolve(fb)
                try:
                    result = action_fn(resolved_fb, *args)
                    self._emit_log(
                        "warn",
                        f"Self-heal: primary selector failed, "
                        f"fallback[{i}] '{resolved_fb}' succeeded",
                        node_id,
                    )
                    return result
                except Exception:
                    continue
            raise primary_err

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
            kind = node["kind"]
            normalized: dict = {
                "id": node.get("id"),
                "kind": kind,
                "type": kind,
                "data": {k: v for k, v in data.items()
                         if k not in ("children", "elseChildren")},
            }
            if raw_action:
                # action may already be snake_case; to_backend is idempotent
                normalized["action"] = to_backend(raw_action)
            settings = node.get("settings")
            if settings is not None:
                normalized["settings"] = settings
            session_id = runtime.get("sessionId") or node.get("session_id")
            if session_id:
                normalized["session_id"] = session_id
            for child_key in ("children", "elseChildren"):
                children = data.get(child_key) or node.get(child_key)
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

        node_type = node.get("type", "action")
        normalized = {
            "id": node.get("id"),
            "kind": node_type,
            "type": node_type,
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
        self._state = ExecutorState()
        self._ctx.total_steps = self._count_nodes(nodes)
        self._ctx.running = True
        logger.info(f"Executing workflow: {workflow_json.get('name', 'unnamed')} ({len(nodes)} top-level nodes)")

        # Apply workflow-level init scripts (Phase 3): runs before any browser action.
        init_scripts = workflow_json.get("init_scripts")
        if init_scripts and self._session_manager:
            try:
                ctrl = self._session_manager.get(self._default_session_id)
                ctrl.register_init_scripts(init_scripts)
                logger.info(f"Registered {len(init_scripts)} workflow init script(s)")
            except Exception as e:
                logger.warning(f"Failed to register workflow init_scripts: {e}")
        elif init_scripts and self._controller:
            try:
                self._controller.register_init_scripts(init_scripts)
            except Exception as e:
                logger.warning(f"Failed to register workflow init_scripts: {e}")

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

    @property
    def state(self) -> ExecutorState:
        return self._state

    def stop(self):
        self._ctx.running = False
        self._state.resume()  # unblock pause gate so loop can exit

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
        timeout_ms = settings.get("timeout", 0)
        timeout_sec = timeout_ms / 1000.0 if timeout_ms > 0 else 0

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

        # ── Pause gate ──
        self._state.current_node_id = node.get("id")
        self._state.current_action = action
        self._state.wait_if_paused()
        if not self._ctx.running:
            return

        # ── Breakpoint check ──
        node_id = node.get("id", "")
        if node_id and self._state.hit_breakpoint(node_id):
            self._emit_log("info", f"Breakpoint hit: {node_id}", node_id)
            self._state.pause()
            self._state.wait_if_paused()
            if not self._ctx.running:
                return

        # ── Drain inject queue ──
        for injected in self._state.drain_inject_queue():
            self._emit_log("info", f"Injecting: {injected.get('action', '?')}", node_id)
            self._execute_action(self._normalize_node(injected))
            if not self._ctx.running:
                return

        last_error: Exception | None = None
        attempts = 1 + retry_count
        for attempt in range(attempts):
            try:
                self._emit_log("info", f"Executing: {action}", node.get("id"))
                if timeout_sec > 0:
                    self._execute_with_timeout(node, ntype, timeout_sec)
                else:
                    self._dispatch_node(node, ntype)
                self._emit_log("info", f"Completed: {action}", node.get("id"))
                if ntype == "action":
                    self._human_delay(action)
                self._state.step_tick()
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
            case "fallback":
                fallback_nodes = node.get("data", {}).get("fallbackNodes", [])
                if fallback_nodes:
                    self._emit_log("info", f"Running fallback for {action}", node_id)
                    self._execute_nodes(fallback_nodes)
                else:
                    logger.warning(f"Node {action} failed, no fallback nodes defined")
            case "stop" | _:
                raise last_error

    def _dispatch_node(self, node: dict, ntype: str):
        """Dispatch execution based on node type."""
        match ntype:
            case "action":
                self._execute_action(node)
            case "condition":
                self._execute_condition(node)
            case "loop":
                self._execute_loop(node)

    def _execute_with_timeout(self, node: dict, ntype: str, timeout_sec: float):
        """Execute a node with a timeout by setting Playwright page default timeout."""
        timeout_ms = int(timeout_sec * 1000)
        ctrl = self._get_ctrl(node)
        page = getattr(ctrl, "_page", None)
        original_timeout = None
        if page is not None:
            try:
                original_timeout = page._timeout_settings._timeout  # internal
            except Exception:
                original_timeout = 30000
            page.set_default_timeout(timeout_ms)
        try:
            self._dispatch_node(node, ntype)
        finally:
            if page is not None and original_timeout is not None:
                page.set_default_timeout(original_timeout)

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
                self._resolve_selector(node, ctrl.click)
            case "dblclick":
                self._resolve_selector(node, ctrl.dblclick)
            case "type":
                h = self._humanize if data.get("humanize") is None else data["humanize"]
                self._resolve_selector(node, lambda sel, v, hm: ctrl.type_text(sel, v, humanize=hm), ctx.resolve(data.get("value", "")), h)
            case "clear":
                self._resolve_selector(node, ctrl.clear)
            case "select":
                self._resolve_selector(node, lambda sel, v: ctrl.select_option(sel, v, humanize=self._humanize), ctx.resolve(data.get("value", "")))
            case "hover":
                self._resolve_selector(node, ctrl.hover)
            case "focus":
                self._resolve_selector(node, ctrl.focus)
            case "scroll":
                sel = ctx.resolve(data.get("selector", "window"))
                ctrl.scroll(sel, data.get("direction", "down"), data.get("amount", 300), humanize=self._humanize)
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
                # Gradient matching: tabId → seq → urlOrigin+urlPath → title → legacy index
                match_hints = {}
                if "tabId" in data:
                    match_hints["tabId"] = data["tabId"]
                if "seq" in data:
                    match_hints["seq"] = int(data["seq"])
                if "urlOrigin" in data:
                    match_hints["urlOrigin"] = ctx.resolve(data["urlOrigin"])
                if "urlPath" in data:
                    match_hints["urlPath"] = ctx.resolve(data["urlPath"])
                if "title" in data:
                    match_hints["title"] = ctx.resolve(data["title"])
                if match_hints:
                    ctrl.switch_tab(match_hints)
                else:
                    ctrl.switch_tab(data.get("tabIndex", 0))
            case "close_tab":
                target = data.get("tabId") or data.get("tabIndex")
                ctrl.close_tab(target)
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
                        humanize=self._humanize,
                        delay_multiplier=self._delay_multiplier,
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
            case "loop_elements":
                # LoopElements is handled by _execute_loop (kind=loop, loopType=elements)
                # If it arrives here as an action, treat as a warning
                logger.warning("loop_elements should be kind=loop, not kind=action")
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

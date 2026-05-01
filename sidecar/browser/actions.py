import json
import threading
from loguru import logger

from rpc.methods import rpc_method
from browser.controller import SessionManager
from browser.recorder import RecordingEngine
from browser.env_check import CamoufoxEnv
from engine.executor import WorkflowExecutor

_mgr = SessionManager()
_recorders: dict[str, RecordingEngine] = {}
_executors: dict[str, WorkflowExecutor] = {}
_aux_lock = threading.Lock()

_server = None

# Ensure browser sessions are cleaned up on exit
import atexit
atexit.register(lambda: _mgr.destroy_all())


def set_server(server):
    global _server
    _server = server
    # Propagate server to env_check for thread-safe notifications
    from browser.env_check import set_server as env_set_server
    env_set_server(server)

    # Wire up session disconnect notifications
    def _on_session_disconnected(session_id):
        if _server:
            _server.send_notification("browser.session_closed", {"session_id": session_id})
    _mgr._on_session_disconnected = _on_session_disconnected


def _get_recorder(session_id: str) -> RecordingEngine:
    with _aux_lock:
        if session_id not in _recorders:
            ctrl = _mgr.get(session_id)
            _recorders[session_id] = RecordingEngine(ctrl)
        return _recorders[session_id]


def _get_executor(session_id: str) -> WorkflowExecutor:
    with _aux_lock:
        if session_id not in _executors:
            _executors[session_id] = WorkflowExecutor(
                session_manager=_mgr,
                default_session_id=session_id,
            )
        return _executors[session_id]


@rpc_method(
    "browser.detect_screens",
    description="Detect connected monitors and return their logical resolutions. Use before launching with a custom viewport to pick a screen size that matches a real display.",
)
def browser_detect_screens():
    """Detect connected monitors and return logical resolutions."""
    from browser.controller import BrowserController
    return BrowserController.get_monitors()


@rpc_method(
    "browser.launch",
    description="Launch a Camoufox browser session. Use this before any other browser action.",
    param_descriptions={
        "session_id": "Identifier for this browser session. Use 'default' for single-session use, or a unique name when running multiple browsers concurrently.",
        "headless": "If true, run without a visible window. Default false (visible window) for interactive use; set true for server/CI environments.",
        "proxy": "Optional proxy config dict: {server: 'http://...', username?: str, password?: str}. Supports http/https/socks5 schemes.",
        "profile": "Optional profile config dict with keys like user_data_dir, os, locale, geoip, block_webrtc, etc. Persists cookies/storage between sessions when user_data_dir is set.",
    },
)
def browser_launch(session_id: str = "default", headless: bool = False,
                   proxy: dict | None = None, profile: dict | None = None):
    logger.info(f"browser.launch: session_id={session_id}, headless={headless}, profile_keys={list(profile.keys()) if profile else None}")
    ctrl = _mgr.create(session_id, headless=headless, proxy=proxy, profile=profile)
    # Send launch warnings as notifications to frontend
    if ctrl.launch_warnings and _server:
        for warning in ctrl.launch_warnings:
            _server.send_notification("browser.warning", {"message": warning})
    status = ctrl.status()
    logger.info(f"browser.launch success: {status}")
    return {"session_id": session_id, "warnings": ctrl.launch_warnings or None, **status}


@rpc_method(
    "browser.close",
    description="Close a browser session and free its resources.",
    param_descriptions={
        "session_id": "The session_id used at launch. Defaults to 'default'.",
    },
)
def browser_close(session_id: str = "default"):
    with _aux_lock:
        _recorders.pop(session_id, None)
        _executors.pop(session_id, None)
    _mgr.destroy(session_id)
    return {"closed": True, "session_id": session_id}


@rpc_method(
    "browser.list_sessions",
    description="List all active browser session IDs. Use to discover what sessions are running before issuing per-session commands.",
)
def browser_list_sessions():
    return {"sessions": _mgr.list_sessions()}


@rpc_method(
    "browser.navigate",
    description="Navigate the active page to a URL.",
    param_descriptions={
        "url": "Fully-qualified URL (e.g. 'https://example.com'). Relative paths are not supported.",
        "session_id": "The session_id used at launch. Defaults to 'default'.",
    },
)
def browser_navigate(url: str, session_id: str = "default"):
    ctrl = _mgr.get(session_id)
    ctrl.navigate(url)
    return {"url": ctrl.get_url()}


@rpc_method(
    "browser.click",
    description="Click an element matched by a CSS selector.",
    param_descriptions={
        "selector": "CSS selector (e.g. 'button#submit', 'a[href*=\"login\"]'). For text-based matching, prefer Playwright text= or role= selectors via browser.evaluate.",
        "session_id": "The session_id used at launch. Defaults to 'default'.",
        "force": "If true, bypass actionability checks (visibility, stable position). Use sparingly — usually a sign the selector is wrong.",
    },
)
def browser_click(selector: str, session_id: str = "default", force: bool = False):
    _mgr.get(session_id).click(selector, force=force)
    return {"clicked": selector}


@rpc_method(
    "browser.type",
    description="Type text into an input/textarea element.",
    param_descriptions={
        "selector": "CSS selector for the input/textarea element.",
        "text": "Text to type. Newlines are sent as Enter key presses.",
        "session_id": "The session_id used at launch. Defaults to 'default'.",
        "humanize": "If true, simulate human-like typing with delays between characters. Default true; set false for fastest input or when stealth is not needed.",
    },
)
def browser_type(selector: str, text: str, session_id: str = "default", humanize: bool = True):
    _mgr.get(session_id).type_text(selector, text, humanize=humanize)
    return {"typed": selector}


@rpc_method(
    "browser.wait",
    description="Wait for a CSS selector to appear in the DOM.",
    param_descriptions={
        "selector": "CSS selector to wait for.",
        "timeout": "Max wait time in milliseconds. Default 5000ms (5s).",
        "session_id": "The session_id used at launch. Defaults to 'default'.",
    },
)
def browser_wait(selector: str, timeout: int = 5000, session_id: str = "default"):
    _mgr.get(session_id).wait_for(selector, timeout=timeout)
    return {"found": selector}


@rpc_method(
    "browser.screenshot",
    description="Capture a screenshot of the current page.",
    param_descriptions={
        "path": "File path to save the PNG. Default 'screenshot.png' in the working directory.",
        "session_id": "The session_id used at launch. Defaults to 'default'.",
    },
)
def browser_screenshot(path: str = "screenshot.png", session_id: str = "default"):
    return {"path": _mgr.get(session_id).screenshot(path)}


@rpc_method(
    "browser.status",
    description="Return browser session status: connected, current URL, number of pages.",
    param_descriptions={
        "session_id": "The session_id used at launch. Defaults to 'default'.",
    },
)
def browser_status(session_id: str = "default"):
    try:
        return _mgr.get(session_id).status()
    except RuntimeError:
        return {"connected": False, "url": None, "pages": 0}


@rpc_method(
    "browser.dblclick",
    description="Double-click an element matched by a CSS selector. Use for opening items, selecting words, or any UI that responds to dblclick.",
    param_descriptions={
        "selector": "CSS selector identifying the element (e.g. '#row-3', '.file-icon').",
        "session_id": "Browser session ID; defaults to 'default' for the primary session.",
    },
)
def browser_dblclick(selector: str, session_id: str = "default"):
    _mgr.get(session_id).dblclick(selector)
    return {"dblclicked": selector}


@rpc_method(
    "browser.hover",
    description="Hover the mouse over an element to trigger hover-only UI (tooltips, dropdown menus).",
    param_descriptions={
        "selector": "CSS selector of the element to hover (e.g. 'nav .menu-item').",
        "session_id": "Browser session ID; defaults to 'default' for the primary session.",
    },
)
def browser_hover(selector: str, session_id: str = "default"):
    _mgr.get(session_id).hover(selector)
    return {"hovered": selector}


@rpc_method(
    "browser.select_option",
    description="Select an <option> by value inside a native <select> element.",
    param_descriptions={
        "selector": "CSS selector of the <select> element (e.g. 'select[name=country]').",
        "value": "The option's value attribute to select (e.g. 'US'). For multi-select, pass a single value per call.",
        "session_id": "Browser session ID; defaults to 'default' for the primary session.",
    },
)
def browser_select_option(selector: str, value: str, session_id: str = "default"):
    _mgr.get(session_id).select_option(selector, value)
    return {"selected": selector, "value": value}


@rpc_method(
    "browser.clear",
    description="Clear the contents of an input or textarea. Use before typing replacement text.",
    param_descriptions={
        "selector": "CSS selector of the input/textarea to clear.",
        "session_id": "Browser session ID; defaults to 'default' for the primary session.",
    },
)
def browser_clear(selector: str, session_id: str = "default"):
    _mgr.get(session_id).clear(selector)
    return {"cleared": selector}


@rpc_method(
    "browser.focus",
    description="Move keyboard focus to an element. Use before sending key presses that target a specific input.",
    param_descriptions={
        "selector": "CSS selector of the element to focus.",
        "session_id": "Browser session ID; defaults to 'default' for the primary session.",
    },
)
def browser_focus(selector: str, session_id: str = "default"):
    _mgr.get(session_id).focus(selector)
    return {"focused": selector}


@rpc_method(
    "browser.go_back",
    description="Navigate back in browser history (equivalent to clicking the back button).",
    param_descriptions={
        "session_id": "Browser session ID; defaults to 'default' for the primary session.",
    },
)
def browser_go_back(session_id: str = "default"):
    _mgr.get(session_id).go_back()
    return {"navigated": "back"}


@rpc_method(
    "browser.go_forward",
    description="Navigate forward in browser history.",
    param_descriptions={
        "session_id": "Browser session ID; defaults to 'default' for the primary session.",
    },
)
def browser_go_forward(session_id: str = "default"):
    _mgr.get(session_id).go_forward()
    return {"navigated": "forward"}


@rpc_method(
    "browser.reload",
    description="Reload the current page (equivalent to F5 / Ctrl+R).",
    param_descriptions={
        "session_id": "Browser session ID; defaults to 'default' for the primary session.",
    },
)
def browser_reload(session_id: str = "default"):
    _mgr.get(session_id).reload()
    return {"reloaded": True}


@rpc_method(
    "browser.press_key",
    description="Press a keyboard key while focused on a selector (or body). Use for Enter, Escape, Tab, arrow keys, etc.",
    param_descriptions={
        "selector": "CSS selector to focus before key press. Default 'body' for global key.",
        "key": "Key name per Playwright spec (e.g. 'Enter', 'Escape', 'ArrowDown', 'Control+A').",
        "session_id": "The session_id used at launch. Defaults to 'default'.",
    },
)
def browser_press_key(selector: str = "body", key: str = "", session_id: str = "default"):
    _mgr.get(session_id).press_key(selector, key)
    return {"pressed": key, "selector": selector}


@rpc_method(
    "browser.scroll",
    description="Scroll the page or a specific element.",
    param_descriptions={
        "selector": "CSS selector of the scrollable element, or 'window' for page scroll. Default 'window'.",
        "direction": "Scroll direction: 'up', 'down', 'left', or 'right'. Default 'down'.",
        "amount": "Pixels to scroll. Default 300.",
        "session_id": "The session_id used at launch. Defaults to 'default'.",
    },
)
def browser_scroll(selector: str = "window", direction: str = "down",
                   amount: int = 300, session_id: str = "default"):
    _mgr.get(session_id).scroll(selector, direction, amount)
    return {"scrolled": selector, "direction": direction}


@rpc_method(
    "browser.evaluate",
    description="Execute a JavaScript expression in the page context and return the result.",
    param_descriptions={
        "expression": "JavaScript expression. Use 'document.title' or '() => Array.from(document.querySelectorAll(...)).map(e => e.innerText)' style.",
        "session_id": "The session_id used at launch. Defaults to 'default'.",
    },
)
def browser_evaluate(expression: str, session_id: str = "default"):
    return {"result": _mgr.get(session_id).evaluate(expression)}


@rpc_method(
    "browser.get_text",
    description="Extract the visible text content of an element.",
    param_descriptions={
        "selector": "CSS selector of the target element.",
        "session_id": "The session_id used at launch. Defaults to 'default'.",
    },
)
def browser_get_text(selector: str, session_id: str = "default"):
    return {"text": _mgr.get(session_id).get_element_text(selector)}


@rpc_method(
    "browser.get_attribute",
    description="Read an HTML attribute value from an element (e.g. href, src, data-id).",
    param_descriptions={
        "selector": "CSS selector of the target element.",
        "attr": "Attribute name to read (e.g. 'href', 'src', 'value', 'data-id').",
        "session_id": "The session_id used at launch. Defaults to 'default'.",
    },
)
def browser_get_attribute(selector: str, attr: str, session_id: str = "default"):
    return {"value": _mgr.get(session_id).get_element_attribute(selector, attr)}


@rpc_method(
    "browser.get_element_count",
    description="Count how many elements match a selector. Use to verify a list rendered or to assert presence/absence.",
    param_descriptions={
        "selector": "CSS selector to count matches for (e.g. 'tr.row', '.product-card').",
        "session_id": "Browser session ID; defaults to 'default' for the primary session.",
    },
)
def browser_get_element_count(selector: str, session_id: str = "default"):
    return {"count": _mgr.get(session_id).get_element_count(selector)}


@rpc_method(
    "browser.extract_table",
    description="Extract an HTML <table> as a list of dict rows keyed by header. Use to scrape tabular data without writing JS.",
    param_descriptions={
        "selector": "CSS selector of the <table> element (e.g. 'table.results').",
        "session_id": "Browser session ID; defaults to 'default' for the primary session.",
    },
)
def browser_extract_table(selector: str, session_id: str = "default"):
    return {"data": _mgr.get(session_id).extract_table(selector)}


@rpc_method(
    "browser.upload_file",
    description="Upload a local file via an <input type=file> element.",
    param_descriptions={
        "selector": "CSS selector of the file input (e.g. 'input[type=file]').",
        "file_path": "Absolute local path to the file to upload.",
        "session_id": "Browser session ID; defaults to 'default' for the primary session.",
    },
)
def browser_upload_file(selector: str, file_path: str, session_id: str = "default"):
    _mgr.get(session_id).upload_file(selector, file_path)
    return {"uploaded": selector, "file": file_path}


@rpc_method(
    "browser.new_tab",
    description="Open a new browser tab and optionally navigate it to a URL. Returns the new tab's stable id and updated session status.",
    param_descriptions={
        "url": "Optional URL to load in the new tab. If empty, opens a blank tab.",
        "session_id": "Browser session ID; defaults to 'default' for the primary session.",
    },
)
def browser_new_tab(url: str = "", session_id: str = "default"):
    ctrl = _mgr.get(session_id)
    tab_info = ctrl.new_tab(url)
    return {**ctrl.status(), "tab": tab_info}


@rpc_method(
    "browser.switch_tab",
    description=(
        "Switch the active tab in a browser session. `target` may be a tab id, "
        "an integer index, or a substring of url/title; additional free-form "
        "hint kwargs (e.g. url_origin, url_path, title) are accepted at runtime "
        "for fuzzy matching but are not part of the MCP schema."
    ),
    param_descriptions={
        "target": "Tab id (int), index (int), or url/title substring (str). Optional when hint kwargs identify the tab.",
        "session_id": "Browser session id; defaults to 'default'.",
    },
)
def browser_switch_tab(target=None, session_id: str = "default", **match_hints):
    ctrl = _mgr.get(session_id)
    # Accept legacy 'index' param for backward compat
    if target is None and "index" in match_hints:
        target = match_hints.pop("index")
    tab_info = ctrl.switch_tab(target, **match_hints)
    return {**ctrl.status(), "tab": tab_info}


@rpc_method(
    "browser.close_tab",
    description="Close a tab by id, index, or url/title substring. Closes the active tab if no target is given.",
    param_descriptions={
        "target": "Tab id (int), index (int), or url/title substring (str). Optional — if omitted, closes the currently active tab.",
        "session_id": "Browser session ID; defaults to 'default' for the primary session.",
    },
)
def browser_close_tab(target=None, session_id: str = "default"):
    ctrl = _mgr.get(session_id)
    ctrl.close_tab(target)
    return ctrl.status()


@rpc_method(
    "browser.get_tabs",
    description="List all open tabs (id, url, title) and the currently active tab. Use to discover tab ids before switch_tab/close_tab.",
    param_descriptions={
        "session_id": "Browser session ID; defaults to 'default' for the primary session.",
    },
)
def browser_get_tabs(session_id: str = "default"):
    ctrl = _mgr.get(session_id)
    return {"tabs": ctrl.get_all_tabs(), "current": ctrl.get_current_tab_info()}


@rpc_method(
    "browser.handle_dialog",
    description="Pre-arm a handler for the next JavaScript dialog (alert/confirm/prompt). Call this BEFORE the action that triggers the dialog.",
    param_descriptions={
        "accept": "If true, click OK/Accept; if false, click Cancel/Dismiss. Default true.",
        "text": "Optional text to enter into a prompt dialog. Ignored for alert/confirm.",
        "session_id": "Browser session ID; defaults to 'default' for the primary session.",
    },
)
def browser_handle_dialog(accept: bool = True, text: str = "", session_id: str = "default"):
    _mgr.get(session_id).handle_dialog(accept, text)
    return {"dialog_handler_set": True}


@rpc_method(
    "recording.start",
    description="Start recording user actions in the browser as workflow events (clicks, typing, navigation, tab switches). Use to author a workflow by demonstration: call this, perform actions in the browser, then call recording.stop to get JSON nodes.",
    param_descriptions={
        "session_id": "Browser session ID to attach the recorder to. Defaults to 'default'.",
    },
)
def recording_start(session_id: str = "default"):
    recorder = _get_recorder(session_id)

    def on_event(event):
        if _server:
            _server.send_notification("recording.event", {**event, "session_id": session_id})
    recorder.event_callback = on_event
    recorder.start()
    return {"recording": True, "session_id": session_id}


@rpc_method(
    "recording.stop",
    description="Stop the recorder and return the captured events plus their conversion to workflow JSON nodes. Use the 'nodes' array as the workflow body.",
    param_descriptions={
        "session_id": "Browser session ID whose recorder to stop. Defaults to 'default'.",
    },
)
def recording_stop(session_id: str = "default"):
    recorder = _get_recorder(session_id)
    events = recorder.stop()
    nodes = RecordingEngine.events_to_workflow_nodes(events)
    return {"events": len(events), "nodes": nodes}


@rpc_method(
    "recording.poll",
    description="Poll new events captured since the last poll without stopping the recording. Use to stream a live preview of what is being recorded.",
    param_descriptions={
        "session_id": "Browser session ID whose recorder to poll. Defaults to 'default'.",
    },
)
def recording_poll(session_id: str = "default"):
    recorder = _get_recorder(session_id)
    new_events = recorder.poll_new_events()
    nodes = RecordingEngine.events_to_workflow_nodes(new_events) if new_events else []
    return {"events": new_events, "nodes": nodes}


@rpc_method(
    "recording.status",
    description="Check whether recording is active for a session.",
    param_descriptions={
        "session_id": "Browser session ID to check. Defaults to 'default'.",
    },
)
def recording_status(session_id: str = "default"):
    if session_id in _recorders:
        return {"recording": _recorders[session_id].is_recording}
    return {"recording": False}


@rpc_method(
    "workflow.execute",
    description="Run a workflow JSON (kind+action+data+settings node graph) end-to-end. Use to execute a recorded or hand-authored workflow. Pair with workflow.pause / workflow.set_breakpoint / workflow.step to debug.",
    param_descriptions={
        "workflow": "Workflow JSON object: {nodes: [...], edges: [...]} per the block-schema contract. Required.",
        "session_id": "Browser session ID to run against. Defaults to 'default'.",
        "humanize": "If true, add human-like delays during typing/clicking. Default true. Set false for fastest deterministic runs.",
        "delay_multiplier": "Multiplier on built-in delays (1.0 = normal, 2.0 = slower for debugging, 0.5 = faster). Default 1.0.",
    },
)
def workflow_execute(workflow: dict | None = None, session_id: str = "default",
                     humanize: bool = True, delay_multiplier: float = 1.0):
    if not workflow:
        return {"success": False, "error": "No workflow provided"}
    # Create a fresh executor each time with the caller's humanize settings
    with _aux_lock:
        executor = WorkflowExecutor(
            session_manager=_mgr,
            default_session_id=session_id,
            humanize=humanize,
            delay_multiplier=delay_multiplier,
        )
        _executors[session_id] = executor

    def on_progress(event):
        if _server:
            _server.send_notification("workflow.progress", {**event, "session_id": session_id})

    def on_log(entry):
        if _server:
            _server.send_notification("workflow.log", {**entry, "session_id": session_id})

    executor.progress_callback = on_progress
    executor.log_callback = on_log
    return executor.execute(workflow)


@rpc_method(
    "workflow.resume",
    description="Resume a previously interrupted workflow from a serialized execution state. Use after a crash, or to continue from a checkpoint produced by workflow.state.",
    param_descriptions={
        "workflow": "The same workflow JSON that was originally executed.",
        "state": "Execution state snapshot (as returned by workflow.state) describing which step to resume from and the variable bindings.",
        "session_id": "Browser session ID. Defaults to 'default'.",
    },
)
def workflow_resume(workflow: dict, state: dict, session_id: str = "default"):
    executor = _get_executor(session_id)

    def on_progress(event):
        if _server:
            _server.send_notification("workflow.progress", {**event, "session_id": session_id})

    def on_log(entry):
        if _server:
            _server.send_notification("workflow.log", {**entry, "session_id": session_id})

    executor.progress_callback = on_progress
    executor.log_callback = on_log
    return executor.resume(workflow, state)


@rpc_method(
    "workflow.stop",
    description="Stop the running workflow execution immediately. Pending steps are abandoned; the browser session remains open.",
    param_descriptions={
        "session_id": "Browser session ID whose executor to stop. Defaults to 'default'.",
    },
)
def workflow_stop(session_id: str = "default"):
    if session_id in _executors:
        _executors[session_id].stop()
    return {"stopped": True}


@rpc_method(
    "workflow.execution_status",
    description="Return execution progress: running flag, current step index, total steps. Use to poll a long-running workflow.",
    param_descriptions={
        "session_id": "Browser session ID. Defaults to 'default'.",
    },
)
def workflow_execution_status(session_id: str = "default"):
    if session_id in _executors:
        return _executors[session_id].context.status()
    return {"running": False, "step": 0, "total": 0}


@rpc_method(
    "workflow.pause",
    description="Pause the running workflow at the next safe step. Use to inspect state mid-run; resume with workflow.unpause.",
    param_descriptions={
        "session_id": "Browser session ID. Defaults to 'default'.",
    },
)
def workflow_pause(session_id: str = "default"):
    if session_id in _executors:
        _executors[session_id].state.pause()
        return {"paused": True, "session_id": session_id}
    return {"paused": False, "error": "No active executor"}


@rpc_method(
    "workflow.unpause",
    description="Resume a paused workflow execution. Counterpart to workflow.pause.",
    param_descriptions={
        "session_id": "Browser session ID. Defaults to 'default'.",
    },
)
def workflow_unpause(session_id: str = "default"):
    """Resume a paused workflow execution."""
    if session_id in _executors:
        _executors[session_id].state.resume()
        return {"resumed": True, "session_id": session_id}
    return {"resumed": False, "error": "No active executor"}


@rpc_method(
    "workflow.step",
    description="Advance a paused workflow by N steps then pause again. Use for fine-grained debugging similar to a debugger's 'step over'.",
    param_descriptions={
        "count": "Number of steps to advance. Default 1.",
        "session_id": "Browser session ID. Defaults to 'default'.",
    },
)
def workflow_step(count: int = 1, session_id: str = "default"):
    if session_id in _executors:
        _executors[session_id].state.step(count)
        return {"stepping": count, "session_id": session_id}
    return {"stepping": 0, "error": "No active executor"}


@rpc_method(
    "workflow.inject",
    description="Splice a single ad-hoc block into the running execution queue (executed before the next normal step). Use to test a fix or run an extra action without editing the workflow JSON.",
    param_descriptions={
        "block": "A single workflow node dict (kind+action+data+settings) to inject. Must follow the block-schema contract.",
        "session_id": "Browser session ID. Defaults to 'default'.",
    },
)
def workflow_inject(block: dict, session_id: str = "default"):
    if session_id in _executors:
        _executors[session_id].state.inject(block)
        return {"injected": True, "queue_size": _executors[session_id].state.inject_queue_size}
    return {"injected": False, "error": "No active executor"}


@rpc_method(
    "workflow.set_breakpoint",
    description="Set a breakpoint on a workflow node by id. Execution will pause when this node is about to run; resume with workflow.unpause or workflow.step.",
    param_descriptions={
        "node_id": "Node id from the workflow JSON (the 'id' field of a node).",
        "session_id": "Browser session ID. Defaults to 'default'.",
    },
)
def workflow_set_breakpoint(node_id: str, session_id: str = "default"):
    if session_id in _executors:
        _executors[session_id].state.add_breakpoint(node_id)
        return {"added": node_id}
    return {"error": "No active executor"}


@rpc_method(
    "workflow.remove_breakpoint",
    description="Remove a previously set breakpoint by node id.",
    param_descriptions={
        "node_id": "Node id whose breakpoint should be cleared.",
        "session_id": "Browser session ID. Defaults to 'default'.",
    },
)
def workflow_remove_breakpoint(node_id: str, session_id: str = "default"):
    if session_id in _executors:
        _executors[session_id].state.remove_breakpoint(node_id)
        return {"removed": node_id}
    return {"error": "No active executor"}


@rpc_method(
    "workflow.list_breakpoints",
    description="List all currently set breakpoint node ids for a session's executor.",
    param_descriptions={
        "session_id": "Browser session ID. Defaults to 'default'.",
    },
)
def workflow_list_breakpoints(session_id: str = "default"):
    if session_id in _executors:
        return {"breakpoints": _executors[session_id].state.list_breakpoints()}
    return {"breakpoints": []}


@rpc_method(
    "workflow.state",
    description="Return full execution state: progress (current step / total) plus control state (paused, breakpoints, inject queue, variable bindings). Use to inspect a paused run before stepping or injecting.",
    param_descriptions={
        "session_id": "Browser session ID. Defaults to 'default'.",
    },
)
def workflow_state(session_id: str = "default"):
    """Full state: execution context + control state."""
    result = {"running": False, "step": 0, "total": 0}
    if session_id in _executors:
        executor = _executors[session_id]
        result = {
            **executor.context.status(),
            **executor.state.snapshot(),
        }
    return result


# --- Camoufox 环境管理 ---


@rpc_method(
    "camoufox.check",
    description="Check whether the Camoufox stealth browser binary is installed and report version info. Run before browser.launch on first use.",
)
def camoufox_check():
    return CamoufoxEnv.check()


@rpc_method(
    "camoufox.install",
    description="Download and install the Camoufox browser binary into the sidecar's app-data directory. Required once before the first browser.launch. Long-running (downloads ~100MB).",
)
def camoufox_install():
    return CamoufoxEnv.install()


@rpc_method(
    "camoufox.check_update",
    description="Check whether a newer Camoufox browser version is available upstream. Returns current and latest version strings.",
)
def camoufox_check_update():
    """Check if a newer Camoufox browser version is available upstream."""
    return CamoufoxEnv.check_update()


@rpc_method(
    "camoufox.update",
    description="Update the Camoufox browser binary to the latest upstream version. Long-running. Close active sessions first.",
)
def camoufox_update():
    """Update Camoufox browser binary to the latest version."""
    return CamoufoxEnv.update_browser()


@rpc_method("shutdown")
def shutdown():
    """Graceful shutdown: destroy all browser sessions, then exit."""
    logger.info("Shutdown requested, cleaning up...")
    _mgr.destroy_all()
    with _aux_lock:
        _recorders.clear()
        _executors.clear()
    logger.info("Cleanup done, exiting")
    # Schedule exit after response is sent
    import threading
    threading.Timer(0.1, lambda: __import__('os')._exit(0)).start()
    return {"shutdown": True}


# ---------------------------------------------------------------------------
# Captcha (Cloudflare click solver MVP)
# ---------------------------------------------------------------------------

@rpc_method(
    "captcha.detect_cloudflare",
    description="Detect whether a Cloudflare challenge (Turnstile widget or full-page Interstitial) is present on the active page. Detection is DOM-only and does not interact with the page.",
    param_descriptions={
        "session_id": "The session_id used at launch. Defaults to 'default'.",
        "challenge_type": "Which challenge to look for: 'turnstile' (small embedded widget) or 'interstitial' (full-page 'Just a moment'). Default 'turnstile'.",
    },
)
def captcha_detect_cloudflare(
    session_id: str = "default",
    challenge_type: str = "turnstile",
):
    from captcha import detect_cloudflare_challenge
    ctrl = _mgr.get(session_id)
    page = ctrl._page  # noqa: SLF001 — controller exposes _page deliberately
    if page is None:
        return {"detected": False, "reason": "no_active_page"}
    detected = detect_cloudflare_challenge(page, challenge_type)
    return {"detected": detected, "challenge_type": challenge_type}


@rpc_method(
    "captcha.solve_cloudflare",
    description="Click-solve a Cloudflare Turnstile or Interstitial challenge using the active session's stealth browser. Returns {solved: true} on success, raises CaptchaSolvingError otherwise. No external API key required.",
    param_descriptions={
        "session_id": "The session_id used at launch. Defaults to 'default'.",
        "challenge_type": "'turnstile' (embedded widget) or 'interstitial' (full-page). Default 'turnstile'.",
        "expected_content_selector": "Optional CSS selector that proves the challenge is over (e.g. main app content). If matched, treated as success even if challenge widget is still visible.",
        "wait_checkbox_attempts": "Max attempts to find a clickable checkbox. Default 10.",
        "wait_checkbox_delay_s": "Seconds between checkbox-find attempts. Default 6.",
        "checkbox_click_attempts": "Max retries on the click itself. Default 3.",
        "solve_click_delay_s": "Seconds to wait after clicking before verifying success. Default 6.",
    },
)
def captcha_solve_cloudflare(
    session_id: str = "default",
    challenge_type: str = "turnstile",
    expected_content_selector: str | None = None,
    wait_checkbox_attempts: int = 10,
    wait_checkbox_delay_s: int = 6,
    checkbox_click_attempts: int = 3,
    solve_click_delay_s: int = 6,
):
    from captcha import solve_cloudflare_by_click
    ctrl = _mgr.get(session_id)
    page = ctrl._page  # noqa: SLF001
    if page is None:
        raise RuntimeError("No active page in session; call browser.launch first")
    return solve_cloudflare_by_click(
        page=page,
        challenge_type=challenge_type,
        expected_content_selector=expected_content_selector,
        wait_checkbox_attempts=wait_checkbox_attempts,
        wait_checkbox_delay_s=wait_checkbox_delay_s,
        checkbox_click_attempts=checkbox_click_attempts,
        solve_click_delay_s=solve_click_delay_s,
    )

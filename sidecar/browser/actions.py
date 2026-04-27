import json
import threading

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


def set_server(server):
    global _server
    _server = server


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


@rpc_method("browser.launch")
def browser_launch(session_id: str = "default", headless: bool = False,
                   proxy: dict | None = None, profile: dict | None = None):
    ctrl = _mgr.create(session_id, headless=headless, proxy=proxy, profile=profile)
    return {"session_id": session_id, **ctrl.status()}


@rpc_method("browser.close")
def browser_close(session_id: str = "default"):
    with _aux_lock:
        _recorders.pop(session_id, None)
        _executors.pop(session_id, None)
    _mgr.destroy(session_id)
    return {"closed": True, "session_id": session_id}


@rpc_method("browser.list_sessions")
def browser_list_sessions():
    return {"sessions": _mgr.list_sessions()}


@rpc_method("browser.navigate")
def browser_navigate(url: str, session_id: str = "default"):
    ctrl = _mgr.get(session_id)
    ctrl.navigate(url)
    return {"url": ctrl.get_url()}


@rpc_method("browser.click")
def browser_click(selector: str, session_id: str = "default"):
    _mgr.get(session_id).click(selector)
    return {"clicked": selector}


@rpc_method("browser.type")
def browser_type(selector: str, text: str, session_id: str = "default"):
    _mgr.get(session_id).type_text(selector, text)
    return {"typed": selector}


@rpc_method("browser.wait")
def browser_wait(selector: str, timeout: int = 5000, session_id: str = "default"):
    _mgr.get(session_id).wait_for(selector, timeout=timeout)
    return {"found": selector}


@rpc_method("browser.screenshot")
def browser_screenshot(path: str = "screenshot.png", session_id: str = "default"):
    return {"path": _mgr.get(session_id).screenshot(path)}


@rpc_method("browser.status")
def browser_status(session_id: str = "default"):
    try:
        return _mgr.get(session_id).status()
    except RuntimeError:
        return {"connected": False, "url": None, "pages": 0}


@rpc_method("browser.dblclick")
def browser_dblclick(selector: str, session_id: str = "default"):
    _mgr.get(session_id).dblclick(selector)
    return {"dblclicked": selector}


@rpc_method("browser.hover")
def browser_hover(selector: str, session_id: str = "default"):
    _mgr.get(session_id).hover(selector)
    return {"hovered": selector}


@rpc_method("browser.select_option")
def browser_select_option(selector: str, value: str, session_id: str = "default"):
    _mgr.get(session_id).select_option(selector, value)
    return {"selected": selector, "value": value}


@rpc_method("browser.clear")
def browser_clear(selector: str, session_id: str = "default"):
    _mgr.get(session_id).clear(selector)
    return {"cleared": selector}


@rpc_method("browser.focus")
def browser_focus(selector: str, session_id: str = "default"):
    _mgr.get(session_id).focus(selector)
    return {"focused": selector}


@rpc_method("browser.go_back")
def browser_go_back(session_id: str = "default"):
    _mgr.get(session_id).go_back()
    return {"navigated": "back"}


@rpc_method("browser.go_forward")
def browser_go_forward(session_id: str = "default"):
    _mgr.get(session_id).go_forward()
    return {"navigated": "forward"}


@rpc_method("browser.reload")
def browser_reload(session_id: str = "default"):
    _mgr.get(session_id).reload()
    return {"reloaded": True}


@rpc_method("browser.press_key")
def browser_press_key(selector: str = "body", key: str = "", session_id: str = "default"):
    _mgr.get(session_id).press_key(selector, key)
    return {"pressed": key, "selector": selector}


@rpc_method("browser.scroll")
def browser_scroll(selector: str = "window", direction: str = "down",
                   amount: int = 300, session_id: str = "default"):
    _mgr.get(session_id).scroll(selector, direction, amount)
    return {"scrolled": selector, "direction": direction}


@rpc_method("browser.evaluate")
def browser_evaluate(expression: str, session_id: str = "default"):
    return {"result": _mgr.get(session_id).evaluate(expression)}


@rpc_method("browser.get_text")
def browser_get_text(selector: str, session_id: str = "default"):
    return {"text": _mgr.get(session_id).get_element_text(selector)}


@rpc_method("browser.get_attribute")
def browser_get_attribute(selector: str, attr: str, session_id: str = "default"):
    return {"value": _mgr.get(session_id).get_element_attribute(selector, attr)}


@rpc_method("browser.get_element_count")
def browser_get_element_count(selector: str, session_id: str = "default"):
    return {"count": _mgr.get(session_id).get_element_count(selector)}


@rpc_method("browser.extract_table")
def browser_extract_table(selector: str, session_id: str = "default"):
    return {"data": _mgr.get(session_id).extract_table(selector)}


@rpc_method("browser.upload_file")
def browser_upload_file(selector: str, file_path: str, session_id: str = "default"):
    _mgr.get(session_id).upload_file(selector, file_path)
    return {"uploaded": selector, "file": file_path}


@rpc_method("browser.new_tab")
def browser_new_tab(url: str = "", session_id: str = "default"):
    ctrl = _mgr.get(session_id)
    ctrl.new_tab(url)
    return ctrl.status()


@rpc_method("browser.switch_tab")
def browser_switch_tab(index: int, session_id: str = "default"):
    ctrl = _mgr.get(session_id)
    ctrl.switch_tab(index)
    return ctrl.status()


@rpc_method("browser.close_tab")
def browser_close_tab(index: int | None = None, session_id: str = "default"):
    ctrl = _mgr.get(session_id)
    ctrl.close_tab(index)
    return ctrl.status()


@rpc_method("browser.handle_dialog")
def browser_handle_dialog(accept: bool = True, text: str = "", session_id: str = "default"):
    _mgr.get(session_id).handle_dialog(accept, text)
    return {"dialog_handler_set": True}


@rpc_method("recording.start")
def recording_start(session_id: str = "default"):
    recorder = _get_recorder(session_id)

    def on_event(event):
        if _server:
            _server.send_notification("recording.event", {**event, "session_id": session_id})
    recorder.event_callback = on_event
    recorder.start()
    return {"recording": True, "session_id": session_id}


@rpc_method("recording.stop")
def recording_stop(session_id: str = "default"):
    recorder = _get_recorder(session_id)
    events = recorder.stop()
    nodes = RecordingEngine.events_to_workflow_nodes(events)
    return {"events": len(events), "nodes": nodes}


@rpc_method("recording.poll")
def recording_poll(session_id: str = "default"):
    recorder = _get_recorder(session_id)
    new_events = recorder.poll_new_events()
    nodes = RecordingEngine.events_to_workflow_nodes(new_events) if new_events else []
    return {"events": new_events, "nodes": nodes}


@rpc_method("recording.status")
def recording_status(session_id: str = "default"):
    if session_id in _recorders:
        return {"recording": _recorders[session_id].is_recording}
    return {"recording": False}


@rpc_method("workflow.execute")
def workflow_execute(workflow: dict | None = None, session_id: str = "default"):
    if not workflow:
        return {"success": False, "error": "No workflow provided"}
    executor = _get_executor(session_id)

    def on_progress(event):
        if _server:
            _server.send_notification("workflow.progress", {**event, "session_id": session_id})

    def on_log(entry):
        if _server:
            _server.send_notification("workflow.log", {**entry, "session_id": session_id})

    executor.progress_callback = on_progress
    executor.log_callback = on_log
    return executor.execute(workflow)


@rpc_method("workflow.resume")
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


@rpc_method("workflow.stop")
def workflow_stop(session_id: str = "default"):
    if session_id in _executors:
        _executors[session_id].stop()
    return {"stopped": True}


@rpc_method("workflow.execution_status")
def workflow_execution_status(session_id: str = "default"):
    if session_id in _executors:
        return _executors[session_id].context.status()
    return {"running": False, "step": 0, "total": 0}


# --- Camoufox 环境管理 ---


@rpc_method("camoufox.check")
def camoufox_check():
    return CamoufoxEnv.check()


@rpc_method("camoufox.install")
def camoufox_install():
    return CamoufoxEnv.install()

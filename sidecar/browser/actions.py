import json

from rpc.methods import rpc_method
from browser.controller import BrowserController
from browser.recorder import RecordingEngine
from browser.env_check import CamoufoxEnv
from engine.executor import WorkflowExecutor

_browser = BrowserController()
_recorder = RecordingEngine(_browser)
_executor = WorkflowExecutor(_browser)

_server = None


def set_server(server):
    global _server
    _server = server


@rpc_method("browser.launch")
def browser_launch(headless: bool = False, proxy: dict | None = None, profile: dict | None = None):
    _browser.launch(headless=headless, proxy=proxy, profile=profile)
    return _browser.status()


@rpc_method("browser.close")
def browser_close():
    _browser.close()
    return {"closed": True}


@rpc_method("browser.navigate")
def browser_navigate(url: str):
    _browser.navigate(url)
    return {"url": _browser.get_url()}


@rpc_method("browser.click")
def browser_click(selector: str):
    _browser.click(selector)
    return {"clicked": selector}


@rpc_method("browser.type")
def browser_type(selector: str, text: str):
    _browser.type_text(selector, text)
    return {"typed": selector}


@rpc_method("browser.wait")
def browser_wait(selector: str, timeout: int = 5000):
    _browser.wait_for(selector, timeout=timeout)
    return {"found": selector}


@rpc_method("browser.screenshot")
def browser_screenshot(path: str = "screenshot.png"):
    return {"path": _browser.screenshot(path)}


@rpc_method("browser.status")
def browser_status():
    return _browser.status()


@rpc_method("browser.dblclick")
def browser_dblclick(selector: str):
    _browser.dblclick(selector)
    return {"dblclicked": selector}


@rpc_method("browser.hover")
def browser_hover(selector: str):
    _browser.hover(selector)
    return {"hovered": selector}


@rpc_method("browser.select_option")
def browser_select_option(selector: str, value: str):
    _browser.select_option(selector, value)
    return {"selected": selector, "value": value}


@rpc_method("browser.clear")
def browser_clear(selector: str):
    _browser.clear(selector)
    return {"cleared": selector}


@rpc_method("browser.focus")
def browser_focus(selector: str):
    _browser.focus(selector)
    return {"focused": selector}


@rpc_method("browser.go_back")
def browser_go_back():
    _browser.go_back()
    return {"navigated": "back"}


@rpc_method("browser.go_forward")
def browser_go_forward():
    _browser.go_forward()
    return {"navigated": "forward"}


@rpc_method("browser.reload")
def browser_reload():
    _browser.reload()
    return {"reloaded": True}


@rpc_method("browser.press_key")
def browser_press_key(selector: str = "body", key: str = ""):
    _browser.press_key(selector, key)
    return {"pressed": key, "selector": selector}


@rpc_method("browser.scroll")
def browser_scroll(selector: str = "window", direction: str = "down", amount: int = 300):
    _browser.scroll(selector, direction, amount)
    return {"scrolled": selector, "direction": direction}


@rpc_method("browser.evaluate")
def browser_evaluate(expression: str):
    return {"result": _browser.evaluate(expression)}


@rpc_method("browser.get_text")
def browser_get_text(selector: str):
    return {"text": _browser.get_element_text(selector)}


@rpc_method("browser.get_attribute")
def browser_get_attribute(selector: str, attr: str):
    return {"value": _browser.get_element_attribute(selector, attr)}


@rpc_method("browser.get_element_count")
def browser_get_element_count(selector: str):
    return {"count": _browser.get_element_count(selector)}


@rpc_method("browser.extract_table")
def browser_extract_table(selector: str):
    return {"data": _browser.extract_table(selector)}


@rpc_method("browser.upload_file")
def browser_upload_file(selector: str, file_path: str):
    _browser.upload_file(selector, file_path)
    return {"uploaded": selector, "file": file_path}


@rpc_method("browser.new_tab")
def browser_new_tab(url: str = ""):
    _browser.new_tab(url)
    return _browser.status()


@rpc_method("browser.switch_tab")
def browser_switch_tab(index: int):
    _browser.switch_tab(index)
    return _browser.status()


@rpc_method("browser.close_tab")
def browser_close_tab(index: int | None = None):
    _browser.close_tab(index)
    return _browser.status()


@rpc_method("browser.handle_dialog")
def browser_handle_dialog(accept: bool = True, text: str = ""):
    _browser.handle_dialog(accept, text)
    return {"dialog_handler_set": True}


@rpc_method("recording.start")
def recording_start():
    _recorder.start()
    return {"recording": True}


@rpc_method("recording.stop")
def recording_stop():
    events = _recorder.stop()
    nodes = RecordingEngine.events_to_workflow_nodes(events)
    return {"events": len(events), "nodes": nodes}


@rpc_method("recording.poll")
def recording_poll():
    new_events = _recorder.poll_new_events()
    nodes = RecordingEngine.events_to_workflow_nodes(new_events) if new_events else []
    return {"events": new_events, "nodes": nodes}


@rpc_method("recording.status")
def recording_status():
    return {"recording": _recorder.is_recording}


@rpc_method("workflow.execute")
def workflow_execute(workflow: dict | None = None):
    if not workflow:
        return {"success": False, "error": "No workflow provided"}

    def on_progress(event):
        if _server:
            _server.send_notification("workflow.progress", event)

    _executor.progress_callback = on_progress
    return _executor.execute(workflow)


@rpc_method("workflow.stop")
def workflow_stop():
    _executor.stop()
    return {"stopped": True}


@rpc_method("workflow.execution_status")
def workflow_execution_status():
    return _executor.context.status()


# --- Camoufox 环境管理 ---


@rpc_method("camoufox.check")
def camoufox_check():
    return CamoufoxEnv.check()


@rpc_method("camoufox.install")
def camoufox_install():
    return CamoufoxEnv.install()

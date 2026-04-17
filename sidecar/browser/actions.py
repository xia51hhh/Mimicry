import json

from rpc.methods import rpc_method
from browser.controller import BrowserController
from browser.recorder import RecordingEngine
from engine.executor import WorkflowExecutor

_browser = BrowserController()
_recorder = RecordingEngine(_browser)
_executor = WorkflowExecutor(_browser)


@rpc_method("browser.launch")
def browser_launch(headless: bool = False, proxy: dict | None = None):
    _browser.launch(headless=headless, proxy=proxy)
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
    return _executor.execute(workflow)


@rpc_method("workflow.stop")
def workflow_stop():
    _executor.stop()
    return {"stopped": True}


@rpc_method("workflow.execution_status")
def workflow_execution_status():
    return _executor.context.status()

"""Bidirectional mapping between frontend PascalCase and backend lowercase action names.

AUTO-GENERATED from shared/action-map.json — do not edit manually.
Run `python3 scripts/sync-action-map.py --fix` after changing the shared map.
"""

# Frontend (PascalCase) → Backend (lowercase)
FRONTEND_TO_BACKEND: dict[str, str] = {
    "Navigate": "open",
    "NewTab": "new_tab",
    "SwitchTab": "switch_tab",
    "CloseTab": "close_tab",
    "GoBack": "back",
    "GoForward": "forward",
    "Reload": "reload",
    "Click": "click",
    "DblClick": "dblclick",
    "Type": "type",
    "Hover": "hover",
    "Scroll": "scroll",
    "SelectOption": "select",
    "PressKey": "press_key",
    "Clear": "clear",
    "Focus": "focus",
    "Wait": "wait",
    "GetText": "extract_text",
    "GetAttribute": "extract_attr",
    "GetURL": "get_url",
    "Screenshot": "screenshot",
    "ExtractTable": "extract_table",
    "SetVariable": "set",
    "Export": "export",
    "RunScript": "run_script",
    "HttpRequest": "http_request",
    "Delay": "sleep",
    "Log": "log",
    "Comment": "comment",
    "HandleDialog": "handle_dialog",
    "UploadFile": "upload_file",
    "SwitchFrame": "switch_frame",
    "WaitForPage": "wait_for_page",
    "Cookie": "cookie",
    "ElementExists": "element_exists",
    "LoopElements": "loop_elements",
    "LoopBreakpoint": "loop_breakpoint",
    "WaitConnections": "wait_connections",
    "ExecuteWorkflow": "execute_workflow",
    "HandleDownload": "handle_download",
    "Transform": "transform",
    "Stop": "stop",
}

# Backend (lowercase) → Frontend (PascalCase)
BACKEND_TO_FRONTEND: dict[str, str] = {v: k for k, v in FRONTEND_TO_BACKEND.items()}


def to_backend(frontend_name: str) -> str:
    """Convert frontend action name to backend. Pass through if already backend."""
    return FRONTEND_TO_BACKEND.get(frontend_name, frontend_name)


def to_frontend(backend_name: str) -> str:
    """Convert backend action name to frontend. Pass through if already frontend."""
    return BACKEND_TO_FRONTEND.get(backend_name, backend_name)

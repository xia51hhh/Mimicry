/**
 * Bidirectional mapping between frontend PascalCase and backend lowercase action names.
 * Must stay in sync with sidecar/engine/action_map.py
 */

export const FRONTEND_TO_BACKEND: Record<string, string> = {
  Navigate: "open",
  NewTab: "new_tab",
  SwitchTab: "switch_tab",
  CloseTab: "close_tab",
  GoBack: "back",
  GoForward: "forward",
  Reload: "reload",
  Click: "click",
  DblClick: "dblclick",
  Type: "type",
  Hover: "hover",
  Scroll: "scroll",
  SelectOption: "select",
  PressKey: "press_key",
  Clear: "clear",
  Focus: "focus",
  Wait: "wait",
  GetText: "extract_text",
  GetAttribute: "extract_attr",
  GetURL: "get_url",
  Screenshot: "screenshot",
  ExtractTable: "extract_table",
  SetVariable: "set",
  Export: "export",
  RunScript: "run_script",
  HttpRequest: "http_request",
  Delay: "sleep",
  Log: "log",
  Comment: "comment",
  HandleDialog: "handle_dialog",
  UploadFile: "upload_file",
};

export const BACKEND_TO_FRONTEND: Record<string, string> = Object.fromEntries(
  Object.entries(FRONTEND_TO_BACKEND).map(([k, v]) => [v, k])
);

export function toBackend(name: string): string {
  return FRONTEND_TO_BACKEND[name] ?? name;
}

export function toFrontend(name: string): string {
  return BACKEND_TO_FRONTEND[name] ?? name;
}

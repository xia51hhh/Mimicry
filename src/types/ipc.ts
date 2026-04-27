export interface RpcRequest {
  jsonrpc: "2.0";
  id: number;
  method: string;
  params?: Record<string, unknown>;
}

export interface RpcResponse {
  jsonrpc: "2.0";
  id: number;
  result?: unknown;
  error?: {
    code: number;
    message: string;
    data?: unknown;
  };
}

export interface BrowserStatus {
  connected: boolean;
  pages: number;
  url?: string;
}

/**
 * Sidecar event names.
 * Python sends `domain.action` notifications → Rust converts to `sidecar:domain/action`.
 */
export const SidecarEvent = {
  RecordingEvent: "sidecar:recording/event",
  WorkflowProgress: "sidecar:workflow/progress",
  WorkflowLog: "sidecar:workflow/log",
  CamoufoxProgress: "sidecar:camoufox/progress",
  BrowserWarning: "sidecar:browser/warning",
} as const;

/** Extract readable message from Tauri AppError (serialized as {kind,message,display}) or any thrown value */
export function errorMessage(e: unknown): string {
  if (e && typeof e === "object" && "message" in e) return String((e as Record<string, unknown>).message);
  return String(e);
}

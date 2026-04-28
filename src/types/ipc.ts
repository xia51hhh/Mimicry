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
  SessionClosed: "sidecar:browser/session_closed",
} as const;

/** Extract readable message from Tauri AppError (serialized as {kind,message,display}) or any thrown value */
export function errorMessage(e: unknown): string {
  if (e && typeof e === "object" && "message" in e) return String((e as Record<string, unknown>).message);
  return String(e);
}

/** Workflow validation diagnostic from Rust validator */
export interface WorkflowDiagnostic {
  level: "error" | "warning" | "info";
  ruleId: string;
  nodeId?: string;
  action?: string;
  message: string;
  suggestion?: string;
}

/** Extract diagnostics array from a Validation AppError */
export function extractDiagnostics(e: unknown): WorkflowDiagnostic[] | null {
  if (e && typeof e === "object" && "kind" in e) {
    const err = e as Record<string, unknown>;
    if (err.kind === "validation" && Array.isArray(err.diagnostics)) {
      return err.diagnostics as WorkflowDiagnostic[];
    }
  }
  return null;
}

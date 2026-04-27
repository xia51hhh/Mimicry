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

/** Extract readable message from Tauri AppError (serialized as {kind,message,display}) or any thrown value */
export function errorMessage(e: unknown): string {
  if (e && typeof e === "object" && "message" in e) return String((e as Record<string, unknown>).message);
  return String(e);
}

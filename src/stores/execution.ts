import { defineStore } from "pinia";
import { ref, shallowRef } from "vue";
import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import { toBackend } from "../types/action-map";
import { errorMessage, SidecarEvent } from "../types/ipc";

function convertNodesToBackend(nodes: Record<string, unknown>[]): Record<string, unknown>[] {
  return nodes.map((n) => {
    // Flatten both canonical workflow nodes:
    // { id, kind, action, data, settings, runtime }
    // and legacy Vue Flow nodes:
    // { id, type, position, data: { action, ... } }
    // into executor format: { id, type, action, selector, ... }.
    const data = (n.data as Record<string, unknown>) || {};
    const runtime = (n.runtime as Record<string, unknown>) || {};
    const flat: Record<string, unknown> = {
      id: n.id,
      type: n.kind ?? n.type,
      ...data,
    };
    if (typeof n.action === "string") {
      flat.action = n.action;
    }
    if (n.settings && typeof n.settings === "object") {
      flat.settings = n.settings;
    }
    if (typeof flat.action === "string") {
      flat.action = toBackend(flat.action as string);
    }
    // Pass session_id for cross-profile execution (from data.sessionId)
    const sessionId = flat.sessionId ?? flat.session_id ?? runtime.sessionId;
    if (sessionId) {
      flat.session_id = sessionId;
      delete flat.sessionId;
    }
    if (Array.isArray(data.children)) {
      flat.children = convertNodesToBackend(data.children as Record<string, unknown>[]);
    }
    if (Array.isArray(data.elseChildren)) {
      flat.elseChildren = convertNodesToBackend(data.elseChildren as Record<string, unknown>[]);
    }
    return flat;
  });
}

interface ExecutionStatusResult {
  running: boolean;
  step?: number;
  total?: number;
  currentNodeId?: string;
  error?: string;
  variables?: Record<string, unknown>;
}

interface ExecutionResult {
  success: boolean;
  error?: string;
  variables?: Record<string, unknown>;
}

export interface LogEntry {
  time: string;
  level: "info" | "warn" | "error" | "debug";
  nodeId?: string;
  message: string;
}

export interface ExecutionState {
  running: boolean;
  step: number;
  total: number;
  currentNodeId?: string;
  error?: string;
  variables: Record<string, unknown>;
}

export const useExecutionStore = defineStore("execution", () => {
  const running = ref(false);
  const step = ref(0);
  const total = ref(0);
  const currentNodeId = ref<string | null>(null);
  const error = ref<string | null>(null);
  const variables = shallowRef<Record<string, unknown>>({});
  const logs = ref<LogEntry[]>([]);
  const completedNodeIds = ref<Set<string>>(new Set());
  const failedNodeIds = ref<Set<string>>(new Set());

  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let progressUnlisten: UnlistenFn | null = null;
  let logUnlisten: UnlistenFn | null = null;

  function addLog(level: LogEntry["level"], message: string, nodeId?: string) {
    logs.value.push({
      time: new Date().toLocaleTimeString(),
      level,
      nodeId,
      message,
    });
  }

  function reset() {
    running.value = false;
    step.value = 0;
    total.value = 0;
    currentNodeId.value = null;
    error.value = null;
    variables.value = {};
    logs.value = [];
    completedNodeIds.value = new Set();
    failedNodeIds.value = new Set();
  }

  async function pollStatus() {
    try {
      const result = await invoke<ExecutionStatusResult>("workflow_execution_status");
      const prevNodeId = currentNodeId.value;

      running.value = result.running;
      step.value = result.step || 0;
      total.value = result.total || 0;
      currentNodeId.value = result.currentNodeId || null;
      error.value = result.error || null;
      variables.value = result.variables || {};

      // Track completed nodes
      if (prevNodeId && prevNodeId !== currentNodeId.value) {
        if (error.value) {
          failedNodeIds.value = new Set([...failedNodeIds.value, prevNodeId]);
        } else {
          completedNodeIds.value = new Set([...completedNodeIds.value, prevNodeId]);
        }
      }

      if (!result.running) {
        stopPolling();
        if (result.error) {
          addLog("error", `execution.failed: ${result.error}`);
        } else {
          addLog("info", "execution.completed");
        }
      }
    } catch {
      // Sidecar might not be ready yet
    }
  }

  function startPolling() {
    stopPolling();
    pollTimer = setInterval(pollStatus, 300);
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  async function listenProgress() {
    stopListening(); // Prevent listener leaks from prior calls
    progressUnlisten = await listen<{
      step: number;
      total: number;
      action: string;
      nodeId?: string;
      status: string;
    }>(SidecarEvent.WorkflowProgress, (event) => {
      const p = event.payload;
      const prevNodeId = currentNodeId.value;

      step.value = p.step;
      total.value = p.total;
      currentNodeId.value = p.nodeId || null;

      if (prevNodeId && prevNodeId !== currentNodeId.value) {
        completedNodeIds.value = new Set([...completedNodeIds.value, prevNodeId]);
      }

      addLog("info", `Step ${p.step + 1}/${p.total}: ${p.action}`, p.nodeId);
    });

    logUnlisten = await listen<{
      level: string;
      message: string;
      nodeId?: string;
      step: number;
      timestamp: number;
    }>(SidecarEvent.WorkflowLog, (event) => {
      const entry = event.payload;
      logs.value.push({
        time: new Date(entry.timestamp * 1000).toLocaleTimeString(),
        level: (entry.level as LogEntry["level"]) || "info",
        nodeId: entry.nodeId,
        message: entry.message,
      });
    });
  }

  function stopListening() {
    if (progressUnlisten) {
      progressUnlisten();
      progressUnlisten = null;
    }
    if (logUnlisten) {
      logUnlisten();
      logUnlisten = null;
    }
  }

  async function execute(workflowJson: { name?: string; nodes: unknown[]; edges: unknown[] }) {
    reset();
    running.value = true;
    addLog("info", `execution.start: ${workflowJson.name || "Untitled"}`);
    await listenProgress();
    startPolling(); // fallback for missed events

    // Convert frontend PascalCase action names to backend lowercase
    const converted = {
      ...workflowJson,
      nodes: convertNodesToBackend(workflowJson.nodes as Record<string, unknown>[]),
    };

    try {
      const result = await invoke<ExecutionResult>("workflow_execute", { workflow: converted });
      running.value = false;
      stopPolling();
      stopListening();

      if (result.success) {
        addLog("info", "execution.success");
        variables.value = result.variables || {};
      } else {
        error.value = result.error || "execution.unknownError";
        addLog("error", `execution.failed: ${error.value}`);
      }

      return result;
    } catch (e: unknown) {
      running.value = false;
      stopPolling();
      stopListening();
      error.value = errorMessage(e);
      addLog("error", `execution.exception: ${e}`);
      throw e;
    }
  }

  async function stop() {
    try {
      await invoke("workflow_stop_execution");
      running.value = false;
      stopPolling();
      stopListening();
      addLog("warn", "execution.stopped");
    } catch (e: unknown) {
      addLog("error", `execution.stopFailed: ${e}`);
    }
  }

  function getNodeStatus(nodeId: string): "idle" | "running" | "success" | "error" {
    if (currentNodeId.value === nodeId && running.value) return "running";
    if (failedNodeIds.value.has(nodeId)) return "error";
    if (completedNodeIds.value.has(nodeId)) return "success";
    return "idle";
  }

  return {
    running, step, total, currentNodeId, error, variables, logs,
    completedNodeIds, failedNodeIds,
    execute, stop, reset, getNodeStatus,
  };
});

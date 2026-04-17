import { defineStore } from "pinia";
import { ref, shallowRef } from "vue";
import { invoke } from "@tauri-apps/api/core";

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
    } catch (e) {
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

  async function execute(workflowJson: { name?: string; nodes: unknown[]; edges: unknown[] }) {
    reset();
    running.value = true;
    addLog("info", `execution.start: ${workflowJson.name || "Untitled"}`);
    startPolling();

    try {
      const result = await invoke<ExecutionResult>("workflow_execute", { workflow: workflowJson });
      running.value = false;
      stopPolling();

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
      error.value = String(e);
      addLog("error", `execution.exception: ${e}`);
      throw e;
    }
  }

  async function stop() {
    try {
      await invoke("workflow_stop_execution");
      running.value = false;
      stopPolling();
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

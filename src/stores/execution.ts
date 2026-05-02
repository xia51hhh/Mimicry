import { defineStore } from 'pinia';
import { ref, shallowRef } from 'vue';
import { invoke } from '@tauri-apps/api/core';
import { listen, type UnlistenFn } from '@tauri-apps/api/event';
import { errorMessage, extractDiagnostics, SidecarEvent } from '../types/ipc';
import { useBrowserStore } from './browser';
import { useValidationStore } from './validation';
import { useSettingsStore } from './settings';

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
  level: 'info' | 'warn' | 'error' | 'debug';
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

export const useExecutionStore = defineStore('execution', () => {
  const running = ref(false);
  const step = ref(0);
  const total = ref(0);
  const currentNodeId = ref<string | null>(null);
  const error = ref<string | null>(null);
  const variables = shallowRef<Record<string, unknown>>({});
  const logs = ref<LogEntry[]>([]);
  const completedNodeIds = ref<Set<string>>(new Set());
  const failedNodeIds = ref<Set<string>>(new Set());

  // Anti-detection delay settings
  const humanize = ref(true);
  const delayMultiplier = ref(1.0);

  // Debug state
  const breakpointIds = ref<Set<string>>(new Set());

  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let progressUnlisten: UnlistenFn | null = null;
  let logUnlisten: UnlistenFn | null = null;

  function addLog(level: LogEntry['level'], message: string, nodeId?: string) {
    logs.value.push({
      time: new Date().toLocaleTimeString(),
      level,
      nodeId,
      message,
    });
  }

  function reset() {
    running.value = false;
    paused.value = false;
    step.value = 0;
    total.value = 0;
    currentNodeId.value = null;
    error.value = null;
    variables.value = {};
    logs.value = [];
    completedNodeIds.value = new Set();
    failedNodeIds.value = new Set();
    breakpointIds.value = new Set();
  }

  async function pollStatus() {
    try {
      const result = await invoke<ExecutionStatusResult>('workflow_execution_status');
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
          addLog('error', `execution.failed: ${result.error}`);
        } else {
          addLog('info', 'execution.completed');
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

      addLog('info', `Step ${p.step + 1}/${p.total}: ${p.action}`, p.nodeId);
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
        level: (entry.level as LogEntry['level']) || 'info',
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
    addLog('info', `execution.start: ${workflowJson.name || 'Untitled'}`);
    await listenProgress();
    startPolling(); // fallback for missed events

    // Send canonical format directly — Rust transform layer handles conversion
    try {
      const browserStore = useBrowserStore();
      const settingsStore = useSettingsStore();
      const result = await invoke<ExecutionResult>('workflow_execute', {
        workflow: workflowJson,
        sessionId: browserStore.activeSessionId,
        humanize: settingsStore.humanize,
        delayMultiplier: settingsStore.delayMultiplier,
      });
      running.value = false;
      stopPolling();
      stopListening();

      if (result.success) {
        addLog('info', 'execution.success');
        variables.value = result.variables || {};
      } else {
        error.value = result.error || 'execution.unknownError';
        addLog('error', `execution.failed: ${error.value}`);
      }

      return result;
    } catch (e: unknown) {
      running.value = false;
      stopPolling();
      stopListening();
      // Check if this is a validation error with diagnostics
      const diags = extractDiagnostics(e);
      if (diags) {
        const validation = useValidationStore();
        validation.setDiagnostics(diags);
        error.value = `${diags.length} validation error(s)`;
        addLog('error', `execution.validationFailed: ${diags.length} error(s)`);
        for (const d of diags) {
          addLog('error', `[${d.ruleId}] ${d.message}`);
        }
      } else {
        error.value = errorMessage(e);
        addLog('error', `execution.exception: ${e}`);
      }
      throw e;
    }
  }

  async function stop() {
    try {
      await invoke('workflow_stop_execution');
      running.value = false;
      stopPolling();
      stopListening();
      addLog('warn', 'execution.stopped');
    } catch (e: unknown) {
      addLog('error', `execution.stopFailed: ${e}`);
    }
  }

  function getNodeStatus(nodeId: string): 'idle' | 'running' | 'success' | 'error' {
    if (currentNodeId.value === nodeId && running.value) return 'running';
    if (failedNodeIds.value.has(nodeId)) return 'error';
    if (completedNodeIds.value.has(nodeId)) return 'success';
    return 'idle';
  }

  // ── Debug controls ──────────────────────────────────────────────

  const paused = ref(false);

  async function pause() {
    try {
      await invoke('workflow_pause');
      paused.value = true;
      addLog('info', 'debug.paused');
    } catch (e: unknown) {
      addLog('error', `debug.pauseFailed: ${e}`);
    }
  }

  async function resume() {
    try {
      await invoke('workflow_unpause');
      paused.value = false;
      addLog('info', 'debug.resumed');
    } catch (e: unknown) {
      addLog('error', `debug.resumeFailed: ${e}`);
    }
  }

  async function stepForward(count = 1) {
    try {
      await invoke('workflow_step', { count });
      addLog('info', `debug.step: ${count}`);
    } catch (e: unknown) {
      addLog('error', `debug.stepFailed: ${e}`);
    }
  }

  async function toggleBreakpoint(nodeId: string) {
    try {
      if (breakpointIds.value.has(nodeId)) {
        await invoke('workflow_remove_breakpoint', { nodeId });
        const next = new Set(breakpointIds.value);
        next.delete(nodeId);
        breakpointIds.value = next;
        addLog('info', `debug.breakpointRemoved: ${nodeId}`);
      } else {
        await invoke('workflow_set_breakpoint', { nodeId });
        breakpointIds.value = new Set([...breakpointIds.value, nodeId]);
        addLog('info', `debug.breakpointSet: ${nodeId}`);
      }
    } catch (e: unknown) {
      addLog('error', `debug.breakpointFailed: ${e}`);
    }
  }

  function hasBreakpoint(nodeId: string): boolean {
    return breakpointIds.value.has(nodeId);
  }

  return {
    running,
    paused,
    step,
    total,
    currentNodeId,
    error,
    variables,
    logs,
    completedNodeIds,
    failedNodeIds,
    breakpointIds,
    humanize,
    delayMultiplier,
    execute,
    stop,
    reset,
    getNodeStatus,
    pause,
    resume,
    stepForward,
    toggleBreakpoint,
    hasBreakpoint,
  };
});

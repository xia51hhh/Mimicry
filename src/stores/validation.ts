import { ref, computed } from "vue";
import { defineStore } from "pinia";
import { invoke } from "@tauri-apps/api/core";
import type { WorkflowDiagnostic } from "../types/ipc";
import { extractDiagnostics } from "../types/ipc";

export const useValidationStore = defineStore("validation", () => {
  const diagnostics = ref<WorkflowDiagnostic[]>([]);

  const errors = computed(() => diagnostics.value.filter((d) => d.level === "error"));
  const warnings = computed(() => diagnostics.value.filter((d) => d.level === "warning"));
  const infos = computed(() => diagnostics.value.filter((d) => d.level === "info"));

  const errorCount = computed(() => errors.value.length);
  const warningCount = computed(() => warnings.value.length);
  const totalCount = computed(() => diagnostics.value.length);

  function setDiagnostics(diags: WorkflowDiagnostic[]) {
    diagnostics.value = diags;
  }

  /** Extract diagnostics from a Validation error thrown by invoke */
  function setFromError(e: unknown): boolean {
    const diags = extractDiagnostics(e);
    if (diags) {
      diagnostics.value = diags;
      return true;
    }
    return false;
  }

  /** Call Rust workflow_validate for standalone validation */
  async function validate(workflow: Record<string, unknown>) {
    try {
      const result = await invoke<WorkflowDiagnostic[]>("workflow_validate", { workflow });
      diagnostics.value = result;
    } catch (e) {
      if (!setFromError(e)) {
        console.error("[Validation] validate failed:", e);
      }
    }
  }

  function clear() {
    diagnostics.value = [];
  }

  function getNodeDiagnostics(nodeId: string): WorkflowDiagnostic[] {
    return diagnostics.value.filter((d) => d.nodeId === nodeId);
  }

  function getNodeMaxLevel(nodeId: string): "error" | "warning" | "info" | null {
    const nodeDiags = getNodeDiagnostics(nodeId);
    if (nodeDiags.some((d) => d.level === "error")) return "error";
    if (nodeDiags.some((d) => d.level === "warning")) return "warning";
    if (nodeDiags.some((d) => d.level === "info")) return "info";
    return null;
  }

  return {
    diagnostics,
    errors,
    warnings,
    infos,
    errorCount,
    warningCount,
    totalCount,
    setDiagnostics,
    setFromError,
    validate,
    clear,
    getNodeDiagnostics,
    getNodeMaxLevel,
  };
});

<script setup lang="ts">
import { ref } from "vue";
import { invoke } from "@tauri-apps/api/core";
import { useBrowserStore } from "../../stores/browser";
import { useWorkflowStore } from "../../stores/workflow";

const browser = useBrowserStore();
const workflow = useWorkflowStore();
const executing = ref(false);

async function toggleRecording() {
  if (browser.recording) {
    const nodes = await browser.stopRecording();
    if (nodes.length > 0) {
      workflow.importRecordedNodes(nodes);
    }
  } else {
    await browser.startRecording();
  }
}

async function runWorkflow() {
  if (executing.value) {
    await invoke("workflow_stop_execution");
    executing.value = false;
    return;
  }
  const workflowJson = workflow.toJSON();
  executing.value = true;
  try {
    await invoke("workflow_execute", { workflow: workflowJson });
  } catch (e) {
    console.error("Workflow execution failed:", e);
  } finally {
    executing.value = false;
  }
}
</script>

<template>
  <header class="flex h-12 items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-surface)] px-4">
    <div class="flex items-center gap-3">
      <button
        class="rounded bg-[var(--color-primary)] px-3 py-1 text-sm text-white hover:opacity-90 disabled:opacity-50"
        :disabled="browser.launching"
        @click="browser.connected ? browser.close() : browser.launch()"
      >
        {{ browser.launching ? 'Launching...' : browser.connected ? 'Close Browser' : 'Launch Browser' }}
      </button>
      <span class="text-xs" :class="browser.connected ? 'text-green-400' : 'text-[var(--color-text-muted)]'">
        {{ browser.connected ? 'Connected' : 'Disconnected' }}
      </span>
    </div>
    <div class="flex items-center gap-2">
      <button
        class="rounded px-3 py-1 text-sm"
        :class="executing
          ? 'bg-orange-600 text-white'
          : 'border border-[var(--color-border)] hover:bg-white/5'"
        :disabled="!browser.connected"
        @click="runWorkflow"
      >
        {{ executing ? '⏹ Stop' : '▶ Run' }}
      </button>
      <button
        class="rounded px-3 py-1 text-sm"
        :class="browser.recording
          ? 'bg-red-600 text-white animate-pulse'
          : 'border border-[var(--color-border)] hover:bg-white/5'"
        :disabled="!browser.connected"
        @click="toggleRecording"
      >
        {{ browser.recording ? '⏹ Stop' : '⏺ Record' }}
      </button>
    </div>
  </header>
</template>

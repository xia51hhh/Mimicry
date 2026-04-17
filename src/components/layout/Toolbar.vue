<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useBrowserStore } from "../../stores/browser";
import { useWorkflowStore } from "../../stores/workflow";
import { useExecutionStore } from "../../stores/execution";

const { t } = useI18n()
const browser = useBrowserStore();
const workflow = useWorkflowStore();
const execution = useExecutionStore();

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
  if (execution.running) {
    await execution.stop();
    return;
  }
  const workflowJson = workflow.toJSON();
  try {
    await execution.execute(workflowJson);
  } catch (e) {
    console.error("Workflow execution failed:", e);
  }
}
</script>

<template>
  <header class="flex h-11 items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-surface)] px-4">
    <div class="flex items-center gap-3">
      <span class="text-sm font-semibold">Mimicry</span>
      <span class="text-xs text-[var(--color-text-muted)]">—</span>
      <button
        class="rounded bg-[var(--color-primary)] px-3 py-1 text-xs text-white hover:opacity-90 disabled:opacity-50"
        :disabled="browser.launching"
        @click="browser.connected ? browser.close() : browser.launch()"
      >
        {{ browser.launching ? t('toolbar.launching') : browser.connected ? t('toolbar.closeBrowser') : t('toolbar.launchBrowser') }}
      </button>
      <span class="text-xs" :class="browser.connected ? 'text-green-400' : 'text-[var(--color-text-muted)]'">
        {{ browser.connected ? t('toolbar.connected') : t('toolbar.disconnected') }}
      </span>
    </div>
    <div class="flex items-center gap-2">
      <button
        class="rounded px-3 py-1 text-xs"
        :class="execution.running
          ? 'bg-orange-600 text-white'
          : 'border border-[var(--color-border)] hover:bg-[var(--color-surface-hover)]'"
        :disabled="!browser.connected"
        @click="runWorkflow"
      >
        {{ execution.running ? t('toolbar.stop') : t('toolbar.run') }}
      </button>
      <span v-if="execution.running" class="text-xs text-[var(--color-text-muted)]">
        {{ execution.step }}/{{ execution.total }}
      </span>
      <button
        class="rounded px-3 py-1 text-xs"
        :class="browser.recording
          ? 'bg-red-600 text-white animate-pulse'
          : 'border border-[var(--color-border)] hover:bg-[var(--color-surface-hover)]'"
        :disabled="!browser.connected"
        @click="toggleRecording"
      >
        {{ browser.recording ? t('toolbar.stopRecord') : t('toolbar.record') }}
      </button>
    </div>
  </header>
</template>

<style scoped>
</style>

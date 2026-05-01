<script setup lang="ts">
  import { useBrowserStore } from '../../stores/browser';
  import { toFrontend } from '../../types/action-map';

  const browser = useBrowserStore();
</script>

<template>
  <div class="flex flex-col h-full">
    <div
      class="flex items-center justify-between px-3 py-1 border-b border-[var(--border-primary)]"
    >
      <span class="text-xs font-medium opacity-70">
        Recording
        <span v-if="browser.recording" class="ml-1 text-red-400 animate-pulse">● REC</span>
      </span>
      <span class="text-xs opacity-40">{{ browser.recordedNodes.length }} events</span>
    </div>
    <div class="flex-1 overflow-y-auto text-xs p-2 space-y-1">
      <div
        v-for="(node, i) in browser.recordedNodes"
        :key="i"
        class="flex gap-2 py-1 px-2 rounded hover:bg-[var(--bg-hover)]"
      >
        <span class="text-[var(--accent-primary)] shrink-0 w-16">{{
          toFrontend(node.action)
        }}</span>
        <span class="opacity-60 truncate">{{
          node.data?.selector || node.data?.url || node.data?.value || ''
        }}</span>
      </div>
      <div v-if="browser.recordedNodes.length === 0" class="text-center opacity-30 py-4">
        {{ browser.recording ? 'Waiting for events...' : 'Start recording to see events' }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'

defineProps<{
  data: {
    action: string
    selector?: string
    value?: string
    url?: string
  }
}>()
</script>

<template>
  <div class="node-action">
    <div class="node-header bg-blue-600">{{ data.action || 'Action' }}</div>
    <div class="node-body">
      <div v-if="data.selector" class="node-field">
        <span class="label">选择器</span>
        <span class="value">{{ data.selector }}</span>
      </div>
      <div v-if="data.value" class="node-field">
        <span class="label">值</span>
        <span class="value">{{ data.value }}</span>
      </div>
      <div v-if="data.url" class="node-field">
        <span class="label">URL</span>
        <span class="value">{{ data.url }}</span>
      </div>
    </div>
    <Handle type="target" :position="Position.Top" />
    <Handle type="source" :position="Position.Bottom" />
  </div>
</template>

<style scoped>
.node-action {
  min-width: 160px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  overflow: hidden;
  font-size: 12px;
}
.node-header {
  padding: 4px 8px;
  color: white;
  font-weight: 600;
  text-transform: uppercase;
  font-size: 11px;
}
.node-body {
  padding: 6px 8px;
}
.node-field {
  display: flex;
  gap: 4px;
}
.node-field .label {
  color: var(--color-text-muted);
}
.node-field .value {
  color: var(--color-text);
  word-break: break-all;
}
</style>

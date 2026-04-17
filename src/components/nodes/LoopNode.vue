<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'

defineProps<{
  data: {
    loopType: string
    count?: number
    condition?: string
    variable?: string
    selector?: string
  }
}>()
</script>

<template>
  <div class="node-loop">
    <div class="node-header bg-purple-600">LOOP {{ data.loopType }}</div>
    <div class="node-body">
      <div v-if="data.count" class="node-field">× {{ data.count }}</div>
      <div v-if="data.condition" class="node-field">{{ data.condition }}</div>
      <div v-if="data.variable" class="node-field text-xs text-[var(--color-text-muted)]">→ {{ data.variable }}</div>
    </div>
    <Handle type="target" :position="Position.Top" />
    <Handle id="body" type="source" :position="Position.Bottom" :style="{ left: '30%' }" />
    <Handle id="done" type="source" :position="Position.Bottom" :style="{ left: '70%' }" />
  </div>
</template>

<style scoped>
.node-loop {
  min-width: 140px;
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
  font-size: 11px;
}
.node-body {
  padding: 6px 8px;
}
</style>

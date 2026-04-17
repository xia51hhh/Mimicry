<script setup lang="ts">
import { NodeResizer } from '@vue-flow/node-resizer'
import '@vue-flow/node-resizer/dist/style.css'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{
  data: {
    label?: string
    color?: string
  }
}>()
</script>

<template>
  <div
    class="node-group"
    :style="{
      borderColor: data.color || 'var(--color-node-group)',
      minWidth: '200px',
      minHeight: '120px',
    }"
  >
    <NodeResizer color="transparent" />
    <div class="group-header" :style="{ color: data.color || 'var(--color-node-group)' }">
      {{ data.label || t('group.defaultLabel') }}
    </div>
  </div>
</template>

<style scoped>
.node-group {
  width: 100%;
  height: 100%;
  border: 2px dashed;
  border-radius: 10px;
  background: var(--color-separator-light, rgba(100, 116, 139, 0.05));
  position: relative;
  transition: border-color 0.2s;
}

.node-group:hover {
  background: var(--color-separator, rgba(100, 116, 139, 0.08));
}

.group-header {
  position: absolute;
  top: -10px;
  left: 12px;
  font-size: 11px;
  font-weight: 600;
  background: var(--color-bg);
  padding: 0 6px;
  border-radius: 3px;
}
</style>

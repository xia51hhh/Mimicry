<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useExecutionStore } from '../../stores/execution'
import { useWorkflowStore } from '../../stores/workflow'
import { useValidationStore } from '../../stores/validation'
import { GitBranch } from 'lucide-vue-next'

const props = defineProps<{
  id: string
  selected?: boolean
  data: {
    condition: string
    selector?: string
  }
}>()

const { t } = useI18n()
const execution = useExecutionStore()
const workflow = useWorkflowStore()
const validation = useValidationStore()
const nodeStatus = computed(() => execution.getNodeStatus(props.id))
const isSelected = computed(() => props.selected || workflow.selectedNodeId === props.id)
const diagLevel = computed(() => validation.getNodeMaxLevel(props.id))
</script>

<template>
  <div class="node-condition" :class="[`status-${nodeStatus}`, { 'node-selected': isSelected }, diagLevel && `diag-${diagLevel}`]">
    <Handle type="target" :position="Position.Left" class="handle handle-target" />
    <div class="node-inner">
      <div class="node-icon">
        <GitBranch :size="18" :stroke-width="1.8" />
      </div>
      <span class="node-label">{{ t('nodeTypes.condition') }}</span>
    </div>
    <span v-if="diagLevel" class="diag-badge" :class="`diag-badge-${diagLevel}`">
      {{ diagLevel === 'error' ? '✕' : diagLevel === 'warning' ? '⚠' : 'ℹ' }}
    </span>
    <div class="branch-outputs">
      <div class="branch-out true-out">
        <span class="branch-label">True</span>
        <Handle id="true" type="source" :position="Position.Right" class="handle handle-source" :style="{ top: '35%' }" />
      </div>
      <div class="branch-out false-out">
        <span class="branch-label">False</span>
        <Handle id="false" type="source" :position="Position.Right" class="handle handle-source" :style="{ top: '65%' }" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.node-condition {
  display: flex;
  align-items: center;
  min-width: 140px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 24px;
  padding: 6px 14px 6px 6px;
  font-size: 13px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
  transition: box-shadow 0.2s, border-color 0.2s;
  cursor: pointer;
  position: relative;
}

.node-condition:hover {
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.15);
}

.node-inner {
  display: flex;
  align-items: center;
  gap: 8px;
}

.node-condition:hover {
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.15);
  border-color: var(--color-border-hover, var(--color-border));
}

.node-selected {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.node-icon {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: rgba(255, 152, 0, 0.12);
  color: #ff9800;
}

.node-label {
  color: var(--color-text);
  font-weight: 500;
  white-space: nowrap;
}

.branch-outputs {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-left: 8px;
  position: relative;
}

.branch-out {
  position: relative;
}

.branch-label {
  font-size: 9px;
  font-weight: 600;
  text-transform: uppercase;
}

.true-out .branch-label { color: #66bb6a; }
.false-out .branch-label { color: #ef5350; }

.handle {
  width: 10px !important;
  height: 10px !important;
  border-radius: 50% !important;
  border: 2px solid var(--color-border) !important;
  background: var(--color-surface) !important;
}

.handle-target {
  left: -5px !important;
}

.handle-source {
  right: -5px !important;
}

.status-running { border-color: #42a5f5; box-shadow: 0 0 8px rgba(66, 165, 245, 0.4); }
.status-completed { border-color: #66bb6a; }
.status-error { border-color: #ef5350; }

.diag-error { border-color: #ef5350; }
.diag-warning { border-color: #ffa726; }
.diag-badge { position: absolute; top: -6px; right: -6px; width: 16px; height: 16px; border-radius: 50%; font-size: 10px; line-height: 16px; text-align: center; font-weight: 700; }
.diag-badge-error { background: #ef5350; color: #fff; }
.diag-badge-warning { background: #ffa726; color: #fff; }
.diag-badge-info { background: #42a5f5; color: #fff; }
</style>

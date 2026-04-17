<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import { computed, markRaw, type Component } from 'vue'
import { useI18n } from 'vue-i18n'
import { useExecutionStore } from '../../stores/execution'
import { useWorkflowStore } from '../../stores/workflow'
import {
  Link, PlusCircle, ArrowLeftRight, X, ArrowLeft, ArrowRight, RotateCw,
  MousePointerClick, Keyboard, Move, ScrollText, ListChecks, Command,
  FileText, Tag, Camera, Table, Pin, Upload,
  Wrench, Globe, Timer, ClipboardList, MessageSquare, Zap, AlertCircle
} from 'lucide-vue-next'

const props = defineProps<{
  id: string
  selected?: boolean
  data: {
    action: string
    selector?: string
    value?: string
    url?: string
  }
}>()

const { t } = useI18n()
const execution = useExecutionStore()
const workflow = useWorkflowStore()
const nodeStatus = computed(() => execution.getNodeStatus(props.id))
const isSelected = computed(() => props.selected || workflow.selectedNodeId === props.id)

// Map action to icon
const iconMap: Record<string, Component> = {
  Navigate: markRaw(Link),
  NewTab: markRaw(PlusCircle),
  SwitchTab: markRaw(ArrowLeftRight),
  CloseTab: markRaw(X),
  GoBack: markRaw(ArrowLeft),
  GoForward: markRaw(ArrowRight),
  Reload: markRaw(RotateCw),
  Click: markRaw(MousePointerClick),
  Type: markRaw(Keyboard),
  Hover: markRaw(Move),
  Scroll: markRaw(ScrollText),
  SelectOption: markRaw(ListChecks),
  PressKey: markRaw(Command),
  GetText: markRaw(FileText),
  GetAttribute: markRaw(Tag),
  Screenshot: markRaw(Camera),
  ExtractTable: markRaw(Table),
  SetVariable: markRaw(Pin),
  Export: markRaw(Upload),
  RunScript: markRaw(Wrench),
  HttpRequest: markRaw(Globe),
  Delay: markRaw(Timer),
  Log: markRaw(ClipboardList),
  Comment: markRaw(MessageSquare),
  HandleDialog: markRaw(AlertCircle),
  Clear: markRaw(X),
  Focus: markRaw(Zap),
  UploadFile: markRaw(Upload),
  GetURL: markRaw(Globe),
}

// Color groups based on block category
const colorMap: Record<string, string> = {
  Navigate: '#f0a030', NewTab: '#f0a030', SwitchTab: '#f0a030', CloseTab: '#f0a030',
  GoBack: '#f0a030', GoForward: '#f0a030', Reload: '#f0a030', HandleDialog: '#f0a030',
  Click: '#66bb6a', Type: '#66bb6a', Hover: '#66bb6a', Scroll: '#66bb6a',
  SelectOption: '#66bb6a', PressKey: '#66bb6a', Focus: '#66bb6a', Clear: '#66bb6a',
  GetText: '#42a5f5', GetAttribute: '#42a5f5', Screenshot: '#42a5f5',
  ExtractTable: '#42a5f5', SetVariable: '#42a5f5', Export: '#42a5f5', GetURL: '#42a5f5',
  RunScript: '#ab47bc', HttpRequest: '#ab47bc', Delay: '#ab47bc',
  Log: '#ab47bc', Comment: '#ab47bc', UploadFile: '#ab47bc',
}

const nodeIcon = computed(() => iconMap[props.data.action] || markRaw(Zap))
const nodeColor = computed(() => colorMap[props.data.action] || '#78909c')
const nodeLabel = computed(() => {
  const key = `blocks.${props.data.action}`
  const translated = t(key)
  return translated !== key ? translated : (props.data.action || 'Action')
})
</script>

<template>
  <div class="node-action" :class="[`status-${nodeStatus}`, { 'node-selected': isSelected }]">
    <Handle type="target" :position="Position.Left" class="handle handle-target" />
    <div class="node-inner">
      <div class="node-icon" :style="{ backgroundColor: nodeColor + '22', color: nodeColor }">
        <component :is="nodeIcon" :size="18" :stroke-width="1.8" />
      </div>
      <span class="node-label">{{ nodeLabel }}</span>
    </div>
    <Handle type="source" :position="Position.Right" class="handle handle-source" />
  </div>
</template>

<style scoped>
.node-action {
  display: flex;
  align-items: center;
  min-width: 120px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 24px;
  padding: 6px 14px 6px 6px;
  font-size: 13px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
  transition: box-shadow 0.2s, border-color 0.2s;
  cursor: pointer;
}

.node-action:hover {
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.15);
  border-color: var(--color-border-hover, var(--color-border));
}

.node-selected {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.node-inner {
  display: flex;
  align-items: center;
  gap: 8px;
}

.node-icon {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.node-label {
  color: var(--color-text);
  font-weight: 500;
  white-space: nowrap;
}

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

/* Execution status indicators */
.status-running {
  border-color: #42a5f5;
  box-shadow: 0 0 8px rgba(66, 165, 245, 0.4);
}

.status-completed {
  border-color: #66bb6a;
}

.status-error {
  border-color: #ef5350;
}
</style>

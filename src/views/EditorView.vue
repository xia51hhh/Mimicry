<script setup lang="ts">
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import '@vue-flow/minimap/dist/style.css'
import { useWorkflowStore } from '../stores/workflow'
import ActionNode from '../components/nodes/ActionNode.vue'
import ConditionNode from '../components/nodes/ConditionNode.vue'
import LoopNode from '../components/nodes/LoopNode.vue'

const store = useWorkflowStore()
const { onConnect, addEdges, onPaneReady } = useVueFlow()

onConnect((params) => {
  addEdges([params])
})

onPaneReady((instance) => {
  instance.fitView()
})

function onDragOver(event: DragEvent) {
  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
}

function onDrop(event: DragEvent) {
  const type = event.dataTransfer?.getData('application/mimicry-node')
  if (!type) return

  const bounds = (event.target as HTMLElement).closest('.vue-flow')?.getBoundingClientRect()
  if (!bounds) return

  const position = {
    x: event.clientX - bounds.left,
    y: event.clientY - bounds.top,
  }

  const dataMap: Record<string, Record<string, unknown>> = {
    action: { action: 'CLICK', selector: '' },
    condition: { condition: 'exists', selector: '' },
    loop: { loopType: 'count', count: 5 },
  }

  store.addNode(type, position, dataMap[type] || {})
}
</script>

<template>
  <div class="flex h-full">
    <!-- Node palette -->
    <div class="w-48 border-r border-[var(--color-border)] p-3 space-y-2 bg-[var(--color-surface)]">
      <div class="text-xs font-semibold text-[var(--color-text-muted)] uppercase mb-2">节点</div>
      <div
        v-for="item in [
          { type: 'action', label: '动作', color: 'bg-blue-600' },
          { type: 'condition', label: '条件', color: 'bg-amber-600' },
          { type: 'loop', label: '循环', color: 'bg-purple-600' },
        ]"
        :key="item.type"
        class="flex items-center gap-2 p-2 rounded cursor-grab border border-[var(--color-border)] hover:border-[var(--color-accent)]"
        draggable="true"
        @dragstart="(e: DragEvent) => e.dataTransfer?.setData('application/mimicry-node', item.type)"
      >
        <span class="w-3 h-3 rounded-sm" :class="item.color"></span>
        <span class="text-sm">{{ item.label }}</span>
      </div>
    </div>

    <!-- Canvas -->
    <div class="flex-1" @drop="onDrop" @dragover="onDragOver">
      <VueFlow
        v-model:nodes="store.nodes"
        v-model:edges="store.edges"
        :default-viewport="{ zoom: 1 }"
        fit-view-on-init
        class="h-full"
      >
        <template #node-action="props">
          <ActionNode v-bind="props" />
        </template>
        <template #node-condition="props">
          <ConditionNode v-bind="props" />
        </template>
        <template #node-loop="props">
          <LoopNode v-bind="props" />
        </template>
        <Background />
        <Controls />
        <MiniMap />
      </VueFlow>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import { useWorkflowStore } from '../stores/workflow'
import ActionNode from '../components/nodes/ActionNode.vue'
import ConditionNode from '../components/nodes/ConditionNode.vue'
import LoopNode from '../components/nodes/LoopNode.vue'
import GroupNode from '../components/nodes/GroupNode.vue'
import PropertyPanel from '../components/editor/PropertyPanel.vue'
import BottomPanel from '../components/editor/BottomPanel.vue'
import ContextMenu from '../components/editor/ContextMenu.vue'
import type { ContextMenuItem } from '../components/editor/ContextMenu.vue'
import { useKeyboardShortcuts } from '../composables/useKeyboardShortcuts'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const store = useWorkflowStore()
const { onConnect, addEdges, onPaneReady, onNodeClick, onPaneClick, onNodeContextMenu, onPaneContextMenu, project, fitView, zoomIn, zoomOut } = useVueFlow()

useKeyboardShortcuts()

const showMinimap = ref(true)

// Context menu state
const contextMenu = ref<{ x: number; y: number; items: ContextMenuItem[]; nodeId?: string } | null>(null)

// Clipboard for copy/paste
const clipboard = ref<{ type: string; position: { x: number; y: number }; data: Record<string, unknown> } | null>(null)
let lastPaneContextPos = { x: 0, y: 0 }

const nodeContextItems = computed<ContextMenuItem[]>(() => [
  { id: 'copy', label: t('contextMenu.copy'), shortcut: 'Ctrl+C' },
  { id: 'sep1', label: '', separator: true },
  { id: 'disconnect', label: t('contextMenu.disconnect') },
  { id: 'delete', label: t('contextMenu.delete'), shortcut: 'Delete' },
])

const paneContextItems = computed<ContextMenuItem[]>(() => [
  { id: 'paste', label: t('contextMenu.paste'), shortcut: 'Ctrl+V' },
  { id: 'sep1', label: '', separator: true },
  { id: 'selectAll', label: t('contextMenu.selectAll'), shortcut: 'Ctrl+A' },
  { id: 'fitView', label: t('contextMenu.fitView') },
])

onConnect((params) => {
  addEdges([params])
})

onPaneReady((instance) => {
  instance.fitView()
})

onNodeClick(({ node }) => {
  store.selectNode(node.id)
})

onPaneClick(() => {
  store.selectNode(null)
  contextMenu.value = null
})

// Right-click on node
onNodeContextMenu(({ event, node }) => {
  event.preventDefault()
  const e = event as MouseEvent
  store.selectNode(node.id)
  contextMenu.value = {
    x: e.clientX,
    y: e.clientY,
    items: nodeContextItems.value,
    nodeId: node.id,
  }
})

// Right-click on empty canvas
onPaneContextMenu((event) => {
  event.preventDefault()
  const e = event as MouseEvent
  const canvasEl = document.querySelector('.vue-flow__pane') as HTMLElement
  const bounds = canvasEl?.getBoundingClientRect() || { left: 0, top: 0 }
  lastPaneContextPos = project({
    x: e.clientX - bounds.left,
    y: e.clientY - bounds.top,
  })
  contextMenu.value = {
    x: e.clientX,
    y: e.clientY,
    items: paneContextItems.value.map(item =>
      item.id === 'paste' ? { ...item, disabled: !clipboard.value } : item
    ),
  }
})

function onContextMenuSelect(id: string) {
  const nodeId = contextMenu.value?.nodeId
  contextMenu.value = null

  switch (id) {
    case 'copy': {
      if (!nodeId) return
      const node = store.nodes.find(n => n.id === nodeId)
      if (node) {
        clipboard.value = {
          type: node.type || 'action',
          position: { ...node.position },
          data: { ...node.data },
        }
      }
      break
    }
    case 'paste': {
      if (!clipboard.value) return
      store.addNode(clipboard.value.type, {
        x: lastPaneContextPos.x,
        y: lastPaneContextPos.y,
      }, { ...clipboard.value.data })
      break
    }
    case 'disconnect': {
      if (!nodeId) return
      store.pushSnapshot()
      store.edges = store.edges.filter(e => e.source !== nodeId && e.target !== nodeId)
      break
    }
    case 'delete': {
      if (!nodeId) return
      store.removeNode(nodeId)
      break
    }
    case 'selectAll': {
      // Vue Flow handles multi-selection visually
      break
    }
    case 'fitView': {
      fitView()
      break
    }
  }
}

function onDragOver(event: DragEvent) {
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
}

function onDrop(event: DragEvent) {
  const type = event.dataTransfer?.getData('application/mimicry-node')
  if (!type) return

  const action = event.dataTransfer?.getData('application/mimicry-action') || ''

  const el = (event.currentTarget as HTMLElement)?.querySelector('.vue-flow') || (event.currentTarget as HTMLElement)
  const bounds = el.getBoundingClientRect()

  // Convert screen coordinates to flow coordinates (respects zoom & pan)
  const position = project({
    x: event.clientX - bounds.left,
    y: event.clientY - bounds.top,
  })

  const dataMap: Record<string, Record<string, unknown>> = {
    action: { action: action || 'Click', selector: '' },
    condition: { condition: 'exists', selector: '' },
    loop: { loopType: 'count', count: 5 },
    group: { label: t('group.newGroup') },
  }

  store.addNode(type, position, dataMap[type] || {})
}
</script>

<template>
  <div class="flex h-full">
    <!-- Left: Canvas + BottomPanel -->
    <div class="flex flex-1 flex-col overflow-hidden">
      <div
        class="flex-1 relative overflow-hidden"
        @drop.prevent="onDrop"
        @dragover.prevent="onDragOver"
      >
        <VueFlow
          v-model:nodes="store.nodes"
          v-model:edges="store.edges"
          :default-viewport="{ zoom: 1 }"
          :selection-key-code="'Control'"
          :nodes-selectable="true"
          fit-view-on-init
          class="h-full editor-canvas"
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
          <template #node-group="props">
            <GroupNode v-bind="props" />
          </template>
          <Background />
        </VueFlow>

        <!-- Context Menu -->
        <ContextMenu
          v-if="contextMenu"
          :items="contextMenu.items"
          :x="contextMenu.x"
          :y="contextMenu.y"
          @select="onContextMenuSelect"
          @close="contextMenu = null"
        />
      </div>
      <BottomPanel />
    </div>

    <!-- Right: PropertyPanel (full height) -->
    <PropertyPanel
      :show-minimap="showMinimap"
      :nodes="store.nodes"
      @toggle-minimap="showMinimap = !showMinimap"
      @zoom-in="zoomIn()"
      @zoom-out="zoomOut()"
      @fit-view="fitView()"
    />
  </div>
</template>

<script setup lang="ts">
  import { ref, computed, onMounted, onUnmounted } from 'vue';
  import { VueFlow, useVueFlow, type GraphNode } from '@vue-flow/core';
  import { Background } from '@vue-flow/background';
  import { MiniMap } from '@vue-flow/minimap';
  import '@vue-flow/core/dist/style.css';
  import '@vue-flow/core/dist/theme-default.css';
  import '@vue-flow/minimap/dist/style.css';
  import { useWorkflowStore } from '../stores/workflow';
  import { useBrowserStore } from '../stores/browser';
  import { useExecutionStore } from '../stores/execution';
  import ActionNode from '../components/nodes/ActionNode.vue';
  import ConditionNode from '../components/nodes/ConditionNode.vue';
  import LoopNode from '../components/nodes/LoopNode.vue';
  import GroupNode from '../components/nodes/GroupNode.vue';
  import PropertyPanel from '../components/editor/PropertyPanel.vue';
  import BottomPanel from '../components/editor/BottomPanel.vue';
  import ContextMenu from '../components/editor/ContextMenu.vue';
  import CommandPalette from '../components/editor/CommandPalette.vue';
  import CamoufoxSetup from '../components/CamoufoxSetup.vue';
  import type { ContextMenuItem } from '../components/editor/ContextMenu.vue';
  import { useKeyboardShortcuts } from '../composables/useKeyboardShortcuts';
  import { useI18n } from 'vue-i18n';

  const { t } = useI18n();
  const store = useWorkflowStore();
  const browser = useBrowserStore();
  const execution = useExecutionStore();
  const vueFlow = useVueFlow();
  const {
    onConnect,
    onConnectEnd,
    addEdges,
    onPaneReady,
    onNodeClick,
    onPaneClick,
    onNodeContextMenu,
    onPaneContextMenu,
    project,
    fitView,
  } = vueFlow;

  useKeyboardShortcuts();

  const showMinimap = ref(true);
  const showCamoufoxSetup = ref(false);
  const showCommandPalette = ref(false);

  onMounted(async () => {
    const result = await browser.checkCamoufox();
    if (!result.installed) {
      showCamoufoxSetup.value = true;
    } else {
      // Silently check for updates in background
      browser.checkCamoufoxUpdate();
    }
    window.addEventListener('mimicry:group-selection', groupSelectedNodes);
    window.addEventListener('mimicry:command-palette', openCommandPalette);
  });

  onUnmounted(() => {
    window.removeEventListener('mimicry:group-selection', groupSelectedNodes);
    window.removeEventListener('mimicry:command-palette', openCommandPalette);
  });

  // Context menu state
  const contextMenu = ref<{
    x: number;
    y: number;
    items: ContextMenuItem[];
    nodeId?: string;
  } | null>(null);

  // Clipboard for copy/paste
  const clipboard = ref<{
    type: string;
    position: { x: number; y: number };
    data: Record<string, unknown>;
  } | null>(null);
  let lastPaneContextPos = { x: 0, y: 0 };

  // Quick-add menu state
  const quickAddMenu = ref<{
    x: number;
    y: number;
    flowPos: { x: number; y: number };
  } | null>(null);

  const quickAddTypes = [
    { type: 'action', action: 'Click', icon: '🖱', label: () => t('blocks.Click') },
    { type: 'action', action: 'Type', icon: '⌨', label: () => t('blocks.Type') },
    { type: 'action', action: 'Navigate', icon: '🔗', label: () => t('blocks.Navigate') },
    { type: 'action', action: 'GetText', icon: '📄', label: () => t('blocks.GetText') },
    { type: 'action', action: 'Delay', icon: '⏱', label: () => t('blocks.Delay') },
    { type: 'condition', action: '', icon: '◆', label: () => t('nodeTypes.condition') },
    { type: 'loop', action: '', icon: '🔁', label: () => t('nodeTypes.loop') },
  ];

  const nodeContextItems = computed<ContextMenuItem[]>(() => [
    { id: 'copy', label: t('contextMenu.copy'), shortcut: 'Ctrl+C' },
    { id: 'sep1', label: '', separator: true },
    { id: 'disconnect', label: t('contextMenu.disconnect') },
    { id: 'delete', label: t('contextMenu.delete'), shortcut: 'Delete' },
    { id: 'sep2', label: '', separator: true },
    { id: 'toggleBreakpoint', label: t('contextMenu.toggleBreakpoint') },
    { id: 'groupSelection', label: t('contextMenu.groupSelection'), shortcut: 'Ctrl+G' },
  ]);

  const paneContextItems = computed<ContextMenuItem[]>(() => [
    { id: 'paste', label: t('contextMenu.paste'), shortcut: 'Ctrl+V' },
    { id: 'sep1', label: '', separator: true },
    { id: 'selectAll', label: t('contextMenu.selectAll'), shortcut: 'Ctrl+A' },
    { id: 'groupSelection', label: t('contextMenu.groupSelection'), shortcut: 'Ctrl+G' },
    { id: 'fitView', label: t('contextMenu.fitView') },
  ]);

  onConnect((params) => {
    addEdges([params]);
  });

  // When user drags from a handle and drops on empty canvas, create a new connected node
  onConnectEnd((event) => {
    if (!event) return;
    // Only handle mouse events on empty canvas (not on a node/handle)
    const target = event.target as HTMLElement;
    if (!target?.closest('.vue-flow__pane')) return;

    const mouseEvent = event as MouseEvent;
    const canvasEl = document.querySelector('.vue-flow__pane') as HTMLElement;
    const bounds = canvasEl?.getBoundingClientRect() || { left: 0, top: 0 };
    const flowPos = project({
      x: mouseEvent.clientX - bounds.left,
      y: mouseEvent.clientY - bounds.top,
    });

    // Find which node was the source of the connection (via Vue Flow state)
    const sourceNodeId = vueFlow.connectionStartHandle.value?.nodeId;
    if (!sourceNodeId) return;

    // Create a new action node at drop position
    const newNodeId = store.addNode('action', flowPos, {
      action: 'Click',
      selector: '',
    });

    // Connect source to new node
    addEdges([{
      id: `edge_${sourceNodeId}_${newNodeId}`,
      source: sourceNodeId,
      target: newNodeId,
    }]);

    store.selectNode(newNodeId);
  });

  onPaneReady((instance) => {
    instance.fitView();
  });

  onNodeClick(({ node }) => {
    store.selectNode(node.id);
  });

  onPaneClick(() => {
    store.selectNode(null);
    contextMenu.value = null;
    quickAddMenu.value = null;
  });

  // Double-click on canvas to quick-add
  function onPaneDblClick(event: MouseEvent) {
    const canvasEl = document.querySelector('.vue-flow__pane') as HTMLElement;
    const bounds = canvasEl?.getBoundingClientRect() || { left: 0, top: 0 };
    const flowPos = project({
      x: event.clientX - bounds.left,
      y: event.clientY - bounds.top,
    });
    quickAddMenu.value = {
      x: event.clientX,
      y: event.clientY,
      flowPos,
    };
  }

  function onQuickAdd(item: (typeof quickAddTypes)[number]) {
    if (!quickAddMenu.value) return;
    const pos = quickAddMenu.value.flowPos;
    const dataMap: Record<string, Record<string, unknown>> = {
      action: { action: item.action || 'Click', selector: '' },
      condition: { condition: 'exists', selector: '' },
      loop: { loopType: 'count', count: 5 },
    };
    const nodeId = store.addNode(item.type, pos, dataMap[item.type] || {});
    store.selectNode(nodeId);
    quickAddMenu.value = null;
  }

  // Right-click on node
  onNodeContextMenu(({ event, node }) => {
    event.preventDefault();
    const e = event as MouseEvent;
    store.selectNode(node.id);
    contextMenu.value = {
      x: e.clientX,
      y: e.clientY,
      items: nodeContextItems.value,
      nodeId: node.id,
    };
  });

  // Right-click on empty canvas
  onPaneContextMenu((event) => {
    event.preventDefault();
    const e = event as MouseEvent;
    const canvasEl = document.querySelector('.vue-flow__pane') as HTMLElement;
    const bounds = canvasEl?.getBoundingClientRect() || { left: 0, top: 0 };
    lastPaneContextPos = project({
      x: e.clientX - bounds.left,
      y: e.clientY - bounds.top,
    });
    contextMenu.value = {
      x: e.clientX,
      y: e.clientY,
      items: paneContextItems.value.map((item) =>
        item.id === 'paste' ? { ...item, disabled: !clipboard.value } : item,
      ),
    };
  });

  function onContextMenuSelect(id: string) {
    const nodeId = contextMenu.value?.nodeId;
    contextMenu.value = null;

    switch (id) {
      case 'copy': {
        if (!nodeId) return;
        const node = store.nodes.find((n) => n.id === nodeId);
        if (node) {
          clipboard.value = {
            type: node.type || 'action',
            position: { ...node.position },
            data: { ...node.data },
          };
        }
        break;
      }
      case 'paste': {
        if (!clipboard.value) return;
        store.addNode(
          clipboard.value.type,
          {
            x: lastPaneContextPos.x,
            y: lastPaneContextPos.y,
          },
          { ...clipboard.value.data },
        );
        break;
      }
      case 'disconnect': {
        if (!nodeId) return;
        store.pushSnapshot();
        store.edges = store.edges.filter((e) => e.source !== nodeId && e.target !== nodeId);
        break;
      }
      case 'delete': {
        if (!nodeId) return;
        store.removeNode(nodeId);
        break;
      }
      case 'selectAll': {
        // Vue Flow handles multi-selection visually
        break;
      }
      case 'fitView': {
        fitView();
        break;
      }
      case 'toggleBreakpoint': {
        if (nodeId) execution.toggleBreakpoint(nodeId);
        break;
      }
      case 'groupSelection': {
        groupSelectedNodes();
        break;
      }
    }
  }

  function groupSelectedNodes() {
    const selected = store.nodes.filter((n) => (n as GraphNode).selected && n.type !== 'group');
    if (selected.length < 2) return;

    const padding = 30;
    const minX = Math.min(...selected.map((n) => n.position.x)) - padding;
    const minY = Math.min(...selected.map((n) => n.position.y)) - padding;
    const maxX = Math.max(...selected.map((n) => n.position.x + ((n as GraphNode).dimensions?.width || 150))) + padding;
    const maxY = Math.max(...selected.map((n) => n.position.y + ((n as GraphNode).dimensions?.height || 50))) + padding;

    store.addNode(
      'group',
      { x: minX, y: minY },
      {
        label: t('group.newGroup'),
        color: '#6366f1',
      },
    );

    // Set the group node dimensions
    const groupNode = store.nodes[store.nodes.length - 1];
    if (groupNode) {
      groupNode.style = {
        width: `${maxX - minX}px`,
        height: `${maxY - minY}px`,
      };
    }
  }

  function onDragOver(event: DragEvent) {
    if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
  }

  function onCommandSelect(type: string, action: string) {
    showCommandPalette.value = false;
    const center = project({ x: 400, y: 300 });
    const dataMap: Record<string, Record<string, unknown>> = {
      action: { action: action || 'Click', selector: '' },
      condition: { condition: 'exists', selector: '' },
      loop: { loopType: 'count', count: 5 },
      group: { label: t('group.newGroup') },
    };
    const nodeId = store.addNode(type, center, dataMap[type] || {});
    store.selectNode(nodeId);
  }

  function openCommandPalette() {
    showCommandPalette.value = true;
  }

  function onDrop(event: DragEvent) {
    const type = event.dataTransfer?.getData('application/mimicry-node');
    if (!type) return;

    const action = event.dataTransfer?.getData('application/mimicry-action') || '';

    const el =
      (event.currentTarget as HTMLElement)?.querySelector('.vue-flow') ||
      (event.currentTarget as HTMLElement);
    const bounds = el.getBoundingClientRect();

    // Convert screen coordinates to flow coordinates (respects zoom & pan)
    const position = project({
      x: event.clientX - bounds.left,
      y: event.clientY - bounds.top,
    });

    const dataMap: Record<string, Record<string, unknown>> = {
      action: { action: action || 'Click', selector: '' },
      condition: { condition: 'exists', selector: '' },
      loop: { loopType: 'count', count: 5 },
      group: { label: t('group.newGroup') },
    };

    store.addNode(type, position, dataMap[type] || {});
  }
</script>

<template>
  <div class="flex h-full">
    <!-- Center: Canvas + BottomPanel -->
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
          :class="['h-full editor-canvas', {
            'execution-running': execution.running && !execution.paused,
            'execution-paused': execution.running && execution.paused,
          }]"
          @dblclick="onPaneDblClick"
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
          <MiniMap v-if="showMinimap" pannable zoomable />
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

        <!-- Quick Add Menu (double-click) -->
        <div
          v-if="quickAddMenu"
          class="quick-add-menu"
          :style="{ left: quickAddMenu.x + 'px', top: quickAddMenu.y + 'px' }"
        >
          <div
            v-for="item in quickAddTypes"
            :key="item.action || item.type"
            class="quick-add-item"
            @click="onQuickAdd(item)"
          >
            <span class="quick-add-icon">{{ item.icon }}</span>
            <span class="quick-add-label">{{ item.label() }}</span>
          </div>
        </div>
      </div>
      <BottomPanel />
    </div>

    <!-- Right: PropertyPanel (full height) -->
    <PropertyPanel />

    <!-- Command Palette -->
    <CommandPalette
      :visible="showCommandPalette"
      @select="onCommandSelect"
      @close="showCommandPalette = false"
    />

    <!-- Camoufox Setup Dialog -->
    <CamoufoxSetup :visible="showCamoufoxSetup" @close="showCamoufoxSetup = false" />
  </div>
</template>

<style scoped>
  .quick-add-menu {
    position: fixed;
    z-index: 100;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    padding: 4px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
    min-width: 140px;
  }

  .quick-add-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    color: var(--color-text);
    transition: background 0.1s;
  }

  .quick-add-item:hover {
    background: var(--color-surface-hover);
  }

  .quick-add-icon {
    font-size: 14px;
    width: 20px;
    text-align: center;
  }

  .quick-add-label {
    white-space: nowrap;
  }
</style>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { markRaw, type Component } from 'vue'
import {
  Link, GitBranch, Repeat, Package,
  PlusCircle, ArrowLeftRight, X, ArrowLeft, ArrowRight, RotateCw,
  MousePointerClick, Keyboard, Move, ScrollText, ListChecks, Command,
  FileText, Tag, Camera, Table, Pin, Upload,
  Wrench, Globe, Timer, ClipboardList, MessageSquare,
} from 'lucide-vue-next'
import { usePanel } from '../../composables/usePanel'

const { t } = useI18n()

defineProps<{
  activeId: string
  visible: boolean
}>()

const searchQuery = ref('')

const { size: sidebarWidth, onResizeStart } = usePanel({
  direction: 'horizontal',
  defaultSize: 260,
  minSize: 200,
  maxSize: 500,
  storageKey: 'mimicry-sidebar-width',
  invertDelta: true,
})

interface BlockItem {
  type: string
  action?: string
  icon: Component
}

// Block categories based on block-system.md
const blockCategories: { key: string; items: BlockItem[] }[] = [
  {
    key: 'trigger',
    items: [
      { type: 'action', action: 'Navigate', icon: markRaw(Link) },
      { type: 'condition', icon: markRaw(GitBranch) },
      { type: 'loop', icon: markRaw(Repeat) },
      { type: 'group', icon: markRaw(Package) },
    ],
  },
  {
    key: 'browser',
    items: [
      { type: 'action', action: 'NewTab', icon: markRaw(PlusCircle) },
      { type: 'action', action: 'SwitchTab', icon: markRaw(ArrowLeftRight) },
      { type: 'action', action: 'CloseTab', icon: markRaw(X) },
      { type: 'action', action: 'GoBack', icon: markRaw(ArrowLeft) },
      { type: 'action', action: 'GoForward', icon: markRaw(ArrowRight) },
      { type: 'action', action: 'Reload', icon: markRaw(RotateCw) },
    ],
  },
  {
    key: 'interaction',
    items: [
      { type: 'action', action: 'Click', icon: markRaw(MousePointerClick) },
      { type: 'action', action: 'Type', icon: markRaw(Keyboard) },
      { type: 'action', action: 'Hover', icon: markRaw(Move) },
      { type: 'action', action: 'Scroll', icon: markRaw(ScrollText) },
      { type: 'action', action: 'SelectOption', icon: markRaw(ListChecks) },
      { type: 'action', action: 'PressKey', icon: markRaw(Command) },
    ],
  },
  {
    key: 'data',
    items: [
      { type: 'action', action: 'GetText', icon: markRaw(FileText) },
      { type: 'action', action: 'GetAttribute', icon: markRaw(Tag) },
      { type: 'action', action: 'Screenshot', icon: markRaw(Camera) },
      { type: 'action', action: 'ExtractTable', icon: markRaw(Table) },
      { type: 'action', action: 'SetVariable', icon: markRaw(Pin) },
      { type: 'action', action: 'Export', icon: markRaw(Upload) },
    ],
  },
  {
    key: 'advanced',
    items: [
      { type: 'action', action: 'RunScript', icon: markRaw(Wrench) },
      { type: 'action', action: 'HttpRequest', icon: markRaw(Globe) },
      { type: 'action', action: 'Delay', icon: markRaw(Timer) },
      { type: 'action', action: 'Log', icon: markRaw(ClipboardList) },
      { type: 'action', action: 'Comment', icon: markRaw(MessageSquare) },
    ],
  },
]

const collapsedCategories = ref<Set<string>>(new Set())

function toggleCategory(key: string) {
  if (collapsedCategories.value.has(key)) {
    collapsedCategories.value.delete(key)
  } else {
    collapsedCategories.value.add(key)
  }
}

function getBlockLabel(item: { type: string; action?: string }): string {
  if (item.action) {
    return t(`blocks.${item.action}`)
  }
  return t(`nodeTypes.${item.type}`)
}

function matchesSearch(item: { type: string; action?: string }): boolean {
  if (!searchQuery.value) return true
  const label = getBlockLabel(item).toLowerCase()
  return label.includes(searchQuery.value.toLowerCase())
}

function onDragStart(e: DragEvent, item: { type: string; action?: string }) {
  if (!e.dataTransfer) return
  e.dataTransfer.effectAllowed = 'move'
  e.dataTransfer.setData('application/mimicry-node', item.type)
  if (item.action) {
    e.dataTransfer.setData('application/mimicry-action', item.action)
  }
}
</script>

<template>
  <aside
    v-show="visible"
    class="sidebar"
    :style="{ width: sidebarWidth + 'px' }"
  >
    <div class="sidebar-content">
      <!-- Header -->
      <div class="sidebar-header">
        <span class="text-sm font-semibold">{{ t('sidebar.blocks') }}</span>
      </div>

      <!-- Search -->
      <div class="sidebar-search">
        <input
          v-model="searchQuery"
          type="text"
          class="search-input"
          :placeholder="t('sidebar.search')"
        />
      </div>

      <!-- Block categories -->
      <div class="sidebar-body">
        <div v-for="cat in blockCategories" :key="cat.key" class="category">
          <button class="category-header" @click="toggleCategory(cat.key)">
            <span class="category-arrow" :class="{ collapsed: collapsedCategories.has(cat.key) }">▼</span>
            <span class="category-label">{{ t(`blockCategories.${cat.key}`) }}</span>
          </button>
          <div
            v-show="!collapsedCategories.has(cat.key)"
            class="category-items"
          >
            <div
              v-for="(item, idx) in cat.items"
              v-show="matchesSearch(item)"
              :key="idx"
              class="block-item"
              draggable="true"
              @dragstart="(e) => onDragStart(e, item)"
            >
              <component :is="item.icon" :size="14" :stroke-width="1.5" class="block-icon" />
              <span class="block-label">{{ getBlockLabel(item) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Resize handle -->
    <div class="resize-handle" @mousedown="onResizeStart" />
  </aside>
</template>

<style scoped>
.sidebar {
  position: relative;
  display: flex;
  min-width: 200px;
  max-width: 500px;
  background: var(--color-surface);
  border-right: 1px solid var(--color-border);
  flex-shrink: 0;
}

.sidebar-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-header {
  padding: 10px 14px;
  border-bottom: 1px solid var(--color-border);
}

.sidebar-search {
  padding: 8px 10px;
}

.search-input {
  width: 100%;
  padding: 6px 10px;
  font-size: 12px;
  background: var(--color-bg);
  color: var(--color-text);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  outline: none;
}

.search-input:focus {
  border-color: var(--color-primary);
}

.sidebar-body {
  flex: 1;
  overflow-y: auto;
  padding: 0 6px 8px;
}

.category {
  margin-bottom: 2px;
}

.category-header {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 6px 8px;
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  background: none;
  border: none;
  cursor: pointer;
}

.category-header:hover {
  color: var(--color-text);
}

.category-arrow {
  font-size: 8px;
  transition: transform 0.15s;
}

.category-arrow.collapsed {
  transform: rotate(-90deg);
}

.category-items {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
  padding: 0 4px 4px;
}

.block-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 8px 4px;
  border-radius: 6px;
  border: 1px solid var(--color-border);
  cursor: grab;
  transition: all 0.15s;
}

.block-item:hover {
  border-color: var(--color-primary);
  background: var(--color-surface-hover);
}

.block-item:active {
  cursor: grabbing;
}

.block-icon {
  color: var(--color-text-muted);
  flex-shrink: 0;
}

.block-label {
  font-size: 11px;
  color: var(--color-text);
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.resize-handle {
  position: absolute;
  top: 0;
  right: -2px;
  width: 4px;
  height: 100%;
  cursor: col-resize;
  z-index: 20;
}

.resize-handle:hover {
  background: var(--color-primary);
  opacity: 0.5;
}
</style>


<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useWorkflowStore } from '../../stores/workflow'
import { usePanel, usePanelLayout } from '../../composables/usePanel'
import { ChevronDown } from 'lucide-vue-next'
import type { Node } from '@vue-flow/core'

const { t } = useI18n()
const store = useWorkflowStore()
const activeTab = ref<'settings' | 'data'>('settings')
const canvasToolsCollapsed = ref(false)

const { size: panelWidth, collapsed, onResizeStart } = usePanel({
  direction: 'horizontal',
  defaultSize: 280,
  minSize: 200,
  maxSize: 500,
  storageKey: 'mimicry-right-width',
})

// Sync with global layout state
const { rightPanelCollapsed } = usePanelLayout()
watch(rightPanelCollapsed, (v) => { collapsed.value = v })
watch(collapsed, (v) => { rightPanelCollapsed.value = v })

defineProps<{
  showMinimap?: boolean
  nodes?: Node[]
}>()

const emit = defineEmits<{
  (e: 'toggle-minimap'): void
  (e: 'zoom-in'): void
  (e: 'zoom-out'): void
  (e: 'fit-view'): void
}>()

const node = computed(() => store.selectedNode)
const nodeType = computed(() => node.value?.type || '')

// Local editable copy of node data
const editData = ref<Record<string, unknown>>({})

watch(
  () => node.value,
  (n) => {
    if (n) {
      editData.value = { ...n.data }
    } else {
      editData.value = {}
    }
  },
  { immediate: true, deep: true }
)

function updateField(field: string, value: unknown) {
  editData.value[field] = value
  if (node.value) {
    store.updateNodeData(node.value.id, { [field]: value })
  }
}

// Action type options based on block-system.md
const actionTypes = [
  { group: t('blockCategories.browser'), items: ['Navigate', 'NewTab', 'SwitchTab', 'CloseTab', 'GoBack', 'GoForward', 'Reload', 'HandleDialog'] },
  { group: t('blockCategories.interaction'), items: ['Click', 'Type', 'Hover', 'PressKey', 'Scroll', 'SelectOption', 'UploadFile', 'Clear', 'Focus'] },
  { group: t('blockCategories.data'), items: ['GetText', 'GetAttribute', 'GetURL', 'Screenshot', 'ExtractTable', 'SetVariable', 'Export'] },
  { group: t('blockCategories.advanced'), items: ['RunScript', 'HttpRequest', 'Log', 'Delay', 'Comment'] },
]

const loopTypes = [
  { value: 'count', label: t('loopTypes.count') },
  { value: 'items', label: t('loopTypes.items') },
  { value: 'while', label: t('loopTypes.while') },
]

const conditionTypes = [
  { value: 'exists', label: t('conditionTypes.exists') },
  { value: 'not_exists', label: t('conditionTypes.not_exists') },
  { value: 'visible', label: t('conditionTypes.visible') },
  { value: 'text_contains', label: t('conditionTypes.text_contains') },
  { value: 'url_contains', label: t('conditionTypes.url_contains') },
  { value: 'expression', label: t('conditionTypes.expression') },
]

const onErrorOptions = [
  { value: 'stop', label: t('errorOptions.stop') },
  { value: 'continue', label: t('errorOptions.continue') },
  { value: 'retry', label: t('errorOptions.retry') },
]
</script>

<template>
  <aside v-show="!collapsed" class="property-panel" :style="{ width: panelWidth + 'px', minWidth: panelWidth + 'px' }">
    <!-- Resize handle (left edge) -->
    <div class="resize-handle-left" @mousedown="onResizeStart" />
    <!-- Empty state -->
    <div v-if="!node" class="empty-state">
      <div class="text-sm text-[var(--color-text-muted)]">{{ t('propertyPanel.selectNode') }}</div>
    </div>

    <!-- Node properties -->
    <template v-else>
      <!-- Header -->
      <div class="panel-header">
        <div class="flex items-center gap-2">
          <span
            class="w-3 h-3 rounded-sm"
            :class="{
              'bg-blue-600': nodeType === 'action',
              'bg-amber-600': nodeType === 'condition',
              'bg-purple-600': nodeType === 'loop',
              'bg-emerald-600': nodeType === 'group',
            }"
          />
          <span class="font-semibold text-sm capitalize">{{ t(`nodeTypes.${nodeType}`) }}</span>
          <span class="text-xs text-[var(--color-text-muted)]">{{ node.id }}</span>
        </div>
      </div>

      <!-- Tabs -->
      <div class="tab-bar">
        <button
          :class="['tab-btn', activeTab === 'settings' && 'active']"
          @click="activeTab = 'settings'"
        >
          {{ t('propertyPanel.settings') }}
        </button>
        <button
          :class="['tab-btn', activeTab === 'data' && 'active']"
          @click="activeTab = 'data'"
        >
          {{ t('propertyPanel.data') }}
        </button>
      </div>

      <!-- Settings Tab -->
      <div v-if="activeTab === 'settings'" class="panel-body">
        <!-- Action Node -->
        <template v-if="nodeType === 'action'">
          <div class="field-group">
            <label class="field-label">{{ t('propertyPanel.actionType') }}</label>
            <select
              class="field-input"
              :value="editData.action"
              @change="updateField('action', ($event.target as HTMLSelectElement).value)"
            >
              <optgroup v-for="group in actionTypes" :key="group.group" :label="group.group">
                <option v-for="item in group.items" :key="item" :value="item">{{ t(`blocks.${item}`) }}</option>
              </optgroup>
            </select>
          </div>

          <div class="field-group">
            <label class="field-label">{{ t('propertyPanel.selector') }}</label>
            <input
              type="text"
              class="field-input"
              :placeholder="t('propertyPanel.selectorPlaceholder')"
              :value="editData.selector"
              @input="updateField('selector', ($event.target as HTMLInputElement).value)"
            />
          </div>

          <div
            v-if="['Type', 'SelectOption'].includes(String(editData.action))"
            class="field-group"
          >
            <label class="field-label">{{ t('propertyPanel.inputValue') }}</label>
            <input
              type="text"
              class="field-input"
              :placeholder="t('propertyPanel.inputValuePlaceholder')"
              :value="editData.value"
              @input="updateField('value', ($event.target as HTMLInputElement).value)"
            />
          </div>

          <div v-if="editData.action === 'Navigate'" class="field-group">
            <label class="field-label">URL</label>
            <input
              type="text"
              class="field-input"
              placeholder="https://..."
              :value="editData.url"
              @input="updateField('url', ($event.target as HTMLInputElement).value)"
            />
          </div>

          <div class="field-group">
            <label class="field-label">{{ t('propertyPanel.timeout') }}</label>
            <input
              type="number"
              class="field-input"
              placeholder="5000"
              :value="editData.timeout"
              @input="updateField('timeout', Number(($event.target as HTMLInputElement).value))"
            />
          </div>
        </template>

        <!-- Condition Node -->
        <template v-if="nodeType === 'condition'">
          <div class="field-group">
            <label class="field-label">{{ t('propertyPanel.conditionType') }}</label>
            <select
              class="field-input"
              :value="editData.condition"
              @change="updateField('condition', ($event.target as HTMLSelectElement).value)"
            >
              <option v-for="opt in conditionTypes" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </div>

          <div class="field-group">
            <label class="field-label">{{ t('propertyPanel.selector') }}</label>
            <input
              type="text"
              class="field-input"
              placeholder="#element"
              :value="editData.selector"
              @input="updateField('selector', ($event.target as HTMLInputElement).value)"
            />
          </div>

          <div
            v-if="['text_contains', 'url_contains', 'expression'].includes(String(editData.condition))"
            class="field-group"
          >
            <label class="field-label">{{ t('propertyPanel.matchValue') }}</label>
            <input
              type="text"
              class="field-input"
              :placeholder="t('propertyPanel.matchValuePlaceholder')"
              :value="editData.matchValue"
              @input="updateField('matchValue', ($event.target as HTMLInputElement).value)"
            />
          </div>
        </template>

        <!-- Loop Node -->
        <template v-if="nodeType === 'loop'">
          <div class="field-group">
            <label class="field-label">{{ t('propertyPanel.loopType') }}</label>
            <select
              class="field-input"
              :value="editData.loopType"
              @change="updateField('loopType', ($event.target as HTMLSelectElement).value)"
            >
              <option v-for="opt in loopTypes" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </div>

          <div v-if="editData.loopType === 'count'" class="field-group">
            <label class="field-label">{{ t('propertyPanel.loopCount') }}</label>
            <input
              type="number"
              class="field-input"
              placeholder="10"
              :value="editData.count"
              @input="updateField('count', Number(($event.target as HTMLInputElement).value))"
            />
          </div>

          <div v-if="editData.loopType === 'items'" class="field-group">
            <label class="field-label">{{ t('propertyPanel.loopSelectorLabel') }}</label>
            <input
              type="text"
              class="field-input"
              placeholder=".list-item"
              :value="editData.selector"
              @input="updateField('selector', ($event.target as HTMLInputElement).value)"
            />
          </div>

          <div v-if="editData.loopType === 'while'" class="field-group">
            <label class="field-label">{{ t('propertyPanel.loopCondition') }}</label>
            <input
              type="text"
              class="field-input"
              placeholder="{{$var.hasNext}}"
              :value="editData.condition"
              @input="updateField('condition', ($event.target as HTMLInputElement).value)"
            />
          </div>

          <div class="field-group">
            <label class="field-label">{{ t('propertyPanel.loopVariable') }}</label>
            <input
              type="text"
              class="field-input"
              placeholder="item"
              :value="editData.variable"
              @input="updateField('variable', ($event.target as HTMLInputElement).value)"
            />
          </div>

          <div class="field-group">
            <label class="field-label">{{ t('propertyPanel.maxIterations') }}</label>
            <input
              type="number"
              class="field-input"
              placeholder="100"
              :value="editData.max"
              @input="updateField('max', Number(($event.target as HTMLInputElement).value))"
            />
          </div>
        </template>

        <!-- Group Node -->
        <template v-if="nodeType === 'group'">
          <div class="field-group">
            <label class="field-label">{{ t('propertyPanel.groupName') }}</label>
            <input
              type="text"
              class="field-input"
              :placeholder="t('propertyPanel.groupName')"
              :value="editData.label"
              @input="updateField('label', ($event.target as HTMLInputElement).value)"
            />
          </div>

          <div class="field-group">
            <label class="field-label">{{ t('propertyPanel.groupColor') }}</label>
            <div class="flex gap-2">
              <button
                v-for="color in ['#3b82f6', '#22c55e', '#eab308', '#ef4444', '#a855f7', '#64748b']"
                :key="color"
                class="w-6 h-6 rounded border-2 transition-all"
                :class="editData.color === color ? 'border-white scale-110' : 'border-transparent'"
                :style="{ background: color }"
                @click="updateField('color', color)"
              />
            </div>
          </div>
        </template>

        <!-- Common: Error handling -->
        <div class="divider" />
        <div class="field-group">
            <label class="field-label">{{ t('propertyPanel.errorHandling') }}</label>
          <select
            class="field-input"
            :value="editData.onError || 'stop'"
            @change="updateField('onError', ($event.target as HTMLSelectElement).value)"
          >
            <option v-for="opt in onErrorOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>

        <div v-if="editData.onError === 'retry'" class="field-group">
          <label class="field-label">{{ t('propertyPanel.retryCount') }}</label>
          <input
            type="number"
            class="field-input"
            placeholder="3"
            :value="editData.retryCount || 3"
            @input="updateField('retryCount', Number(($event.target as HTMLInputElement).value))"
          />
        </div>

        <!-- Note -->
        <div class="field-group">
          <label class="field-label">{{ t('propertyPanel.note') }}</label>
          <textarea
            class="field-input resize-none"
            rows="2"
            :placeholder="t('propertyPanel.notePlaceholder')"
            :value="editData.note as string"
            @input="updateField('note', ($event.target as HTMLTextAreaElement).value)"
          />
        </div>
      </div>

      <!-- Data Tab -->
      <div v-if="activeTab === 'data'" class="panel-body">
        <div class="text-xs text-[var(--color-text-muted)] mb-2">{{ t('propertyPanel.nodeData') }}</div>
        <pre class="data-view">{{ JSON.stringify(node.data, null, 2) }}</pre>
      </div>
    </template>

    <!-- Canvas Tools at bottom (matches BottomPanel height) -->
    <div
      class="canvas-tools"
      :style="{ height: canvasToolsCollapsed ? '30px' : '200px' }"
    >
      <div class="canvas-tools-header" @click="canvasToolsCollapsed = !canvasToolsCollapsed" style="cursor: pointer;">
        <div style="display: flex; align-items: center; gap: 4px;">
          <ChevronDown
            :size="12"
            :stroke-width="2"
            :style="{ transform: canvasToolsCollapsed ? 'rotate(-90deg)' : 'rotate(0)', transition: 'transform 0.2s' }"
          />
          <span class="tools-label">{{ t('canvas.title') }}</span>
        </div>
        <div class="tools-actions" @click.stop>
          <button class="tool-btn" :title="t('canvas.zoomIn')" @click="emit('zoom-in')">+</button>
          <button class="tool-btn" :title="t('canvas.zoomOut')" @click="emit('zoom-out')">−</button>
          <button class="tool-btn" :title="t('canvas.fitView')" @click="emit('fit-view')">⊞</button>
          <button class="tool-btn" :title="showMinimap ? t('canvas.hideMinimap') : t('canvas.showMinimap')" @click="emit('toggle-minimap')">
            {{ showMinimap ? '👁' : '👁‍🗨' }}
          </button>
        </div>
      </div>
      <div v-if="showMinimap && !canvasToolsCollapsed" class="minimap-placeholder">
        <div class="minimap-content">
          <div
            v-for="n in (nodes || [])"
            :key="n.id"
            class="minimap-node"
            :style="{
              left: (n.position.x / 10) + 'px',
              top: (n.position.y / 10) + 'px',
              background: n.type === 'action' ? 'var(--color-node-action)' :
                          n.type === 'condition' ? 'var(--color-node-condition)' :
                          n.type === 'loop' ? 'var(--color-node-loop)' :
                          'var(--color-node-group)',
            }"
          />
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.property-panel {
  position: relative;
  border-left: 1px solid var(--color-border);
  background: var(--color-surface);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex-shrink: 0;
}

.resize-handle-left {
  position: absolute;
  top: 0;
  left: -2px;
  width: 4px;
  height: 100%;
  cursor: col-resize;
  z-index: 20;
}

.resize-handle-left:hover {
  background: var(--color-primary);
  opacity: 0.5;
}

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.panel-header {
  padding: 10px 12px;
  border-bottom: 1px solid var(--color-border);
}

.tab-bar {
  display: flex;
  border-bottom: 1px solid var(--color-border);
}

.tab-btn {
  flex: 1;
  padding: 6px 0;
  font-size: 12px;
  color: var(--color-text-muted);
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  transition: all 0.15s;
}

.tab-btn:hover {
  color: var(--color-text);
}

.tab-btn.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
}

.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.field-group {
  margin-bottom: 12px;
}

.field-label {
  display: block;
  font-size: 11px;
  color: var(--color-text-muted);
  margin-bottom: 4px;
  font-weight: 500;
}

.field-input {
  width: 100%;
  padding: 6px 8px;
  font-size: 12px;
  background: var(--color-bg);
  color: var(--color-text);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  outline: none;
  transition: border-color 0.15s;
}

.field-input:focus {
  border-color: var(--color-primary);
}

select.field-input {
  cursor: pointer;
}

.divider {
  height: 1px;
  background: var(--color-border);
  margin: 12px 0;
}

.data-view {
  font-size: 11px;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  padding: 8px;
  overflow: auto;
  max-height: 400px;
  white-space: pre-wrap;
  word-break: break-all;
}

/* Canvas tools section */
.canvas-tools {
  border-top: 1px solid var(--color-border);
  flex-shrink: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: height 0.2s ease;
}

.canvas-tools-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
}

.tools-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.tools-actions {
  display: flex;
  gap: 2px;
}

.tool-btn {
  width: 24px;
  height: 24px;
  border-radius: 4px;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-text-muted);
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.tool-btn:hover {
  background: var(--color-surface-hover);
  color: var(--color-text);
}

.minimap-placeholder {
  padding: 0 10px 10px;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.minimap-content {
  position: relative;
  flex: 1;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  overflow: hidden;
}

.minimap-node {
  position: absolute;
  width: 16px;
  height: 8px;
  border-radius: 2px;
  opacity: 0.8;
}
</style>

<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import JsonEditor from './JsonEditor.vue'
import { useExecutionStore } from '../../stores/execution'
import { usePanel, usePanelLayout } from '../../composables/usePanel'

const { t } = useI18n()

const execution = useExecutionStore()
const activeTab = ref<'json' | 'logs' | 'variables'>('json')
const logContainer = ref<HTMLElement>()

const { size: panelHeight, collapsed, onResizeStart, toggle: toggleCollapse } = usePanel({
  direction: 'vertical',
  defaultSize: 200,
  minSize: 100,
  maxSize: 500,
  storageKey: 'mimicry-bottom-height',
})

// Sync with global layout state
const { bottomCollapsed, bottomPanelHeight } = usePanelLayout()
watch(bottomCollapsed, (v) => { collapsed.value = v })
watch(collapsed, (v) => { bottomCollapsed.value = v })
watch(panelHeight, (v) => { bottomPanelHeight.value = v }, { immediate: true })

// Auto-scroll logs
watch(
  () => execution.logs.length,
  async () => {
    if (activeTab.value === 'logs' && logContainer.value) {
      await nextTick()
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  }
)

// Auto-switch to logs when execution starts
watch(
  () => execution.running,
  (isRunning) => {
    if (isRunning) {
      activeTab.value = 'logs'
      collapsed.value = false
    }
  }
)

const levelColors: Record<string, string> = {
  info: 'text-blue-400',
  warn: 'text-amber-400',
  error: 'text-red-400',
  debug: 'text-gray-400',
}
</script>

<template>
  <div class="bottom-panel" :class="{ collapsed }" :style="collapsed ? {} : { height: panelHeight + 'px' }">
    <!-- Resize handle -->
    <div class="resize-handle" @mousedown="onResizeStart" />
    <!-- Tab bar -->
    <div class="tab-bar">
      <div class="flex items-center gap-1">
        <button
          :class="['tab-btn', activeTab === 'json' && 'active']"
          @click="activeTab = 'json'; collapsed = false"
        >
          {{ t('bottomPanel.json') }}
        </button>
        <button
          :class="['tab-btn', activeTab === 'logs' && 'active']"
          @click="activeTab = 'logs'; collapsed = false"
        >
          {{ t('bottomPanel.logs') }}
        </button>
        <button
          :class="['tab-btn', activeTab === 'variables' && 'active']"
          @click="activeTab = 'variables'; collapsed = false"
        >
          {{ t('bottomPanel.variables') }}
        </button>
      </div>
      <button class="collapse-btn" @click="toggleCollapse">
        {{ collapsed ? '▲' : '▼' }}
      </button>
    </div>

    <!-- Panel content -->
    <div v-show="!collapsed" class="panel-content">
      <JsonEditor v-if="activeTab === 'json'" />

      <div v-else-if="activeTab === 'logs'" ref="logContainer" class="log-panel">
        <div v-if="execution.logs.length === 0" class="empty-hint">{{ t('bottomPanel.noLogs') }}</div>
        <div v-else class="log-entries">
          <div
            v-for="(entry, i) in execution.logs"
            :key="i"
            class="log-entry"
          >
            <span class="log-time">{{ entry.time }}</span>
            <span :class="['log-level', levelColors[entry.level]]">{{ entry.level.toUpperCase() }}</span>
            <span class="log-msg">{{ entry.message }}</span>
          </div>
        </div>
      </div>

      <div v-else-if="activeTab === 'variables'" class="variables-panel">
        <div v-if="Object.keys(execution.variables).length === 0" class="empty-hint">{{ t('bottomPanel.noVariables') }}</div>
        <table v-else class="var-table">
          <thead>
            <tr>
              <th>{{ t('bottomPanel.varName') }}</th>
              <th>{{ t('bottomPanel.varValue') }}</th>
              <th>{{ t('bottomPanel.varType') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(val, key) in execution.variables" :key="key">
              <td class="var-name">{{ key }}</td>
              <td class="var-value">{{ typeof val === 'object' ? JSON.stringify(val) : String(val) }}</td>
              <td class="var-type">{{ typeof val }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.bottom-panel {
  border-top: 1px solid var(--color-border);
  background: var(--color-surface);
  display: flex;
  flex-direction: column;
  height: 200px;
  min-height: 32px;
  transition: height 0.2s ease;
  position: relative;
}

.bottom-panel.collapsed {
  height: 32px !important;
}

.resize-handle {
  position: absolute;
  top: -2px;
  left: 0;
  right: 0;
  height: 4px;
  cursor: row-resize;
  z-index: 20;
}

.resize-handle:hover {
  background: var(--color-primary);
  opacity: 0.5;
}

.tab-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 32px;
  min-height: 32px;
  padding: 0 8px;
  border-bottom: 1px solid var(--color-border);
}

.tab-btn {
  padding: 4px 10px;
  font-size: 11px;
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

.collapse-btn {
  padding: 2px 6px;
  font-size: 10px;
  color: var(--color-text-muted);
  background: none;
  border: none;
  cursor: pointer;
}

.collapse-btn:hover {
  color: var(--color-text);
}

.panel-content {
  flex: 1;
  overflow: hidden;
}

.log-panel,
.variables-panel {
  height: 100%;
  overflow-y: auto;
  padding: 8px 12px;
}

.empty-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  font-size: 12px;
  color: var(--color-text-muted);
}

.log-entries {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 11px;
}

.log-entry {
  display: flex;
  gap: 8px;
  padding: 2px 0;
  border-bottom: 1px solid var(--color-separator-light);
}

.log-time {
  color: var(--color-text-muted);
  flex-shrink: 0;
}

.log-level {
  flex-shrink: 0;
  width: 44px;
  font-weight: 600;
}

.log-msg {
  color: var(--color-text);
  word-break: break-all;
}

.var-table {
  width: 100%;
  font-size: 12px;
  border-collapse: collapse;
}

.var-table th {
  text-align: left;
  font-size: 11px;
  font-weight: 500;
  color: var(--color-text-muted);
  padding: 4px 8px;
  border-bottom: 1px solid var(--color-border);
}

.var-table td {
  padding: 4px 8px;
  border-bottom: 1px solid var(--color-separator-light);
}

.var-name {
  color: var(--color-primary);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}

.var-value {
  color: var(--color-text);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  max-width: 400px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.var-type {
  color: var(--color-text-muted);
  font-size: 11px;
}
</style>

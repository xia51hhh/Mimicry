<script setup lang="ts">
  import { ref, nextTick, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import JsonEditor from './JsonEditor.vue';
  import { useExecutionStore } from '../../stores/execution';
  import { useValidationStore } from '../../stores/validation';
  import { useWorkflowStore } from '../../stores/workflow';
  import { usePanel, usePanelLayout } from '../../composables/usePanel';
  import { useFileOps } from '../../composables/useFileOps';
  import { save } from '@tauri-apps/plugin-dialog';
  import { invoke } from '@tauri-apps/api/core';

  const { t } = useI18n();

  const execution = useExecutionStore();
  const validation = useValidationStore();
  const workflow = useWorkflowStore();
  const fileOps = useFileOps();
  const activeTab = ref<'json' | 'logs' | 'variables' | 'problems'>('json');
  const logContainer = ref<HTMLElement>();

  const {
    size: panelHeight,
    collapsed,
    onResizeStart,
    toggle: toggleCollapse,
  } = usePanel({
    direction: 'vertical',
    defaultSize: 200,
    minSize: 100,
    maxSize: 500,
    storageKey: 'mimicry-bottom-height',
  });

  // Sync with global layout state
  const { bottomCollapsed, bottomPanelHeight } = usePanelLayout();
  watch(bottomCollapsed, (v) => {
    collapsed.value = v;
  });
  watch(collapsed, (v) => {
    bottomCollapsed.value = v;
  });
  watch(
    panelHeight,
    (v) => {
      bottomPanelHeight.value = v;
    },
    { immediate: true },
  );

  // Auto-scroll logs
  watch(
    () => execution.logs.length,
    async () => {
      if (activeTab.value === 'logs' && logContainer.value) {
        await nextTick();
        logContainer.value.scrollTop = logContainer.value.scrollHeight;
      }
    },
  );

  // Auto-switch to logs when execution starts
  watch(
    () => execution.running,
    (isRunning) => {
      if (isRunning) {
        activeTab.value = 'logs';
        collapsed.value = false;
      }
    },
  );

  const levelColors: Record<string, string> = {
    info: 'text-blue-400',
    warn: 'text-amber-400',
    error: 'text-red-400',
    debug: 'text-gray-400',
  };

  /** Import workflow JSON from clipboard or file (supports all formats) */
  async function importJson() {
    await fileOps.importFile();
  }

  /** Run standalone validation */
  async function runValidation() {
    const wf = workflow.toJSON();
    if (wf) {
      await validation.validate(wf as unknown as Record<string, unknown>);
    }
  }

  /** Export execution logs as text file */
  async function exportLogs() {
    if (execution.logs.length === 0) return;
    try {
      const text = execution.logs
        .map(
          (e) =>
            `[${e.time}] ${e.level.toUpperCase()} ${e.nodeId ? `(${e.nodeId}) ` : ''}${e.message}`,
        )
        .join('\n');
      const path = await save({
        filters: [{ name: 'Log File', extensions: ['log', 'txt'] }],
        defaultPath: 'mimicry-execution.log',
      });
      if (!path) return;
      await invoke('file_write_text', { path, content: text });
    } catch (e) {
      console.error('[DevTools] Export logs failed:', e);
    }
  }
</script>

<template>
  <div
    class="bottom-panel"
    :class="{ collapsed }"
    :style="collapsed ? {} : { height: panelHeight + 'px' }"
  >
    <!-- Resize handle -->
    <div class="resize-handle" @mousedown="onResizeStart" />
    <!-- Tab bar -->
    <div class="tab-bar">
      <div class="flex items-center gap-1">
        <button
          :class="['tab-btn', activeTab === 'json' && 'active']"
          @click="
            activeTab = 'json';
            collapsed = false;
          "
        >
          {{ t('bottomPanel.json') }}
        </button>
        <button
          :class="['tab-btn', activeTab === 'logs' && 'active']"
          @click="
            activeTab = 'logs';
            collapsed = false;
          "
        >
          {{ t('bottomPanel.logs') }}
        </button>
        <button
          :class="['tab-btn', activeTab === 'variables' && 'active']"
          @click="
            activeTab = 'variables';
            collapsed = false;
          "
        >
          {{ t('bottomPanel.variables') }}
        </button>
        <button
          :class="['tab-btn', activeTab === 'problems' && 'active']"
          @click="
            activeTab = 'problems';
            collapsed = false;
          "
        >
          {{ t('bottomPanel.problems') }}
          <span
            v-if="validation.totalCount > 0"
            class="badge"
            :class="validation.errorCount > 0 ? 'badge-error' : 'badge-warning'"
          >
            {{ validation.totalCount }}
          </span>
        </button>
      </div>
      <div class="flex items-center gap-1">
        <button class="collapse-btn" @click="toggleCollapse">
          {{ collapsed ? '▲' : '▼' }}
        </button>
        <button
          v-if="activeTab === 'json'"
          class="action-btn"
          :title="t('devTools.importJson')"
          @click="importJson"
        >
          ↓ {{ t('devTools.import') }}
        </button>
        <button
          v-if="activeTab === 'logs' && execution.logs.length > 0"
          class="action-btn"
          :title="t('devTools.exportLogs')"
          @click="exportLogs"
        >
          ↑ {{ t('devTools.export') }}
        </button>
        <button v-if="activeTab === 'problems'" class="action-btn" @click="runValidation">
          ⟳ {{ t('bottomPanel.validateNow') }}
        </button>
      </div>
    </div>

    <!-- Panel content -->
    <div v-show="!collapsed" class="panel-content">
      <JsonEditor v-if="activeTab === 'json'" />

      <div v-else-if="activeTab === 'logs'" ref="logContainer" class="log-panel">
        <div v-if="execution.logs.length === 0" class="empty-hint">
          {{ t('bottomPanel.noLogs') }}
        </div>
        <div v-else class="log-entries">
          <div v-for="(entry, i) in execution.logs" :key="i" class="log-entry">
            <span class="log-time">{{ entry.time }}</span>
            <span :class="['log-level', levelColors[entry.level]]">{{
              entry.level.toUpperCase()
            }}</span>
            <span class="log-msg">{{ entry.message }}</span>
          </div>
        </div>
      </div>

      <div v-else-if="activeTab === 'variables'" class="variables-panel">
        <div v-if="Object.keys(execution.variables).length === 0" class="empty-hint">
          {{ t('bottomPanel.noVariables') }}
        </div>
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
              <td class="var-value">
                {{ typeof val === 'object' ? JSON.stringify(val) : String(val) }}
              </td>
              <td class="var-type">{{ typeof val }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-else-if="activeTab === 'problems'" class="problems-panel">
        <div v-if="validation.totalCount === 0" class="empty-hint">
          {{ t('bottomPanel.noProblems') }}
        </div>
        <div v-else class="problem-entries">
          <div
            v-for="(diag, i) in validation.diagnostics"
            :key="i"
            class="problem-entry"
            :class="`problem-${diag.level}`"
          >
            <span class="problem-icon">{{
              diag.level === 'error' ? '✕' : diag.level === 'warning' ? '⚠' : 'ℹ'
            }}</span>
            <span class="problem-rule">{{ diag.ruleId }}</span>
            <span class="problem-msg">{{ diag.message }}</span>
            <span v-if="diag.action" class="problem-action">{{ diag.action }}</span>
            <span v-if="diag.suggestion" class="problem-suggestion">{{ diag.suggestion }}</span>
          </div>
        </div>
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

  .action-btn {
    padding: 2px 8px;
    font-size: 10px;
    color: var(--color-text-muted);
    background: none;
    border: 1px solid var(--color-border);
    border-radius: 3px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .action-btn:hover {
    color: var(--color-text);
    background: var(--color-surface-hover);
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

  /* Problems panel */
  .problems-panel {
    height: 100%;
    overflow-y: auto;
    padding: 8px 12px;
  }

  .problem-entries {
    font-size: 12px;
  }

  .problem-entry {
    display: flex;
    align-items: baseline;
    gap: 8px;
    padding: 4px 0;
    border-bottom: 1px solid var(--color-separator-light);
  }

  .problem-icon {
    flex-shrink: 0;
    font-size: 12px;
  }

  .problem-error .problem-icon {
    color: #ef5350;
  }

  .problem-warning .problem-icon {
    color: #ffa726;
  }

  .problem-info .problem-icon {
    color: #42a5f5;
  }

  .problem-rule {
    flex-shrink: 0;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 11px;
    color: var(--color-text-muted);
    min-width: 40px;
  }

  .problem-msg {
    color: var(--color-text);
  }

  .problem-action {
    flex-shrink: 0;
    font-size: 10px;
    color: var(--color-text-muted);
    background: var(--color-surface-hover);
    padding: 1px 6px;
    border-radius: 3px;
  }

  .problem-suggestion {
    font-size: 11px;
    color: var(--color-text-muted);
    font-style: italic;
  }

  /* Badge on tab */
  .badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 16px;
    height: 16px;
    padding: 0 4px;
    font-size: 10px;
    font-weight: 600;
    border-radius: 8px;
    margin-left: 4px;
  }

  .badge-error {
    background: #ef5350;
    color: #fff;
  }

  .badge-warning {
    background: #ffa726;
    color: #fff;
  }
</style>

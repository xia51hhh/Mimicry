<script setup lang="ts">
  import { ref, nextTick, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import JsonEditor from './JsonEditor.vue';
  import { useExecutionStore } from '../../stores/execution';
  import { useValidationStore } from '../../stores/validation';
  import { useWorkflowStore } from '../../stores/workflow';
  import { useBrowserStore } from '../../stores/browser';
  import { usePanel, usePanelLayout } from '../../composables/usePanel';
  import { useFileOps } from '../../composables/useFileOps';
  import { save } from '@tauri-apps/plugin-dialog';
  import { invoke } from '@tauri-apps/api/core';
  import { Crosshair, FlaskConical, Highlighter, Eye } from 'lucide-vue-next';

  const { t } = useI18n();

  const execution = useExecutionStore();
  const validation = useValidationStore();
  const workflow = useWorkflowStore();
  const browser = useBrowserStore();
  const fileOps = useFileOps();
  const activeTab = ref<'json' | 'logs' | 'variables' | 'problems' | 'debug' | 'selector'>('json');
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

  // --- Selector Analysis Panel ---
  const selectorInput = ref('');
  const selectorPicking = ref(false);
  const selectorTestResult = ref<{ matchCount: number; isUnique: boolean } | null>(null);
  const selectorCandidates = ref<
    Array<{
      selector: string;
      strategy: string;
      score: number;
      is_unique: boolean;
      match_count: number;
    }>
  >([]);
  const selectorLoading = ref(false);

  async function selectorStartPick() {
    if (!browser.connected) return;
    try {
      selectorPicking.value = true;
      await invoke('selector_start_picking');
      const pollInterval = setInterval(async () => {
        try {
          const result = await invoke<{ picked: Record<string, unknown> | null }>(
            'selector_get_picked',
          );
          if (result?.picked) {
            clearInterval(pollInterval);
            selectorPicking.value = false;
            const picked = result.picked as { selector: string };
            if (picked.selector) {
              selectorInput.value = picked.selector;
              selectorRunAnalysis();
            }
          }
        } catch {
          clearInterval(pollInterval);
          selectorPicking.value = false;
        }
      }, 500);
      setTimeout(() => {
        clearInterval(pollInterval);
        if (selectorPicking.value) {
          selectorPicking.value = false;
          invoke('selector_stop_picking').catch(() => {});
        }
      }, 30000);
    } catch {
      selectorPicking.value = false;
    }
  }

  async function selectorRunTest() {
    if (!selectorInput.value || !browser.connected) return;
    try {
      const result = await invoke<{ matchCount: number; isUnique: boolean }>('selector_test', {
        selector: selectorInput.value,
      });
      selectorTestResult.value = result;
      await invoke('selector_highlight', { selector: selectorInput.value, durationMs: 2000 });
    } catch {
      selectorTestResult.value = { matchCount: -1, isUnique: false };
    }
  }

  async function selectorRunAnalysis() {
    if (!selectorInput.value || !browser.connected) return;
    selectorLoading.value = true;
    try {
      const result = await invoke<{
        candidates: Array<{
          selector: string;
          strategy: string;
          score: number;
          is_unique: boolean;
          match_count: number;
        }>;
      }>('selector_analyze', { selector: selectorInput.value });
      selectorCandidates.value = result?.candidates || [];
      // Also test the current one
      await selectorRunTest();
    } catch {
      selectorCandidates.value = [];
    } finally {
      selectorLoading.value = false;
    }
  }

  async function selectorHighlightCandidate(sel: string) {
    if (!browser.connected) return;
    try {
      await invoke('selector_highlight', { selector: sel, durationMs: 2500 });
    } catch {
      /* ignore */
    }
  }

  function selectorUseCandidate(sel: string) {
    selectorInput.value = sel;
    selectorTestResult.value = null;
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
        <button
          :class="['tab-btn', activeTab === 'debug' && 'active']"
          @click="
            activeTab = 'debug';
            collapsed = false;
          "
        >
          {{ t('bottomPanel.debug') }}
          <span v-if="execution.breakpointIds.size > 0" class="badge badge-debug">
            {{ execution.breakpointIds.size }}
          </span>
        </button>
        <button
          :class="['tab-btn', activeTab === 'selector' && 'active']"
          @click="
            activeTab = 'selector';
            collapsed = false;
          "
        >
          {{ t('bottomPanel.selector') }}
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

      <div v-else-if="activeTab === 'debug'" class="debug-panel">
        <!-- Status bar -->
        <div class="debug-status-bar">
          <span
            class="debug-state-indicator"
            :class="{
              'state-running': execution.running && !execution.paused,
              'state-paused': execution.paused,
              'state-idle': !execution.running,
            }"
          >
            {{
              execution.paused
                ? t('bottomPanel.debugPaused')
                : execution.running
                  ? t('bottomPanel.debugRunning')
                  : t('bottomPanel.debugIdle')
            }}
          </span>
          <span v-if="execution.currentNodeId" class="debug-current-node">
            {{ t('bottomPanel.debugCurrentNode') }}: {{ execution.currentNodeId }}
          </span>
        </div>
        <!-- Breakpoints list -->
        <div class="debug-section">
          <div class="debug-section-title">
            {{ t('bottomPanel.debugBreakpoints') }} ({{ execution.breakpointIds.size }})
          </div>
          <div v-if="execution.breakpointIds.size === 0" class="empty-hint">
            {{ t('bottomPanel.debugNoBreakpoints') }}
          </div>
          <div v-else class="breakpoint-list">
            <div
              v-for="bpId in [...execution.breakpointIds]"
              :key="bpId"
              class="breakpoint-item"
            >
              <span class="bp-dot" />
              <span class="bp-id">{{ bpId }}</span>
              <button class="bp-remove" @click="execution.toggleBreakpoint(bpId)">✕</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Selector Analysis Panel -->
      <div v-else-if="activeTab === 'selector'" class="selector-panel">
        <div class="selector-toolbar">
          <div class="selector-input-group">
            <input
              v-model="selectorInput"
              type="text"
              class="selector-input"
              :placeholder="t('selector.inputPlaceholder')"
              @keydown.enter="selectorRunAnalysis"
            />
            <button
              v-if="browser.connected"
              class="sel-tool-btn"
              :class="{ active: selectorPicking }"
              :title="t('selector.pick')"
              @click="selectorStartPick"
            >
              <Crosshair :size="14" />
            </button>
            <button
              class="sel-tool-btn"
              :disabled="!selectorInput || !browser.connected"
              :title="t('selector.test')"
              @click="selectorRunTest"
            >
              <FlaskConical :size="14" />
            </button>
            <button
              class="sel-tool-btn"
              :disabled="!selectorInput || !browser.connected || selectorLoading"
              :title="t('selector.analyze')"
              @click="selectorRunAnalysis"
            >
              <Eye :size="14" />
            </button>
          </div>
          <div v-if="selectorTestResult" class="selector-test-badge">
            <span
              :class="[
                'sel-badge',
                selectorTestResult.isUnique
                  ? 'sel-badge-ok'
                  : selectorTestResult.matchCount === 0
                    ? 'sel-badge-none'
                    : 'sel-badge-warn',
              ]"
            >
              {{
                selectorTestResult.matchCount === 0
                  ? t('selector.noMatch')
                  : selectorTestResult.isUnique
                    ? t('selector.unique')
                    : t('selector.multiMatch', { count: selectorTestResult.matchCount })
              }}
            </span>
          </div>
        </div>
        <div v-if="selectorLoading" class="selector-loading">
          {{ t('selector.analyzing') }}
        </div>
        <div v-else-if="selectorCandidates.length" class="selector-results">
          <table class="selector-table">
            <thead>
              <tr>
                <th>{{ t('selector.colSelector') }}</th>
                <th>{{ t('selector.colStrategy') }}</th>
                <th>{{ t('selector.colScore') }}</th>
                <th>{{ t('selector.colMatch') }}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(c, i) in selectorCandidates" :key="i">
                <td class="sel-col-selector" :title="c.selector">{{ c.selector }}</td>
                <td><span class="sel-strategy-tag">{{ c.strategy }}</span></td>
                <td>
                  <span
                    class="sel-score"
                    :class="c.score >= 80 ? 'score-high' : c.score >= 50 ? 'score-mid' : 'score-low'"
                  >
                    {{ Math.round(c.score) }}
                  </span>
                </td>
                <td>
                  <span :class="c.is_unique ? 'sel-unique' : 'sel-multi'">
                    {{ c.match_count }}{{ c.is_unique ? ' ✓' : '' }}
                  </span>
                </td>
                <td class="sel-actions">
                  <button
                    class="sel-action-btn"
                    :title="t('selector.highlight')"
                    @click="selectorHighlightCandidate(c.selector)"
                  >
                    <Highlighter :size="12" />
                  </button>
                  <button
                    class="sel-action-btn"
                    :title="t('selector.use')"
                    @click="selectorUseCandidate(c.selector)"
                  >
                    ✓
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="empty-hint">
          {{ t('selector.emptyHint') }}
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

  .badge-debug {
    background: #ef5350;
    color: #fff;
  }

  /* Debug panel */
  .debug-panel {
    height: 100%;
    overflow-y: auto;
    padding: 8px 12px;
    font-size: 12px;
  }

  .debug-status-bar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 6px 10px;
    background: var(--color-surface-hover);
    border-radius: 6px;
    margin-bottom: 8px;
  }

  .debug-state-indicator {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-weight: 600;
    font-size: 11px;
  }

  .debug-state-indicator::before {
    content: '';
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }

  .state-idle::before {
    background: var(--color-text-muted);
  }
  .state-running::before {
    background: #42a5f5;
    animation: pulse-dot 1.5s ease-in-out infinite;
  }
  .state-paused::before {
    background: #ffa726;
  }

  @keyframes pulse-dot {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }

  .debug-current-node {
    color: var(--color-text-muted);
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 11px;
  }

  .debug-section {
    margin-top: 8px;
  }

  .debug-section-title {
    font-weight: 600;
    font-size: 11px;
    color: var(--color-text-muted);
    text-transform: uppercase;
    margin-bottom: 4px;
  }

  .breakpoint-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .breakpoint-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 3px 8px;
    border-radius: 4px;
    transition: background 0.15s;
  }
  .breakpoint-item:hover {
    background: var(--color-surface-hover);
  }

  .bp-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #ef5350;
    flex-shrink: 0;
  }

  .bp-id {
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 11px;
    color: var(--color-text);
  }

  .bp-remove {
    margin-left: auto;
    background: none;
    border: none;
    color: var(--color-text-muted);
    cursor: pointer;
    font-size: 10px;
    padding: 2px 4px;
    border-radius: 3px;
    opacity: 0;
    transition: opacity 0.15s;
  }
  .breakpoint-item:hover .bp-remove {
    opacity: 1;
  }
  .bp-remove:hover {
    color: #ef5350;
    background: rgba(239, 83, 80, 0.1);
  }

  /* Selector Analysis Panel */
  .selector-panel {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .selector-toolbar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    border-bottom: 1px solid var(--color-border);
    flex-shrink: 0;
  }

  .selector-input-group {
    display: flex;
    align-items: center;
    gap: 4px;
    flex: 1;
  }

  .selector-input {
    flex: 1;
    height: 26px;
    padding: 0 8px;
    font-size: 12px;
    font-family: var(--font-mono, monospace);
    background: var(--color-bg);
    border: 1px solid var(--color-border);
    border-radius: 4px;
    color: var(--color-text);
    outline: none;
  }

  .selector-input:focus {
    border-color: var(--color-primary);
  }

  .sel-tool-btn {
    width: 26px;
    height: 26px;
    border-radius: 4px;
    border: 1px solid var(--color-border);
    background: var(--color-surface);
    color: var(--color-text-muted);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: all 0.15s;
  }

  .sel-tool-btn:hover:not(:disabled) {
    background: var(--color-surface-hover);
    color: var(--color-text);
  }

  .sel-tool-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .sel-tool-btn.active {
    background: var(--color-accent);
    color: white;
    border-color: var(--color-accent);
  }

  .selector-test-badge {
    flex-shrink: 0;
  }

  .sel-badge {
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 3px;
    font-weight: 500;
    white-space: nowrap;
  }

  .sel-badge-ok {
    background: rgba(34, 197, 94, 0.15);
    color: #22c55e;
  }

  .sel-badge-warn {
    background: rgba(245, 158, 11, 0.15);
    color: #f59e0b;
  }

  .sel-badge-none {
    background: rgba(239, 68, 68, 0.15);
    color: #ef4444;
  }

  .selector-loading {
    padding: 12px;
    text-align: center;
    color: var(--color-text-muted);
    font-size: 12px;
  }

  .selector-results {
    flex: 1;
    overflow: auto;
  }

  .selector-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }

  .selector-table th {
    text-align: left;
    padding: 4px 10px;
    font-size: 10px;
    font-weight: 600;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.3px;
    border-bottom: 1px solid var(--color-border);
    position: sticky;
    top: 0;
    background: var(--color-surface);
  }

  .selector-table td {
    padding: 4px 10px;
    border-bottom: 1px solid var(--color-border);
    vertical-align: middle;
  }

  .selector-table tbody tr:hover {
    background: var(--color-surface-hover);
  }

  .sel-col-selector {
    font-family: var(--font-mono, monospace);
    max-width: 300px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .sel-strategy-tag {
    font-size: 10px;
    padding: 1px 5px;
    border-radius: 2px;
    background: rgba(99, 102, 241, 0.15);
    color: #818cf8;
  }

  .sel-score {
    font-weight: 600;
    font-size: 11px;
  }

  .score-high {
    color: #22c55e;
  }

  .score-mid {
    color: #f59e0b;
  }

  .score-low {
    color: #ef4444;
  }

  .sel-unique {
    color: #22c55e;
    font-weight: 500;
  }

  .sel-multi {
    color: #f59e0b;
  }

  .sel-actions {
    display: flex;
    gap: 4px;
  }

  .sel-action-btn {
    width: 22px;
    height: 22px;
    border-radius: 3px;
    border: 1px solid var(--color-border);
    background: var(--color-surface);
    color: var(--color-text-muted);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    transition: all 0.15s;
  }

  .sel-action-btn:hover {
    background: var(--color-surface-hover);
    color: var(--color-text);
  }
</style>

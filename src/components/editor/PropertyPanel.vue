<script setup lang="ts">
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useWorkflowStore } from '../../stores/workflow';
  import { useBrowserStore } from '../../stores/browser';
  import { usePanel, usePanelLayout } from '../../composables/usePanel';
  import { Crosshair, FlaskConical, Highlighter } from 'lucide-vue-next';
  import { invoke } from '@tauri-apps/api/core';

  const { t } = useI18n();
  const store = useWorkflowStore();
  const browser = useBrowserStore();
  const activeTab = ref<'settings' | 'data'>('settings');

  const {
    size: panelWidth,
    collapsed,
    onResizeStart,
  } = usePanel({
    direction: 'horizontal',
    defaultSize: 280,
    minSize: 200,
    maxSize: 500,
    storageKey: 'mimicry-right-width',
  });

  // Sync with global layout state
  const { rightPanelCollapsed } = usePanelLayout();
  watch(rightPanelCollapsed, (v) => {
    collapsed.value = v;
  });
  watch(collapsed, (v) => {
    rightPanelCollapsed.value = v;
  });

  const node = computed(() => store.selectedNode);
  const nodeType = computed(() => node.value?.type || '');

  // Local editable copy of node data
  const editData = ref<Record<string, unknown>>({});

  watch(
    () => node.value,
    (n) => {
      if (n) {
        editData.value = { ...n.data };
      } else {
        editData.value = {};
      }
    },
    { immediate: true, deep: true },
  );

  function updateField(field: string, value: unknown) {
    editData.value[field] = value;
    if (node.value) {
      store.updateNodeData(node.value.id, { [field]: value });
    }
  }

  // Action type options based on block-system.md
  const actionTypes = [
    {
      group: t('blockCategories.browser'),
      items: [
        'Navigate',
        'NewTab',
        'SwitchTab',
        'CloseTab',
        'GoBack',
        'GoForward',
        'Reload',
        'HandleDialog',
        'SwitchFrame',
        'WaitForPage',
      ],
    },
    {
      group: t('blockCategories.interaction'),
      items: [
        'Click',
        'DblClick',
        'Type',
        'Hover',
        'PressKey',
        'Scroll',
        'SelectOption',
        'UploadFile',
        'Clear',
        'Focus',
      ],
    },
    {
      group: t('blockCategories.data'),
      items: [
        'GetText',
        'GetAttribute',
        'GetURL',
        'Screenshot',
        'ExtractTable',
        'SetVariable',
        'Transform',
        'Export',
        'Cookie',
        'ElementExists',
      ],
    },
    {
      group: t('blockCategories.advanced'),
      items: ['RunScript', 'HttpRequest', 'HandleDownload', 'Log', 'Delay', 'Comment'],
    },
    {
      group: t('blockCategories.flow'),
      items: ['Wait', 'ExecuteWorkflow', 'Stop', 'Fail', 'LoopBreakpoint', 'WaitConnections'],
    },
  ];

  const loopTypes = [
    { value: 'count', label: t('loopTypes.count') },
    { value: 'items', label: t('loopTypes.items') },
    { value: 'elements', label: t('loopTypes.elements') },
    { value: 'while', label: t('loopTypes.while') },
  ];

  const conditionTypes = [
    { value: 'exists', label: t('conditionTypes.exists') },
    { value: 'not_exists', label: t('conditionTypes.not_exists') },
    { value: 'visible', label: t('conditionTypes.visible') },
    { value: 'text_contains', label: t('conditionTypes.text_contains') },
    { value: 'url_contains', label: t('conditionTypes.url_contains') },
    { value: 'expression', label: t('conditionTypes.expression') },
  ];

  const onErrorOptions = [
    { value: 'stop', label: t('errorOptions.stop') },
    { value: 'continue', label: t('errorOptions.continue') },
    { value: 'retry', label: t('errorOptions.retry') },
  ];

  const sessionOptions = computed(() =>
    Array.from(browser.sessions.values()).map((s) => ({
      value: s.sessionId,
      label: s.profileId ?? s.sessionId,
    })),
  );

  const nodeSessionId = computed(() => editData.value.sessionId as string | undefined);

  function updateSessionId(value: string) {
    if (!node.value) return;
    updateField('sessionId', value || undefined);
  }

  // --- Selector tools ---
  const isPicking = ref(false);
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
  const showCandidates = ref(false);

  async function startPicking() {
    if (!browser.connected) return;
    try {
      isPicking.value = true;
      await invoke('selector_start_picking');
      // Poll for result
      const pollInterval = setInterval(async () => {
        try {
          const result = await invoke<{ picked: Record<string, unknown> | null }>(
            'selector_get_picked',
          );
          if (result?.picked) {
            clearInterval(pollInterval);
            isPicking.value = false;
            const picked = result.picked as { selector: string };
            if (picked.selector && node.value) {
              updateField('selector', picked.selector);
              // Auto-analyze
              analyzeSelectorCandidates(picked.selector);
            }
          }
        } catch {
          clearInterval(pollInterval);
          isPicking.value = false;
        }
      }, 500);
      // Timeout after 30s
      setTimeout(() => {
        clearInterval(pollInterval);
        if (isPicking.value) {
          isPicking.value = false;
          invoke('selector_stop_picking').catch(() => {});
        }
      }, 30000);
    } catch {
      isPicking.value = false;
    }
  }

  async function testSelector() {
    const sel = editData.value.selector as string;
    if (!sel || !browser.connected) return;
    try {
      const result = await invoke<{ matchCount: number; isUnique: boolean }>('selector_test', {
        selector: sel,
      });
      selectorTestResult.value = result;
      // Also highlight in browser
      await invoke('selector_highlight', { selector: sel, durationMs: 2000 });
    } catch {
      selectorTestResult.value = { matchCount: -1, isUnique: false };
    }
  }

  async function analyzeSelectorCandidates(sel?: string) {
    const selector = sel || (editData.value.selector as string);
    if (!selector || !browser.connected) return;
    try {
      const result = await invoke<{
        candidates: Array<{
          selector: string;
          strategy: string;
          score: number;
          is_unique: boolean;
          match_count: number;
        }>;
      }>('selector_analyze', { selector });
      selectorCandidates.value = result?.candidates || [];
      showCandidates.value = true;
    } catch {
      selectorCandidates.value = [];
    }
  }

  function useCandidateSelector(sel: string) {
    if (!node.value) return;
    updateField('selector', sel);
    showCandidates.value = false;
    selectorTestResult.value = null;
  }
</script>

<template>
  <aside
    v-show="!collapsed"
    class="property-panel"
    :style="{ width: panelWidth + 'px', minWidth: panelWidth + 'px' }"
  >
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
        <button :class="['tab-btn', activeTab === 'data' && 'active']" @click="activeTab = 'data'">
          {{ t('propertyPanel.data') }}
        </button>
      </div>

      <!-- Settings Tab -->
      <div v-if="activeTab === 'settings'" class="panel-body">
        <!-- Session selector (cross-profile) -->
        <div v-if="sessionOptions.length > 1" class="field-group">
          <label class="field-label">{{ t('session.target') }}</label>
          <select
            class="field-input"
            :value="nodeSessionId || ''"
            @change="updateSessionId(($event.target as HTMLSelectElement).value)"
          >
            <option value="">{{ t('session.inherit') }}</option>
            <option v-for="opt in sessionOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>

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
                <option v-for="item in group.items" :key="item" :value="item">
                  {{ t(`blocks.${item}`) }}
                </option>
              </optgroup>
            </select>
          </div>

          <div class="field-group">
            <label class="field-label">{{ t('propertyPanel.selector') }}</label>
            <div class="selector-input-row">
              <input
                type="text"
                class="field-input selector-field"
                :placeholder="t('propertyPanel.selectorPlaceholder')"
                :value="editData.selector"
                @input="updateField('selector', ($event.target as HTMLInputElement).value)"
              />
              <button
                v-if="browser.connected"
                class="selector-btn"
                :class="{ active: isPicking }"
                :title="t('selector.pick')"
                @click="startPicking"
              >
                <Crosshair :size="14" />
              </button>
              <button
                v-if="browser.connected && editData.selector"
                class="selector-btn"
                :title="t('selector.test')"
                @click="testSelector"
              >
                <FlaskConical :size="14" />
              </button>
              <button
                v-if="browser.connected && editData.selector"
                class="selector-btn"
                :title="t('selector.analyze')"
                @click="analyzeSelectorCandidates()"
              >
                <Highlighter :size="14" />
              </button>
            </div>
            <!-- Test result badge -->
            <div v-if="selectorTestResult" class="selector-test-result">
              <span
                :class="[
                  'test-badge',
                  selectorTestResult.isUnique
                    ? 'badge-ok'
                    : selectorTestResult.matchCount === 0
                      ? 'badge-none'
                      : 'badge-warn',
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
            <!-- Candidate selectors -->
            <div v-if="showCandidates && selectorCandidates.length" class="selector-candidates">
              <div class="candidates-header">
                <span class="text-xs font-medium">{{ t('selector.candidates') }}</span>
                <button class="text-xs text-[var(--color-text-muted)]" @click="showCandidates = false">✕</button>
              </div>
              <div
                v-for="(c, i) in selectorCandidates.slice(0, 6)"
                :key="i"
                class="candidate-item"
                @click="useCandidateSelector(c.selector)"
              >
                <div class="candidate-selector">{{ c.selector }}</div>
                <div class="candidate-meta">
                  <span class="strategy-tag">{{ c.strategy }}</span>
                  <span class="score-tag" :class="c.score >= 80 ? 'score-high' : c.score >= 50 ? 'score-mid' : 'score-low'">
                    {{ Math.round(c.score) }}
                  </span>
                  <span v-if="c.is_unique" class="unique-tag">✓</span>
                </div>
              </div>
            </div>
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

          <div v-if="editData.action === 'NewTab'" class="field-group">
            <label class="field-label">URL</label>
            <input
              type="text"
              class="field-input"
              placeholder="https://..."
              :value="editData.url"
              @input="updateField('url', ($event.target as HTMLInputElement).value)"
            />
          </div>

          <div v-if="editData.action === 'SwitchTab'" class="field-group">
            <label class="field-label">{{ t('propertyPanel.seq') }}</label>
            <input
              type="number"
              class="field-input"
              :placeholder="t('propertyPanel.seqHint')"
              :value="editData.seq"
              @input="updateField('seq', Number(($event.target as HTMLInputElement).value))"
            />
            <label class="field-label">{{ t('propertyPanel.urlOrigin') }}</label>
            <input
              type="text"
              class="field-input"
              placeholder="https://example.com"
              :value="editData.urlOrigin"
              @input="updateField('urlOrigin', ($event.target as HTMLInputElement).value)"
            />
            <label class="field-label">{{ t('propertyPanel.urlPath') }}</label>
            <input
              type="text"
              class="field-input"
              placeholder="/login"
              :value="editData.urlPath"
              @input="updateField('urlPath', ($event.target as HTMLInputElement).value)"
            />
            <label class="field-label">{{ t('propertyPanel.title') }}</label>
            <input
              type="text"
              class="field-input"
              :placeholder="t('propertyPanel.titleHint')"
              :value="editData.title"
              @input="updateField('title', ($event.target as HTMLInputElement).value)"
            />
            <label class="field-label">{{ t('propertyPanel.tabIndex') }}</label>
            <input
              type="number"
              class="field-input"
              :placeholder="t('propertyPanel.tabIndexHint')"
              :value="editData.tabIndex"
              @input="updateField('tabIndex', Number(($event.target as HTMLInputElement).value))"
            />
          </div>

          <div v-if="editData.action === 'CloseTab'" class="field-group">
            <label class="field-label">{{ t('propertyPanel.tabIndex') }}</label>
            <input
              type="number"
              class="field-input"
              :placeholder="t('propertyPanel.tabIndexHint')"
              :value="editData.tabIndex"
              @input="updateField('tabIndex', Number(($event.target as HTMLInputElement).value))"
            />
          </div>

          <div v-if="editData.action === 'PressKey'" class="field-group">
            <label class="field-label">{{ t('propertyPanel.key') }}</label>
            <input
              type="text"
              class="field-input"
              placeholder="Enter, Tab, Escape..."
              :value="editData.key"
              @input="updateField('key', ($event.target as HTMLInputElement).value)"
            />
          </div>

          <div v-if="editData.action === 'Scroll'" class="field-group">
            <label class="field-label">{{ t('propertyPanel.direction') }}</label>
            <select
              class="field-input"
              :value="editData.direction || 'down'"
              @change="updateField('direction', ($event.target as HTMLSelectElement).value)"
            >
              <option value="down">↓ Down</option>
              <option value="up">↑ Up</option>
            </select>
          </div>

          <div v-if="editData.action === 'Scroll'" class="field-group">
            <label class="field-label">{{ t('propertyPanel.amount') }}</label>
            <input
              type="number"
              class="field-input"
              placeholder="300"
              :value="editData.amount || 300"
              @input="updateField('amount', Number(($event.target as HTMLInputElement).value))"
            />
          </div>

          <div v-if="editData.action === 'Delay'" class="field-group">
            <label class="field-label">{{ t('propertyPanel.duration') }}</label>
            <input
              type="text"
              class="field-input"
              placeholder="1s, 500ms"
              :value="editData.duration"
              @input="updateField('duration', ($event.target as HTMLInputElement).value)"
            />
          </div>

          <div
            v-if="
              ['GetText', 'GetAttribute', 'GetURL', 'ExtractTable'].includes(
                String(editData.action),
              )
            "
            class="field-group"
          >
            <label class="field-label">{{ t('propertyPanel.saveAs') }}</label>
            <input
              type="text"
              class="field-input"
              placeholder="$_result"
              :value="editData.into || '$_result'"
              @input="updateField('into', ($event.target as HTMLInputElement).value)"
            />
          </div>

          <div v-if="editData.action === 'GetAttribute'" class="field-group">
            <label class="field-label">{{ t('propertyPanel.attrName') }}</label>
            <input
              type="text"
              class="field-input"
              placeholder="href, src, class..."
              :value="editData.attrName"
              @input="updateField('attrName', ($event.target as HTMLInputElement).value)"
            />
          </div>

          <div v-if="editData.action === 'SetVariable'" class="field-group">
            <label class="field-label">{{ t('propertyPanel.variableName') }}</label>
            <input
              type="text"
              class="field-input"
              placeholder="$myVar"
              :value="editData.variable"
              @input="updateField('variable', ($event.target as HTMLInputElement).value)"
            />
          </div>

          <div v-if="editData.action === 'SetVariable'" class="field-group">
            <label class="field-label">{{ t('propertyPanel.inputValue') }}</label>
            <input
              type="text"
              class="field-input"
              :value="editData.value"
              @input="updateField('value', ($event.target as HTMLInputElement).value)"
            />
          </div>

          <div v-if="editData.action === 'RunScript'" class="field-group">
            <label class="field-label">{{ t('propertyPanel.script') }}</label>
            <textarea
              class="field-input resize-none"
              rows="4"
              placeholder="return document.title"
              :value="editData.script as string"
              @input="updateField('script', ($event.target as HTMLTextAreaElement).value)"
            />
          </div>

          <div v-if="editData.action === 'RunScript'" class="field-group">
            <label class="field-label">{{ t('propertyPanel.saveAs') }}</label>
            <input
              type="text"
              class="field-input"
              placeholder="$_result"
              :value="editData.into"
              @input="updateField('into', ($event.target as HTMLInputElement).value)"
            />
          </div>

          <div v-if="editData.action === 'HttpRequest'" class="field-group">
            <label class="field-label">URL</label>
            <input
              type="text"
              class="field-input"
              placeholder="https://api.example.com/data"
              :value="editData.url"
              @input="updateField('url', ($event.target as HTMLInputElement).value)"
            />
          </div>

          <div v-if="editData.action === 'HttpRequest'" class="field-group">
            <label class="field-label">{{ t('propertyPanel.method') }}</label>
            <select
              class="field-input"
              :value="editData.method || 'GET'"
              @change="updateField('method', ($event.target as HTMLSelectElement).value)"
            >
              <option value="GET">GET</option>
              <option value="POST">POST</option>
              <option value="PUT">PUT</option>
              <option value="DELETE">DELETE</option>
            </select>
          </div>

          <div
            v-if="
              editData.action === 'HttpRequest' && ['POST', 'PUT'].includes(String(editData.method))
            "
            class="field-group"
          >
            <label class="field-label">Body</label>
            <textarea
              class="field-input resize-none"
              rows="3"
              placeholder='{"key": "value"}'
              :value="editData.body as string"
              @input="updateField('body', ($event.target as HTMLTextAreaElement).value)"
            />
          </div>

          <div v-if="editData.action === 'HttpRequest'" class="field-group">
            <label class="field-label">{{ t('propertyPanel.saveAs') }}</label>
            <input
              type="text"
              class="field-input"
              placeholder="$_result"
              :value="editData.into || '$_result'"
              @input="updateField('into', ($event.target as HTMLInputElement).value)"
            />
          </div>

          <div v-if="editData.action === 'HandleDialog'" class="field-group">
            <label class="field-label">{{ t('propertyPanel.dialogAction') }}</label>
            <select
              class="field-input"
              :value="editData.accept !== false ? 'accept' : 'dismiss'"
              @change="
                updateField('accept', ($event.target as HTMLSelectElement).value === 'accept')
              "
            >
              <option value="accept">{{ t('propertyPanel.accept') }}</option>
              <option value="dismiss">{{ t('propertyPanel.dismiss') }}</option>
            </select>
          </div>

          <div v-if="editData.action === 'HandleDialog'" class="field-group">
            <label class="field-label">{{ t('propertyPanel.promptText') }}</label>
            <input
              type="text"
              class="field-input"
              :placeholder="t('propertyPanel.promptTextPlaceholder')"
              :value="editData.text"
              @input="updateField('text', ($event.target as HTMLInputElement).value)"
            />
          </div>

          <div v-if="editData.action === 'UploadFile'" class="field-group">
            <label class="field-label">{{ t('propertyPanel.filePath') }}</label>
            <input
              type="text"
              class="field-input"
              placeholder="C:\files\data.csv"
              :value="editData.filePath"
              @input="updateField('filePath', ($event.target as HTMLInputElement).value)"
            />
          </div>

          <div v-if="editData.action === 'Export'" class="field-group">
            <label class="field-label">{{ t('propertyPanel.format') }}</label>
            <select
              class="field-input"
              :value="editData.format || 'json'"
              @change="updateField('format', ($event.target as HTMLSelectElement).value)"
            >
              <option value="json">JSON</option>
              <option value="csv">CSV</option>
            </select>
          </div>

          <div v-if="editData.action === 'Export'" class="field-group">
            <label class="field-label">{{ t('propertyPanel.filePath') }}</label>
            <input
              type="text"
              class="field-input"
              placeholder="export.json"
              :value="editData.path"
              @input="updateField('path', ($event.target as HTMLInputElement).value)"
            />
          </div>

          <div v-if="editData.action === 'Log'" class="field-group">
            <label class="field-label">{{ t('propertyPanel.message') }}</label>
            <input
              type="text"
              class="field-input"
              placeholder="$var1 $var2"
              :value="editData.parts ? (editData.parts as string[]).join(' ') : ''"
              @input="updateField('parts', ($event.target as HTMLInputElement).value.split(' '))"
            />
          </div>

          <div v-if="editData.action === 'Comment'" class="field-group">
            <label class="field-label">{{ t('propertyPanel.comment') }}</label>
            <textarea
              class="field-input resize-none"
              rows="2"
              :value="editData.comment as string"
              @input="updateField('comment', ($event.target as HTMLTextAreaElement).value)"
            />
          </div>

          <div v-if="editData.action === 'Wait'" class="field-group">
            <label class="field-label">{{ t('propertyPanel.waitType') }}</label>
            <select
              class="field-input"
              :value="editData.selector ? 'selector' : editData.url_contains ? 'url' : 'time'"
              @change="
                (e) => {
                  const v = (e.target as HTMLSelectElement).value;
                  if (v === 'selector') {
                    updateField('url_contains', undefined);
                    updateField('time', undefined);
                  } else if (v === 'url') {
                    updateField('selector', undefined);
                    updateField('time', undefined);
                    updateField('url_contains', editData.url_contains || '');
                  } else {
                    updateField('selector', undefined);
                    updateField('url_contains', undefined);
                    updateField('time', editData.time || '1s');
                  }
                }
              "
            >
              <option value="selector">{{ t('propertyPanel.waitSelector') }}</option>
              <option value="url">{{ t('propertyPanel.waitUrl') }}</option>
              <option value="time">{{ t('propertyPanel.waitTime') }}</option>
            </select>
          </div>

          <div
            v-if="editData.action === 'Wait' && editData.url_contains !== undefined"
            class="field-group"
          >
            <label class="field-label">{{ t('propertyPanel.urlContains') }}</label>
            <input
              type="text"
              class="field-input"
              placeholder="/dashboard"
              :value="editData.url_contains"
              @input="updateField('url_contains', ($event.target as HTMLInputElement).value)"
            />
          </div>

          <div v-if="editData.action === 'Wait' && editData.time !== undefined" class="field-group">
            <label class="field-label">{{ t('propertyPanel.waitDuration') }}</label>
            <input
              type="text"
              class="field-input"
              placeholder="2s, 500ms"
              :value="editData.time"
              @input="updateField('time', ($event.target as HTMLInputElement).value)"
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
            v-if="
              ['text_contains', 'url_contains', 'expression'].includes(String(editData.condition))
            "
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
        <div class="text-xs text-[var(--color-text-muted)] mb-2">
          {{ t('propertyPanel.nodeData') }}
        </div>
        <pre class="data-view">{{ JSON.stringify(node.data, null, 2) }}</pre>
      </div>
    </template>
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

  /* Selector tools */
  .selector-input-row {
    display: flex;
    gap: 4px;
    align-items: center;
  }

  .selector-field {
    flex: 1;
    min-width: 0;
  }

  .selector-btn {
    width: 28px;
    height: 28px;
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

  .selector-btn:hover {
    background: var(--color-surface-hover);
    color: var(--color-text);
  }

  .selector-btn.active {
    background: var(--color-accent);
    color: white;
    border-color: var(--color-accent);
  }

  .selector-test-result {
    margin-top: 4px;
  }

  .test-badge {
    font-size: 11px;
    padding: 1px 6px;
    border-radius: 3px;
    font-weight: 500;
  }

  .badge-ok {
    background: rgba(34, 197, 94, 0.15);
    color: #22c55e;
  }

  .badge-warn {
    background: rgba(245, 158, 11, 0.15);
    color: #f59e0b;
  }

  .badge-none {
    background: rgba(239, 68, 68, 0.15);
    color: #ef4444;
  }

  .selector-candidates {
    margin-top: 6px;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    overflow: hidden;
  }

  .candidates-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 4px 8px;
    background: var(--color-surface);
    border-bottom: 1px solid var(--color-border);
  }

  .candidate-item {
    padding: 4px 8px;
    cursor: pointer;
    border-bottom: 1px solid var(--color-border);
    transition: background 0.1s;
  }

  .candidate-item:last-child {
    border-bottom: none;
  }

  .candidate-item:hover {
    background: var(--color-surface-hover);
  }

  .candidate-selector {
    font-size: 11px;
    font-family: var(--font-mono, monospace);
    color: var(--color-text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .candidate-meta {
    display: flex;
    gap: 4px;
    margin-top: 2px;
    align-items: center;
  }

  .strategy-tag {
    font-size: 10px;
    padding: 0 4px;
    border-radius: 2px;
    background: rgba(99, 102, 241, 0.15);
    color: #818cf8;
  }

  .score-tag {
    font-size: 10px;
    padding: 0 4px;
    border-radius: 2px;
    font-weight: 600;
  }

  .score-high {
    background: rgba(34, 197, 94, 0.15);
    color: #22c55e;
  }

  .score-mid {
    background: rgba(245, 158, 11, 0.15);
    color: #f59e0b;
  }

  .score-low {
    background: rgba(239, 68, 68, 0.15);
    color: #ef4444;
  }

  .unique-tag {
    font-size: 10px;
    color: #22c55e;
    font-weight: 600;
  }
</style>

import { defineStore } from 'pinia';
import { ref, computed, watch } from 'vue';
import type { Workflow } from '../types/workflow';

export interface WorkspaceTab {
  id: string;
  name: string;
  /** persisted workflow id from DB, null for unsaved */
  workflowId: string | null;
  /** file path on disk, null for DB-only workflows */
  filePath?: string | null;
  /** dirty flag synced from workflow store */
  dirty?: boolean;
}

/** Serialized tab metadata for localStorage */
interface PersistedTab {
  id: string;
  name: string;
  workflowId: string | null;
  filePath?: string | null;
}

const STORAGE_KEY = 'mimicry-workspace-tabs';

/** Per-tab serialized workflow snapshot */
export type TabWorkflowData = Workflow;

export const useWorkspaceStore = defineStore('workspace', () => {
  const tabs = ref<WorkspaceTab[]>([{ id: 'tab_1', name: 'Untitled Workflow', workflowId: null }]);
  const activeTabId = ref('tab_1');

  /** In-memory workflow data per tab */
  const tabDataMap = ref<Record<string, TabWorkflowData>>({});

  const activeTab = computed(
    () => tabs.value.find((t) => t.id === activeTabId.value) || tabs.value[0],
  );

  // ── Persistence ───────────────────────────────────────────────────

  function persistTabs() {
    try {
      const data: { tabs: PersistedTab[]; activeTabId: string } = {
        tabs: tabs.value.map((t) => ({
          id: t.id,
          name: t.name,
          workflowId: t.workflowId,
          filePath: t.filePath,
        })),
        activeTabId: activeTabId.value,
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch {
      // localStorage may be full or unavailable
    }
  }

  function restoreTabs() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const data = JSON.parse(raw) as { tabs: PersistedTab[]; activeTabId: string };
      if (!Array.isArray(data.tabs) || data.tabs.length === 0) return;
      tabs.value = data.tabs.map((t) => ({
        id: t.id,
        name: t.name,
        workflowId: t.workflowId,
        filePath: t.filePath ?? null,
      }));
      activeTabId.value = data.activeTabId || data.tabs[0].id;
    } catch {
      // Corrupted data — keep defaults
    }
  }

  // Auto-persist on tab changes
  watch([tabs, activeTabId], persistTabs, { deep: true });

  function saveTabData(tabId: string, data: TabWorkflowData) {
    tabDataMap.value[tabId] = data;
  }

  function getTabData(tabId: string): TabWorkflowData | undefined {
    return tabDataMap.value[tabId];
  }

  function addTab(name?: string) {
    const id = `tab_${Date.now()}`;
    tabs.value.push({
      id,
      name: name || 'Untitled Workflow',
      workflowId: null,
    });
    // Initialize empty workflow data for new tab
    tabDataMap.value[id] = {
      id: `wf_${Date.now()}`,
      name: name || 'Untitled Workflow',
      nodes: [],
      edges: [],
    };
    activeTabId.value = id;
    return id;
  }

  function closeTab(tabId: string) {
    const idx = tabs.value.findIndex((t) => t.id === tabId);
    if (idx === -1 || tabs.value.length <= 1) return;

    tabs.value.splice(idx, 1);
    delete tabDataMap.value[tabId];
    if (activeTabId.value === tabId) {
      activeTabId.value = tabs.value[Math.min(idx, tabs.value.length - 1)].id;
    }
  }

  function switchTab(tabId: string) {
    activeTabId.value = tabId;
  }

  function renameTab(tabId: string, name: string) {
    const tab = tabs.value.find((t) => t.id === tabId);
    if (tab) tab.name = name;
  }

  return {
    tabs,
    activeTabId,
    activeTab,
    tabDataMap,
    saveTabData,
    getTabData,
    addTab,
    closeTab,
    switchTab,
    renameTab,
    persistTabs,
    restoreTabs,
  };
});

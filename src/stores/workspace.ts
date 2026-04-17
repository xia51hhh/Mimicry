import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface WorkspaceTab {
  id: string
  name: string
  /** persisted workflow id from DB, null for unsaved */
  workflowId: string | null
}

/** Per-tab serialized workflow snapshot */
export interface TabWorkflowData {
  name: string
  nodes: Array<{ id: string; type: string; position: { x: number; y: number }; data: Record<string, unknown> }>
  edges: Array<{ id: string; source: string; target: string; sourceHandle?: string | null; targetHandle?: string | null; label?: string }>
}

export const useWorkspaceStore = defineStore('workspace', () => {
  const tabs = ref<WorkspaceTab[]>([
    { id: 'tab_1', name: 'Untitled Workflow', workflowId: null },
  ])
  const activeTabId = ref('tab_1')

  /** In-memory workflow data per tab */
  const tabDataMap = ref<Record<string, TabWorkflowData>>({})

  const activeTab = computed(() =>
    tabs.value.find((t) => t.id === activeTabId.value) || tabs.value[0]
  )

  function saveTabData(tabId: string, data: TabWorkflowData) {
    tabDataMap.value[tabId] = data
  }

  function getTabData(tabId: string): TabWorkflowData | undefined {
    return tabDataMap.value[tabId]
  }

  function addTab(name?: string) {
    const id = `tab_${Date.now()}`
    tabs.value.push({
      id,
      name: name || 'Untitled Workflow',
      workflowId: null,
    })
    // Initialize empty workflow data for new tab
    tabDataMap.value[id] = { name: name || 'Untitled Workflow', nodes: [], edges: [] }
    activeTabId.value = id
    return id
  }

  function closeTab(tabId: string) {
    const idx = tabs.value.findIndex((t) => t.id === tabId)
    if (idx === -1 || tabs.value.length <= 1) return

    tabs.value.splice(idx, 1)
    delete tabDataMap.value[tabId]
    if (activeTabId.value === tabId) {
      activeTabId.value = tabs.value[Math.min(idx, tabs.value.length - 1)].id
    }
  }

  function switchTab(tabId: string) {
    activeTabId.value = tabId
  }

  function renameTab(tabId: string, name: string) {
    const tab = tabs.value.find((t) => t.id === tabId)
    if (tab) tab.name = name
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
  }
})

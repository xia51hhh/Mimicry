import { ref, shallowRef } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { save, open } from '@tauri-apps/plugin-dialog'
import { useWorkflowStore } from '../stores/workflow'
import { useWorkspaceStore } from '../stores/workspace'

export interface RecentFile {
  path: string
  name: string
  openedAt: string
}

/** Current file path for the active tab (null = unsaved / from DB) */
const currentFilePath = ref<string | null>(null)
const recentFiles = shallowRef<RecentFile[]>([])
const lastError = ref<string | null>(null)

const FILTERS = [{ name: 'Mimicry Workflow', extensions: ['mimicry.json'] }]
const IMPORT_FILTERS = [
  { name: 'Mimicry Workflow', extensions: ['mimicry.json', 'json'] },
]
const COMPACT_FILTERS = [{ name: 'Compact Workflow', extensions: ['compact.json', 'json'] }]

export function useFileOps() {
  const workflow = useWorkflowStore()
  const workspace = useWorkspaceStore()

  function setError(msg: string) {
    lastError.value = msg
    console.error('[FileOps]', msg)
  }

  async function loadRecentFiles() {
    try {
      recentFiles.value = await invoke<RecentFile[]>('recent_files_list')
    } catch (e) {
      setError(`Failed to load recent files: ${e}`)
    }
  }

  async function saveFile(): Promise<boolean> {
    try {
      if (currentFilePath.value) {
        await writeFile(currentFilePath.value)
      } else {
        return await saveFileAs()
      }
      return true
    } catch (e) {
      setError(`Save failed: ${e}`)
      return false
    }
  }

  async function saveFileAs(): Promise<boolean> {
    try {
      const path = await save({ filters: FILTERS, defaultPath: `${workflow.name}.mimicry.json` })
      if (!path) return false
      await writeFile(path)
      currentFilePath.value = path
      return true
    } catch (e) {
      setError(`Save As failed: ${e}`)
      return false
    }
  }

  async function openFile(): Promise<boolean> {
    try {
      const path = await open({ filters: FILTERS, multiple: false, directory: false })
      if (!path) return false
      await readFile(path as string)
      return true
    } catch (e) {
      setError(`Open failed: ${e}`)
      return false
    }
  }

  /** Open any workflow file (Canonical / Compact / Recording / Legacy) via Rust transform. */
  async function importFile(): Promise<boolean> {
    try {
      const path = await open({ filters: IMPORT_FILTERS, multiple: false, directory: false })
      if (!path) return false
      await readFileTransform(path as string)
      return true
    } catch (e) {
      setError(`Import failed: ${e}`)
      return false
    }
  }

  async function openRecentFile(path: string): Promise<boolean> {
    try {
      await readFile(path)
      return true
    } catch (e) {
      setError(`Failed to open recent file: ${e}`)
      // File may have been deleted — remove from recent list
      await removeRecent(path)
      return false
    }
  }

  async function readFile(path: string) {
    const data = await invoke<{ name: string; nodes: unknown[]; edges: unknown[] }>('file_read', { path })
    if (!data || !Array.isArray(data.nodes) || !Array.isArray(data.edges)) {
      throw new Error('Invalid workflow file format')
    }
    workflow.fromJSON({ name: data.name, nodes: data.nodes as never[], edges: data.edges as never[] })
    currentFilePath.value = path

    workspace.renameTab(workspace.activeTabId, data.name)

    const name = path.split(/[\\/]/).pop() || data.name
    await invoke('recent_files_add', { path, name })
    await loadRecentFiles()
  }

  /** Read any format via Rust auto-detect + transform to Canonical. */
  async function readFileTransform(path: string) {
    const data = await invoke<{ name?: string; nodes: unknown[]; edges: unknown[] }>('file_import', { path })
    if (!data || !Array.isArray(data.nodes)) {
      throw new Error('Invalid workflow file format')
    }
    workflow.fromJSON({
      name: data.name,
      nodes: data.nodes as never[],
      edges: (data.edges ?? []) as never[],
    })
    currentFilePath.value = path

    const displayName = data.name || path.split(/[\\/]/).pop() || 'Imported'
    workspace.renameTab(workspace.activeTabId, displayName)

    const fileName = path.split(/[\\/]/).pop() || displayName
    await invoke('recent_files_add', { path, name: fileName })
    await loadRecentFiles()
  }

  async function writeFile(path: string) {
    const json = workflow.toJSON()
    await invoke('file_write', {
      path,
      workspace: { name: json.name, nodes: json.nodes, edges: json.edges },
    })

    const name = path.split(/[\\/]/).pop() || json.name
    await invoke('recent_files_add', { path, name })
    await loadRecentFiles()
  }

  /** Export current workflow as Compact format (LLM-friendly, no positions/edges). */
  async function exportCompact(): Promise<boolean> {
    try {
      const path = await save({
        filters: COMPACT_FILTERS,
        defaultPath: `${workflow.name}.compact.json`,
      })
      if (!path) return false
      const json = workflow.toJSON()
      await invoke('file_export_compact', { path, workflow: json })
      return true
    } catch (e) {
      setError(`Export Compact failed: ${e}`)
      return false
    }
  }

  async function removeRecent(path: string) {
    try {
      await invoke('recent_files_remove', { path })
      await loadRecentFiles()
    } catch (e) {
      setError(`Failed to remove recent file: ${e}`)
    }
  }

  async function clearRecent() {
    try {
      await invoke('recent_files_clear')
      recentFiles.value = []
    } catch (e) {
      setError(`Failed to clear recent files: ${e}`)
    }
  }

  function renameWorkflow(newName: string) {
    workflow.name = newName
    workspace.renameTab(workspace.activeTabId, newName)
  }

  return {
    currentFilePath,
    recentFiles,
    lastError,
    saveFile,
    saveFileAs,
    openFile,
    importFile,
    exportCompact,
    openRecentFile,
    removeRecent,
    clearRecent,
    loadRecentFiles,
    renameWorkflow,
  }
}

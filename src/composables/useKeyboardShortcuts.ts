import { onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useWorkflowStore } from '../stores/workflow'
import { usePanelLayout } from './usePanel'
import { useShortcutToast } from './useShortcutToast'

export function useKeyboardShortcuts() {
  const { t } = useI18n()
  const workflow = useWorkflowStore()
  const { toggleSidebar, toggleBottom, toggleRightPanel } = usePanelLayout()
  const { showToast } = useShortcutToast()

  function onKeyDown(e: KeyboardEvent) {
    const ctrl = e.ctrlKey || e.metaKey
    const key = e.key.toLowerCase()

    // Ctrl+Z — Undo
    if (ctrl && !e.shiftKey && key === 'z') {
      e.preventDefault()
      workflow.undo()
      showToast(t('shortcut.undo'), 'Ctrl+Z')
      return
    }

    // Ctrl+Y — Redo
    if (ctrl && key === 'y') {
      e.preventDefault()
      workflow.redo()
      showToast(t('shortcut.redo'), 'Ctrl+Y')
      return
    }

    // Ctrl+Shift+Z — Redo (alternative)
    if (ctrl && e.shiftKey && key === 'z') {
      e.preventDefault()
      workflow.redo()
      showToast(t('shortcut.redo'), 'Ctrl+Shift+Z')
      return
    }

    // Ctrl+S — Save (prevent default browser save)
    if (ctrl && key === 's') {
      e.preventDefault()
      showToast(t('shortcut.save'), 'Ctrl+S')
      // TODO: implement save to DB
      return
    }

    // Ctrl+B — Toggle sidebar
    if (ctrl && !e.altKey && key === 'b') {
      e.preventDefault()
      toggleSidebar()
      showToast(t('shortcut.toggleSidebar'), 'Ctrl+B')
      return
    }

    // Ctrl+J — Toggle bottom panel
    if (ctrl && key === 'j') {
      e.preventDefault()
      toggleBottom()
      showToast(t('shortcut.toggleBottom'), 'Ctrl+J')
      return
    }

    // Ctrl+Alt+B — Toggle right panel
    if (ctrl && e.altKey && key === 'b') {
      e.preventDefault()
      toggleRightPanel()
      showToast(t('shortcut.toggleRight'), 'Ctrl+Alt+B')
      return
    }

    // Delete — Remove selected node
    if (key === 'delete' && workflow.selectedNodeId) {
      workflow.removeNode(workflow.selectedNodeId)
      showToast(t('shortcut.deleteNode'), 'Delete')
      return
    }
  }

  onMounted(() => {
    window.addEventListener('keydown', onKeyDown)
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', onKeyDown)
  })
}

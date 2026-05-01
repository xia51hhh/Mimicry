import { onMounted, onUnmounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useWorkflowStore } from '../stores/workflow';
import { usePanelLayout } from './usePanel';
import { useShortcutToast } from './useShortcutToast';
import { useFileOps } from './useFileOps';

export function useKeyboardShortcuts() {
  const { t } = useI18n();
  const workflow = useWorkflowStore();
  const { toggleSidebar, toggleBottom, toggleRightPanel } = usePanelLayout();
  const { showToast } = useShortcutToast();
  const fileOps = useFileOps();

  function onKeyDown(e: KeyboardEvent) {
    const ctrl = e.ctrlKey || e.metaKey;
    const key = e.key.toLowerCase();

    // Ctrl+Z — Undo
    if (ctrl && !e.shiftKey && key === 'z') {
      e.preventDefault();
      workflow.undo();
      showToast(t('shortcut.undo'), 'Ctrl+Z');
      return;
    }

    // Ctrl+Y — Redo
    if (ctrl && key === 'y') {
      e.preventDefault();
      workflow.redo();
      showToast(t('shortcut.redo'), 'Ctrl+Y');
      return;
    }

    // Ctrl+Shift+Z — Redo (alternative)
    if (ctrl && e.shiftKey && key === 'z') {
      e.preventDefault();
      workflow.redo();
      showToast(t('shortcut.redo'), 'Ctrl+Shift+Z');
      return;
    }

    // Ctrl+S — Save
    if (ctrl && !e.shiftKey && key === 's') {
      e.preventDefault();
      fileOps.saveFile();
      showToast(t('shortcut.save'), 'Ctrl+S');
      return;
    }

    // Ctrl+Shift+S — Save As
    if (ctrl && e.shiftKey && key === 's') {
      e.preventDefault();
      fileOps.saveFileAs();
      showToast(t('fileMenu.saveAs'), 'Ctrl+Shift+S');
      return;
    }

    // Ctrl+O — Open File (multi-format import)
    if (ctrl && key === 'o') {
      e.preventDefault();
      fileOps.importFile();
      showToast(t('fileMenu.open'), 'Ctrl+O');
      return;
    }

    // Ctrl+B — Toggle sidebar
    if (ctrl && !e.altKey && key === 'b') {
      e.preventDefault();
      toggleSidebar();
      showToast(t('shortcut.toggleSidebar'), 'Ctrl+B');
      return;
    }

    // Ctrl+J — Toggle bottom panel
    if (ctrl && key === 'j') {
      e.preventDefault();
      toggleBottom();
      showToast(t('shortcut.toggleBottom'), 'Ctrl+J');
      return;
    }

    // Ctrl+Alt+B — Toggle right panel
    if (ctrl && e.altKey && key === 'b') {
      e.preventDefault();
      toggleRightPanel();
      showToast(t('shortcut.toggleRight'), 'Ctrl+Alt+B');
      return;
    }

    // Delete — Remove selected node
    if (key === 'delete' && workflow.selectedNodeId) {
      workflow.removeNode(workflow.selectedNodeId);
      showToast(t('shortcut.deleteNode'), 'Delete');
      return;
    }
  }

  function onBeforeUnload(e: BeforeUnloadEvent) {
    if (workflow.isDirty) {
      e.preventDefault();
    }
  }

  onMounted(() => {
    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('beforeunload', onBeforeUnload);
  });

  onUnmounted(() => {
    window.removeEventListener('keydown', onKeyDown);
    window.removeEventListener('beforeunload', onBeforeUnload);
  });
}

<script setup lang="ts">
  import { ref, onMounted, provide } from 'vue';
  import MainLayout from './components/layout/MainLayout.vue';
  import UpdateNotifier from './components/UpdateNotifier.vue';
  import ShortcutToast from './components/ui/ShortcutToast.vue';
  import SetupDialog from './components/ui/SetupDialog.vue';
  import { useShortcutToast } from './composables/useShortcutToast';
  import { useWorkspaceStore } from './stores/workspace';
  import { useWorkflowStore } from './stores/workflow';

  const { message, shortcut, visible } = useShortcutToast();
  const workspace = useWorkspaceStore();
  const workflow = useWorkflowStore();

  const updaterRef = ref<InstanceType<typeof UpdateNotifier>>();

  async function checkForUpdate(manual = false) {
    return updaterRef.value?.checkForUpdate(manual) ?? false;
  }

  provide('checkForUpdate', checkForUpdate);

  onMounted(async () => {
    workspace.restoreTabs();
    // Restore active tab's workflow from DB if it has a workflowId
    const activeTab = workspace.activeTab;
    if (activeTab?.workflowId) {
      try {
        await workflow.loadWorkflow(activeTab.workflowId);
      } catch {
        // DB entry may have been deleted — keep empty canvas
      }
    }
    checkForUpdate();
  });
</script>

<template>
  <MainLayout />
  <UpdateNotifier ref="updaterRef" />
  <ShortcutToast :message="message" :shortcut="shortcut" :visible="visible" />
  <SetupDialog />
</template>

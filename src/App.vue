<script setup lang="ts">
import { ref, onMounted, provide } from "vue";
import MainLayout from "./components/layout/MainLayout.vue";
import UpdateNotifier from "./components/UpdateNotifier.vue";
import ShortcutToast from "./components/ui/ShortcutToast.vue";
import { useShortcutToast } from "./composables/useShortcutToast";

const { message, shortcut, visible } = useShortcutToast();

const updaterRef = ref<InstanceType<typeof UpdateNotifier>>();

async function checkForUpdate(manual = false) {
  return updaterRef.value?.checkForUpdate(manual) ?? false;
}

provide("checkForUpdate", checkForUpdate);

onMounted(() => {
  checkForUpdate();
});
</script>

<template>
  <MainLayout />
  <UpdateNotifier ref="updaterRef" />
  <ShortcutToast :message="message" :shortcut="shortcut" :visible="visible" />
</template>
<script setup lang="ts">
import MainLayout from "./components/layout/MainLayout.vue";
import UpdateNotifier from "./components/UpdateNotifier.vue";
import ShortcutToast from "./components/ui/ShortcutToast.vue";
import { useShortcutToast } from "./composables/useShortcutToast";

const { message, shortcut, visible } = useShortcutToast();
</script>

<template>
  <MainLayout />
  <UpdateNotifier />
  <ShortcutToast :message="message" :shortcut="shortcut" :visible="visible" />
</template>
<script setup lang="ts">
import Sidebar from "./Sidebar.vue";
import Toolbar from "./Toolbar.vue";
</script>

<template>
  <div class="flex h-screen w-screen overflow-hidden">
    <Sidebar />
    <div class="flex flex-1 flex-col overflow-hidden">
      <Toolbar />
      <main class="flex-1 overflow-hidden">
        <router-view />
      </main>
    </div>
  </div>
</template>

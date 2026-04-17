<script setup lang="ts">
</script>

<template>
  <aside class="flex w-56 flex-col border-r border-[var(--color-border)] bg-[var(--color-surface)]">
    <div class="flex h-12 items-center px-4 text-lg font-bold tracking-wide">
      Mimicry
    </div>
    <nav class="flex-1 space-y-1 p-2">
      <router-link
        to="/"
        class="flex items-center gap-2 rounded px-3 py-2 text-sm hover:bg-white/5"
      >
        Workflow Editor
      </router-link>
    </nav>
  </aside>
</template>

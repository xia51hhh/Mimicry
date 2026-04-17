<script setup lang="ts">
defineProps<{
  message: string
  shortcut: string
  visible: boolean
}>()
</script>

<template>
  <Transition name="toast">
    <div v-if="visible" class="shortcut-toast">
      <span class="toast-message">{{ message }}</span>
      <kbd class="toast-kbd">{{ shortcut }}</kbd>
    </div>
  </Transition>
</template>

<style scoped>
.shortcut-toast {
  position: fixed;
  bottom: 48px;
  right: 24px;
  z-index: 9999;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 16px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
  font-size: 13px;
  color: var(--color-text);
  pointer-events: none;
}

.toast-message {
  font-weight: 500;
}

.toast-kbd {
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  font-size: 11px;
  font-family: monospace;
  color: var(--color-text-muted);
}

.toast-enter-active {
  transition: all 0.25s ease-out;
}
.toast-leave-active {
  transition: all 0.3s ease-in;
}
.toast-enter-from {
  opacity: 0;
  transform: translateY(12px) scale(0.95);
}
.toast-leave-to {
  opacity: 0;
  transform: translateY(-8px) scale(0.95);
}
</style>

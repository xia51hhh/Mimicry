<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'

export interface ContextMenuItem {
  id: string
  label: string
  shortcut?: string
  separator?: boolean
  disabled?: boolean
}

const props = defineProps<{
  items: ContextMenuItem[]
  x: number
  y: number
}>()

const emit = defineEmits<{
  (e: 'select', id: string): void
  (e: 'close'): void
}>()

const menuRef = ref<HTMLElement>()
const adjustedX = ref(props.x)
const adjustedY = ref(props.y)

onMounted(async () => {
  await nextTick()
  // Adjust position to keep menu within viewport
  if (menuRef.value) {
    const rect = menuRef.value.getBoundingClientRect()
    if (rect.right > window.innerWidth) {
      adjustedX.value = window.innerWidth - rect.width - 4
    }
    if (rect.bottom > window.innerHeight) {
      adjustedY.value = window.innerHeight - rect.height - 4
    }
  }
  document.addEventListener('mousedown', onClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('mousedown', onClickOutside)
})

function onClickOutside(e: MouseEvent) {
  if (menuRef.value && !menuRef.value.contains(e.target as Node)) {
    emit('close')
  }
}

function onItemClick(item: ContextMenuItem) {
  if (item.disabled || item.separator) return
  emit('select', item.id)
  emit('close')
}
</script>

<template>
  <div
    ref="menuRef"
    class="context-menu"
    :style="{ left: adjustedX + 'px', top: adjustedY + 'px' }"
  >
    <template v-for="item in items" :key="item.id">
      <div v-if="item.separator" class="context-separator" />
      <button
        v-else
        class="context-item"
        :class="{ disabled: item.disabled }"
        @click="onItemClick(item)"
      >
        <span class="item-label">{{ item.label }}</span>
        <span v-if="item.shortcut" class="item-shortcut">{{ item.shortcut }}</span>
      </button>
    </template>
  </div>
</template>

<style scoped>
.context-menu {
  position: fixed;
  z-index: 9999;
  min-width: 180px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 4px 0;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
}

.context-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 5px 12px;
  border: none;
  background: none;
  color: var(--color-text);
  font-size: 12px;
  cursor: pointer;
  text-align: left;
  transition: background 0.1s;
}

.context-item:hover:not(.disabled) {
  background: var(--color-accent);
  color: #fff;
}

.context-item.disabled {
  color: var(--color-text-muted);
  cursor: default;
  opacity: 0.5;
}

.item-shortcut {
  color: var(--color-text-muted);
  font-size: 11px;
  margin-left: 24px;
}

.context-item:hover:not(.disabled) .item-shortcut {
  color: rgba(255, 255, 255, 0.7);
}

.context-separator {
  height: 1px;
  background: var(--color-border);
  margin: 4px 0;
}
</style>

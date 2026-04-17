<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { Workflow, Globe, Database, Clock, Settings } from 'lucide-vue-next'
import { markRaw, type Component } from 'vue'

const { t } = useI18n()
const router = useRouter()

const emit = defineEmits<{
  (e: 'select', id: string): void
}>()

const props = defineProps<{
  activeId: string
}>()

interface ActivityItem {
  id: string
  icon: Component
  labelKey: string
  route?: string
}

const topItems: ActivityItem[] = [
  { id: 'workflow', icon: markRaw(Workflow), labelKey: 'activity.workflow', route: '/' },
  { id: 'browser', icon: markRaw(Globe), labelKey: 'activity.browser' },
  { id: 'data', icon: markRaw(Database), labelKey: 'activity.data' },
  { id: 'schedule', icon: markRaw(Clock), labelKey: 'activity.schedule' },
]

const bottomItems: ActivityItem[] = [
  { id: 'settings', icon: markRaw(Settings), labelKey: 'activity.settings', route: '/settings' },
]

function handleClick(item: ActivityItem) {
  if (item.id === 'settings' && props.activeId === 'settings') {
    router.push('/')
  } else if (item.route) {
    router.push(item.route)
  }
  emit('select', item.id)
}
</script>

<template>
  <div class="activity-bar">
    <div class="top-icons">
      <button
        v-for="item in topItems"
        :key="item.id"
        class="activity-icon"
        :class="{ active: activeId === item.id }"
        :title="t(item.labelKey)"
        @click="handleClick(item)"
      >
        <component :is="item.icon" :size="20" :stroke-width="1.5" />
      </button>
    </div>
    <div class="bottom-icons">
      <button
        v-for="item in bottomItems"
        :key="item.id"
        class="activity-icon"
        :class="{ active: activeId === item.id }"
        :title="t(item.labelKey)"
        @click="handleClick(item)"
      >
        <component :is="item.icon" :size="20" :stroke-width="1.5" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.activity-bar {
  width: 48px;
  min-width: 48px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  background: var(--color-bg);
  border-right: 1px solid var(--color-border);
  z-index: 10;
}

.top-icons,
.bottom-icons {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.activity-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: none;
  border-radius: 6px;
  cursor: pointer;
  position: relative;
  color: var(--color-text-muted);
  transition: all 0.15s;
}

.activity-icon:hover {
  background: var(--color-surface-hover);
  color: var(--color-text);
}

.activity-icon.active {
  color: var(--color-text);
}

.activity-icon.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 2px;
  background: var(--color-primary);
  border-radius: 0 2px 2px 0;
}
</style>

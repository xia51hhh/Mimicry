<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import TabBar from './TabBar.vue'
import ActivityBar from './ActivityBar.vue'
import Sidebar from './Sidebar.vue'
import Toolbar from './Toolbar.vue'
import { usePanelLayout } from '../../composables/usePanel'

const route = useRoute()
const { sidebarCollapsed } = usePanelLayout()

const activeActivity = ref('workflow')
const sidebarVisible = ref(true)

// Two-way sync: sidebarVisible <-> sidebarCollapsed
watch(sidebarCollapsed, (v) => { sidebarVisible.value = !v })
watch(sidebarVisible, (v) => { sidebarCollapsed.value = !v })

function onActivitySelect(id: string) {
  if (id === activeActivity.value) {
    if (id === 'settings') {
      // Toggle back from settings to editor
      activeActivity.value = 'workflow'
      sidebarVisible.value = true
    } else {
      sidebarVisible.value = !sidebarVisible.value
    }
  } else {
    sidebarVisible.value = id !== 'settings'
    activeActivity.value = id
  }
}

// Sync active activity from route
watch(
  () => route.path,
  (path) => {
    if (path === '/settings') {
      activeActivity.value = 'settings'
      sidebarVisible.value = false
    } else if (path === '/') {
      activeActivity.value = 'workflow'
    }
  },
  { immediate: true }
)
</script>

<template>
  <div class="flex h-screen w-screen flex-col overflow-hidden">
    <TabBar />
    <div class="flex flex-1 overflow-hidden">
      <ActivityBar :active-id="activeActivity" @select="onActivitySelect" />
      <Sidebar :active-id="activeActivity" :visible="sidebarVisible" />
      <div class="flex flex-1 flex-col overflow-hidden">
        <Toolbar />
        <main class="flex-1 overflow-hidden">
          <router-view />
        </main>
      </div>
    </div>
  </div>
</template>

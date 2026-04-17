<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useWorkspaceStore } from '../../stores/workspace'
import { useWorkflowStore } from '../../stores/workflow'
import { usePanelLayout } from '../../composables/usePanel'
import { Plus, X, PanelLeft, PanelBottom, PanelRight, Minus, Square, Maximize2, Undo2, Redo2, Save } from 'lucide-vue-next'
import MimicryLogo from '../../assets/mimicry-logo.svg'

const { t } = useI18n()
const router = useRouter()
const workspace = useWorkspaceStore()
const workflow = useWorkflowStore()
const { sidebarCollapsed, bottomCollapsed, rightPanelCollapsed, toggleSidebar, toggleBottom, toggleRightPanel } = usePanelLayout()

const menuOpen = ref(false)
const isMaximized = ref(false)

// Window control functions (Tauri API)
import type { Window as TauriWindow } from '@tauri-apps/api/window'

let appWindow: TauriWindow | null = null
let unlistenResize: (() => void) | null = null

onMounted(async () => {
  try {
    const { getCurrentWindow } = await import('@tauri-apps/api/window')
    appWindow = getCurrentWindow()
    isMaximized.value = await appWindow.isMaximized()
    // Listen for resize to track maximize state
    unlistenResize = await appWindow.onResized(async () => {
      isMaximized.value = await appWindow!.isMaximized()
    })
  } catch {
    // Not in Tauri environment (web dev)
  }
})

onUnmounted(() => {
  unlistenResize?.()
})

function minimizeWindow() {
  appWindow?.minimize()
}

function toggleMaximize() {
  appWindow?.toggleMaximize()
}

function closeWindow() {
  appWindow?.close()
}

function onTabClick(tabId: string) {
  if (tabId === workspace.activeTabId) return
  // Save current tab's workflow data
  workspace.saveTabData(workspace.activeTabId, workflow.toJSON())
  // Switch tab
  workspace.switchTab(tabId)
  // Restore target tab's workflow data
  const data = workspace.getTabData(tabId)
  if (data) {
    workflow.fromJSON(data)
  } else {
    workflow.clear()
  }
  router.push('/')
}

function onAddTab() {
  // Save current tab's workflow data before switching
  workspace.saveTabData(workspace.activeTabId, workflow.toJSON())
  workspace.addTab()
  workflow.clear()
  router.push('/')
}

function onCloseTab(e: MouseEvent, tabId: string) {
  e.stopPropagation()
  const wasActive = tabId === workspace.activeTabId
  workspace.closeTab(tabId)
  if (wasActive) {
    // Restore the new active tab's data
    const data = workspace.getTabData(workspace.activeTabId)
    if (data) {
      workflow.fromJSON(data)
    } else {
      workflow.clear()
    }
  }
}

function toggleMenu() {
  menuOpen.value = !menuOpen.value
}

function closeMenu() {
  menuOpen.value = false
}

interface MenuItem {
  label: string
  action?: () => void
  separator?: boolean
}

const menuItems: MenuItem[] = [
  { label: t('app.title'), separator: true },
  { label: t('sidebar.blocks'), action: () => router.push('/') },
  { label: t('settings.title'), action: () => router.push('/settings') },
]
</script>

<template>
  <div class="tab-bar" data-tauri-drag-region>
    <!-- JB-style app menu button -->
    <div class="menu-area">
      <button class="menu-btn" @click="toggleMenu" :title="t('app.title')">
        <span class="menu-logo" :style="{ maskImage: `url(${MimicryLogo})`, WebkitMaskImage: `url(${MimicryLogo})` }" />
      </button>
      <Transition name="fade">
        <div v-if="menuOpen" class="menu-overlay" @click="closeMenu" />
      </Transition>
      <Transition name="slide">
        <div v-if="menuOpen" class="menu-dropdown">
          <template v-for="(item, idx) in menuItems" :key="idx">
            <div v-if="item.separator" class="menu-separator" />
            <button
              v-else
              class="menu-item"
              @click="() => { item.action?.(); closeMenu() }"
            >
              {{ item.label }}
            </button>
          </template>
        </div>
      </Transition>
    </div>

    <!-- Tabs -->
    <div class="tabs-scroll">
      <div
        v-for="tab in workspace.tabs"
        :key="tab.id"
        class="tab"
        :class="{ active: workspace.activeTabId === tab.id }"
        @click="onTabClick(tab.id)"
      >
        <span class="tab-name">{{ tab.name }}</span>
        <button
          v-if="workspace.tabs.length > 1"
          class="tab-close"
          @click="(e) => onCloseTab(e, tab.id)"
        >
          <X :size="12" :stroke-width="2" />
        </button>
      </div>
    </div>

    <!-- New tab button -->
    <button class="new-tab-btn" @click="onAddTab" :title="t('toolbar.newWorkflow') || 'New Tab'">
      <Plus :size="14" :stroke-width="2" />
    </button>

    <!-- Right area: actions + panel toggles + window controls -->
    <div class="right-controls">
      <!-- Undo/Redo/Save -->
      <button
        class="panel-toggle"
        :class="{ disabled: !workflow.canUndo }"
        :title="t('tabBar.undo')"
        @click="workflow.undo()"
      >
        <Undo2 :size="14" :stroke-width="1.5" />
      </button>
      <button
        class="panel-toggle"
        :class="{ disabled: !workflow.canRedo }"
        :title="t('tabBar.redo')"
        @click="workflow.redo()"
      >
        <Redo2 :size="14" :stroke-width="1.5" />
      </button>
      <button
        class="panel-toggle"
        :title="t('tabBar.save')"
      >
        <Save :size="14" :stroke-width="1.5" />
      </button>

      <span class="controls-separator" />

      <!-- Panel toggles -->
      <button
        class="panel-toggle"
        :class="{ active: !sidebarCollapsed }"
        :title="t('tabBar.toggleSidebar')"
        @click="toggleSidebar"
      >
        <PanelLeft :size="14" :stroke-width="1.5" />
      </button>
      <button
        class="panel-toggle"
        :class="{ active: !bottomCollapsed }"
        :title="t('tabBar.togglePanel')"
        @click="toggleBottom"
      >
        <PanelBottom :size="14" :stroke-width="1.5" />
      </button>
      <button
        class="panel-toggle"
        :class="{ active: !rightPanelCollapsed }"
        :title="t('tabBar.toggleAuxSidebar')"
        @click="toggleRightPanel"
      >
        <PanelRight :size="14" :stroke-width="1.5" />
      </button>

      <!-- Window controls -->
      <span class="controls-separator" />
      <button class="window-btn" @click="minimizeWindow" :title="t('tabBar.minimize')">
        <Minus :size="14" :stroke-width="1.5" />
      </button>
      <button class="window-btn" @click="toggleMaximize" :title="isMaximized ? t('tabBar.restore') : t('tabBar.maximize')">
        <component :is="isMaximized ? Square : Maximize2" :size="12" :stroke-width="1.5" />
      </button>
      <button class="window-btn window-close" @click="closeWindow" :title="t('tabBar.close')">
        <X :size="14" :stroke-width="1.5" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.tab-bar {
  display: flex;
  align-items: center;
  height: 36px;
  min-height: 36px;
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-border);
  user-select: none;
  -webkit-app-region: drag;
}

.menu-area {
  position: relative;
  -webkit-app-region: no-drag;
}

.menu-btn {
  width: 48px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  color: var(--color-text-muted);
  cursor: pointer;
  transition: all 0.15s;
}

.menu-btn:hover {
  background: var(--color-surface-hover);
  color: var(--color-text);
}

.menu-logo {
  display: block;
  width: 50px;
  height: 50px;
  background-color: currentColor;
  mask-size: contain;
  mask-repeat: no-repeat;
  mask-position: center;
  -webkit-mask-size: contain;
  -webkit-mask-repeat: no-repeat;
  -webkit-mask-position: center;
}

.menu-overlay {
  position: fixed;
  inset: 0;
  z-index: 99;
}

.menu-dropdown {
  position: absolute;
  top: 36px;
  left: 0;
  min-width: 200px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 4px 0;
  z-index: 100;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
}

.menu-item {
  display: block;
  width: 100%;
  padding: 6px 16px;
  background: none;
  border: none;
  color: var(--color-text);
  font-size: 13px;
  text-align: left;
  cursor: pointer;
  transition: background 0.1s;
}

.menu-item:hover {
  background: var(--color-surface-hover);
}

.menu-separator {
  height: 1px;
  margin: 4px 8px;
  background: var(--color-separator);
}

.tabs-scroll {
  display: flex;
  flex: 1;
  overflow-x: auto;
  overflow-y: hidden;
  -webkit-app-region: no-drag;
}

.tabs-scroll::-webkit-scrollbar {
  height: 0;
}

.tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 12px;
  height: 36px;
  font-size: 12px;
  color: var(--color-text-muted);
  cursor: pointer;
  white-space: nowrap;
  border-right: 1px solid var(--color-border);
  transition: all 0.15s;
  flex-shrink: 0;
  max-width: 200px;
}

.tab:hover {
  background: var(--color-surface-hover);
  color: var(--color-text);
}

.tab.active {
  background: var(--color-surface);
  color: var(--color-text);
}

.tab-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tab-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border: none;
  background: none;
  color: var(--color-text-muted);
  border-radius: 4px;
  cursor: pointer;
  opacity: 0;
  transition: all 0.1s;
  flex-shrink: 0;
}

.tab:hover .tab-close {
  opacity: 1;
}

.tab-close:hover {
  background: var(--color-surface-active, var(--color-surface-hover));
  color: var(--color-text);
}

.new-tab-btn {
  width: 32px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  color: var(--color-text-muted);
  cursor: pointer;
  transition: all 0.15s;
  -webkit-app-region: no-drag;
  flex-shrink: 0;
}

.new-tab-btn:hover {
  background: var(--color-surface-hover);
  color: var(--color-text);
}

/* Transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-enter-active,
.slide-leave-active {
  transition: all 0.15s;
}
.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* Right controls area */
.right-controls {
  display: flex;
  align-items: center;
  -webkit-app-region: no-drag;
  flex-shrink: 0;
}

.panel-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 36px;
  border: none;
  background: none;
  color: var(--color-text-muted);
  cursor: pointer;
  transition: all 0.15s;
}

.panel-toggle:hover {
  background: var(--color-surface-hover);
  color: var(--color-text);
}

.panel-toggle.active {
  color: var(--color-text);
}

.panel-toggle.disabled {
  opacity: 0.35;
  cursor: default;
}

.controls-separator {
  width: 1px;
  height: 16px;
  background: var(--color-border);
  margin: 0 2px;
}

.window-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 46px;
  height: 36px;
  border: none;
  background: none;
  color: var(--color-text-muted);
  cursor: pointer;
  transition: all 0.15s;
}

.window-btn:hover {
  background: var(--color-surface-hover);
  color: var(--color-text);
}

.window-close:hover {
  background: #e81123;
  color: #fff;
}
</style>

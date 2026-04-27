<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import { listen, type UnlistenFn } from '@tauri-apps/api/event'
import { SidecarEvent } from '../types/ipc'
import { useI18n } from 'vue-i18n'
import { useBrowserStore } from '../stores/browser'
import { Download, CheckCircle, XCircle } from 'lucide-vue-next'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ (e: 'close'): void }>()

watch(() => props.visible, (v) => {
  document.body.style.overflow = v ? 'hidden' : ''
})

const { t } = useI18n()
const browser = useBrowserStore()
const installError = ref<string | null>(null)
const installProgress = ref(0)
const installMessage = ref('')

const state = computed(() => {
  if (browser.camoufoxInstalling) return 'installing'
  if (browser.camoufoxInstalled) return 'success'
  if (installError.value) return 'error'
  return 'prompt'
})

// Listen for progress notifications from sidecar
let unlisten: UnlistenFn | null = null

async function startListening() {
  unlisten = await listen<{ stage: string; progress: number; message: string }>(
    SidecarEvent.CamoufoxProgress,
    (event) => {
      installProgress.value = event.payload.progress
      installMessage.value = event.payload.message
    }
  )
}

startListening()

onUnmounted(() => {
  unlisten?.()
})

async function handleInstall() {
  installError.value = null
  installProgress.value = 0
  installMessage.value = ''
  const result = await browser.installCamoufox()
  if (!result.success) {
    installError.value = result.error ?? 'Unknown error'
  }
}

function handleClose() {
  installError.value = null
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="camoufox-overlay" @click.self="handleClose">
      <div class="camoufox-dialog">
        <!-- Prompt -->
        <template v-if="state === 'prompt'">
          <div class="dialog-icon">
            <Download :size="32" />
          </div>
          <h3 class="dialog-title">{{ t('camoufox.notInstalled') }}</h3>
          <p class="dialog-desc">{{ t('camoufox.notInstalledDesc') }}</p>
          <div class="dialog-actions">
            <button class="btn-primary" @click="handleInstall">
              <Download :size="14" />
              {{ t('camoufox.install') }}
            </button>
            <button class="btn-secondary" @click="handleClose">
              {{ t('camoufox.cancel') }}
            </button>
          </div>
        </template>

        <!-- Installing with progress -->
        <template v-if="state === 'installing'">
          <h3 class="dialog-title">{{ t('camoufox.installing') }}</h3>
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: installProgress + '%' }" />
          </div>
          <p class="progress-text">{{ installProgress }}%</p>
          <p class="install-message" v-if="installMessage">{{ installMessage }}</p>
        </template>

        <!-- Success -->
        <template v-if="state === 'success'">
          <div class="dialog-icon success">
            <CheckCircle :size="32" />
          </div>
          <h3 class="dialog-title">{{ t('camoufox.installSuccess') }}</h3>
          <p class="dialog-desc" v-if="browser.camoufoxVersion">
            {{ t('camoufox.version') }}: {{ browser.camoufoxVersion }}
          </p>
          <div class="dialog-actions">
            <button class="btn-primary" @click="handleClose">OK</button>
          </div>
        </template>

        <!-- Error -->
        <template v-if="state === 'error'">
          <div class="dialog-icon error">
            <XCircle :size="32" />
          </div>
          <h3 class="dialog-title">{{ t('camoufox.installFailed') }}</h3>
          <p class="dialog-desc error-text">{{ installError }}</p>
          <div class="dialog-actions">
            <button class="btn-primary" @click="handleInstall">
              {{ t('camoufox.retry') }}
            </button>
            <button class="btn-secondary" @click="handleClose">
              {{ t('camoufox.cancel') }}
            </button>
          </div>
        </template>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.camoufox-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(2px);
}

.camoufox-dialog {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 32px;
  width: 400px;
  max-width: 90vw;
  max-height: 80vh;
  overflow-y: auto;
  text-align: center;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.dialog-icon {
  margin-bottom: 16px;
  color: var(--color-primary);
}

.dialog-icon.success {
  color: #22c55e;
}

.dialog-icon.error {
  color: #ef4444;
}

.dialog-icon.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.dialog-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: 8px;
}

.dialog-desc {
  font-size: 13px;
  color: var(--color-text-muted);
  line-height: 1.5;
  margin-bottom: 20px;
}

.error-text {
  color: #ef4444;
  font-family: monospace;
  font-size: 12px;
  max-height: 80px;
  overflow-y: auto;
  text-align: left;
  background: rgba(239, 68, 68, 0.1);
  padding: 8px;
  border-radius: 4px;
}

.dialog-actions {
  display: flex;
  gap: 8px;
  justify-content: center;
}

.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 20px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  background: var(--color-primary);
  color: white;
  border: none;
  cursor: pointer;
  transition: opacity 0.15s;
}

.btn-primary:hover {
  opacity: 0.9;
}

.btn-secondary {
  padding: 8px 20px;
  border-radius: 6px;
  font-size: 13px;
  background: transparent;
  color: var(--color-text-muted);
  border: 1px solid var(--color-border);
  cursor: pointer;
  transition: background 0.15s;
}

.btn-secondary:hover {
  background: rgba(255, 255, 255, 0.05);
}

.progress-bar {
  height: 6px;
  background: var(--color-bg);
  border-radius: 3px;
  margin: 16px 0 8px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--color-primary);
  border-radius: 3px;
  transition: width 0.3s;
}

.progress-text {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text);
  margin-bottom: 4px;
}

.install-message {
  font-size: 11px;
  color: var(--color-text-muted);
  font-family: monospace;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>

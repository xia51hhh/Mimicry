<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useBrowserStore } from '../../stores/browser'
import { Download, CheckCircle, XCircle, Loader2, Package, Shield, Copy, ChevronDown, ChevronUp } from 'lucide-vue-next'

const { t } = useI18n()
const browser = useBrowserStore()
const errorExpanded = ref(false)
const copied = ref(false)

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1)
}

const steps = [
  { key: 'venv' as const, label: () => t('setup.stepVenv') },
  { key: 'pip' as const, label: () => t('setup.stepPip') },
  { key: 'browser' as const, label: () => t('setup.stepBrowser') },
]

function stepStatus(stepKey: string) {
  if (!browser.installStep) return 'pending'
  const order = ['venv', 'pip', 'browser']
  const currentIdx = order.indexOf(browser.installStep)
  const stepIdx = order.indexOf(stepKey)
  if (stepIdx < currentIdx) return 'done'
  if (stepIdx === currentIdx) {
    return browser.installProgress >= 100 ? 'done' : 'active'
  }
  return 'pending'
}

const overallProgress = computed(() => {
  const order = ['venv', 'pip', 'browser']
  const currentIdx = order.indexOf(browser.installStep || 'venv')
  const base = (currentIdx / 3) * 100
  const stepContrib = (browser.installProgress / 3)
  return Math.min(Math.round(base + stepContrib), 100)
})

function handleInstallSystemPkg() {
  browser.installSystemPkg(browser.systemPkgName)
}

/** Extract the last meaningful line from a Python traceback as summary */
const errorSummary = computed(() => {
  const err = browser.setupError
  if (!err) return ''
  // Find the last exception line (e.g. "requests.exceptions.HTTPError: 403 ...")
  const lines = err.split(/\n/)
  for (let i = lines.length - 1; i >= 0; i--) {
    const line = lines[i].trim()
    if (line && !line.startsWith('File ') && !line.startsWith('~~~') && !line.startsWith('^')) {
      return line
    }
  }
  return err.length > 200 ? err.slice(0, 200) + '...' : err
})

const hasFullError = computed(() => {
  return browser.setupError !== null && browser.setupError !== errorSummary.value
})

async function copyError() {
  if (!browser.setupError) return
  await navigator.clipboard.writeText(browser.setupError)
  copied.value = true
  setTimeout(() => { copied.value = false }, 2000)
}
</script>

<template>
  <Teleport to="body">
    <Transition name="dialog">
      <div
        v-if="browser.setupPhase !== 'idle' && browser.setupPhase !== 'checking'"
        class="dialog-overlay"
        @click.self="browser.setupPhase === 'prompt' || browser.setupPhase === 'completed' || browser.setupPhase === 'failed' ? browser.resetSetup() : undefined"
      >
        <div class="dialog-content">
          <!-- Header -->
          <div class="dialog-header">
            <Package :size="20" />
            <span>{{ t('setup.title') }}</span>
          </div>

          <!-- Prompt phase: show what will be installed -->
          <template v-if="browser.setupPhase === 'prompt'">
            <p class="dialog-desc">{{ t('setup.notInstalled') }}</p>
            <ul class="dep-list">
              <li>{{ t('setup.depPythonVenv') }}</li>
              <li>{{ t('setup.depPipPackages') }}</li>
              <li>{{ t('setup.depCamoufox') }}</li>
            </ul>
            <div class="dialog-actions">
              <button class="btn btn-secondary" @click="browser.resetSetup()">
                {{ t('setup.cancel') }}
              </button>
              <button class="btn btn-primary" @click="browser.installBrowser()">
                <Download :size="14" />
                {{ t('setup.install') }}
              </button>
            </div>
          </template>

          <!-- Need system package -->
          <template v-else-if="browser.setupPhase === 'need_system_pkg'">
            <div class="system-pkg-section">
              <Shield :size="20" class="text-warning" />
              <p class="dialog-desc">{{ t('setup.needSystemPkg') }}</p>
            </div>
            <p class="dialog-hint">{{ t('setup.systemPkgHint') }}</p>
            <code class="cmd-block">sudo apt install {{ browser.systemPkgName }}</code>
            <div v-if="browser.setupError" class="error-block">
              <div class="error-summary">
                <span class="error-text">{{ errorSummary }}</span>
                <button class="icon-btn" @click="copyError" :title="copied ? '已复制' : '复制'">
                  <CheckCircle v-if="copied" :size="14" class="text-success" />
                  <Copy v-else :size="14" />
                </button>
              </div>
            </div>
            <div class="dialog-actions">
              <button class="btn btn-secondary" @click="browser.resetSetup()">
                {{ t('setup.cancel') }}
              </button>
              <button class="btn btn-secondary" @click="browser.installBrowser()">
                {{ t('setup.manualInstall') }}
              </button>
              <button class="btn btn-primary" @click="handleInstallSystemPkg">
                <Shield :size="14" />
                {{ t('setup.autoInstall') }}
              </button>
            </div>
          </template>

          <!-- Installing phase: show progress -->
          <template v-else-if="browser.setupPhase === 'installing'">
            <div class="steps-list">
              <div v-for="step in steps" :key="step.key" class="step-item" :class="stepStatus(step.key)">
                <CheckCircle v-if="stepStatus(step.key) === 'done'" :size="16" class="step-icon done" />
                <Loader2 v-else-if="stepStatus(step.key) === 'active'" :size="16" class="step-icon active spin" />
                <div v-else class="step-icon pending-dot" />
                <span class="step-label">{{ step.label() }}</span>
              </div>
            </div>
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: overallProgress + '%' }" />
            </div>
            <p class="progress-text">
              {{ browser.installStep ? t(`setup.step${capitalize(browser.installStep)}`) : '' }}
              <span v-if="browser.installDetail" class="progress-detail">{{ browser.installDetail }}</span>
              <span v-else>...</span>
            </p>
          </template>

          <!-- Completed -->
          <template v-else-if="browser.setupPhase === 'completed'">
            <div class="result-section success">
              <CheckCircle :size="32" />
              <p>{{ t('setup.completed') }}</p>
            </div>
            <div class="dialog-actions">
              <button class="btn btn-primary" @click="browser.launchAfterSetup()">
                {{ t('toolbar.launchBrowser') }}
              </button>
            </div>
          </template>

          <!-- Failed -->
          <template v-else-if="browser.setupPhase === 'failed'">
            <div class="result-section error">
              <XCircle :size="32" />
              <p>{{ t('setup.failed') }}</p>
            </div>
            <div v-if="browser.setupError" class="error-block">
              <div class="error-summary">
                <span class="error-text">{{ errorSummary }}</span>
                <div class="error-actions">
                  <button v-if="hasFullError" class="icon-btn" @click="errorExpanded = !errorExpanded" :title="errorExpanded ? '收起' : '展开'">
                    <ChevronUp v-if="errorExpanded" :size="14" />
                    <ChevronDown v-else :size="14" />
                  </button>
                  <button class="icon-btn" @click="copyError" :title="copied ? '已复制' : '复制错误信息'">
                    <CheckCircle v-if="copied" :size="14" class="text-success" />
                    <Copy v-else :size="14" />
                  </button>
                </div>
              </div>
              <pre v-if="errorExpanded" class="error-detail">{{ browser.setupError }}</pre>
            </div>
            <div class="dialog-actions">
              <button class="btn btn-secondary" @click="browser.resetSetup()">
                {{ t('setup.close') }}
              </button>
              <button class="btn btn-primary" @click="browser.installBrowser()">
                {{ t('setup.retry') }}
              </button>
            </div>
          </template>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.dialog-content {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 24px;
  min-width: 420px;
  max-width: 500px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

.dialog-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: 16px;
}

.dialog-desc {
  font-size: 13px;
  color: var(--color-text-muted);
  margin-bottom: 12px;
  line-height: 1.5;
}

.dep-list {
  list-style: none;
  padding: 0;
  margin: 0 0 20px;
}

.dep-list li {
  font-size: 13px;
  color: var(--color-text);
  padding: 6px 0;
  padding-left: 16px;
  position: relative;
}

.dep-list li::before {
  content: "•";
  position: absolute;
  left: 0;
  color: var(--color-primary);
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 16px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  border: none;
  transition: all 0.15s;
}

.btn-primary {
  background: var(--color-primary);
  color: white;
}

.btn-primary:hover {
  opacity: 0.9;
}

.btn-secondary {
  background: var(--color-surface-hover, #333);
  color: var(--color-text);
}

.btn-secondary:hover {
  background: var(--color-surface-active, #444);
}

.steps-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 20px;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: var(--color-text-muted);
}

.step-item.done {
  color: var(--color-text);
}

.step-item.active {
  color: var(--color-primary);
}

.step-icon.done {
  color: #22c55e;
}

.step-icon.active {
  color: var(--color-primary);
}

.pending-dot {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid var(--color-border);
  box-sizing: border-box;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.progress-bar {
  height: 4px;
  background: var(--color-border);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 8px;
}

.progress-fill {
  height: 100%;
  background: var(--color-primary);
  border-radius: 2px;
  transition: width 0.3s ease;
}

.progress-text {
  font-size: 12px;
  color: var(--color-text-muted);
  text-align: center;
}

.progress-detail {
  font-family: monospace;
  margin-left: 4px;
  color: var(--color-text);
}

.result-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 20px 0;
}

.result-section.success {
  color: #22c55e;
}

.result-section.error {
  color: #ef4444;
}

.result-section p {
  font-size: 15px;
  font-weight: 500;
}

.error-block {
  margin-top: 8px;
}

.error-summary {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(239, 68, 68, 0.1);
  padding: 8px 12px;
  border-radius: 4px;
}

.error-text {
  flex: 1;
  font-size: 12px;
  color: #ef4444;
  user-select: text;
  -webkit-user-select: text;
  word-break: break-word;
}

.error-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
  border-radius: 4px;
  flex-shrink: 0;
}

.icon-btn:hover {
  background: var(--color-surface-hover, #333);
  color: var(--color-text);
}

.icon-btn .text-success {
  color: #22c55e;
}

.error-detail {
  font-size: 11px;
  color: #ef4444;
  background: rgba(239, 68, 68, 0.05);
  border: 1px solid rgba(239, 68, 68, 0.15);
  border-top: none;
  border-radius: 0 0 4px 4px;
  padding: 8px 12px;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  user-select: text;
  -webkit-user-select: text;
  margin: 0;
  font-family: monospace;
}

.system-pkg-section {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 8px;
}

.system-pkg-section .text-warning {
  color: #f59e0b;
  flex-shrink: 0;
  margin-top: 2px;
}

.dialog-hint {
  font-size: 12px;
  color: var(--color-text-muted);
  margin-bottom: 8px;
}

.cmd-block {
  display: block;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 13px;
  font-family: monospace;
  color: var(--color-text);
  margin-bottom: 8px;
}

.dialog-enter-active,
.dialog-leave-active {
  transition: opacity 0.2s;
}

.dialog-enter-from,
.dialog-leave-to {
  opacity: 0;
}
</style>

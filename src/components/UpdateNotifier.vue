<script setup lang="ts">
  import { ref, computed, watch } from 'vue';
  import { check, type Update } from '@tauri-apps/plugin-updater';
  import { openUrl } from '@tauri-apps/plugin-opener';
  import { useI18n } from 'vue-i18n';
  import { Download, X, ExternalLink } from 'lucide-vue-next';

  const { t } = useI18n();

  const SKIPPED_VERSION_KEY = 'mimicry_skipped_update_version';

  const visible = ref(false);
  const version = ref('');
  const body = ref('');
  const downloading = ref(false);
  const progress = ref(0);
  const contentLength = ref(0);
  const downloaded = ref(0);
  const isManualFallback = ref(false);

  let pendingUpdate: Update | null = null;

  // Lock body scroll
  watch(visible, (v) => {
    document.body.style.overflow = v ? 'hidden' : '';
  });

  const progressText = computed(() => {
    if (contentLength.value > 0) {
      const mb = (n: number) => (n / 1024 / 1024).toFixed(1);
      return `${mb(downloaded.value)} / ${mb(contentLength.value)} MB`;
    }
    return `${progress.value}%`;
  });

  async function checkForUpdate(manual = false) {
    try {
      const update = await check();
      if (!update) {
        if (manual) pendingUpdate = null;
        return false;
      }
      if (!manual) {
        const skipped = localStorage.getItem(SKIPPED_VERSION_KEY);
        if (skipped === update.version) return false;
      }
      pendingUpdate = update;
      version.value = update.version;
      body.value = update.body || '';
      isManualFallback.value = false;
      downloading.value = false;
      progress.value = 0;
      visible.value = true;
      return true;
    } catch (e) {
      console.debug('Update check failed:', e);
      if (manual) throw e;
      return false;
    }
  }

  function handleSkipVersion() {
    localStorage.setItem(SKIPPED_VERSION_KEY, version.value);
    visible.value = false;
  }

  function handleClose() {
    if (!downloading.value) visible.value = false;
  }

  async function handleInstall() {
    if (!pendingUpdate) return;
    downloading.value = true;
    downloaded.value = 0;
    contentLength.value = 0;
    try {
      await pendingUpdate.downloadAndInstall((event) => {
        switch (event.event) {
          case 'Started':
            contentLength.value = (event.data as { contentLength?: number }).contentLength ?? 0;
            break;
          case 'Progress':
            downloaded.value += (event.data as { chunkLength: number }).chunkLength;
            progress.value =
              contentLength.value > 0
                ? Math.round((downloaded.value / contentLength.value) * 100)
                : 0;
            break;
          case 'Finished':
            progress.value = 100;
            break;
        }
      });
    } catch (e) {
      console.warn('Auto-update failed, fallback to manual:', e);
      downloading.value = false;
      isManualFallback.value = true;
    }
  }

  async function openReleasePage() {
    await openUrl('https://github.com/51hhh/Mimicry/releases/latest');
    visible.value = false;
  }

  defineExpose({ checkForUpdate });
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="update-overlay" @click.self="handleClose">
      <div class="update-dialog">
        <!-- Header -->
        <div class="dialog-header">
          <h3 class="dialog-title">
            {{ isManualFallback ? t('update.manualTitle') : t('update.title') }}
          </h3>
          <button v-if="!downloading" class="close-btn" @click="handleClose">
            <X :size="16" />
          </button>
        </div>

        <!-- Manual fallback -->
        <template v-if="isManualFallback">
          <p class="dialog-desc">
            {{ t('update.manualDesc', { version: version }) }}
          </p>
          <div class="dialog-actions">
            <button class="btn-primary" @click="openReleasePage">
              <ExternalLink :size="14" />
              {{ t('update.goDownload') }}
            </button>
            <button class="btn-secondary" @click="handleClose">
              {{ t('update.close') }}
            </button>
          </div>
        </template>

        <!-- Downloading -->
        <template v-else-if="downloading">
          <p class="dialog-desc">{{ t('update.downloading', { version: version }) }}</p>
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: progress + '%' }" />
          </div>
          <p class="progress-text">{{ progressText }}</p>
        </template>

        <!-- Update available -->
        <template v-else>
          <p class="dialog-desc">
            {{ t('update.available', { version: version }) }}
          </p>
          <!-- Changelog -->
          <pre v-if="body" class="changelog">{{ body }}</pre>
          <div class="dialog-actions">
            <button class="btn-primary" @click="handleInstall">
              <Download :size="14" />
              {{ t('update.install') }}
            </button>
            <button class="btn-secondary" @click="handleClose">
              {{ t('update.later') }}
            </button>
            <button class="btn-ghost" @click="handleSkipVersion">
              {{ t('update.skipVersion') }}
            </button>
          </div>
        </template>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
  .update-overlay {
    position: fixed;
    inset: 0;
    z-index: 100;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(2px);
  }

  .update-dialog {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: 12px;
    padding: 24px;
    width: 440px;
    max-width: 90vw;
    max-height: 80vh;
    overflow-y: auto;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  }

  .dialog-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
  }

  .dialog-title {
    font-size: 16px;
    font-weight: 600;
    color: var(--color-text);
    margin: 0;
  }

  .close-btn {
    background: none;
    border: none;
    color: var(--color-text-muted);
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;
    display: flex;
  }

  .close-btn:hover {
    color: var(--color-text);
    background: var(--color-hover);
  }

  .dialog-desc {
    font-size: 13px;
    color: var(--color-text-muted);
    margin: 0 0 16px;
    line-height: 1.5;
  }

  .changelog {
    font-size: 12px;
    color: var(--color-text-muted);
    background: var(--color-bg);
    border: 1px solid var(--color-border);
    border-radius: 6px;
    padding: 12px;
    max-height: 160px;
    overflow-y: auto;
    margin-bottom: 16px;
    white-space: pre-wrap;
    word-break: break-word;
    font-family: inherit;
  }

  .progress-bar {
    height: 6px;
    background: var(--color-bg);
    border-radius: 3px;
    margin-bottom: 8px;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    background: var(--color-primary);
    border-radius: 3px;
    transition: width 0.3s;
  }

  .progress-text {
    font-size: 12px;
    color: var(--color-text-muted);
    text-align: center;
    margin: 0;
  }

  .dialog-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .btn-primary {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 16px;
    font-size: 13px;
    background: var(--color-primary);
    color: white;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    transition: opacity 0.15s;
  }

  .btn-primary:hover {
    opacity: 0.9;
  }

  .btn-secondary {
    padding: 6px 16px;
    font-size: 13px;
    background: none;
    color: var(--color-text);
    border: 1px solid var(--color-border);
    border-radius: 6px;
    cursor: pointer;
  }

  .btn-secondary:hover {
    background: var(--color-hover);
  }

  .btn-ghost {
    padding: 6px 12px;
    font-size: 12px;
    background: none;
    color: var(--color-text-muted);
    border: none;
    cursor: pointer;
    margin-left: auto;
  }

  .btn-ghost:hover {
    color: var(--color-text);
  }
</style>

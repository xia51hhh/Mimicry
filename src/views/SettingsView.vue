<script setup lang="ts">
  import { ref, inject, onMounted } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useSettingsStore, ACCENT_COLORS } from '../stores/settings';
  import { useBrowserStore } from '../stores/browser';
  import { getVersion } from '@tauri-apps/api/app';
  import {
    Sun,
    Palette,
    Languages,
    Check,
    Globe,
    Download,
    RefreshCw,
    Info,
  } from 'lucide-vue-next';
  import CamoufoxSetup from '../components/CamoufoxSetup.vue';

  const { t } = useI18n();
  const settings = useSettingsStore();
  const browser = useBrowserStore();
  const showCamoufoxSetup = ref(false);
  const appVersion = ref('');
  const updateChecking = ref(false);
  const updateResult = ref<string | null>(null);
  const browserUpdateChecking = ref(false);

  const checkForUpdate = inject<(manual?: boolean) => Promise<boolean>>('checkForUpdate');

  async function handleCheckUpdate() {
    updateChecking.value = true;
    updateResult.value = null;
    try {
      const found = await checkForUpdate?.(true);
      if (!found) updateResult.value = t('update.upToDate');
    } catch {
      updateResult.value = '检查失败';
    } finally {
      updateChecking.value = false;
    }
  }

  async function handleBrowserUpdate() {
    browserUpdateChecking.value = true;
    try {
      const result = await browser.checkCamoufoxUpdate();
      if (result.update_available) {
        // Update is available, trigger update
        await browser.updateCamoufox();
      }
    } finally {
      browserUpdateChecking.value = false;
    }
  }

  onMounted(async () => {
    browser.checkCamoufox();
    appVersion.value = await getVersion();
  });
</script>

<template>
  <div class="settings-view">
    <h1 class="settings-title">{{ t('settings.title') }}</h1>

    <!-- Appearance -->
    <section class="settings-section">
      <h2 class="section-title">{{ t('settings.appearance') }}</h2>

      <!-- Theme -->
      <div class="setting-row">
        <div class="setting-info">
          <Palette :size="16" class="setting-icon" />
          <span class="setting-label">{{ t('settings.theme') }}</span>
        </div>
        <div class="setting-control">
          <div class="theme-grid">
            <button
              v-for="theme in settings.allThemes"
              :key="theme.id"
              class="theme-card"
              :class="{ active: settings.themeId === theme.id }"
              @click="settings.setTheme(theme.id)"
            >
              <div
                class="theme-preview"
                :style="{
                  background: theme.colors.bg,
                  borderColor:
                    settings.themeId === theme.id ? 'var(--color-primary)' : theme.colors.border,
                }"
              >
                <div class="preview-bar" :style="{ background: theme.colors.surface }" />
                <div class="preview-content">
                  <div class="preview-dot" :style="{ background: theme.colors.primary }" />
                  <div class="preview-line" :style="{ background: theme.colors.textMuted }" />
                </div>
              </div>
              <span class="theme-name">{{ theme.name }}</span>
              <Check v-if="settings.themeId === theme.id" :size="12" class="theme-check" />
            </button>
          </div>
        </div>
      </div>

      <!-- Accent Color -->
      <div class="setting-row">
        <div class="setting-info">
          <Sun :size="16" class="setting-icon" />
          <span class="setting-label">{{ t('settings.accentColor') }}</span>
        </div>
        <div class="setting-control">
          <div class="color-palette">
            <button
              v-for="color in ACCENT_COLORS"
              :key="color"
              class="color-swatch"
              :class="{ active: settings.accentColor === color }"
              :style="{ background: color }"
              @click="settings.setAccentColor(color)"
            >
              <Check v-if="settings.accentColor === color" :size="14" color="white" />
            </button>
          </div>
        </div>
      </div>

      <!-- Language -->
      <div class="setting-row">
        <div class="setting-info">
          <Languages :size="16" class="setting-icon" />
          <span class="setting-label">{{ t('settings.language') }}</span>
        </div>
        <div class="setting-control">
          <select
            class="setting-select"
            :value="settings.locale"
            @change="settings.setLocale(($event.target as HTMLSelectElement).value)"
          >
            <option value="zh-CN">中文</option>
            <option value="en">English</option>
          </select>
        </div>
      </div>
    </section>

    <!-- Browser Engine -->
    <section class="settings-section">
      <h2 class="section-title">{{ t('settings.browser') }}</h2>
      <div class="setting-row">
        <div class="setting-info">
          <Globe :size="16" class="setting-icon" />
          <span class="setting-label">Camoufox</span>
        </div>
        <div class="setting-control">
          <div class="camoufox-info">
            <template v-if="browser.camoufoxChecking">
              <span class="camoufox-badge">{{ t('camoufox.checking') }}</span>
            </template>
            <template v-else>
              <span class="camoufox-badge" :class="{ installed: browser.camoufoxInstalled }">
                {{
                  browser.camoufoxInstalled
                    ? t('camoufox.installed')
                    : t('camoufox.notInstalledShort')
                }}
              </span>
            </template>
            <span v-if="browser.camoufoxVersion" class="camoufox-version">
              v{{ browser.camoufoxVersion }}
            </span>
            <button
              v-if="!browser.camoufoxInstalled"
              class="camoufox-install-btn"
              :disabled="browser.camoufoxInstalling"
              @click="showCamoufoxSetup = true"
            >
              <Download :size="12" />
              {{ t('camoufox.install') }}
            </button>
            <button
              v-if="browser.camoufoxInstalled"
              class="camoufox-update-btn"
              :disabled="browser.camoufoxUpdating || browserUpdateChecking"
              @click="handleBrowserUpdate"
            >
              <RefreshCw
                :size="12"
                :class="{ spinning: browserUpdateChecking || browser.camoufoxUpdating }"
              />
              {{ browser.camoufoxUpdating ? t('camoufox.updating') : t('camoufox.checkUpdate') }}
            </button>
            <span v-if="browser.camoufoxUpdateAvailable" class="camoufox-update-badge">
              {{ t('camoufox.updateAvailable', { version: browser.camoufoxLatestVersion }) }}
            </span>
          </div>
        </div>
      </div>
    </section>

    <!-- About -->
    <section class="settings-section">
      <h2 class="section-title">{{ t('settings.about') }}</h2>
      <div class="setting-row">
        <div class="setting-info">
          <Info :size="16" class="setting-icon" />
          <span class="setting-label">{{ t('update.currentVersion') }}</span>
        </div>
        <div class="setting-control">
          <span class="version-text">v{{ appVersion }}</span>
        </div>
      </div>
      <div class="setting-row">
        <div class="setting-info">
          <RefreshCw :size="16" class="setting-icon" />
          <span class="setting-label">{{ t('update.checkUpdate') }}</span>
        </div>
        <div class="setting-control">
          <button
            class="camoufox-install-btn"
            :disabled="updateChecking"
            @click="handleCheckUpdate"
          >
            <RefreshCw :size="12" :class="{ spinning: updateChecking }" />
            {{ updateChecking ? t('update.checking') : t('update.checkUpdate') }}
          </button>
          <span v-if="updateResult" class="update-result">{{ updateResult }}</span>
        </div>
      </div>
    </section>

    <CamoufoxSetup :visible="showCamoufoxSetup" @close="showCamoufoxSetup = false" />
  </div>
</template>

<style scoped>
  .settings-view {
    height: 100%;
    overflow-y: auto;
    padding: 32px 48px;
    max-width: 720px;
  }

  .settings-title {
    font-size: 24px;
    font-weight: 600;
    margin-bottom: 32px;
    color: var(--color-text);
  }

  .settings-section {
    margin-bottom: 32px;
  }

  .section-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--color-border);
  }

  .setting-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    padding: 14px 0;
  }

  .setting-info {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .setting-icon {
    color: var(--color-text-muted);
    flex-shrink: 0;
  }

  .setting-label {
    font-size: 14px;
    color: var(--color-text);
  }

  .setting-control {
    display: flex;
    align-items: center;
  }

  .theme-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
  }

  .theme-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding: 6px;
    border: 1px solid transparent;
    border-radius: 8px;
    background: none;
    cursor: pointer;
    position: relative;
    transition: all 0.15s;
  }

  .theme-card:hover {
    background: var(--color-surface-hover);
  }

  .theme-card.active {
    border-color: var(--color-primary);
  }

  .theme-preview {
    width: 80px;
    height: 52px;
    border-radius: 6px;
    border: 2px solid;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  .preview-bar {
    height: 8px;
  }

  .preview-content {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 4px 6px;
  }

  .preview-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .preview-line {
    height: 3px;
    flex: 1;
    border-radius: 2px;
    opacity: 0.5;
  }

  .theme-name {
    font-size: 11px;
    color: var(--color-text-muted);
  }

  .theme-check {
    position: absolute;
    top: 4px;
    right: 4px;
    color: var(--color-primary);
  }

  .color-palette {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }

  .color-swatch {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    border: 2px solid transparent;
    cursor: pointer;
    transition: all 0.15s;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .color-swatch:hover {
    transform: scale(1.15);
  }

  .color-swatch.active {
    border-color: var(--color-text);
  }

  .setting-select {
    padding: 6px 12px;
    font-size: 13px;
    background: var(--color-bg);
    color: var(--color-text);
    border: 1px solid var(--color-border);
    border-radius: 6px;
    outline: none;
    cursor: pointer;
  }

  .setting-select:focus {
    border-color: var(--color-primary);
  }

  .camoufox-info {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .camoufox-badge {
    font-size: 12px;
    padding: 2px 8px;
    border-radius: 4px;
    background: rgba(239, 68, 68, 0.15);
    color: #ef4444;
  }

  .camoufox-badge.installed {
    background: rgba(34, 197, 94, 0.15);
    color: #22c55e;
  }

  .camoufox-version {
    font-size: 12px;
    color: var(--color-text-muted);
    font-family: monospace;
  }

  .camoufox-install-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 12px;
    font-size: 12px;
    background: var(--color-primary);
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: opacity 0.15s;
  }

  .camoufox-install-btn:hover {
    opacity: 0.9;
  }

  .camoufox-install-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .camoufox-update-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 12px;
    font-size: 12px;
    background: var(--color-bg-elevated);
    color: var(--color-text);
    border: 1px solid var(--color-border);
    border-radius: 4px;
    cursor: pointer;
    transition: opacity 0.15s;
  }

  .camoufox-update-btn:hover {
    opacity: 0.9;
    border-color: var(--color-primary);
  }

  .camoufox-update-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .camoufox-update-badge {
    font-size: 11px;
    color: var(--color-primary);
    font-weight: 500;
  }

  @keyframes spin {
    from {
      transform: rotate(0deg);
    }
    to {
      transform: rotate(360deg);
    }
  }

  .spinning {
    animation: spin 1s linear infinite;
  }

  .version-text {
    font-size: 13px;
    color: var(--color-text);
    font-family: monospace;
  }

  .update-result {
    font-size: 12px;
    color: var(--color-text-muted);
    margin-left: 8px;
  }

  .spinning {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from {
      transform: rotate(0deg);
    }
    to {
      transform: rotate(360deg);
    }
  }
</style>

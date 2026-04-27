<script setup lang="ts">
import { ref, watch, computed, onMounted, onUnmounted } from "vue";
import { useI18n } from "vue-i18n";
import { invoke } from "@tauri-apps/api/core";
import type { Profile } from "../stores/profiles";
import { DEFAULT_BROWSER_CONFIG, type BrowserConfig } from "../stores/profiles";

const { t } = useI18n();

const isDark = ref(document.documentElement.getAttribute('data-theme') === 'dark');
let themeObserver: MutationObserver | null = null;

onMounted(() => {
  themeObserver = new MutationObserver(() => {
    isDark.value = document.documentElement.getAttribute('data-theme') === 'dark';
  });
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
});

onUnmounted(() => {
  themeObserver?.disconnect();
});

interface MonitorInfo {
  name: string;
  physical_width: number;
  physical_height: number;
  scale: number;
  logical_width: number;
  logical_height: number;
}

const detectedMonitors = ref<MonitorInfo[]>([]);
const detectingScreens = ref(false);

async function detectScreens() {
  detectingScreens.value = true;
  try {
    const monitors = await invoke<MonitorInfo[]>("browser_detect_screens");
    detectedMonitors.value = monitors;
  } catch (e) {
    console.error("Screen detection failed:", e);
  } finally {
    detectingScreens.value = false;
  }
}

const windowScale = ref(100);
const baseWidth = ref(0);
const baseHeight = ref(0);

function applyMonitor(m: MonitorInfo) {
  baseWidth.value = m.logical_width;
  baseHeight.value = m.logical_height;
  windowScale.value = 100;
  bc.value.window_width = m.logical_width;
  bc.value.window_height = m.logical_height;
  detectedMonitors.value = [];
}

watch(windowScale, (pct) => {
  if (baseWidth.value && baseHeight.value) {
    bc.value.window_width = Math.max(Math.round(baseWidth.value * pct / 100), 800);
    bc.value.window_height = Math.max(Math.round(baseHeight.value * pct / 100), 600);
  }
});

const props = defineProps<{
  open: boolean;
  profile?: Profile | null;
}>();

type ProfileForm = {
  id: string;
  name: string;
  os_target: string;
  fingerprint: Record<string, unknown>;
  user_data_dir: string;
  proxy: Profile["proxy"];
  browser_config: BrowserConfig;
};

const emit = defineEmits<{
  close: [];
  save: [profile: ProfileForm];
}>();

const form = ref<ProfileForm>({
  id: "",
  name: "",
  os_target: "windows",
  fingerprint: {},
  user_data_dir: "",
  proxy: null,
  browser_config: { ...DEFAULT_BROWSER_CONFIG },
});

const useProxy = ref(false);
const nameError = ref("");
const showAdvanced = ref(false);

watch(
  () => props.profile,
  (p) => {
    nameError.value = "";
    showAdvanced.value = false;
    if (p) {
      form.value = {
        id: p.id,
        name: p.name,
        os_target: p.os_target,
        fingerprint: p.fingerprint,
        user_data_dir: p.user_data_dir,
        proxy: p.proxy ? { ...p.proxy } : null,
        browser_config: { ...DEFAULT_BROWSER_CONFIG, ...(p.browser_config || {}) },
      };
      useProxy.value = !!p.proxy;
    } else {
      form.value = {
        id: `profile_${Date.now()}`,
        name: "",
        os_target: "windows",
        fingerprint: {},
        user_data_dir: "",
        proxy: null,
        browser_config: { ...DEFAULT_BROWSER_CONFIG },
      };
      useProxy.value = false;
    }
  },
  { immediate: true }
);

watch(useProxy, (v) => {
  if (v && !form.value.proxy) {
    form.value.proxy = { server: "", username: undefined, password: undefined };
  } else if (!v) {
    form.value.proxy = null;
  }
});

const bc = computed(() => form.value.browser_config);

const humanizeEnabled = computed({
  get: () => !!bc.value.humanize,
  set: (v: boolean) => {
    bc.value.humanize = v ? 1.0 : false;
  },
});

const humanizeValue = computed({
  get: () => (typeof bc.value.humanize === "number" ? bc.value.humanize : 1.0),
  set: (v: number) => {
    bc.value.humanize = v;
  },
});

const isValid = computed(() => form.value.name.trim().length > 0);

function onSave() {
  if (!form.value.name.trim()) {
    nameError.value = t("profile.nameRequired");
    return;
  }
  nameError.value = "";
  emit("save", { ...form.value, name: form.value.name.trim() });
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="dialog-overlay" @click="emit('close')">
      <div class="dialog-box" :style="{ colorScheme: isDark ? 'dark' : 'light' }" @click.stop>
        <h3 class="dialog-title">{{ profile ? t('profile.edit') : t('profile.create') }}</h3>

        <div class="form-fields">
          <!-- Name -->
          <div class="form-group">
            <label class="form-label">{{ t('profile.name') }} *</label>
            <input
              v-model="form.name"
              class="form-input"
              :class="{ error: nameError }"
              :placeholder="t('profile.namePlaceholder')"
              @input="nameError = ''"
            />
            <span v-if="nameError" class="form-error">{{ nameError }}</span>
          </div>

          <!-- OS Target -->
          <div class="form-group">
            <label class="form-label">{{ t('profile.osTarget') }}</label>
            <select v-model="form.os_target" class="form-input">
              <option value="windows">Windows</option>
              <option value="macos">macOS</option>
              <option value="linux">Linux</option>
            </select>
          </div>

          <!-- ── 基础 ── -->
          <div class="section-title">{{ t('profile.sectionBasic') }}</div>

          <div class="form-group form-row">
            <div class="form-col">
              <label class="form-label">{{ t('profile.windowWidth') }}</label>
              <input
                v-model.number="bc.window_width"
                type="number"
                class="form-input"
                :placeholder="t('profile.auto')"
                min="800"
              />
            </div>
            <div class="form-col">
              <label class="form-label">{{ t('profile.windowHeight') }}</label>
              <input
                v-model.number="bc.window_height"
                type="number"
                class="form-input"
                :placeholder="t('profile.auto')"
                min="600"
              />
            </div>
            <div class="form-col form-col-btn">
              <button class="btn btn-detect" :disabled="detectingScreens" @click="detectScreens">
                {{ detectingScreens ? '...' : t('profile.detectScreen') }}
              </button>
            </div>
          </div>

          <!-- Monitor selection -->
          <div v-if="detectedMonitors.length" class="monitor-list">
            <button
              v-for="(m, i) in detectedMonitors"
              :key="i"
              class="monitor-item"
              @click="applyMonitor(m)"
            >
              <span class="monitor-name">{{ m.name }}</span>
              <span class="monitor-res">{{ m.logical_width }}×{{ m.logical_height }}</span>
              <span v-if="m.scale > 1" class="monitor-scale">@{{ m.scale }}x</span>
            </button>
          </div>

          <!-- Window scale slider (visible after detecting a monitor) -->
          <div v-if="baseWidth > 0" class="form-group form-row" style="align-items: center;">
            <label class="form-label" style="min-width: 50px;">{{ t('profile.windowScale') }}</label>
            <input
              v-model.number="windowScale"
              type="range"
              class="slider"
              min="50"
              max="200"
              step="5"
              style="flex: 1;"
            />
            <span style="min-width: 40px; text-align: right;">{{ windowScale }}%</span>
          </div>

          <div class="form-group">
            <label class="form-label">{{ t('profile.startupUrl') }}</label>
            <input
              v-model="bc.startup_url"
              class="form-input"
              placeholder="https://..."
            />
          </div>

          <div class="form-group">
            <label class="form-label form-label-row">
              <span>{{ t('profile.headless') }}</span>
              <button class="toggle-btn" :class="{ active: bc.headless }" @click="bc.headless = !bc.headless">
                <span class="toggle-dot" />
              </button>
            </label>
          </div>

          <!-- ── 网络 ── -->
          <div class="section-title">{{ t('profile.sectionNetwork') }}</div>

          <div class="form-group">
            <label class="form-label form-label-row">
              <span>GeoIP</span>
              <button class="toggle-btn" :class="{ active: bc.geoip }" @click="bc.geoip = !bc.geoip">
                <span class="toggle-dot" />
              </button>
            </label>
          </div>

          <!-- Proxy -->
          <div class="form-group">
            <label class="form-label form-label-row">
              <span>{{ t('profile.proxy') }}</span>
              <button
                class="toggle-btn"
                :class="{ active: useProxy }"
                @click="useProxy = !useProxy"
              >
                <span class="toggle-dot" />
              </button>
            </label>
            <div v-if="useProxy && form.proxy" class="proxy-fields">
              <input
                v-model="form.proxy.server"
                class="form-input"
                :placeholder="t('profile.proxyServer')"
              />
              <div class="proxy-row">
                <input
                  v-model="form.proxy.username"
                  class="form-input"
                  :placeholder="t('profile.proxyUser')"
                />
                <input
                  v-model="form.proxy.password"
                  type="password"
                  class="form-input"
                  :placeholder="t('profile.proxyPass')"
                />
              </div>
            </div>
          </div>

          <!-- ── 反检测 ── -->
          <div class="section-title">{{ t('profile.sectionAntiDetect') }}</div>

          <div class="form-group">
            <label class="form-label form-label-row">
              <span>{{ t('profile.blockWebrtc') }}</span>
              <button class="toggle-btn" :class="{ active: bc.block_webrtc }" @click="bc.block_webrtc = !bc.block_webrtc">
                <span class="toggle-dot" />
              </button>
            </label>
          </div>

          <div class="form-group">
            <label class="form-label form-label-row">
              <span>{{ t('profile.blockWebgl') }}</span>
              <button class="toggle-btn" :class="{ active: bc.block_webgl }" @click="bc.block_webgl = !bc.block_webgl">
                <span class="toggle-dot" />
              </button>
            </label>
          </div>

          <div class="form-group">
            <label class="form-label form-label-row">
              <span>{{ t('profile.humanize') }}</span>
              <button class="toggle-btn" :class="{ active: humanizeEnabled }" @click="humanizeEnabled = !humanizeEnabled">
                <span class="toggle-dot" />
              </button>
            </label>
            <div v-if="humanizeEnabled" class="slider-row">
              <input type="range" v-model.number="humanizeValue" min="0.5" max="5" step="0.5" class="slider" />
              <span class="slider-value">{{ humanizeValue.toFixed(1) }}</span>
            </div>
          </div>

          <!-- ── 性能 ── -->
          <div class="section-title">{{ t('profile.sectionPerf') }}</div>

          <div class="form-group">
            <label class="form-label form-label-row">
              <span>{{ t('profile.blockImages') }}</span>
              <button class="toggle-btn" :class="{ active: bc.block_images }" @click="bc.block_images = !bc.block_images">
                <span class="toggle-dot" />
              </button>
            </label>
          </div>

          <div class="form-group">
            <label class="form-label form-label-row">
              <span>{{ t('profile.enableCache') }}</span>
              <button class="toggle-btn" :class="{ active: bc.enable_cache }" @click="bc.enable_cache = !bc.enable_cache">
                <span class="toggle-dot" />
              </button>
            </label>
          </div>

          <!-- ── 高级 ── -->
          <button class="advanced-toggle" @click="showAdvanced = !showAdvanced">
            <span class="advanced-arrow" :class="{ expanded: showAdvanced }">▶</span>
            {{ t('profile.sectionAdvanced') }}
          </button>

          <template v-if="showAdvanced">
            <div class="form-group">
              <label class="form-label form-label-row">
                <span>{{ t('profile.disableCoop') }}</span>
                <button class="toggle-btn" :class="{ active: bc.disable_coop }" @click="bc.disable_coop = !bc.disable_coop">
                  <span class="toggle-dot" />
                </button>
              </label>
            </div>

            <div class="form-group">
              <label class="form-label">{{ t('profile.locale') }}</label>
              <input v-model="bc.locale" class="form-input" placeholder="en-US, zh-CN" />
            </div>

            <div class="form-group">
              <label class="form-label">{{ t('profile.executablePath') }}</label>
              <input v-model="bc.executable_path" class="form-input" :placeholder="t('profile.auto')" />
            </div>

            <div class="form-group">
              <label class="form-label">{{ t('profile.virtualDisplay') }}</label>
              <input v-model="bc.virtual_display" class="form-input" placeholder=":99" />
            </div>

            <div class="form-group">
              <label class="form-label">{{ t('profile.launchArgs') }}</label>
              <input
                :value="(bc.args || []).join(' ')"
                class="form-input"
                placeholder="--flag1 --flag2"
                @change="bc.args = ($event.target as HTMLInputElement).value.split(/\s+/).filter(Boolean)"
              />
            </div>
          </template>

          <!-- Data Dir (read-only, auto-assigned) -->
          <div v-if="profile && form.user_data_dir" class="form-group">
            <label class="form-label">{{ t('profile.dataDir') }}</label>
            <input
              :value="form.user_data_dir"
              class="form-input readonly"
              readonly
            />
          </div>
        </div>

        <div class="dialog-footer">
          <button class="btn btn-secondary" @click="emit('close')">{{ t('profile.cancel') }}</button>
          <button class="btn btn-primary" :disabled="!isValid" @click="onSave">{{ t('profile.save') }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.5);
}

.dialog-box {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 24px;
  width: 480px;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

.dialog-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: 20px;
}

.form-fields {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-label {
  font-size: 12px;
  color: var(--color-text-muted);
}

.form-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.form-input {
  padding: 7px 10px;
  font-size: 13px;
  background: var(--color-bg);
  color: var(--color-text);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  outline: none;
  transition: border-color 0.15s;
}

/* Select dropdown */
select.form-input {
  appearance: none;
  -webkit-appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23888' d='M2 4l4 4 4-4'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 8px center;
  padding-right: 28px;
  cursor: pointer;
}

select.form-input option {
  background: var(--color-surface);
  color: var(--color-text);
}

/* Number input spinner */
input[type="number"].form-input {
  -moz-appearance: textfield;
}

input[type="number"].form-input::-webkit-inner-spin-button,
input[type="number"].form-input::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.form-input:focus {
  border-color: var(--color-primary);
}

.form-input.error {
  border-color: var(--color-error);
}

.form-input.readonly {
  opacity: 0.6;
  cursor: default;
  font-family: monospace;
  font-size: 11px;
}

.form-error {
  font-size: 11px;
  color: var(--color-error);
}

/* Toggle */
.toggle-btn {
  position: relative;
  width: 32px;
  height: 18px;
  border-radius: 9px;
  border: none;
  background: var(--color-border);
  cursor: pointer;
  transition: background 0.2s;
  padding: 0;
}

.toggle-btn.active {
  background: var(--color-primary);
}

.toggle-dot {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: white;
  transition: transform 0.2s;
}

.toggle-btn.active .toggle-dot {
  transform: translateX(14px);
}

.proxy-fields {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 4px;
}

.proxy-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
}

.btn {
  padding: 7px 16px;
  font-size: 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: opacity 0.15s;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: var(--color-surface-hover);
  color: var(--color-text);
  border: 1px solid var(--color-border);
}

.btn-primary {
  background: var(--color-primary);
  color: white;
}

.btn:hover:not(:disabled) {
  opacity: 0.9;
}

/* Section titles */
.section-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-top: 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--color-border);
}

/* Form row (side by side) */
.form-row {
  flex-direction: row !important;
  gap: 8px !important;
}

.form-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

/* Slider */
.slider-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}

.slider {
  flex: 1;
  height: 4px;
  -webkit-appearance: none;
  appearance: none;
  background: var(--color-border);
  border-radius: 2px;
  outline: none;
}

.slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--color-primary);
  cursor: pointer;
}

.slider-value {
  font-size: 11px;
  color: var(--color-text-muted);
  min-width: 28px;
  text-align: right;
}

/* Advanced toggle */
.advanced-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  color: var(--color-text-muted);
  font-size: 12px;
  cursor: pointer;
  padding: 6px 0;
  margin-top: 4px;
}

.advanced-toggle:hover {
  color: var(--color-text);
}

.advanced-arrow {
  font-size: 10px;
  transition: transform 0.2s;
}

.advanced-arrow.expanded {
  transform: rotate(90deg);
}

/* Detect button */
.form-col-btn {
  justify-content: flex-end;
  min-width: 60px;
}

.btn-detect {
  padding: 7px 10px;
  font-size: 11px;
  background: var(--color-surface-hover);
  color: var(--color-text);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  cursor: pointer;
  white-space: nowrap;
}

.btn-detect:hover:not(:disabled) {
  border-color: var(--color-primary);
}

/* Monitor selection */
.monitor-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.monitor-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  color: var(--color-text);
  transition: border-color 0.15s;
}

.monitor-item:hover {
  border-color: var(--color-primary);
}

.monitor-name {
  color: var(--color-text-muted);
}

.monitor-res {
  font-weight: 600;
}

.monitor-scale {
  font-size: 10px;
  color: var(--color-text-muted);
  background: var(--color-surface-hover);
  padding: 1px 4px;
  border-radius: 3px;
}
</style>

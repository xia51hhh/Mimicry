<script setup lang="ts">
import { ref, watch, computed } from "vue";
import { useI18n } from "vue-i18n";
import type { Profile } from "../stores/profiles";

const { t } = useI18n();

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
});

const useProxy = ref(false);
const nameError = ref("");

watch(
  () => props.profile,
  (p) => {
    nameError.value = "";
    if (p) {
      form.value = {
        id: p.id,
        name: p.name,
        os_target: p.os_target,
        fingerprint: p.fingerprint,
        user_data_dir: p.user_data_dir,
        proxy: p.proxy ? { ...p.proxy } : null,
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
      <div class="dialog-box" @click.stop>
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
  width: 440px;
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
</style>

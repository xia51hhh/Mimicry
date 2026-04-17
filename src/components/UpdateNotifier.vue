<script setup lang="ts">
import { ref, onMounted } from "vue";
import { check } from "@tauri-apps/plugin-updater";
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

interface DownloadProgress {
  contentLength?: number;
  chunkLength: number;
}

const updateAvailable = ref(false);
const updateVersion = ref("");
const downloading = ref(false);
const progress = ref(0);
let downloaded = 0;

async function checkForUpdate() {
  try {
    const update = await check();
    if (update) {
      updateAvailable.value = true;
      updateVersion.value = update.version;
    }
  } catch (e) {
    console.debug("Update check skipped:", e);
  }
}

async function installUpdate() {
  downloading.value = true;
  downloaded = 0;
  try {
    const update = await check();
    if (update) {
      await update.downloadAndInstall((event) => {
        if (event.event === "Progress") {
          const data = event.data as DownloadProgress;
          downloaded += data.chunkLength;
          if (data.contentLength) {
            progress.value = Math.round((downloaded / data.contentLength) * 100);
          }
        }
      });
    }
  } catch (e) {
    console.error("Update failed:", e);
  } finally {
    downloading.value = false;
  }
}

onMounted(() => {
  checkForUpdate();
});
</script>

<template>
  <div v-if="updateAvailable" class="fixed bottom-4 right-4 z-50 rounded-lg border border-[var(--color-primary)] bg-[var(--color-surface)] p-4 shadow-xl">
    <p class="text-sm">
      {{ t('update.newVersion') }} <strong>{{ updateVersion }}</strong> {{ t('update.available') }}
    </p>
    <div class="mt-2 flex gap-2">
      <button
        class="rounded bg-[var(--color-primary)] px-3 py-1 text-sm text-white hover:opacity-90 disabled:opacity-50"
        :disabled="downloading"
        @click="installUpdate"
      >
        {{ downloading ? `${t('update.downloading')} ${progress}%` : t('update.install') }}
      </button>
      <button
        class="rounded border border-[var(--color-border)] px-3 py-1 text-sm hover:bg-white/5"
        @click="updateAvailable = false"
      >
        {{ t('update.later') }}
      </button>
    </div>
  </div>
</template>

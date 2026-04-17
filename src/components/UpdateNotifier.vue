<script setup lang="ts">
import { ref, onMounted } from "vue";
import { check } from "@tauri-apps/plugin-updater";

const updateAvailable = ref(false);
const updateVersion = ref("");
const downloading = ref(false);
const progress = ref(0);

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
  try {
    const update = await check();
    if (update) {
      await update.downloadAndInstall((event) => {
        if (event.event === "Progress") {
          const { contentLength, chunkLength } = event.data as any;
          if (contentLength) {
            progress.value = Math.round((chunkLength / contentLength) * 100);
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
      新版本 <strong>{{ updateVersion }}</strong> 可用
    </p>
    <div class="mt-2 flex gap-2">
      <button
        class="rounded bg-[var(--color-primary)] px-3 py-1 text-sm text-white hover:opacity-90 disabled:opacity-50"
        :disabled="downloading"
        @click="installUpdate"
      >
        {{ downloading ? `下载中 ${progress}%` : '立即更新' }}
      </button>
      <button
        class="rounded border border-[var(--color-border)] px-3 py-1 text-sm hover:bg-white/5"
        @click="updateAvailable = false"
      >
        稍后
      </button>
    </div>
  </div>
</template>

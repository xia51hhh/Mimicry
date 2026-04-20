<script setup lang="ts">
import { ref, watch } from "vue";
import type { Profile } from "../stores/profiles";

const props = defineProps<{
  open: boolean;
  profile?: Profile | null;
}>();

const emit = defineEmits<{
  close: [];
  save: [profile: Omit<Profile, "created_at" | "updated_at">];
}>();

const form = ref({
  id: "",
  name: "",
  os_target: "windows",
  fingerprint: {} as Record<string, unknown>,
  user_data_dir: "",
  proxy: null as Profile["proxy"],
});

watch(
  () => props.profile,
  (p) => {
    if (p) {
      form.value = { ...p };
    } else {
      form.value = {
        id: `profile_${Date.now()}`,
        name: "",
        os_target: "windows",
        fingerprint: {},
        user_data_dir: "",
        proxy: null,
      };
    }
  },
  { immediate: true }
);

function onSave() {
  emit("save", { ...form.value });
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div class="bg-[var(--bg-secondary)] rounded-lg p-6 w-[480px] shadow-xl">
        <h3 class="text-lg font-medium mb-4">{{ profile ? 'Edit Profile' : 'New Profile' }}</h3>

        <div class="space-y-3">
          <div>
            <label class="block text-xs mb-1 opacity-70">Name</label>
            <input v-model="form.name" class="w-full px-3 py-1.5 rounded bg-[var(--bg-primary)] border border-[var(--border-primary)]" />
          </div>
          <div>
            <label class="block text-xs mb-1 opacity-70">OS Target</label>
            <select v-model="form.os_target" class="w-full px-3 py-1.5 rounded bg-[var(--bg-primary)] border border-[var(--border-primary)]">
              <option value="windows">Windows</option>
              <option value="macos">macOS</option>
              <option value="linux">Linux</option>
            </select>
          </div>
        </div>

        <div class="flex justify-end gap-2 mt-6">
          <button @click="emit('close')" class="px-4 py-1.5 rounded border border-[var(--border-primary)]">Cancel</button>
          <button @click="onSave" class="px-4 py-1.5 rounded bg-[var(--accent-primary)] text-white">Save</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

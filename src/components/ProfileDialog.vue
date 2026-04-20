<script setup lang="ts">
import { ref, watch } from "vue";
import type { Profile } from "../stores/profiles";

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

watch(
  () => props.profile,
  (p) => {
    if (p) {
      form.value = {
        id: p.id,
        name: p.name,
        os_target: p.os_target,
        fingerprint: p.fingerprint,
        user_data_dir: p.user_data_dir,
        proxy: p.proxy ?? null,
      };
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

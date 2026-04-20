<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useProfileStore, type Profile } from "../stores/profiles";
import ProfileDialog from "./ProfileDialog.vue";

const store = useProfileStore();
const showDialog = ref(false);
const editingProfile = ref<Profile | null>(null);

onMounted(() => store.fetchAll());

function onCreate() {
  editingProfile.value = null;
  showDialog.value = true;
}

function onEdit(profile: Profile) {
  editingProfile.value = profile;
  showDialog.value = true;
}

async function onSave(data: Omit<Profile, "created_at" | "updated_at">) {
  if (editingProfile.value) {
    await store.update({ ...editingProfile.value, ...data });
  } else {
    await store.create(data);
  }
  showDialog.value = false;
}

async function onDelete(id: string) {
  await store.remove(id);
}
</script>

<template>
  <div class="p-4">
    <div class="flex items-center justify-between mb-3">
      <h3 class="font-medium">Profiles</h3>
      <button @click="onCreate" class="px-3 py-1 text-sm rounded bg-[var(--accent-primary)] text-white">+ New</button>
    </div>

    <div v-if="store.loading" class="text-center py-4 opacity-50">Loading...</div>

    <div v-else class="space-y-2">
      <div
        v-for="p in store.profiles"
        :key="p.id"
        class="flex items-center justify-between p-3 rounded border border-[var(--border-primary)] hover:bg-[var(--bg-hover)] cursor-pointer"
        :class="{ 'border-[var(--accent-primary)]': store.selectedId === p.id }"
        @click="store.selectedId = p.id"
      >
        <div>
          <div class="font-medium text-sm">{{ p.name }}</div>
          <div class="text-xs opacity-50">{{ p.os_target }} · {{ p.id.slice(0, 12) }}</div>
        </div>
        <div class="flex gap-1">
          <button @click.stop="onEdit(p)" class="px-2 py-1 text-xs rounded hover:bg-[var(--bg-hover)]">Edit</button>
          <button @click.stop="onDelete(p.id)" class="px-2 py-1 text-xs rounded text-red-400 hover:bg-red-500/10">Delete</button>
        </div>
      </div>
    </div>

    <ProfileDialog :open="showDialog" :profile="editingProfile" @close="showDialog = false" @save="onSave" />
  </div>
</template>

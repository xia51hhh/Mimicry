<script setup lang="ts">
  import { onMounted, ref, computed } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useProfileStore, type Profile } from '../stores/profiles';
  import { useBrowserStore } from '../stores/browser';
  import ProfileDialog from './ProfileDialog.vue';
  import {
    Plus,
    Pencil,
    Trash2,
    Monitor,
    Apple,
    Terminal,
    Play,
    X as XIcon,
  } from 'lucide-vue-next';

  const { t } = useI18n();
  const store = useProfileStore();
  const browser = useBrowserStore();
  const showDialog = ref(false);
  const editingProfile = ref<Profile | null>(null);
  const deleteConfirmId = ref<string | null>(null);

  onMounted(() => store.fetchAll());

  const sessionList = computed(() => Array.from(browser.sessions.values()));

  function getSessionLabel(s: { profileId?: string; sessionId: string }) {
    const profile = store.profiles.find((p) => p.id === s.profileId);
    const name = profile?.name || s.profileId || 'default';
    return `${name} (${s.sessionId})`;
  }

  function onCreate() {
    editingProfile.value = null;
    showDialog.value = true;
  }

  function onEdit(profile: Profile) {
    editingProfile.value = profile;
    showDialog.value = true;
  }

  async function onSave(data: Omit<Profile, 'created_at' | 'updated_at'>) {
    if (editingProfile.value) {
      await store.update({ ...editingProfile.value, ...data });
    } else {
      await store.create(data);
    }
    showDialog.value = false;
  }

  function confirmDelete(id: string) {
    deleteConfirmId.value = id;
  }

  async function onDelete() {
    if (deleteConfirmId.value) {
      await store.remove(deleteConfirmId.value);
      deleteConfirmId.value = null;
    }
  }

  function getOsIcon(os: string) {
    if (os === 'macos') return Apple;
    if (os === 'linux') return Terminal;
    return Monitor;
  }
</script>

<template>
  <div class="profile-manager">
    <div class="manager-header">
      <span class="header-label">{{ t('profile.title') }}</span>
      <button class="btn-icon-sm" :title="t('profile.create')" @click="onCreate">
        <Plus :size="14" />
      </button>
    </div>

    <!-- Active sessions -->
    <div v-if="sessionList.length > 0" class="session-section">
      <div class="session-header">
        <span class="header-label">{{ t('session.title') }}</span>
      </div>
      <div class="session-list">
        <div
          v-for="s in sessionList"
          :key="s.sessionId"
          class="session-item"
          :class="{ active: s.sessionId === browser.activeSessionId }"
          @click="browser.setActiveSession(s.sessionId)"
        >
          <span class="session-dot" />
          <span class="session-name">{{ getSessionLabel(s) }}</span>
          <button
            class="btn-icon-xs btn-danger"
            :title="t('session.close')"
            @click.stop="browser.close(s.sessionId)"
          >
            <XIcon :size="12" />
          </button>
        </div>
      </div>
    </div>

    <div v-if="store.loading" class="loading-state">
      {{ t('profile.loading') }}
    </div>

    <div v-else-if="store.profiles.length === 0" class="empty-state">
      {{ t('profile.empty') }}
    </div>

    <div v-else class="profile-list">
      <div
        v-for="p in store.profiles"
        :key="p.id"
        class="profile-card"
        :class="{ selected: store.selectedId === p.id }"
        @click="store.selectedId = p.id"
      >
        <div class="profile-info">
          <component :is="getOsIcon(p.os_target)" :size="14" class="os-icon" />
          <div class="profile-text">
            <span class="profile-name">{{ p.name }}</span>
            <span class="profile-meta">{{ p.os_target }}</span>
          </div>
        </div>
        <div class="profile-actions">
          <button
            class="btn-icon-xs btn-launch"
            :title="t('profile.launch')"
            :disabled="browser.launching"
            @click.stop="browser.launch(p.id)"
          >
            <Play :size="12" />
          </button>
          <button class="btn-icon-xs" :title="t('profile.edit')" @click.stop="onEdit(p)">
            <Pencil :size="12" />
          </button>
          <button
            class="btn-icon-xs btn-danger"
            :title="t('profile.delete')"
            @click.stop="confirmDelete(p.id)"
          >
            <Trash2 :size="12" />
          </button>
        </div>
      </div>
    </div>

    <!-- Delete confirmation -->
    <Teleport to="body">
      <div v-if="deleteConfirmId" class="modal-overlay" @click="deleteConfirmId = null">
        <div class="modal-box" @click.stop>
          <p class="modal-text">{{ t('profile.deleteConfirm') }}</p>
          <div class="modal-actions">
            <button class="btn btn-secondary" @click="deleteConfirmId = null">
              {{ t('profile.cancel') }}
            </button>
            <button class="btn btn-danger" @click="onDelete">{{ t('profile.delete') }}</button>
          </div>
        </div>
      </div>
    </Teleport>

    <ProfileDialog
      :open="showDialog"
      :profile="editingProfile"
      @close="showDialog = false"
      @save="onSave"
    />
  </div>
</template>

<style scoped>
  .profile-manager {
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  .manager-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 14px;
    border-bottom: 1px solid var(--color-border);
  }

  .header-label {
    font-size: 11px;
    font-weight: 600;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .btn-icon-sm {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border: none;
    background: none;
    border-radius: 4px;
    cursor: pointer;
    color: var(--color-text-muted);
    transition: all 0.15s;
  }

  .btn-icon-sm:hover {
    background: var(--color-surface-hover);
    color: var(--color-text);
  }

  .loading-state,
  .empty-state {
    padding: 24px 14px;
    text-align: center;
    font-size: 12px;
    color: var(--color-text-muted);
  }

  .profile-list {
    flex: 1;
    overflow-y: auto;
    padding: 6px;
  }

  .profile-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 10px;
    border-radius: 6px;
    border: 1px solid transparent;
    cursor: pointer;
    transition: all 0.15s;
  }

  .profile-card:hover {
    background: var(--color-surface-hover);
  }

  .profile-card.selected {
    border-color: var(--color-primary);
    background: var(--color-surface-hover);
  }

  .profile-info {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }

  .os-icon {
    color: var(--color-text-muted);
    flex-shrink: 0;
  }

  .profile-text {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .profile-name {
    font-size: 13px;
    color: var(--color-text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .profile-meta {
    font-size: 11px;
    color: var(--color-text-muted);
  }

  .profile-actions {
    display: flex;
    gap: 2px;
    opacity: 0;
    transition: opacity 0.15s;
  }

  .profile-card:hover .profile-actions {
    opacity: 1;
  }

  .btn-icon-xs {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    border: none;
    background: none;
    border-radius: 4px;
    cursor: pointer;
    color: var(--color-text-muted);
    transition: all 0.15s;
  }

  .btn-icon-xs:hover {
    background: var(--color-surface-hover);
    color: var(--color-text);
  }

  .btn-icon-xs.btn-danger:hover {
    color: var(--color-error);
  }

  /* Modal */
  .modal-overlay {
    position: fixed;
    inset: 0;
    z-index: 100;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0, 0, 0, 0.5);
  }

  .modal-box {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    padding: 20px;
    width: 320px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  }

  .modal-text {
    font-size: 14px;
    color: var(--color-text);
    margin-bottom: 16px;
  }

  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }

  .btn {
    padding: 6px 14px;
    font-size: 12px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: opacity 0.15s;
  }

  .btn-secondary {
    background: var(--color-surface-hover);
    color: var(--color-text);
    border: 1px solid var(--color-border);
  }

  .btn-danger {
    background: var(--color-error);
    color: white;
  }

  .btn:hover {
    opacity: 0.9;
  }

  /* Launch */
  .default-launch {
    padding: 8px 14px;
    border-bottom: 1px solid var(--color-border);
  }

  .btn-default-launch {
    display: flex;
    align-items: center;
    gap: 6px;
    width: 100%;
    padding: 6px 10px;
    font-size: 12px;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    background: transparent;
    color: var(--color-text-muted);
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-default-launch:hover:not(:disabled) {
    background: var(--color-surface-hover);
    color: var(--color-text);
  }

  .btn-default-launch:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .btn-icon-xs.btn-launch {
    color: var(--color-primary);
  }

  .btn-icon-xs.btn-launch:hover {
    background: color-mix(in srgb, var(--color-primary) 15%, transparent);
  }

  /* Active sessions */
  .session-section {
    border-bottom: 1px solid var(--color-border);
  }

  .session-header {
    padding: 8px 14px 4px;
  }

  .session-list {
    padding: 0 6px 6px;
  }

  .session-item {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 8px;
    border-radius: 4px;
    cursor: pointer;
    transition: background 0.15s;
  }

  .session-item:hover {
    background: var(--color-surface-hover);
  }

  .session-item.active {
    background: color-mix(in srgb, var(--color-primary) 10%, transparent);
  }

  .session-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--color-success, #4caf50);
    flex-shrink: 0;
  }

  .session-name {
    flex: 1;
    font-size: 12px;
    color: var(--color-text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
</style>

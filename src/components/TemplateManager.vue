<script setup lang="ts">
  import { onMounted, ref, computed } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useTemplateStore, type Template } from '../stores/templates';
  import { useWorkflowStore } from '../stores/workflow';
  import { Plus, Trash2, Download, Upload, FileText, Search } from 'lucide-vue-next';

  const { t } = useI18n();
  const store = useTemplateStore();
  const workflow = useWorkflowStore();

  const searchQuery = ref('');
  const showSaveDialog = ref(false);
  const saveName = ref('');
  const saveDescription = ref('');
  const saveCategory = ref('custom');
  const deleteConfirmId = ref<string | null>(null);

  onMounted(() => store.loadTemplates());

  const categories = ['custom', 'scraping', 'testing', 'automation', 'monitoring'];

  const filteredTemplates = computed(() => {
    if (!searchQuery.value) return store.templates;
    const q = searchQuery.value.toLowerCase();
    return store.templates.filter(
      (t) =>
        t.name.toLowerCase().includes(q) ||
        t.description.toLowerCase().includes(q) ||
        t.category.toLowerCase().includes(q),
    );
  });

  function openSaveDialog() {
    saveName.value = '';
    saveDescription.value = '';
    saveCategory.value = 'custom';
    showSaveDialog.value = true;
  }

  async function saveCurrentAsTemplate() {
    if (!saveName.value.trim()) return;
    await store.saveFromWorkflow(
      saveName.value.trim(),
      saveDescription.value.trim(),
      saveCategory.value,
      workflow.nodes,
      workflow.edges,
    );
    showSaveDialog.value = false;
  }

  function loadTemplate(template: Template) {
    workflow.nodes = JSON.parse(JSON.stringify(template.nodes));
    workflow.edges = JSON.parse(JSON.stringify(template.edges));
  }

  async function confirmDelete(id: string) {
    deleteConfirmId.value = id;
  }

  async function doDelete() {
    if (deleteConfirmId.value) {
      await store.deleteTemplate(deleteConfirmId.value);
      deleteConfirmId.value = null;
    }
  }

  async function exportTemplate(template: Template) {
    const data = JSON.stringify(
      {
        name: template.name,
        description: template.description,
        category: template.category,
        nodes: template.nodes,
        edges: template.edges,
        tags: template.tags,
        exportedAt: new Date().toISOString(),
        version: '1.0',
      },
      null,
      2,
    );
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${template.name}.mimicry-template.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function importTemplate() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) return;
      const text = await file.text();
      try {
        const data = JSON.parse(text);
        if (!data.name || !data.nodes) {
          throw new Error('Invalid template format');
        }
        await store.createTemplate(
          data.name,
          data.description || '',
          data.category || 'custom',
          data.nodes,
          data.edges || [],
          data.tags || [],
        );
      } catch {
        // Invalid file — silently ignore
      }
    };
    input.click();
  }
</script>

<template>
  <div class="template-manager">
    <div class="sidebar-header">
      <span class="text-sm font-semibold">{{ t('templates.title') }}</span>
      <div class="header-actions">
        <button class="icon-btn" :title="t('templates.import')" @click="importTemplate">
          <Upload :size="14" />
        </button>
        <button class="icon-btn" :title="t('templates.saveAsCurrent')" @click="openSaveDialog">
          <Plus :size="14" />
        </button>
      </div>
    </div>

    <div class="sidebar-search">
      <Search :size="12" class="search-icon" />
      <input
        v-model="searchQuery"
        type="text"
        class="search-input"
        :placeholder="t('templates.search')"
      />
    </div>

    <div class="template-list">
      <div v-if="store.loading" class="empty-state">{{ t('common.loading') }}</div>
      <div v-else-if="filteredTemplates.length === 0" class="empty-state">
        {{ t('templates.empty') }}
      </div>
      <div
        v-for="tmpl in filteredTemplates"
        v-else
        :key="tmpl.id"
        class="template-item"
        @click="loadTemplate(tmpl)"
      >
        <div class="template-info">
          <FileText :size="14" class="template-icon" />
          <div class="template-details">
            <span class="template-name">{{ tmpl.name }}</span>
            <span class="template-category">{{ tmpl.category }}</span>
          </div>
        </div>
        <div class="template-actions" @click.stop>
          <button class="icon-btn" :title="t('templates.export')" @click="exportTemplate(tmpl)">
            <Download :size="12" />
          </button>
          <button class="icon-btn danger" :title="t('common.delete')" @click="confirmDelete(tmpl.id)">
            <Trash2 :size="12" />
          </button>
        </div>
      </div>
    </div>

    <!-- Save Dialog -->
    <Teleport to="body">
      <div v-if="showSaveDialog" class="dialog-overlay" @click.self="showSaveDialog = false">
        <div class="dialog">
          <h3>{{ t('templates.saveAsCurrent') }}</h3>
          <div class="dialog-field">
            <label>{{ t('templates.name') }}</label>
            <input v-model="saveName" type="text" class="dialog-input" />
          </div>
          <div class="dialog-field">
            <label>{{ t('templates.description') }}</label>
            <input v-model="saveDescription" type="text" class="dialog-input" />
          </div>
          <div class="dialog-field">
            <label>{{ t('templates.category') }}</label>
            <select v-model="saveCategory" class="dialog-input">
              <option v-for="cat in categories" :key="cat" :value="cat">{{ cat }}</option>
            </select>
          </div>
          <div class="dialog-actions">
            <button class="btn-secondary" @click="showSaveDialog = false">
              {{ t('common.cancel') }}
            </button>
            <button class="btn-primary" :disabled="!saveName.trim()" @click="saveCurrentAsTemplate">
              {{ t('common.save') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Delete Confirm -->
    <Teleport to="body">
      <div v-if="deleteConfirmId" class="dialog-overlay" @click.self="deleteConfirmId = null">
        <div class="dialog">
          <h3>{{ t('templates.confirmDelete') }}</h3>
          <div class="dialog-actions">
            <button class="btn-secondary" @click="deleteConfirmId = null">
              {{ t('common.cancel') }}
            </button>
            <button class="btn-danger" @click="doDelete">
              {{ t('common.delete') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
  .template-manager {
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  .sidebar-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px;
    border-bottom: 1px solid var(--color-border);
  }

  .header-actions {
    display: flex;
    gap: 4px;
  }

  .sidebar-search {
    padding: 8px 12px;
    position: relative;
  }

  .search-icon {
    position: absolute;
    left: 20px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--color-text-muted);
  }

  .search-input {
    width: 100%;
    padding: 4px 8px 4px 24px;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    background: var(--color-bg);
    color: var(--color-text);
    font-size: 12px;
  }

  .template-list {
    flex: 1;
    overflow-y: auto;
    padding: 4px 0;
  }

  .empty-state {
    padding: 24px 12px;
    text-align: center;
    color: var(--color-text-muted);
    font-size: 12px;
  }

  .template-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    cursor: pointer;
    transition: background 0.15s;
  }

  .template-item:hover {
    background: var(--color-hover);
  }

  .template-info {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }

  .template-icon {
    color: var(--color-text-muted);
    flex-shrink: 0;
  }

  .template-details {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .template-name {
    font-size: 12px;
    color: var(--color-text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .template-category {
    font-size: 10px;
    color: var(--color-text-muted);
  }

  .template-actions {
    display: flex;
    gap: 2px;
    opacity: 0;
    transition: opacity 0.15s;
  }

  .template-item:hover .template-actions {
    opacity: 1;
  }

  .icon-btn {
    padding: 4px;
    border: none;
    background: transparent;
    color: var(--color-text-muted);
    cursor: pointer;
    border-radius: 4px;
  }

  .icon-btn:hover {
    background: var(--color-hover);
    color: var(--color-text);
  }

  .icon-btn.danger:hover {
    color: var(--color-error);
  }

  .dialog-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 1000;
  }

  .dialog {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    padding: 20px;
    min-width: 360px;
    max-width: 460px;
  }

  .dialog h3 {
    margin: 0 0 16px;
    font-size: 14px;
  }

  .dialog-field {
    margin-bottom: 12px;
  }

  .dialog-field label {
    display: block;
    font-size: 12px;
    color: var(--color-text-muted);
    margin-bottom: 4px;
  }

  .dialog-input {
    width: 100%;
    padding: 6px 8px;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    background: var(--color-bg);
    color: var(--color-text);
    font-size: 13px;
  }

  .dialog-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 16px;
  }

  .btn-primary,
  .btn-secondary,
  .btn-danger {
    padding: 6px 14px;
    border-radius: 4px;
    font-size: 12px;
    cursor: pointer;
    border: 1px solid var(--color-border);
  }

  .btn-primary {
    background: var(--color-accent);
    color: white;
    border-color: var(--color-accent);
  }

  .btn-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-secondary {
    background: var(--color-surface);
    color: var(--color-text);
  }

  .btn-danger {
    background: var(--color-error);
    color: white;
    border-color: var(--color-error);
  }
</style>

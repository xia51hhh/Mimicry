<script setup lang="ts">
  import { ref, computed } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { Search, ChevronRight } from 'lucide-vue-next';

  const { t } = useI18n();
  const search = ref('');
  const expandedCategories = ref<Set<string>>(new Set(['interaction', 'navigation', 'data']));

  interface BlockDef {
    type: string;
    action: string;
    icon: string;
    category: string;
  }

  const blocks: BlockDef[] = [
    // Interaction
    { type: 'action', action: 'Click', icon: '🖱', category: 'interaction' },
    { type: 'action', action: 'DblClick', icon: '🖱', category: 'interaction' },
    { type: 'action', action: 'Type', icon: '⌨', category: 'interaction' },
    { type: 'action', action: 'Hover', icon: '👆', category: 'interaction' },
    { type: 'action', action: 'PressKey', icon: '⌨', category: 'interaction' },
    { type: 'action', action: 'Scroll', icon: '📜', category: 'interaction' },
    { type: 'action', action: 'SelectOption', icon: '☑', category: 'interaction' },
    { type: 'action', action: 'Focus', icon: '🎯', category: 'interaction' },
    { type: 'action', action: 'Clear', icon: '🧹', category: 'interaction' },
    { type: 'action', action: 'UploadFile', icon: '📎', category: 'interaction' },
    { type: 'action', action: 'HandleDialog', icon: '💬', category: 'interaction' },
    // Navigation
    { type: 'action', action: 'Navigate', icon: '🔗', category: 'navigation' },
    { type: 'action', action: 'NewTab', icon: '➕', category: 'navigation' },
    { type: 'action', action: 'SwitchTab', icon: '🔀', category: 'navigation' },
    { type: 'action', action: 'CloseTab', icon: '✖', category: 'navigation' },
    { type: 'action', action: 'GoBack', icon: '◀', category: 'navigation' },
    { type: 'action', action: 'GoForward', icon: '▶', category: 'navigation' },
    { type: 'action', action: 'Reload', icon: '🔄', category: 'navigation' },
    { type: 'action', action: 'SwitchFrame', icon: '🖼', category: 'navigation' },
    // Data
    { type: 'action', action: 'GetText', icon: '📄', category: 'data' },
    { type: 'action', action: 'GetAttribute', icon: '🏷', category: 'data' },
    { type: 'action', action: 'GetURL', icon: '🌐', category: 'data' },
    { type: 'action', action: 'ExtractTable', icon: '📊', category: 'data' },
    { type: 'action', action: 'Screenshot', icon: '📸', category: 'data' },
    { type: 'action', action: 'SetVariable', icon: '📝', category: 'data' },
    { type: 'action', action: 'Transform', icon: '🔧', category: 'data' },
    { type: 'action', action: 'Export', icon: '💾', category: 'data' },
    // Wait & Control
    { type: 'action', action: 'Wait', icon: '⏳', category: 'control' },
    { type: 'action', action: 'Delay', icon: '⏱', category: 'control' },
    { type: 'action', action: 'WaitForPage', icon: '📄', category: 'control' },
    { type: 'action', action: 'Log', icon: '📋', category: 'control' },
    { type: 'action', action: 'Comment', icon: '💬', category: 'control' },
    { type: 'action', action: 'RunScript', icon: '⚡', category: 'control' },
    { type: 'action', action: 'HttpRequest', icon: '🌐', category: 'control' },
    { type: 'action', action: 'Stop', icon: '🛑', category: 'control' },
    { type: 'action', action: 'Fail', icon: '❌', category: 'control' },
    // Flow
    { type: 'condition', action: '', icon: '◆', category: 'flow' },
    { type: 'loop', action: '', icon: '🔁', category: 'flow' },
    { type: 'group', action: '', icon: '📦', category: 'flow' },
  ];

  const categories = ['interaction', 'navigation', 'data', 'control', 'flow'] as const;

  const filteredBlocks = computed(() => {
    const q = search.value.toLowerCase().trim();
    if (!q) return blocks;
    return blocks.filter(
      (b) =>
        t(`blocks.${b.action}` || b.type).toLowerCase().includes(q) ||
        b.action.toLowerCase().includes(q) ||
        b.type.toLowerCase().includes(q),
    );
  });

  function blocksByCategory(cat: string) {
    return filteredBlocks.value.filter((b) => b.category === cat);
  }

  function toggleCategory(cat: string) {
    if (expandedCategories.value.has(cat)) {
      expandedCategories.value.delete(cat);
    } else {
      expandedCategories.value.add(cat);
    }
    expandedCategories.value = new Set(expandedCategories.value);
  }

  function onDragStart(event: DragEvent, block: BlockDef) {
    if (!event.dataTransfer) return;
    event.dataTransfer.setData('application/mimicry-node', block.type);
    event.dataTransfer.setData('application/mimicry-action', block.action);
    event.dataTransfer.effectAllowed = 'move';
  }

  function categoryLabel(cat: string): string {
    return t(`blockCategory.${cat}`);
  }
</script>

<template>
  <div class="block-palette">
    <div class="palette-search">
      <Search :size="14" class="search-icon" />
      <input
        v-model="search"
        type="text"
        class="search-input"
        :placeholder="t('blockPalette.search')"
      />
    </div>
    <div class="palette-list">
      <div v-for="cat in categories" :key="cat" class="palette-category">
        <div
          v-if="blocksByCategory(cat).length > 0"
          class="category-header"
          @click="toggleCategory(cat)"
        >
          <ChevronRight
            :size="14"
            class="category-chevron"
            :class="{ expanded: expandedCategories.has(cat) }"
          />
          <span class="category-label">{{ categoryLabel(cat) }}</span>
          <span class="category-count">{{ blocksByCategory(cat).length }}</span>
        </div>
        <div v-if="expandedCategories.has(cat)" class="category-blocks">
          <div
            v-for="block in blocksByCategory(cat)"
            :key="block.action || block.type"
            class="block-item"
            draggable="true"
            @dragstart="onDragStart($event, block)"
          >
            <span class="block-icon">{{ block.icon }}</span>
            <span class="block-label">{{
              block.action ? t(`blocks.${block.action}`) : t(`nodeTypes.${block.type}`)
            }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
  .block-palette {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }

  .palette-search {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px;
    border-bottom: 1px solid var(--color-border);
  }

  .search-icon {
    color: var(--color-text-muted);
    flex-shrink: 0;
  }

  .search-input {
    flex: 1;
    background: transparent;
    border: none;
    outline: none;
    font-size: 12px;
    color: var(--color-text);
  }

  .palette-list {
    flex: 1;
    overflow-y: auto;
    padding: 4px 0;
  }

  .category-header {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 6px 8px;
    cursor: pointer;
    user-select: none;
    font-size: 11px;
    font-weight: 600;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .category-header:hover {
    color: var(--color-text);
  }

  .category-chevron {
    transition: transform 0.15s;
  }

  .category-chevron.expanded {
    transform: rotate(90deg);
  }

  .category-count {
    margin-left: auto;
    font-size: 10px;
    opacity: 0.6;
  }

  .category-blocks {
    padding: 0 4px 4px;
  }

  .block-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 5px 8px;
    border-radius: 4px;
    cursor: grab;
    font-size: 12px;
    color: var(--color-text);
    transition: background 0.1s;
  }

  .block-item:hover {
    background: var(--color-surface-hover);
  }

  .block-item:active {
    cursor: grabbing;
  }

  .block-icon {
    font-size: 13px;
    width: 18px;
    text-align: center;
  }

  .block-label {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
</style>

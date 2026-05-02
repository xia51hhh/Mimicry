<script setup lang="ts">
  import { ref, computed, watch, nextTick } from 'vue';
  import { useI18n } from 'vue-i18n';

  const { t } = useI18n();

  const props = defineProps<{
    visible: boolean;
    position?: { x: number; y: number };
  }>();

  const emit = defineEmits<{
    select: [type: string, action: string];
    close: [];
  }>();

  const query = ref('');
  const selectedIndex = ref(0);
  const inputRef = ref<HTMLInputElement | null>(null);

  interface CommandItem {
    type: string;
    action: string;
    icon: string;
    label: string;
    category: string;
  }

  const allCommands = computed<CommandItem[]>(() => [
    // Interaction
    { type: 'action', action: 'Click', icon: '🖱', label: t('blocks.Click'), category: t('blockCategory.interaction') },
    { type: 'action', action: 'DblClick', icon: '🖱', label: t('blocks.DblClick'), category: t('blockCategory.interaction') },
    { type: 'action', action: 'Type', icon: '⌨', label: t('blocks.Type'), category: t('blockCategory.interaction') },
    { type: 'action', action: 'Hover', icon: '👆', label: t('blocks.Hover'), category: t('blockCategory.interaction') },
    { type: 'action', action: 'PressKey', icon: '⌨', label: t('blocks.PressKey'), category: t('blockCategory.interaction') },
    { type: 'action', action: 'Scroll', icon: '📜', label: t('blocks.Scroll'), category: t('blockCategory.interaction') },
    { type: 'action', action: 'SelectOption', icon: '☑', label: t('blocks.SelectOption'), category: t('blockCategory.interaction') },
    // Navigation
    { type: 'action', action: 'Navigate', icon: '🔗', label: t('blocks.Navigate'), category: t('blockCategory.navigation') },
    { type: 'action', action: 'NewTab', icon: '➕', label: t('blocks.NewTab'), category: t('blockCategory.navigation') },
    { type: 'action', action: 'GoBack', icon: '◀', label: t('blocks.GoBack'), category: t('blockCategory.navigation') },
    { type: 'action', action: 'Reload', icon: '🔄', label: t('blocks.Reload'), category: t('blockCategory.navigation') },
    // Data
    { type: 'action', action: 'GetText', icon: '📄', label: t('blocks.GetText'), category: t('blockCategory.data') },
    { type: 'action', action: 'Screenshot', icon: '📸', label: t('blocks.Screenshot'), category: t('blockCategory.data') },
    { type: 'action', action: 'SetVariable', icon: '📝', label: t('blocks.SetVariable'), category: t('blockCategory.data') },
    { type: 'action', action: 'ExtractTable', icon: '📊', label: t('blocks.ExtractTable'), category: t('blockCategory.data') },
    // Control
    { type: 'action', action: 'Delay', icon: '⏱', label: t('blocks.Delay'), category: t('blockCategory.control') },
    { type: 'action', action: 'Wait', icon: '⏳', label: t('blocks.Wait'), category: t('blockCategory.control') },
    { type: 'action', action: 'RunScript', icon: '⚡', label: t('blocks.RunScript'), category: t('blockCategory.control') },
    { type: 'action', action: 'HttpRequest', icon: '🌐', label: t('blocks.HttpRequest'), category: t('blockCategory.control') },
    // Flow
    { type: 'condition', action: '', icon: '◆', label: t('nodeTypes.condition'), category: t('blockCategory.flow') },
    { type: 'loop', action: '', icon: '🔁', label: t('nodeTypes.loop'), category: t('blockCategory.flow') },
  ]);

  const filtered = computed(() => {
    const q = query.value.toLowerCase().trim();
    if (!q) return allCommands.value;
    return allCommands.value.filter(
      (c) =>
        c.label.toLowerCase().includes(q) ||
        c.action.toLowerCase().includes(q) ||
        c.category.toLowerCase().includes(q),
    );
  });

  watch(
    () => props.visible,
    (v) => {
      if (v) {
        query.value = '';
        selectedIndex.value = 0;
        nextTick(() => inputRef.value?.focus());
      }
    },
  );

  watch(filtered, () => {
    selectedIndex.value = 0;
  });

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      selectedIndex.value = Math.min(selectedIndex.value + 1, filtered.value.length - 1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      selectedIndex.value = Math.max(selectedIndex.value - 1, 0);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const item = filtered.value[selectedIndex.value];
      if (item) emit('select', item.type, item.action);
    } else if (e.key === 'Escape') {
      emit('close');
    }
  }

  function selectItem(item: CommandItem) {
    emit('select', item.type, item.action);
  }
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="command-overlay" @click.self="emit('close')">
      <div class="command-palette" :style="position ? { left: position.x + 'px', top: position.y + 'px', position: 'fixed' } : {}">
        <div class="command-input-wrap">
          <input
            ref="inputRef"
            v-model="query"
            type="text"
            class="command-input"
            :placeholder="t('commandPalette.placeholder')"
            @keydown="onKeydown"
          />
        </div>
        <div class="command-list">
          <div
            v-for="(item, i) in filtered"
            :key="item.action || item.type"
            class="command-item"
            :class="{ selected: i === selectedIndex }"
            @click="selectItem(item)"
            @mouseenter="selectedIndex = i"
          >
            <span class="command-icon">{{ item.icon }}</span>
            <span class="command-label">{{ item.label }}</span>
            <span class="command-category">{{ item.category }}</span>
          </div>
          <div v-if="filtered.length === 0" class="command-empty">
            {{ t('commandPalette.noResults') }}
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
  .command-overlay {
    position: fixed;
    inset: 0;
    z-index: 1000;
    display: flex;
    justify-content: center;
    padding-top: 20vh;
    background: rgba(0, 0, 0, 0.3);
  }

  .command-palette {
    width: 400px;
    max-height: 360px;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .command-input-wrap {
    padding: 12px;
    border-bottom: 1px solid var(--color-border);
  }

  .command-input {
    width: 100%;
    background: transparent;
    border: none;
    outline: none;
    font-size: 14px;
    color: var(--color-text);
  }

  .command-list {
    flex: 1;
    overflow-y: auto;
    padding: 4px;
  }

  .command-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 13px;
    color: var(--color-text);
  }

  .command-item.selected {
    background: var(--color-surface-hover);
  }

  .command-icon {
    font-size: 14px;
    width: 20px;
    text-align: center;
  }

  .command-label {
    flex: 1;
  }

  .command-category {
    font-size: 11px;
    color: var(--color-text-muted);
  }

  .command-empty {
    padding: 16px;
    text-align: center;
    font-size: 13px;
    color: var(--color-text-muted);
  }
</style>

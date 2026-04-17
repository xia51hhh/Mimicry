<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as monaco from 'monaco-editor'
import { useWorkflowStore } from '../../stores/workflow'
import { useSettingsStore } from '../../stores/settings'

// Configure Monaco workers
self.MonacoEnvironment = {
  getWorker(_: string, label: string) {
    if (label === 'json') {
      return new Worker(
        new URL('monaco-editor/esm/vs/language/json/json.worker.js', import.meta.url),
        { type: 'module' }
      )
    }
    return new Worker(
      new URL('monaco-editor/esm/vs/editor/editor.worker.js', import.meta.url),
      { type: 'module' }
    )
  },
}

const store = useWorkflowStore()
const settings = useSettingsStore()
const editorContainer = ref<HTMLElement>()
let editor: monaco.editor.IStandaloneCodeEditor | null = null
let isUpdatingFromStore = false
let isUpdatingFromEditor = false
let debounceTimer: ReturnType<typeof setTimeout> | undefined

onMounted(() => {
  if (!editorContainer.value) return

  editor = monaco.editor.create(editorContainer.value, {
    value: JSON.stringify(store.toJSON(), null, 2),
    language: 'json',
    theme: settings.monacoTheme,
    minimap: { enabled: false },
    fontSize: 12,
    fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
    lineNumbers: 'on',
    scrollBeyondLastLine: false,
    automaticLayout: true,
    tabSize: 2,
    wordWrap: 'on',
    folding: true,
    renderLineHighlight: 'line',
  })

  // Editor → Store sync (debounced)
  editor.onDidChangeModelContent(() => {
    if (isUpdatingFromStore) return
    clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => {
      if (!editor) return
      const text = editor.getValue()
      try {
        const parsed = JSON.parse(text)
        isUpdatingFromEditor = true
        store.fromJSON(parsed)
        nextTick(() => {
          isUpdatingFromEditor = false
        })
        // Clear markers on valid JSON
        monaco.editor.setModelMarkers(editor.getModel()!, 'json', [])
      } catch {
        // Invalid JSON — let Monaco's built-in validation handle it
      }
    }, 500)
  })
})

// Store → Editor sync
watch(
  () => store.toJSON(),
  (json) => {
    if (isUpdatingFromEditor || !editor) return
    const newText = JSON.stringify(json, null, 2)
    const currentText = editor.getValue()
    if (newText !== currentText) {
      isUpdatingFromStore = true
      const pos = editor.getPosition()
      editor.setValue(newText)
      if (pos) editor.setPosition(pos)
      isUpdatingFromStore = false
    }
  },
  { deep: true }
)

// Theme follow
watch(
  () => settings.monacoTheme,
  (theme) => {
    if (editor) {
      monaco.editor.setTheme(theme)
    }
  }
)

onBeforeUnmount(() => {
  clearTimeout(debounceTimer)
  editor?.dispose()
  editor = null
})
</script>

<template>
  <div ref="editorContainer" class="h-full w-full" />
</template>

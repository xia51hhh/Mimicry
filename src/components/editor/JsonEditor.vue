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
    debounceTimer = setTimeout(async () => {
      if (!editor) return
      const text = editor.getValue()
      isUpdatingFromEditor = true
      const result = await store.applyJsonText(text)
      if (result.success) {
        // Clear markers on valid JSON
        monaco.editor.setModelMarkers(editor.getModel()!, 'json', [])
      }
      nextTick(() => {
        isUpdatingFromEditor = false
      })
    }, 500)
  })
})

// Store → Editor sync
watch(
  () => store.jsonText,
  (newText) => {
    if (isUpdatingFromEditor || !editor) return
    const currentText = editor.getValue()
    if (newText !== currentText) {
      isUpdatingFromStore = true
      const pos = editor.getPosition()
      editor.setValue(newText)
      if (pos) editor.setPosition(pos)
      isUpdatingFromStore = false
    }
  }
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

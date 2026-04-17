# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Fixed
- **[Critical]** Replace all `any` types with proper interfaces across stores (`browser.ts`, `execution.ts`, `workflow.ts`, `workspace.ts`) and `UpdateNotifier.vue`
- **[Bug]** `UpdateNotifier.vue` download progress calculation: accumulate chunk bytes instead of showing single-chunk ratio
- **[Bug]** `execution.ts` node status tracking: assign `currentNodeId` before comparing with previous value, preventing missed transitions
- **[Bug]** `JsonEditor.vue` debounce timer leak on unmount
- **[i18n]** Replace all hardcoded Chinese text with `t()` calls in `UpdateNotifier.vue`, `EditorView.vue`, `GroupNode.vue`, `PropertyPanel.vue`, `TabBar.vue`, `execution.ts`
- **[i18n]** Add missing i18n keys: `update.*`, `canvas.*`, `tabBar.*`, `group.*`, `propertyPanel.matchValuePlaceholder`, `propertyPanel.loopSelectorLabel`
- **[Minor]** Remove duplicate `:hover` CSS rule in `LoopNode.vue`
- **[Minor]** Type `appWindow` as `TauriWindow` instead of `any` in `TabBar.vue`
- **[Minor]** Serialize edge `label` safely in `workflow.ts` `toJSON()` (filter non-string VNode labels)

## v0.1.0

### Added
- Project scaffolding: Tauri v2 + Vue 3 + TailwindCSS v4
- SQLite database layer for workflow persistence
- Python Sidecar with JSON-RPC over stdio
- Camoufox anti-detect browser integration
- Vue Flow workflow editor with drag-drop nodes
- Pseudocode DSL engine (parse ↔ compile bidirectional)
- Browser action recording via JS injection
- Workflow execution engine with conditions, loops, variables
- Auto-update support via Tauri updater plugin
- GitHub Actions CI/CD: Release (5 targets) / CI Check / Frontend Check / Clippy Lint
- Cross-compile: Windows x64/ARM64, Linux x64/ARM64/ARMv7

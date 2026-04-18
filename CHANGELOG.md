# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added
- **Auto-update system**: UpdateNotifier dialog with "Install Now / Remind Later / Skip Version", download progress bar, manual fallback to GitHub releases
- **Settings About section**: Version display (`@tauri-apps/api/app getVersion`), manual check-for-update button
- **Camoufox install progress bar**: Real-time streaming via JSON-RPC notifications (Python → Rust Tauri events → Vue listen)
- **Cross-platform screen detection**: DPI-aware browser window sizing (Windows `SetProcessDPIAware` + `GetDeviceCaps` / macOS `system_profiler` / Linux `xdpyinfo`)

### Fixed
- **[Critical]** `camoufox.__version__` is a module object, not a string — caused `TypeError: Object of type module is not JSON serializable` on every `camoufox.check` and `camoufox.install` RPC call. Fixed by using `pip show` for version detection
- **[Bug]** Browser window exceeding screen size on HiDPI displays — now accounts for DPI scaling factor
- **[Bug]** TabBar drag region too small — `.tabs-scroll` area now supports window dragging, individual tabs remain clickable
- **[Bug]** CamoufoxSetup dialog not scrollable / body scroll leak — added `max-height: 80vh; overflow-y: auto` and body scroll lock
- **[Critical]** Replace all `any` types with proper interfaces across stores (`browser.ts`, `execution.ts`, `workflow.ts`, `workspace.ts`) and `UpdateNotifier.vue`
- **[Bug]** `UpdateNotifier.vue` download progress calculation: accumulate chunk bytes instead of showing single-chunk ratio
- **[Bug]** `execution.ts` node status tracking: assign `currentNodeId` before comparing with previous value, preventing missed transitions
- **[Bug]** `JsonEditor.vue` debounce timer leak on unmount
- **[i18n]** Replace all hardcoded Chinese text with `t()` calls in `UpdateNotifier.vue`, `EditorView.vue`, `GroupNode.vue`, `PropertyPanel.vue`, `TabBar.vue`, `execution.ts`
- **[i18n]** Add missing i18n keys: `update.*`, `canvas.*`, `tabBar.*`, `group.*`, `propertyPanel.matchValuePlaceholder`, `propertyPanel.loopSelectorLabel`
- **[Minor]** Remove duplicate `:hover` CSS rule in `LoopNode.vue`
- **[Minor]** Type `appWindow` as `TauriWindow` instead of `any` in `TabBar.vue`
- **[Minor]** Serialize edge `label` safely in `workflow.ts` `toJSON()` (filter non-string VNode labels)

### Cross-platform Test Matrix (TODO)
- [ ] **Windows x64** — Auto-update download + install, Camoufox install progress, DPI scaling (100%/125%/150%/200%), TabBar drag
- [ ] **Windows ARM64** — Same as above
- [ ] **macOS Intel** — Auto-update (`tauri-plugin-updater` .tar.gz), Camoufox install, screen detection via `system_profiler`
- [ ] **macOS Apple Silicon** — Same as above
- [ ] **Linux x64** — Auto-update (AppImage), Camoufox install, screen detection via `xdpyinfo`, Wayland fallback
- [ ] **Linux ARM64** — Same as above

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

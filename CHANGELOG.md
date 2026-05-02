# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added (2026-04-28 → 2026-05-02)

- **Workflow Templates system** — SQLite `templates` table + Tauri commands (`templates.rs`) + Pinia store (`stores/templates.ts`) + TemplateManager UI + integrated panel in editor (commits `1ffd154` `866c00c`)
- **Multi-strategy Selector system** — `sidecar/browser/selector.py` 多策略评分引擎 + `scripts/picker.js` 浏览器拾取叠加层 + RPC 接口（`browser_pick_start/stop/analyze`）+ PropertyPanel 选择器分析 UI + BottomPanel 独立分析面板（commits `23dc99c` `5f27cde`）
- **Canvas editor enhancements** — 画布双击快捷添加节点 / 拖拽创建连接 / 节点分组（Ctrl+G）/ CommandPalette（commits `78c68db` `1ffd154`）
- **Sidebar BlockPalette consolidation** — 删除重复的 `EditorView` 内嵌 BlockPalette，统一走 Sidebar；Sidebar 节点面板补 7 个缺失节点（commits `f4f0802` `4b46d2c`）
- **Settings page** — 完整 SettingsView（执行超时 / 录制暂停 / 包管理 / 各类用户偏好），新 `stores/settings.ts`（commit `1ffd154`）
- **Sidecar 3-stage captcha framework** — `sidecar/captcha/base.py` 抽象基类，`cloudflare.py` 扩展为 3 阶段（detect / interact / verify）（commit `d6581d8`）
- **Sidecar 3-tier process cleanup** — `controller.py` 三级清理（page / context / browser process），杜绝僵尸进程（commit `d6581d8`）
- **JS scripts modularization** — `sidecar/browser/scripts/{picker.js, recorder.js}` 抽离，主 Python 文件瘦身（recorder.py 380 → 190 行）（commit `d6581d8`）
- **Humanize enhancements** — recorder 拟人化检测增强（commit `d6581d8`）
- **Rust Workflow Transform Layer** — 4-format interchange (Canonical / Compact / Backend / Legacy) + auto-layout with condition/loop branch offsets; new Tauri commands `workflow_transform_import`, `workflow_export_compact`, `workflow_detect_format` (commits `5f882da` `9985352` `001c237` `f064821`)
- **Workflow Static Validator** — 37 rules (W001-W014 + I001-I011) intercept before `workflow_execute`; frontend Problems panel + per-node diagnostic badges (commits `d710a64` `5ca1f21` `dabc3bb` `d52f4f4` `897b4e4`)
- **Sidecar three-mode entry** — Tauri stdio JSON-RPC + CLI Daemon (UDS) + MCP Server (stdio) sharing `browser/actions.py` + `rpc/methods.py`. **81 RPC methods auto-mapped to 80+ MCP tools** (commits `a88865a` `cb9fa6c` `7f12f2a` `4615d7c` `f08887c` `15bcf79` `1eafb24` `9c14fe6` `6b47444` `23dc99c` `1ffd154` `d6581d8`). MCP `isError` protocol, schema inference from `@rpc_method` descriptions, network capture / console buffer / `init_scripts` injection
- **Tab Identification System** — TabInfo registry with gradient matching (`tabId` → `seq` → `urlOrigin+urlPath` → `title` → `tabIndex`); recorder auto-inserts SwitchTab on tab change (commits `7cbc580` `956bfd3` `fdd6257`)
- **Canonical block schema unification** — flat `{type, action, url}` migrated to canonical `{kind, action, data, settings}` across frontend / Rust / sidecar (commits `fd53189` `0d8810d` `4d3c899` `0f072ee`)
- **Complete Debug UI** — Tauri commands `workflow_pause/unpause/step/inject/set_breakpoint/remove_breakpoint/list_breakpoints/state`; Toolbar buttons; F9/F5/F10/F6 shortcuts; breakpoint indicator + pause animation + Debug panel + right-click menu; node Tooltip + edge flow animation + MiniMap + selector self-healing (commits `138db37` `b9c4714` `7a459d6` `55f52ff`)
- **Multi-Profile / Multi-Session Browser** — per-Profile `user_data_dir`, proxy, OS target, browser config; `sessionId` routing in node `data` / `runtime` (commit `25248c4`)
- **Cloudflare Captcha Click Solver** — `sidecar/captcha/cloudflare.py` for Turnstile / Interstitial (commit `a8580ce`, adapted from `techinz/playwright-captcha`)
- **Parallel Worktree Protocol** — `task.py worktree create/list/status/remove`; per-worktree `.current-task` (gitignored); SessionStart hook auto-injection (commits `0a09e9c` `eb246b1` `6f27a67`)
- **CI P0 closure** — `pipeline.yml` covers typecheck / lint / sidecar pytest / Rust clippy & test / version triple-lock / action-map sync; release pipeline triggered by `vX.Y.Z` git tags with CHANGELOG enforcement (commit `a8580ce`)
- **README rewrite (Clippy marketing style)** — banner, badges, install / quick start / MCP / tech stack / architecture / project structure / contributing / credits / legal-ethics (commit `b488c88`)
- **Anti-detection 12-dimension model** — Symbol key injection, multi-site test results (Google ✅, DDG ✅, Cloudflare ✅, BrowserScan ✅, CreepJS ✅, Incolumitas ⚠️, Bing ❌); JS global leak fix (commits `9b20096` `c330cf5`)

### Removed (2026-04-28 → 2026-05-02)

- `sidecar/cli_legacy.py` deleted; `sidecar/dev_cli.py` partially cleaned (commit `7f12f2a`)
- Sidecar test scratch files purged: `_*.py` ad-hoc scripts, `screenshots/` (45 files), `e2e_*.txt`, `demo_*.json`, `screenshot.png` (commit `15efc28`)
- Dev-time `src-tauri/mimicry.db` removed from repo (commit `4a46935`)

### Documentation (2026-05-02 — full audit refresh)

- All living docs aligned with code reality: `architecture.md` / `project-structure.md` / `block-api.md` (full canonical upgrade absorbing 04-28-block-doc-update task) / `dev-cli.md` / `llm-interactive-guide.md` / 8 design docs / 2 workflow docs / 3 README files
- New ADRs in `decisions.md`: 007 Workflow Validator / 008 Transform Layer / 009 Sidecar Three-Mode / 010 Parallel Worktree
- `pseudocode-spec.md` marked as deprecated (per ADR-001 JSON direct execution)

### Original Unreleased entries (pre-2026-04-27 baseline)

#### Added
- **Auto-update system**: UpdateNotifier dialog with "Install Now / Remind Later / Skip Version", download progress bar, manual fallback to GitHub releases
- **Settings About section**: Version display (`@tauri-apps/api/app getVersion`), manual check-for-update button
- **Camoufox install progress bar**: Real-time streaming via JSON-RPC notifications (Python → Rust Tauri events → Vue listen)
- **Cross-platform screen detection**: DPI-aware browser window sizing (Windows `SetProcessDPIAware` + `GetDeviceCaps` / macOS `system_profiler` / Linux `xdpyinfo`)

#### Fixed
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

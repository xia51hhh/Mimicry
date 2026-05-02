# Code Reality Audit (combined: frontend + Rust + sidecar + block/action-map)

## Action map（CI 强制契约）

**42 个 action**，三处文件已对齐：

- `shared/action-map.json` （42 entries）
- `sidecar/engine/action_map.py` （42 entries）
- `src/types/action-map.ts` （42 entries，AUTO-GENERATED 注释）
- `scripts/sync-action-map.py` 校验脚本：用 regex 解析三处文件 → 对比 → `--fix` 模式可重生成 PY/TS

**完整 action 清单**（按功能聚合）：

| 类别 | Frontend (PascalCase) → Backend (snake_case) |
|---|---|
| 导航 | Navigate→open, GoBack→back, GoForward→forward, Reload→reload, WaitForPage→wait_for_page |
| Tab | NewTab→new_tab, SwitchTab→switch_tab, CloseTab→close_tab |
| 交互 | Click→click, DblClick→dblclick, Type→type, Hover→hover, Scroll→scroll, SelectOption→select, PressKey→press_key, Clear→clear, Focus→focus |
| 等待 | Wait→wait, Delay→sleep, WaitConnections→wait_connections |
| 提取 | GetText→extract_text, GetAttribute→extract_attr, GetURL→get_url, ExtractTable→extract_table, ElementExists→element_exists |
| 文件 | Screenshot→screenshot, UploadFile→upload_file, HandleDownload→handle_download |
| 上下文 | SetVariable→set, Cookie→cookie, SwitchFrame→switch_frame, HandleDialog→handle_dialog |
| 控制流 | LoopElements→loop_elements, LoopBreakpoint→loop_breakpoint, ExecuteWorkflow→execute_workflow, Stop→stop, Fail→fail |
| 工具 | RunScript→run_script, HttpRequest→http_request, Log→log, Comment→comment, Export→export, Transform→transform |

**关键发现 — 04-28-block-doc-update 假设的 action 不存在**：

- ❌ `UseBrowser` — action map 里没有；多浏览器隔离通过 `data.sessionId` 字段实现（在 `src/types/workflow.ts` 的 `ActionData/ConditionData/LoopData` 都有可选 `sessionId`）
- ❌ `WaitForNewTab` — 没有；最接近的是 `WaitForPage`（wait_for_page）
- ✅ `NewTab/SwitchTab/CloseTab` — 都已存在，是 04-28 唯一可落地的 Tab 块
- ✅ Tab 梯度匹配字段 — 已在 PropertyPanel 实现（commit `fdd6257`），保存到 SwitchTab 节点的 data 中

→ **04-28 PRD 部分臆想，更新文档时应基于真实 action map**

## Block schema（canonical 当前形态）

定义在 `src/types/workflow.ts`：

```typescript
type WorkflowNodeKind = 'action' | 'condition' | 'loop' | 'group';

interface CanonicalWorkflowNode {
  id: string;
  kind: WorkflowNodeKind;          // 注意：用 kind，不是 type
  action?: string;                  // PascalCase, 仅 kind=action 时必填
  position: { x: number; y: number };
  data: Record<string, unknown>;    // 含 selector/value/url/sessionId/timeout 等
  settings?: WorkflowNodeSettings;  // onError/retryCount/retryInterval/note/disabled
  runtime?: WorkflowNodeRuntime;    // sessionId 等运行时字段
  selected?: boolean;
}

interface Workflow {
  id: string;
  name: string;
  nodes: CanonicalWorkflowNode[];
  edges: CanonicalWorkflowEdge[];
}
```

`WorkflowNodeSettings` 字段：`onError | retryOnFail | retryCount | retryInterval | note | disabled`。

老 `WorkflowNode` 类型（用 `type` 字段）仍存在但仅做兼容；`Workflow` 用的是 `CanonicalWorkflowNode[]`。

`docs/block-api.md` 当前文档里如果还在用 flat `{type, action, url}` 就是 stale。

## Frontend (`src/`) — 7 stores · 4 composables · 14 components · 2 views

### Stores (Pinia setup syntax)
- `browser.ts` — 浏览器/Camoufox 状态（launch/close/sessions）
- `execution.ts` — 工作流执行 + 调试状态（pause/step/breakpoint/state）
- `profiles.ts` — Profile 管理（多浏览器隔离）
- `settings.ts` — 应用设置
- `validation.ts` — workflow_validator 结果（Problems 面板数据源）
- `workflow.ts` — 当前工作流（dirty 检测、节点 CRUD）
- `workspace.ts` — 多 tab 持久化（最近文件、当前 tab）

### Composables
- `useFileOps.ts` — 文件 import/export/save（含 dirty 检测）
- `useKeyboardShortcuts.ts` — 全局快捷键（含 F9/F5/F10 调试）
- `usePanel.ts` — 底部面板伸缩状态
- `useShortcutToast.ts` — 快捷键提示 toast

### Components
- 顶层 4 件：CamoufoxSetup, ProfileDialog, ProfileManager, UpdateNotifier
- `editor/`：BottomPanel（日志/Problems/控制台）、ContextMenu（右键菜单含调试）、JsonEditor（Monaco）、PropertyPanel（节点属性，含 SwitchTab 梯度字段）、RecordingPreview
- `layout/`：ActivityBar, MainLayout, Sidebar, TabBar, Toolbar（调试按钮 + MiniMap toggle）
- `nodes/`：ActionNode, ConditionNode, LoopNode, GroupNode（含连线动画 + 节点 Tooltip + 断点指示器）
- `ui/`：SetupDialog, ShortcutToast

### Views
- `EditorView.vue` — Vue Flow 主画布
- `SettingsView.vue` — 应用设置页

### Types
- `action-map.ts`（自动生成）, `ipc.ts`（Tauri invoke 类型）, `workflow.ts`（block schema）

### Utils
- `workflowSchema.ts` + `__tests__/workflowSchema.test.ts`

### i18n
- `locales/{en,zh-CN}.json` — 全部用户可见字符串

## Rust core (`src-tauri/src/`) — Tauri commands 全列表

注册于 `lib.rs::run()` 的 `tauri::generate_handler!`。

| 类别 | Commands |
|---|---|
| System | `system_info`, `check_environment`, `install_system_pkg` |
| Profile（多浏览器） | `profile_list/get/create/update/delete` |
| Browser | `browser_launch/close/navigate/status/list_sessions/detect_screens/install` |
| Camoufox | `camoufox_check/install/check_update/update` |
| Recording | `recording_start/stop/poll`（poll 替代了失效的 notification 监听） |
| Workflow CRUD（DB） | `workflow_list/get/create/save/delete/export/import` |
| Workflow execute | `workflow_execute/stop_execution/execution_status/validate` |
| Debug surface | `workflow_pause/unpause/step/inject/set_breakpoint/remove_breakpoint/list_breakpoints/state` |
| Transform | `workflow_transform_import/export_compact/detect_format` |
| File ops | `file_read/import/export_compact/write/write_text` |
| Recent files | `recent_files_add/list/remove/clear` |

### transform/ 模块（5/1 升级了自动布局）

- `mod.rs` — 模块入口
- `types.rs` — 转化层类型
- `action_map.rs` — Rust 侧 action map 引用
- `backend.rs` — 后端格式生成
- `compact.rs` — Compact 格式（单文件持久化）
- `detect.rs` — 格式自动识别（canonical/legacy/compact/recording）
- `legacy.rs` — 旧 flat 格式 → canonical 迁移
- `layout.rs` — 自动布局（**支持 condition/loop 分支偏移**）

### workflow_validator.rs

37 条规则（W001-W014 + I001-I011），在 `workflow_execute` 前拦截。

### db/ 模块

`schema.rs` 表：`workflows`, `settings`, `recent_files`, `profiles`。SQLite 路径：`<app-data>/com.mimicry.app/mimicry.db`。

### ipc/ 模块

`jsonrpc.rs` JSON-RPC 2.0 client；`sidecar.rs` sidecar 生命周期管理。

## Sidecar (`sidecar/`) — 三入口 + 共享内核

### 入口（main.py 仅 50 行，做 mode 路由）

`main.py::_detect_mode()` 根据 `--mcp/--daemon/无` 切到对应入口；3 模式共享 `browser/actions.py` + `rpc/methods.py`。

| 模式 | 入口 | 用途 |
|---|---|---|
| Tauri stdio JSON-RPC | `main.py`（默认）→ `rpc/server.py` | Tauri shell 方式 |
| CLI + Daemon UDS | `cli.py` ↔ UDS `/tmp/mimicry-{uid}.sock` ↔ `daemon.py` | LLM/人 CLI 用 |
| MCP Server stdio | `cli.py --mcp` → `mcp_server.py` | MCP 客户端（Claude Desktop / Cursor）|

注意：`dev_cli.py` 仍存在但功能被 `cli.py` 取代，可视为遗留辅助。

### CLI 命令清单（来自 `cli.py` argparse）

- Daemon：`daemon start/stop/status` (含 `--foreground`)
- Browser：`launch [--headless --proxy]`, `close`, `sessions`
- 交互：`navigate <url>`, `click <sel> [--force]`, `type <sel> <text> [--no-humanize]`, `eval <js>`, `screenshot [path]`, `scroll <dir> [amount]`
- Workflow：`run <file> [--step --break-at... --no-humanize]`, `pause`, `resume`, `stop`, `step [N]`, `state`, `context`
- Inject + Breakpoints：`inject <json>`, `breakpoint add/rm/list`（别名 `bp`）
- 工具：`validate <file>`（**离线，无 daemon**，5/1 改为 JSON 输出 commit `9c14fe6`）, `--json`, `-s/--session`

### sidecar/SKILL.md（LLM-facing）

200 行，与 `docs/llm-interactive-guide.md` 双源；架构示意图 + 命令表 + 5 个 Pattern + 反检测站点状态表。**MCP 工具数声明为 68**（来自 SKILL.md 文末），需校验当前 `mcp_server.py` 注册数量。

### browser/

- `actions.py` — 共享 action 适配层（所有 RPC method 的 LLM-facing description 在此，`6b47444`）
- `controller.py` — 浏览器生命周期 + network 捕获 + console 缓冲 + init_scripts（`15bcf79` `1eafb24`）
- `recorder.py` — 录制（poll 定时器版本，`2ecefbd`；自动检测 tab 切换插入 SwitchTab，`956bfd3`）
- `profile.py` — Profile 隔离（多 session 实现）
- `env_check.py` — 环境检查（dependencies/system）

### engine/

- `executor.py` — Workflow 执行核心（pause/step/breakpoint）
- `executor_state.py` — 执行状态机
- `condition_parser.py` — Condition 节点表达式
- `action_map.py` — backend 侧 action 映射（同 shared/action-map.json）

### captcha/（5/1 新增）

- `cloudflare.py` — Cloudflare Turnstile click solver（`a8580ce`）

### dsl/（已弃用 per ADR-001，仍在仓库）

`ast_nodes.py / compiler.py / lexer.py / parser.py / rpc_methods.py` — 不要扩展。

### rpc/

- `methods.py` — `@rpc_method` 装饰器注册的方法
- `protocol.py` — JSON-RPC 2.0 编解码
- `server.py` — stdio server loop

## examples/

仓库根的 `examples/` 仅含 `external/` 子目录（gitignored），**不在 git 跟踪范围**。文档若引用 `examples/foo.json` 应改为内联示例或迁移到 `docs/` 内。

## 关键 drift 摘要（驱动 Phase 2 更新）

| 文档 | 关键 drift |
|---|---|
| README × 3 | 需补：transform 层 / validator 37 规则 / 调试 UI / MCP 服务 / CLI Daemon / 多 session / 验证码解算器 / 并行 worktree |
| architecture.md | Rust 增加 transform/ + workflow_validator；sidecar 三模式说明需对齐当前实现；新增 captcha/ 模块 |
| project-structure.md | 已是 5/1 新建；核对 cli_legacy 删除、sidecar/captcha/ 新增、dev_cli 现状 |
| block-api.md | **flat → canonical 全面升级**；Tab 梯度匹配描述（基于真实代码，不是 04-28 PRD 的臆想 UseBrowser/WaitForNewTab） |
| dev-cli.md | 校对每条命令是否仍在 cli.py argparse 中；validate 输出已改 JSON |
| llm-interactive-guide.md | 与 SKILL.md 对齐；MCP 工具数核对；isError 协议 + init_scripts + console buffer 新特性 |
| anti-detection.md | 12 维模型 + 多 site 测试结果已加；可能仅小校对 |
| cicd-guide.md | pipeline.yml P0 闭环 + captcha 模块 CI 测试 |
| parallel-agents.md | 已被 a6ad9a4 简化重写；与 task.py 当前命令对齐 |
| pseudocode-spec.md | 校对是否仍反映 ADR-001 JSON 直执行（DSL 已弃用，**伪代码 spec 是否仍合理？**） |
| design/block-system.md | 5/1 已 touch（network/console/init_scripts）；canonical 强调 |
| design/data-flow.md | 加 transform 层 + validator 拦截 + 三模式 sidecar |
| design/debug-system.md | 5/1 已 touch；校对前端 UI 元素与 stores/execution.ts 一致 |
| design/decisions.md | ADR-001 仍 OK；**考虑新增 ADR**：transform 层 / validator / parallel worktree / tab 梯度匹配 |
| design/element-selector.md | 加选择器自愈机制（commit `55f52ff`） |
| design/package-system.md | tauri.conf.json 改了 + 三方版本锁说明 |
| design/transform-layer.md | 是否反映 Rust 7 文件实现（含 layout 分支偏移） |
| design/ui-description.md | 加 Toolbar 调试按钮 / 节点 Tooltip / MiniMap / Problems 面板 / 节点诊断徽标 |
| workflow/canvas-interaction.md | F9/F5/F10 调试快捷键 + 右键菜单 + 选择器自愈 |
| workflow/monaco-integration.md | 校对当前 monaco 集成（JsonEditor.vue） |
| CHANGELOG.md | 仅核对 0.1.0 段；不强行 bump |

## Verifications passed

- `python scripts/sync-action-map.py` 不会报错（三文件已同步）
- `examples/` 不存在但被 .gitignore（合理）
- `sidecar/dsl/` 仍被保留作 deprecated 引用（per ADR-001）
- 三方版本锁未变（Cargo.toml / package.json / tauri.conf.json 同步在历次 commit）

# Mimicry 架构概览

> **状态**: Implemented 主流，仍有 Planned 项 | **最后更新**: 2026-05-02

> 现实边界（5/2）：
> - ✅ Tauri v2 shell + Vue 3 前端 + SQLite + Rust ↔ Python JSON-RPC + Camoufox 控制器 + 录制器 + JSON 工作流执行器
> - ✅ Rust transform 层（4 格式互转 + 自动布局，含 condition/loop 分支偏移）
> - ✅ Workflow validator（37 条规则，前端 Problems 面板 + 节点诊断徽标）
> - ✅ Sidecar 三入口（Tauri stdio / CLI+Daemon UDS / MCP stdio）
> - ✅ 完整调试 UI（断点 / 暂停 / 单步 / Debug 面板 / 右键菜单）
> - ✅ 多 Profile / 多 session 隔离 + Cloudflare Turnstile click solver
> - ⏳ 执行历史持久化（`execution_logs` 表）：Planned
> - ⏳ PyInstaller 单文件 sidecar：spec 文件 ready，完整嵌入仍在打磨

---

## 整体架构

```
┌────────────────────────────────────────────────────────────┐
│                       Tauri v2 Shell                       │
│                                                            │
│  ┌─────────────────────────┐   ┌────────────────────────┐  │
│  │      Rust Core          │   │     Vue 3 WebView      │  │
│  │                         │   │                        │  │
│  │  Tauri Commands         │   │  Vue Flow Canvas       │  │
│  │  (~50 个 invoke 处理器) │◄──┤   - 节点 / 连线 / 分组 │  │
│  │   - browser / profile   │──►│   - MiniMap / Tooltip  │  │
│  │   - workflow / file_ops │   │   - 调试断点指示器     │  │
│  │   - debug / system      │   │  Monaco JsonEditor     │  │
│  │                         │   │  Pinia stores (×7)     │  │
│  │  Workflow Validator     │   │   browser/execution/   │  │
│  │  (37 条规则)            │   │   profiles/settings/   │  │
│  │                         │   │   validation/workflow/ │  │
│  │  Transform 层           │   │   workspace            │  │
│  │  (4 格式互转 + 布局)    │   │  i18n (en/zh-CN)       │  │
│  │                         │   │  Tailwind v4 + themes  │  │
│  │  SQLite (rusqlite)      │   └────────────────────────┘  │
│  │   workflows / settings  │                               │
│  │   recent_files /        │                               │
│  │   profiles              │                               │
│  │                         │                               │
│  │  Logger (tracing)       │                               │
│  │                         │                               │
│  │  Sidecar Manager        │                               │
│  │   - 进程生命周期        │                               │
│  │   - JSON-RPC 2.0 client │                               │
│  └─────────┬───────────────┘                               │
│            │ stdio (JSON-RPC 2.0)                          │
│  ┌─────────▼─────────────────────────┐                     │
│  │  Python Sidecar（三入口共享内核） │                     │
│  │                                   │                     │
│  │  入口分发：main.py                │                     │
│  │   ├─ stdio JSON-RPC (Tauri)       │                     │
│  │   ├─ UDS Daemon ↔ cli.py          │                     │
│  │   └─ MCP stdio (mcp_server.py)    │                     │
│  │                                   │                     │
│  │  RPC Registry (rpc/methods.py)    │                     │
│  │   - @rpc_method 装饰器注册        │                     │
│  │   - 71 个 method（MCP 自动映射）  │                     │
│  │                                   │                     │
│  │  Browser Controller               │                     │
│  │   - Camoufox 生命周期             │                     │
│  │   - Page actions                  │     ┌────────────┐  │
│  │   - Network capture / Console     │────►│ Camoufox   │  │
│  │   - init_scripts                  │     │ (Firefox)  │  │
│  │   - Selector self-healing         │     └────────────┘  │
│  │                                   │                     │
│  │  Recorder (poll-based)            │                     │
│  │   - DOM 事件捕获                  │                     │
│  │   - Tab 切换自动插入 SwitchTab    │                     │
│  │                                   │                     │
│  │  Engine                           │                     │
│  │   - Executor (JSON 解释执行)      │                     │
│  │   - ExecutorState (暂停/单步/bp)  │                     │
│  │   - Condition parser              │                     │
│  │                                   │                     │
│  │  Captcha (Cloudflare Turnstile)   │                     │
│  └───────────────────────────────────┘                     │
└────────────────────────────────────────────────────────────┘
```

---

## 模块职责

### Rust Core（`src-tauri/src/`）

| 模块 | 路径 | 职责 |
|---|---|---|
| Commands | `commands/` | Tauri invoke 处理器：browser / profile / workflow / file_ops / system；调试命令（pause/unpause/step/breakpoint/state/inject）也在 `browser.rs` |
| Transform | `transform/` | 工作流 4 格式互转（canonical / legacy / compact / recording）+ 自动布局（dagre 驱动，分支偏移）。详见 [transform-layer.md](design/transform-layer.md) |
| Workflow Validator | `workflow_validator.rs` | 37 条静态规则（W001-W014 + I001-I011），在 `workflow_execute` 前拦截；结果通过 IPC 回前端 `validation` store |
| DB | `db/` | SQLite 数据访问。表：`workflows` / `settings` / `recent_files` / `profiles` |
| IPC | `ipc/` | Sidecar 进程管理 + stdio 上的 JSON-RPC 2.0 client |
| Logger | `logger.rs` | tracing 日志，按天滚动 |
| Error | `error.rs` | 全局错误类型 |

### Vue 3 前端（`src/`）

| 模块 | 路径 | 职责 |
|---|---|---|
| Views | `views/` | 页面级：`EditorView.vue`（Vue Flow 主画布）、`SettingsView.vue` |
| Components | `components/` | `editor/`（5 件套：BottomPanel/ContextMenu/JsonEditor/PropertyPanel/RecordingPreview）、`layout/`（5 件套：ActivityBar/MainLayout/Sidebar/TabBar/Toolbar）、`nodes/`（4 件：Action/Condition/Loop/Group）、`ui/`（SetupDialog/ShortcutToast）、顶层 4 件（CamoufoxSetup/ProfileDialog/ProfileManager/UpdateNotifier） |
| Stores | `stores/` | 7 个 Pinia store（setup 语法）：browser / execution（含调试状态）/ profiles / settings / validation（Problems 面板数据源）/ workflow（dirty 检测）/ workspace（多 tab 持久化） |
| Composables | `composables/` | `useFileOps`、`useKeyboardShortcuts`（含 F9/F5/F10 调试快捷键）、`usePanel`、`useShortcutToast` |
| Types | `types/` | `action-map.ts`（自动生成）、`ipc.ts`、`workflow.ts`（canonical 节点类型） |
| Utils | `utils/` | `workflowSchema.ts` + `__tests__/` |
| Locales | `locales/` | `en.json` / `zh-CN.json` — 所有用户可见字符串通过 `t()` |
| Themes | `themes.ts` | 主题 token |

### Python Sidecar（`sidecar/`）

| 模块 | 路径 | 职责 |
|---|---|---|
| 入口分发 | `main.py` | 50 行；按 flag (`--mcp` / `--daemon` / 默认) 路由到三种入口 |
| Tauri stdio 入口 | `rpc/server.py` | stdio JSON-RPC 2.0 server（默认模式） |
| CLI 客户端 | `cli.py` | 525 行；UDS 客户端，约 25 个子命令（含 `--mcp` flag） |
| Daemon | `daemon.py` | 392 行；UDS Socket `/tmp/mimicry-{uid}.sock`，浏览器宿主进程 |
| MCP Server | `mcp_server.py` | 262 行；把 `@rpc_method` 注册自动映射成 MCP 工具 |
| Dev CLI | `dev_cli.py` | 450 行；老开发工具（带 REPL / anti-detect 跑分），逐步收敛到 `cli.py` |
| RPC Registry | `rpc/methods.py` | `@rpc_method` 装饰器；71 个 method（MCP 工具数 = 此数 - 测试方法过滤） |
| RPC Protocol | `rpc/protocol.py` | 长度前缀帧（Daemon ↔ CLI 用） |
| Browser | `browser/` | `actions.py`（共享 action 适配，所有 RPC method 的 LLM-facing description 在此）、`controller.py`（Playwright 包装含 network capture / console buffer / init_scripts）、`recorder.py`（poll-based 录制 + 自动插 SwitchTab）、`profile.py`（Profile 隔离）、`env_check.py` |
| Engine | `engine/` | `executor.py`（JSON 解释执行）、`executor_state.py`（暂停/单步/bp/inject）、`condition_parser.py`、`action_map.py`（与 shared/ 同步） |
| Captcha | `captcha/cloudflare.py` | Cloudflare Turnstile click solver（改编自 `techinz/playwright-captcha`） |
| LLM Skill | `SKILL.md` | LLM agent 的 CLI 操控教程 |
| DSL（已弃用） | `dsl/` | ADR-001 后停止扩展，仅历史保留 |

### Sidecar 三种入口模式

```
模式 1: Tauri Sidecar（Tauri 应用默认）
  Tauri Shell ──stdio JSON-RPC──► main.py ──► rpc/server.py ──► browser/actions.py ──► Camoufox

模式 2: CLI + Daemon（开发者 / LLM agent 直接驱动）
  LLM Agent / 终端 ──shell──► cli.py ──UDS─► daemon.py ──► browser/actions.py ──► Camoufox

模式 3: MCP Server（MCP 客户端集成）
  MCP Client (Claude Desktop / Cursor) ──stdio MCP──► cli.py --mcp / mcp_server.py ──► browser/actions.py ──► Camoufox
```

三模式共享同一个 `browser/actions.py` + `rpc/methods.py`：每加一个 action 都自动出现在三个模式中，无重复实现。

---

## IPC 通信

```
Vue 3 WebView  ──invoke()──►  Rust Core  ──stdio JSON-RPC──►  Python Sidecar
               ◄──event()──              ◄────response────
```

### 前端 ↔ Rust（Tauri v2 invoke / event）

```typescript
// 前端调用 Rust 命令
const result = await invoke('browser_navigate', { url: 'https://example.com', sessionId: 'default' });

// 前端监听 Rust 事件（执行进度、断点命中、validation 结果）
listen('execution-state', (event) => {
  console.log(event.payload);  // { state: 'paused', currentNode: 'n3', ... }
});
```

主要事件类型（来自 `src/types/ipc.ts`）：执行状态变更、节点完成、断点命中、录制事件、validation diagnostics、sidecar 健康状态。

### Rust ↔ Python Sidecar（JSON-RPC 2.0 over stdio）

```json
// Request (Rust → Python)
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "browser.navigate",
  "params": { "url": "https://example.com", "session_id": "default" }
}

// Response (Python → Rust)
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": { "ok": true, "url": "https://example.com" }
}
```

Method 命名采用点号分组（`browser.*` / `workflow.*` / `recording.*` / `network.*` 等），由 `@rpc_method("name.method")` 注册。

---

## 存储

SQLite（`rusqlite`），文件路径 `<app-data>/com.mimicry.app/mimicry.db`，schema 由 `src-tauri/src/db/schema.rs` 在首次启动时初始化。

| 表 | 内容 | 状态 |
|---|---|---|
| `workflows` | 工作流元数据 + canonical JSON 全文 | Implemented |
| `settings` | 应用配置（键值对） | Implemented |
| `recent_files` | 最近打开的工作流文件路径 | Implemented |
| `profiles` | Camoufox Profile 配置 + 隔离 user_data_dir | Implemented |
| `execution_logs` | 执行历史记录 | Planned |

---

## 构建与打包

| 命令 | 用途 |
|---|---|
| `cargo tauri dev` | 全栈开发（Vite :1420 + Rust shell + sidecar） |
| `pnpm dev` | 仅前端（Vite） |
| `pnpm build` | `vue-tsc --noEmit && vite build` |
| `cargo tauri build` | 构建发布包到 `src-tauri/target/release/bundle/` |
| `python -m pytest`（在 `sidecar/` 中） | 跑 sidecar 测试 |

**版本三方锁**：`package.json` / `src-tauri/tauri.conf.json` / `src-tauri/Cargo.toml` 三处版本必须一致（CI 强制）。`vX.Y.Z` git tag 触发发版，要求 `CHANGELOG.md` 有匹配 `## vX.Y.Z` 段。

**Sidecar venv**：首次启动时在 OS app-data（`<data-dir>/com.mimicry.app/venv/`）创建，**不在仓库内**。开发期 `src-tauri/src/lib.rs::resolve_sidecar_dir` 解析到仓库 `sidecar/` 目录。

---

## 跨层契约

- `shared/action-map.json` — 前端 PascalCase ↔ 后端 snake_case action 名映射的唯一来源（42 项），由 `scripts/sync-action-map.py`（CI 强制）校验 `sidecar/engine/action_map.py` + `src/types/action-map.ts` 同步
- Canonical block schema — 见 [block-system.md](design/block-system.md) 与 [block-api.md](block-api.md)；前端 `Workflow` 类型定义在 `src/types/workflow.ts`
- ADR-001：JSON 工作流直接解释执行，不再走 DSL（`sidecar/dsl/` 弃用）

---

## 相关文档

- [设计决策记录（ADR）](./design/decisions.md)
- [Block 体系设计](./design/block-system.md)
- [Block API 参考](./block-api.md)
- [数据流](./design/data-flow.md)
- [Transform 层](./design/transform-layer.md)
- [调试系统](./design/debug-system.md)
- [元素选择器](./design/element-selector.md)
- [项目结构](./project-structure.md)
- [开发 CLI](./dev-cli.md)
- [LLM 互动指南](./llm-interactive-guide.md)
- [并行 Agent](./parallel-agents.md)

# 项目结构 — Mimicry

> 仓库内每个目录与重要文件的清单。与 `docs/architecture.md`（讲模块职责）和 `README.md`（一屏项目树）配套使用。
>
> 最近一次盘点：2026-05-02。目录有变动时请同步更新本文件。

---

## 顶层布局

```
Mimicry/
├── .claude/         Claude Code 配置：agents、skills、hooks
├── .github/         GitHub Actions、Copilot 配置、prompt/skill 镜像
├── .trellis/        Trellis 任务系统：脚本、规范、任务、工作区、worktree
├── .vscode/         VS Code 的 MCP 配置
├── .pytest_cache/   pytest 缓存（gitignored，运行时产生）
├── dist/            Vite 构建输出（gitignored，运行时产生）
├── node_modules/    pnpm 安装产物（gitignored）
├── docs/            项目文档、设计 ADR、计划、调研
├── examples/        Demo 工作流 + 用于调研的外部项目克隆
├── key/             Tauri 自动更新签名密钥（gitignored）
├── public/          Vite 静态资源（favicon 等）
├── scripts/         跨层构建/校验脚本
├── shared/          跨层契约文件（action-map.json）
├── sidecar/         Python 自动化 sidecar（Camoufox + 工作流引擎 + RPC + MCP）
├── src/             Vue 3 前端（编辑器画布、JSON 编辑器、stores）
├── src-tauri/       Rust 核（Tauri 命令、SQLite、sidecar 管理、IPC）
├── AGENTS.md        多平台 agent 调度手册
├── CHANGELOG.md     版本历史（每个 vX.Y.Z tag 的发布说明）
├── CLAUDE.md        Claude Code 项目指南（每次会话自动注入）
├── README.md        项目首页
├── check.bat        Windows 便捷脚本：跑 typecheck + lint + tests
├── eslint.config.js ESLint flat 配置
├── index.html       Vite 入口 HTML（Tauri WebView 宿主）
├── package.json     前端 manifest + script 目标；锁定 pnpm 版本
├── pnpm-lock.yaml   pnpm 锁文件
├── tsconfig.json    src/ 的 TS 配置
├── tsconfig.node.json vite.config.ts 等工具的 TS 配置
├── vite.config.ts   Vite + Tauri 集成配置
└── .gitignore .prettierrc
```

---

## 根目录文件

| 文件 | 用途 |
|---|---|
| `AGENTS.md` | 多平台 agent 调度协议——`trellis-implement` / `trellis-check` / `trellis-research` 各阶段在不同平台（Claude Code、Cursor、Codex、Gemini 等）由谁来跑。 |
| `CHANGELOG.md` | 每个版本的变更说明。CI 要求 tag 必须有匹配的 `## vX.Y.Z` 段才能发版。 |
| `CLAUDE.md` | Claude Code 项目指南，每次会话自动加载。包含：技术栈摘要、常用命令、sidecar 三入口图、关键约定、Trellis 工作流入口。 |
| `README.md` | 公开首页：安装、快速上手、MCP 接线、技术栈、架构图、项目树、贡献、致谢、许可/伦理声明。 |
| `check.bat` | Windows 批处理便捷命令：`pnpm typecheck && pnpm lint && pnpm test`。 |
| `eslint.config.js` | `src/` 的 flat-config ESLint（Vue + TS 规则）。 |
| `index.html` | Vite/Tauri WebView 入口（挂载 `src/main.ts`）。 |
| `package.json` | 前端 manifest。`packageManager: pnpm@10.12.1` 强制锁定。脚本：`dev`、`build`、`typecheck`、`lint`、`format`、`test`、`test:watch`。 |
| `pnpm-lock.yaml` | pnpm 锁文件（约 10 万行）。 |
| `tsconfig.json` | `src/` 的严格模式 TS 配置。允许 `_` 前缀的未用参数。 |
| `tsconfig.node.json` | 工具脚本（`vite.config.ts`）的 TS 配置。 |
| `vite.config.ts` | Vite + `@vitejs/plugin-vue` + Tauri 强制要求的端口 1420。 |
| `.gitignore` | 忽略日志、缓存、构建产物、签名密钥、sidecar 构建产物、外部 example 克隆、Trellis worktree。 |
| `.prettierrc` | Prettier 规则。 |

---

## `.claude/` — Claude Code 项目配置

| 路径 | 用途 |
|---|---|
| `agents/` | 项目级子代理定义：`trellis-check.md`、`trellis-implement.md`、`trellis-research.md`。Claude Code 调度子代理时加载。 |
| `commands/trellis/` | 自定义斜杠命令目录。 |
| `hooks/` | `inject-subagent-context.py`、`inject-workflow-state.py`、`session-start.py`、`statusline.py`——Claude Code 在会话/回合边界调用的钩子。 |
| `skills/` | 项目 skill 包：`trellis-before-dev`、`trellis-brainstorm`、`trellis-break-loop`、`trellis-check`、`trellis-update-spec`。 |
| `settings.json` | Claude Code 设置（权限、env）。 |

---

## `.github/` — CI + 多平台 agent 配置

| 路径 | 用途 |
|---|---|
| `workflows/pipeline.yml` | 主 CI：lint、typecheck、tests、版本三联锁校验、action-map 同步校验。 |
| `workflows/release.yml` | `vX.Y.Z` tag 触发的发布管线 → 构建 Tauri 包、签名、发布到 GitHub Release。 |
| `instructions/` | GitHub Copilot 的分包编码指引：`python-sidecar`、`rust-backend`、`vue-frontend`。 |
| `agents/` | Trellis 子代理定义在非 Claude 平台的镜像。 |
| `copilot/` | Copilot 专用钩子 + 配置（`hooks/`、`hooks.json`）。 |
| `copilot-instructions.md` | 仓库级 Copilot 系统提示词。 |
| `hooks/trellis.json` | 通用钩子清单，给会读它的编辑器使用。 |
| `prompts/` | `continue.prompt.md`、`finish-work.prompt.md`——斜杠提示词定义。 |
| `skills/` | Trellis skill 在依赖 `.github/` 平台的镜像。 |
| `PULL_REQUEST_TEMPLATE.md` | 默认 PR 描述模板。 |

---

## `.trellis/` — Trellis 任务系统

| 路径 | 用途 |
|---|---|
| `config.yaml` | 项目级 Trellis 设置（commit message、journal 行数上限等）。 |
| `workflow.md` | 权威的阶段定义（Plan → Execute → Finish）、状态机、各平台 skill 路由。 |
| `scripts/` | CLI 工具：`task.py`（create/start/finish/archive/worktree/list）、`add_session.py`、`init_developer.py`、`get_context.py`、`get_developer.py`。 |
| `scripts/common/` | 共享 Python 模块：`cli_adapter.py`、`config.py`、`developer.py`、`git.py`、`git_context.py`、`io.py`、`log.py`、`packages_context.py`、`paths.py`、`session_context.py`、`task_context.py`、`task_queue.py`、`task_store.py`、`task_utils.py`、`tasks.py`、`types.py`、`workflow_phase.py`、`worktree.py`。 |
| `scripts/hooks/linear_sync.py` | 可选的 Linear 工单同步钩子。 |
| `spec/cross-layer/` | 跨层契约：`block-schema.md`、`code-generators.md`、`parallel-development.md`，以及 `index.md`。 |
| `spec/frontend/` | 前端规范：`component-guidelines.md`、`directory-structure.md`、`hook-guidelines.md`、`quality-guidelines.md`、`state-management.md`、`type-safety.md`，以及 `index.md`。 |
| `spec/guides/` | 跨包思维指南：`code-reuse-thinking-guide.md`、`cross-layer-thinking-guide.md`、`parallel-task-thinking-guide.md`，以及 `index.md`。 |
| `tasks/` | 每个任务一个 `MM-DD-name/` 目录，含 `prd.md`、`implement.jsonl`、`check.jsonl`、`task.json`，可选 `research/`、`info.md`。当前顶层 17 个活动目录（见下表）。 |
| `tasks/archive/2026-04/` | 已归档的 4 月任务（2 个）：`04-27-block-schema-unification`、`04-28-04-28-block-execution-fix`。 |
| `tasks/archive/2026-05/` | 已归档的 5 月任务（19 个）：5/1 当天集中归档了 12 个完成任务（含 `04-27-docs-reality-alignment` / `04-27-readme-positioning` / `04-27-sidecar-rpc-spec` / `04-27-profile-isolation-mvp` / `04-28-tab-identification-system` / `04-28-block-anti-detection-overhaul` / `04-28-workflow-branch-tab-validator` / `04-28-workflow-interchange-layer` / `05-01-mcp-cli-camoufox-gap-analysis` / `05-01-mcp-gap-followup` / `05-01-parallel-protocol-peer` / `05-01-parallel-worktrees-protocol` / `05-01-project-structure-cleanup` / `05-01-readme-clippy-style` / `05-01-ci-mcp-captcha` / `04-30-04-30-research-external-projects` / `04-27-browser-config` / `04-27-ci-pipeline-fix` / `00-bootstrap-guidelines`）。 |
| `workspace/` | 各开发者的会话日志目录。`index.md`（跨开发者索引）+ `<开发者名>/journal-N.md`。当前有 `zwx19990307/`。 |
| `worktrees/` | 默认空，由 `task.py worktree create` 在并行任务时填充（每个目录是独立的 git 检出）。已 gitignored。（注意：`peer-demo` worktree 已注册，文件位于 `.trellis/worktrees/peer-demo/`。） |

### 当前 `.trellis/tasks/` 下活动任务目录（2026-05-02）

```
04-28-block-doc-update                   （planned；docs/block-api.md canonical 升级）
04-28-i18n-log-normalization             （planned；日志中英混合规范化）
04-28-log-panel-enhancement              （planned；BottomPanel 复制日志按钮）
05-02-docs-refresh-audit                 （in_progress；本任务）
```

> 5/1 当天通过 `archive` 命令把已完成的任务批量归档到 `archive/2026-05/`。当前活动队列只剩 4 个任务。

---

## `.vscode/`

| 文件 | 用途 |
|---|---|
| `mcp.json` | VS Code 的 MCP 服务注册，让编辑器能通过 MCP 协议跟 Mimicry sidecar 对话。 |

---

## `docs/` — 项目文档

| 路径 | 用途 |
|---|---|
| `README.md` | 文档站点的镜像首页。 |
| `README.zh-CN.md` | 中文 README。 |
| `architecture.md` | 模块图、IPC 布局、sidecar 三入口模式（含 Partial / Implemented / Planned 现状标注）。 |
| `anti-detection.md` | Camoufox 反检测特性说明。 |
| `block-api.md` | 工作流节点的 Block JSON API 契约。 |
| `cicd-guide.md` | CI/CD 管线参考。 |
| `dev-cli.md` | CLI 用法参考：`dev_cli.py`（旧版）和 `cli.py + daemon.py`（当前）。 |
| `llm-interactive-guide.md` | LLM agent 通过 CLI / MCP 操控浏览器的常见模式。 |
| `pseudocode-spec.md` | ADR-001 之前的 DSL 伪代码设计（已被淘汰，留作历史）。 |
| `banner.png` | README 横幅图。 |
| `design/` | ADR + 各系统设计文档（见下）。 |
| `plans/` | 上一代（pre-Trellis）的规划文档（见下）。 |
| `research/` | 工具/生态调研产出（见下）。 |
| `workflow/` | 工作流编辑器设计文档（见下）。 |
| `img/` | 文档用截图（`PixPin_*.png`、`image.png`）。 |

### `docs/design/`

| 文件 | 用途 |
|---|---|
| `decisions.md` | 6 条 ADR：001 JSON 直驱、002 选择器多策略、003 Loop+Breakpoint、004 三层调试、005 Block 级错误配置、006 Package 系统。 |
| `block-system.md` | Canonical Block JSON schema（跨层契约）。 |
| `data-flow.md` | Block 节点之间的数据流（变量、作用域）。 |
| `debug-system.md` | 三层调试设计（断点、步进、观察）。 |
| `element-selector.md` | 多策略选择器 + 自愈设计。 |
| `package-system.md` | Block 打包（视觉封装 + 可展开调试）。 |
| `transform-layer.md` | Vue Flow / canonical / legacy / compact 四种工作流格式间的转换。 |
| `ui-description.md` | UI 结构描述语言。 |

### `docs/plans/`

5 份 pre-Trellis 时代的规划文档。当前 README/CLAUDE.md/architecture.md 都没有引用（仅 `mimicry-mvp.md` 被一份归档调研文档引用）。留在磁盘上作为历史记录。

| 文件 | 大小 |
|---|---|
| `2026-04-17-browser-integration.md` | 20 KB |
| `2026-04-20-phase1-stabilization.md` | 35 KB |
| `2026-04-20-phase2-features.md` | 74 KB |
| `mimicry-mvp.md` | 9 KB |
| `p1-core-operations.md` | 22 KB |

### `docs/research/`

| 文件 | 用途 |
|---|---|
| `anti-detection-landscape-2026.md` | 2026 年反检测工具生态调研（Camoufox、undetected-chromedriver 等）。 |
| `external-projects-analysis.md` | 与克隆的外部项目（`HeadlessX`、`WebAI2API` 等）的详细对比——由一个已归档的调研任务产出。 |
| `llm-cli-architecture.md` | LLM 驱动 CLI 工具的架构调研（影响了三入口 sidecar 设计）。 |
| `solution-comparison.md` | Block 体系的方案对比（被 ADR / block-system.md 引用）。 |

### `docs/workflow/`

| 文件 | 用途 |
|---|---|
| `canvas-interaction.md` | Vue Flow 画布交互模型设计（拖拽、吸附、分组）。 |
| `monaco-integration.md` | Monaco JSON 编辑器集成设计（schema、双向同步）。 |

---

## `examples/`

| 路径 | 用途 |
|---|---|
| `external/`（gitignored） | 用于参考的外部项目克隆：`HeadlessX`、`WebAI2API`、`camoufox-mcp`、`camoufox-reverse-mcp`、`playwright-captcha`。归档调研任务用过；不属于源码树。 |

---

## `key/`（gitignored）

Tauri 自动更新签名密钥：`private`、`public`。用于给更新包签名（auto-update 功能）。不入库；如缺失可用 `tauri signer generate` 重建。

---

## `public/`

Vite/Tauri 直接 serve 的静态资源。

| 文件 | 用途 |
|---|---|
| `tauri.svg` | Tauri logo（默认脚手架）。 |
| `vite.svg` | Vite logo（默认脚手架）。 |

---

## `scripts/`

| 文件 | 用途 |
|---|---|
| `sync-action-map.py` | 跨层契约校验器。读 `shared/action-map.json`，验证 `src/types/action-map.ts` 和 `sidecar/engine/action_map.py` 都同步了。CI 会跑。 |

---

## `shared/`

| 文件 | 用途 |
|---|---|
| `action-map.json` | 前端 action 名 ↔ 后端 RPC 方法名映射的唯一来源。跨层契约——改动后要跑 `scripts/sync-action-map.py`。 |

---

## `sidecar/` — Python 自动化 sidecar

三种入口模式共享 `browser/actions.py` + `rpc/methods.py`：
1. Tauri stdio JSON-RPC → `main.py`
2. CLI + UDS daemon → `cli.py` + `daemon.py`
3. MCP stdio server → `mcp_server.py`

| 文件 / 目录 | 用途 |
|---|---|
| `main.py` | 入口分发器（50 行）。按 flag 选择模式：默认 stdio JSON-RPC、`--mcp`、`--daemon`。 |
| `cli.py` | CLI 客户端（525 行，当前主路径）。通过 UDS 跟 `daemon.py` 通信。约 25 个子命令。`--mcp` 启动 MCP server。 |
| `daemon.py` | CLI 模式的 UDS daemon 后端（392 行）。Socket 路径 `/tmp/mimicry-{uid}.sock`。 |
| `dev_cli.py` | 老开发 CLI（450 行）——绕过 Tauri 直接操控 sidecar 组件。带 REPL、`anti-detect` 跑分、`blocks-test`。被 `cli.py` 取代，逐步收敛中。 |
| `mcp_server.py` | MCP stdio 服务器（262 行）。把 `@rpc_method` 注册表自动映射为 MCP 工具（当前注册 71 个 method，扣除 `test.*` 过滤后即 MCP 工具数）。 |
| `fetch_browser.py` | Camoufox fetch 包装器。注入 `GITHUB_TOKEN` 鉴权头（避开速率限制），并把进度以 JSON 行输出给 Tauri UI。 |
| `SKILL.md` | 给 LLM agent 的 skill 文档：怎么通过 Mimicry CLI 驱动真实浏览器。 |
| `pyproject.toml` | sidecar Python 包元数据。 |
| `requirements.txt` | 运行时依赖。 |
| `requirements-dev.txt` | 开发/测试依赖（pytest 等）。 |
| `mimicry-sidecar.spec` | PyInstaller 单文件打包 spec。 |
| `daemon.log` | 运行时日志（gitignored）。 |
| `mimicry-sidecar.log` | 运行时日志（gitignored）。 |
| `__pycache__/` | Python 字节码缓存（gitignored）。 |
| `.pytest_cache/` | pytest 状态（gitignored）。 |

### `sidecar/browser/`

| 文件 | 用途 |
|---|---|
| `__init__.py` | Package 标识。 |
| `actions.py` | Action 适配层——三入口模式共用的唯一分发面。 |
| `controller.py` | Camoufox 生命周期（启动/关闭），Playwright BrowserContext 持有方。 |
| `env_check.py` | 启动前的环境与依赖健康检查。 |
| `profile.py` | Profile 加载：每 profile 独立 `user_data_dir`、proxy、OS target、浏览器配置。 |
| `recorder.py` | DOM 事件捕获 → 动作流（编辑器的录制功能用这个）。 |

### `sidecar/captcha/`

| 文件 | 用途 |
|---|---|
| `__init__.py` | Package 标识。 |
| `cloudflare.py` | Cloudflare Turnstile / Interstitial click solver。改编自 `techinz/playwright-captcha`（文件头标注了上游 commit）。 |

### `sidecar/dsl/`

DSL 伪代码层。**已被 ADR-001 淘汰**（工作流是 JSON 节点图，不是 DSL）。仅保留作参考；当前只剩 `dev_cli.py` 和 `tests/test_dsl.py` 还引用它。

| 文件 | 用途 |
|---|---|
| `__init__.py` | Package 标识。 |
| `ast_nodes.py` | AST 节点类型。 |
| `compiler.py` | 把 DSL 编译成工作流 JSON。 |
| `lexer.py` | 词法分析器。 |
| `parser.py` | 语法分析器。 |
| `rpc_methods.py` | DSL 相关的 RPC 方法（注册进 RPC registry——内部用）。 |

### `sidecar/engine/`

| 文件 | 用途 |
|---|---|
| `__init__.py` | Package 标识。 |
| `executor.py` | 工作流 JSON 解释器——遍历节点图、分发动作、管理变量。 |
| `executor_state.py` | 暂停 / 单步 / 断点 / 注入动作的运行时状态（调试用）。 |
| `action_map.py` | `shared/action-map.json` 的 Python 侧镜像；CI 同步。 |
| `condition_parser.py` | `Condition` 和 `WhileLoop` Block 用的布尔 / 表达式解析器。 |

### `sidecar/rpc/`

| 文件 | 用途 |
|---|---|
| `__init__.py` | Package 标识。 |
| `server.py` | stdio JSON-RPC 服务（`main.py` Tauri-sidecar 模式用）。 |
| `methods.py` | 方法注册表——RPC 方法的唯一来源。MCP 服务器从这里自动映射工具。 |
| `protocol.py` | 长度前缀帧协议（`daemon.py` ↔ `cli.py` 通过 UDS 用，跟 stdio JSON-RPC 是两回事）。 |

### `sidecar/utils/`

目前几乎是空的。

| 文件 | 用途 |
|---|---|
| `__init__.py` | Package 标识。 |

### `sidecar/tests/`

pytest 测试。开发期残留的 `_*.py` 调研脚本、`screenshots/`、`e2e_*.txt`、`demo_*.json` 等已在 5/1 仓库清理（commit `15efc28`）中删除。

| 文件 | 测试内容 |
|---|---|
| `test_action_map.py` | Action map 一致性。 |
| `test_anti_detect.py` | 反检测引擎冒烟。 |
| `test_blocks_e2e.py` | Block 端到端执行。 |
| `test_captcha_cloudflare.py` | Cloudflare Turnstile click solver。 |
| `test_cli.py` | CLI 接口。 |
| `test_condition_parser.py` | 布尔表达式解析器。 |
| `test_dsl.py` | 已弃用的 `dsl/` 模块的测试。 |
| `test_env_check.py` | 环境检查。 |
| `test_executor.py` | 工作流执行器（最大测试文件）。 |
| `test_executor_init_scripts.py` | Launch flush + init_scripts 注入回归。 |
| `test_google_search.py` | Google 搜索 e2e（重型）。 |
| `test_mcp_descriptions.py` | MCP method 描述完整性 + isError 协议。 |
| `test_rpc.py` | RPC 方法注册表。 |
| `conftest.py` | pytest fixtures。 |

---

## `src/` — Vue 3 前端

| 路径 | 用途 |
|---|---|
| `main.ts` | App 入口：创建 Vue app、挂 Pinia、i18n、Vue Router，把 `App.vue` 挂到 `#app`。 |
| `App.vue` | 根布局。引入 `CamoufoxSetup`、`UpdateNotifier`、`ProfileManager`。 |
| `i18n.ts` | vue-i18n 初始化（加载 `locales/en.json`、`locales/zh-CN.json`）。 |
| `themes.ts` | 主题 token。 |
| `styles.css` | 全局 Tailwind 指令 + CSS 变量。 |
| `vite-env.d.ts` | Vite 环境类型。 |
| `assets/` | 静态图：`mimicry-logo.svg`、`vue.svg`。 |
| `locales/` | i18n：`en.json`、`zh-CN.json`。 |
| `views/` | 页级组件：`EditorView.vue`、`SettingsView.vue`。 |
| `components/` | 复用组件——见下。 |
| `composables/` | 组合式 API hook：`useFileOps.ts`、`useKeyboardShortcuts.ts`、`usePanel.ts`、`useShortcutToast.ts`。 |
| `stores/` | Pinia stores：`browser.ts`、`execution.ts`、`profiles.ts`、`settings.ts`、`validation.ts`、`workflow.ts`、`workspace.ts`。 |
| `types/` | 跨层 TS 类型：`action-map.ts`（`shared/action-map.json` 的镜像）、`ipc.ts`、`workflow.ts`。 |
| `utils/` | `workflowSchema.ts` + `__tests__/workflowSchema.test.ts`。 |

### `src/components/`

根级（4 个）：`CamoufoxSetup.vue`、`ProfileDialog.vue`、`ProfileManager.vue`、`UpdateNotifier.vue`。

子目录：

| 子目录 | 文件 |
|---|---|
| `editor/` | `BottomPanel.vue`、`ContextMenu.vue`、`JsonEditor.vue`（Monaco 包装）、`PropertyPanel.vue`、`RecordingPreview.vue`。 |
| `layout/` | `ActivityBar.vue`、`MainLayout.vue`、`Sidebar.vue`、`TabBar.vue`、`Toolbar.vue`。 |
| `nodes/` | Vue Flow 节点组件：`ActionNode.vue`、`ConditionNode.vue`、`GroupNode.vue`、`LoopNode.vue`。 |
| `ui/` | 通用 UI：`SetupDialog.vue`、`ShortcutToast.vue`。 |

---

## `src-tauri/` — Rust 核（Tauri 外壳）

| 路径 | 用途 |
|---|---|
| `Cargo.toml` | Rust manifest——版本与 `package.json`、`tauri.conf.json` 三联锁。 |
| `Cargo.lock` | Rust 锁文件。 |
| `tauri.conf.json` | Tauri shell 配置：窗口大小、identifier、sidecar 二进制注册、updater 配置。 |
| `build.rs` | Tauri 构建脚本。 |
| `capabilities/default.json` | Tauri v2 capability（哪些 IPC 命令被允许）。 |
| `gen/schemas/` | 生成的 capability schema（`acl-manifests.json`、`capabilities.json`、`desktop-schema.json`、`linux-schema.json`）。Gitignored——Tauri 构建时重新生成。 |
| `icons/` | 全平台 app 图标（Windows `.ico`、macOS `.icns`、Linux/Android/iOS 多尺寸 PNG，加 `app-icon.svg`）。 |
| `binaries/` | 各 target triple 下的捆绑 sidecar 二进制。当前有 `mimicry-sidecar-x86_64-pc-windows-msvc.exe`。 |
| `tests/transform_integration.rs` | 工作流 transform 层的 Rust 集成测试。 |
| `logs/` | App 日志（按天滚动）：`mimicry.log.2026-04-26` 至 `mimicry.log.2026-05-01`。**注意**：父级还有一份 `src-tauri/mimicry-sidecar.log`——sidecar 继承了错误的 CWD 写出来的。 |
| `mimicry-sidecar.log` | 错位的 sidecar 日志（gitignored，见上）。 |
| `mimicry.db` | SQLite DB（gitignored）。运行时 DB 在系统 app-data 目录；这份是开发跑分时 CWD 错位留下的。 |
| `target/` | Cargo 构建输出（gitignored）。 |
| `src/` | Rust 源码——见下。 |

### `src-tauri/src/`

| 文件 | 用途 |
|---|---|
| `main.rs` | 二进制入口：调用 `lib::run()`。 |
| `lib.rs` | Tauri builder 装配：注册命令、插件（updater、fs、dialog）、状态、sidecar 解析器。 |
| `error.rs` | 跨命令使用的全局 `Error` 枚举。 |
| `logger.rs` | `tracing` 装配，按天滚动文件 appender。 |
| `workflow_validator.rs` | 工作流节点图的 JSON-schema 风格校验器。 |
| `commands/` | Tauri 命令处理器——前端通过 `invoke()` 调用。 |
| `db/` | SQLite 访问——schema + 各表模块。 |
| `ipc/` | Sidecar 进程管理 + JSON-RPC 客户端。 |
| `transform/` | 工作流格式转换（4 种表示）。 |

### `src-tauri/src/commands/`

| 文件 | 用途 |
|---|---|
| `mod.rs` | re-export。 |
| `browser.rs` | 浏览器相关命令（启动、导航、截图、关闭）。 |
| `file_ops.rs` | 文件打开/保存对话框、recent-files。 |
| `profiles.rs` | Profile 增删改查。 |
| `system.rs` | OS 级信息（路径、app data 目录）。 |
| `workflow.rs` | 工作流增删改查 + run/stop/pause 转发给 sidecar。 |

### `src-tauri/src/db/`

| 文件 | 用途 |
|---|---|
| `mod.rs` | 连接池 + 模块 re-export。 |
| `schema.rs` | DB schema 初始化。表：`workflows`、`settings`、`recent_files`、`profiles`。 |
| `workflow.rs` | workflows 表访问。 |
| `profiles.rs` | profiles 表访问。 |
| `recent_files.rs` | recent_files 表访问。 |

### `src-tauri/src/ipc/`

| 文件 | 用途 |
|---|---|
| `mod.rs` | re-export。 |
| `sidecar.rs` | Sidecar 进程 spawn / 生命周期 / stdio 管道。 |
| `jsonrpc.rs` | stdio 上的 JSON-RPC 2.0 客户端。 |

### `src-tauri/src/transform/`

| 文件 | 用途 |
|---|---|
| `mod.rs` | 格式转换的公开 API。 |
| `types.rs` | 4 种工作流表示的共享类型。 |
| `detect.rs` | 检测一份输入 JSON 是哪种格式。 |
| `legacy.rs` | 旧版 Vue Flow 格式 ↔ canonical。 |
| `compact.rs` | Compact（树状）↔ canonical。 |
| `backend.rs` | 后端侧的归一化。 |
| `action_map.rs` | 按跨层 action map 解析 action 名。 |
| `layout.rs` | 自动布局（Dagre 驱动），用于画布展示。 |

---

## 磁盘上可见的开发/运行时产物

不属于源码，由工具产生。全部 gitignored。

| 路径 | 产生者 |
|---|---|
| `node_modules/` | pnpm install。 |
| `dist/` | `pnpm build` / Vite。 |
| `src-tauri/target/` | `cargo build`。 |
| `src-tauri/gen/` | Tauri 构建（capability schema）。 |
| `src-tauri/logs/` | App `tracing` logger。 |
| `src-tauri/mimicry-sidecar.log` | CWD = `src-tauri/` 时 sidecar 写错位置的日志。 |
| `src-tauri/mimicry.db` | CWD = `src-tauri/` 时写错位置的开发 SQLite DB。 |
| `sidecar/__pycache__/`、`sidecar/<子模块>/__pycache__/`（×9） | Python 字节码。 |
| `.pytest_cache/`、`sidecar/.pytest_cache/` | pytest 状态。 |
| `sidecar/daemon.log`、`sidecar/mimicry-sidecar.log` | sidecar 运行时残留。 |
| `key/private`、`key/public` | Tauri 自动更新密钥。 |
| `examples/external/` | 调研用的外部项目克隆。 |
| `.trellis/worktrees/` | Trellis 并行开发 worktree（每个目录是独立 git 检出）。 |

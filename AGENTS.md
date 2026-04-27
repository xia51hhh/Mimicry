<!-- TRELLIS:START -->
# Trellis Instructions

These instructions are for AI assistants working in this project.

Use the `/trellis:start` command when starting a new session to:
- Initialize your developer identity
- Understand current project context
- Read relevant guidelines

Use `@/.trellis/` to learn:
- Development workflow (`workflow.md`)
- Project structure guidelines (`spec/`)
- Developer workspace (`workspace/`)

If you're using Codex, project-scoped helpers may also live in:
- `.agents/skills/` for reusable Trellis skills
- `.codex/agents/` for optional custom subagents

Keep this managed block so 'trellis update' can refresh the instructions.

<!-- TRELLIS:END -->

# Mimicry — AI Agent Guidelines

## What Is This Project

Mimicry 是一款跨平台浏览器自动化桌面应用（Tauri v2），内置 Camoufox 反检测浏览器引擎，支持可视化工作流编辑、录制回放与 JSON 直驱执行。

## Architecture

三层架构，两种 IPC：

```
Vue 3 WebView ──invoke()/emit()──► Rust Core ──stdio JSON-RPC 2.0──► Python Sidecar
```

- **前端** (`src/`): Vue 3 + TypeScript + Pinia + Vue Flow + Monaco Editor
- **后端** (`src-tauri/src/`): Rust — Tauri commands, SQLite (rusqlite), Sidecar 进程管理
- **Sidecar** (`sidecar/`): Python — Camoufox/Playwright 浏览器控制, JSON-RPC 服务端, 工作流执行引擎

详细架构见 [docs/architecture.md](docs/architecture.md)，设计决策见 [docs/design/decisions.md](docs/design/decisions.md)。

## Build & Dev Commands

| Layer | Command | Purpose |
|-------|---------|---------|
| Frontend | `pnpm dev` | Vite 开发服务器 (port 1420) |
| Frontend | `pnpm build` | `vue-tsc --noEmit && vite build` |
| Frontend | `pnpm lint` | ESLint (src/) |
| Frontend | `pnpm format` | Prettier 格式化 |
| Frontend | `pnpm typecheck` | `vue-tsc --noEmit` |
| Rust | `cargo tauri dev` | 全栈开发联调 |
| Rust | `cargo clippy --all-targets --all-features -- -D warnings` | Lint |
| Rust | `cargo test --all-targets --all-features` | 测试 |
| Sidecar | `pip install -r sidecar/requirements-dev.txt` | 安装依赖 |
| Sidecar | `python -m pytest sidecar/tests/ -v` | 测试 |

## Key Conventions

- **包管理器**: pnpm（`packageManager` 字段锁定 `pnpm@10.12.1`）
- **版本一致性**: `package.json` / `tauri.conf.json` / `Cargo.toml` 三端版本必须相同（CI 强制）
- **Vue 组件**: 全部使用 `<script setup lang="ts">` Composition API，无 Options API
- **Pinia Store**: 使用 `defineStore("name", () => { ... })` setup 语法
- **ESLint**: Flat config (v9)，允许单词组件名，`any` 为 warn，忽略 `_` 前缀参数
- **TypeScript**: 严格模式 (`strict: true`, `noUnusedLocals`, `noUnusedParameters`)
- **国际化**: `vue-i18n`，locale 文件在 `src/locales/` (en.json, zh-CN.json)
- **DSL 已弃用**: `sidecar/dsl/` 保留代码但不再使用，ADR-001 决定 JSON 直驱取代 DSL
- **Release**: tag `vX.Y.Z` 触发构建，CHANGELOG.md 须含 `## vX.Y.Z` 标题

## Documentation

完整文档索引见 [docs/README.md](docs/README.md)，重点参考：

- [Block 体系](docs/design/block-system.md) — Block 分类、JSON Schema、连接规则
- [数据流](docs/design/data-flow.md) — WorkflowContext、变量系统
- [UI 描述](docs/design/ui-description.md) — 完整界面布局与交互
- [CI/CD 指南](docs/cicd-guide.md) — Pipeline 配置与发布流程

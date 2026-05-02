# Mimicry 项目文档中心

> **状态**: Reality-aligned（5/2 全量审计） | **最后更新**: 2026-05-02

Mimicry 是一款基于 Tauri v2 + Vue 3 + Python Sidecar 的跨平台浏览器自动化桌面应用，内置 Camoufox 浏览器自动化运行时，支持可视化工作流编辑、录制回放、隔离 Profile、JSON 直驱执行、完整调试 UI、71 个 RPC 方法（含 70+ 个 MCP 工具）。

> 说明：本文档目录同时包含"已实现能力"和"设计方向"。带 **Partial / Planned / Deferred** 标记的章节不应被理解为已完整交付。

---

## 📖 文档索引

### 状态标记

| 标记 | 含义 |
|------|------|
| Implemented | 当前代码已有主体实现 |
| Partial | 当前代码已有部分实现，但文档包含未完成设计 |
| Planned | 产品/架构方向，尚未完整落地 |
| Deferred | 暂缓或历史参考 |

### 概述与入口

| 文档 | 状态 | 说明 |
|------|------|------|
| [架构概览](./architecture.md) | Implemented | 三层架构、Tauri commands、71 个 RPC、sidecar 三入口、SQLite schema |
| [项目结构](./project-structure.md) | Implemented | 仓库每个目录与重要文件的清单（5/2 同步） |
| [Block API 参考](./block-api.md) | Implemented | 42 个 action 完整文档（canonical 格式） |

### 设计文档

| 文档 | 状态 | 说明 |
|------|------|------|
| [设计决策记录](./design/decisions.md) | Implemented + Active | 10 项 ADR：001 JSON 直驱 / 002 选择器多策略 / 003 Loop+Breakpoint / 004 三层调试（A/B/C 全实现）/ 005 Block 错误配置 / 006 Package / **007 Workflow Validator / 008 Transform 层 / 009 Sidecar 三入口 / 010 并行 Worktree** |
| [Block 体系设计](./design/block-system.md) | Partial | Block 分类、canonical Schema、init_scripts 注入 |
| [数据流设计](./design/data-flow.md) | Partial | WorkflowContext、变量、表达式；边驱动多输入合并仍为目标设计 |
| [Transform 层设计](./design/transform-layer.md) | Implemented | Rust 4 格式互转 + 自动布局（含 condition/loop 分支偏移） |
| [元素选择器设计](./design/element-selector.md) | Partial | 选择器自愈已实现（_resolve_selector），智能分析面板仍为目标 |
| [调试系统设计](./design/debug-system.md) | Implemented | 三层调试 A/B/C 全实现（断点 + 单步 + 实时观察 + Debug 面板 + 右键菜单 + F9/F5/F10） |
| [Package 系统设计](./design/package-system.md) | Planned | 视觉封装 / 端口绑定 / 库管理；当前可用 ExecuteWorkflow 近似 |
| [UI 设计描述](./design/ui-description.md) | Partial / Implemented | 顶栏 / 工具栏调试 / Tooltip / MiniMap / Problems 面板已实现 |

### 工作流编辑器

| 文档 | 状态 | 说明 |
|------|------|------|
| [画布交互设计](./workflow/canvas-interaction.md) | Partial / Implemented | 缩放平移 / 拖拽连线 / 快捷键 / 右键菜单 / MiniMap / Tooltip 已实现 |
| [Monaco Editor 集成](./workflow/monaco-integration.md) | Partial | JsonEditor.vue + Monaco v0.55.1，分屏与高级补全仍待打磨 |

### 开发指南

| 文档 | 状态 | 说明 |
|------|------|------|
| [CI/CD 指南](./cicd-guide.md) | Implemented | 单一 pipeline.yml 流水线 + 三方版本锁 + CHANGELOG 强制 |
| [反检测体系](./anti-detection.md) | Implemented | Camoufox 12 维指纹模型 + 行为模拟层 + 多 site 测试结果 |
| [Dev CLI 调试文档](./dev-cli.md) | Implemented | cli.py 主入口 + dev_cli.py 老版本 |
| [LLM 交互式开发指南](./llm-interactive-guide.md) | Implemented | LLM Agent 的 CLI/MCP 操控模式与排错降级 |
| [并行 Agent 协议](./parallel-agents.md) | Implemented | git worktree-based 并行任务隔离协议（task.py worktree） |

> **已归档 / Deferred**: [伪代码规范](./pseudocode-spec.md) 已弃用（ADR-001 JSON 直驱取代 DSL），仅作历史参考。

### 调研资料 / 计划（历史快照）

| 文档 | 说明 |
|------|------|
| [外部项目分析](./research/external-projects-analysis.md) | HeadlessX / WebAI2API / Camoufox-MCP 等的工程审计（5/1 调研） |
| [LLM CLI 架构调研](./research/llm-cli-architecture.md) | 三入口 sidecar 设计的源头依据 |
| [反检测生态 2026](./research/anti-detection-landscape-2026.md) | Camoufox / undetected-chromedriver 等生态调研 |
| [方案对比](./research/solution-comparison.md) | Automa / n8n / ComfyUI 方案分析（被 ADR / block-system 引用） |
| [MVP 实施计划](./plans/mimicry-mvp.md) | MVP 阶段任务拆分与里程碑（pre-Trellis 时代） |

---

## 技术栈一览

| 层 | 技术 |
|----|------|
| 桌面框架 | Tauri v2 (Rust) |
| 前端 | Vue 3 + Vite + Pinia + Tailwind v4 + vue-i18n |
| 画布 | Vue Flow（Dagre 自动布局，含 MiniMap） |
| 代码编辑 | Monaco Editor v0.55 |
| 浏览器引擎 | Camoufox（anti-detect Firefox） + Playwright |
| Sidecar | Python 3.10+ + PyInstaller |
| IPC | Tauri invoke/event + JSON-RPC 2.0 (stdio) + UDS (CLI daemon) + MCP (stdio) |
| 存储 | SQLite (rusqlite) |
| 日志 | tracing (Rust) / loguru (Python) |
| 验证码 | sidecar/captcha/cloudflare.py（Cloudflare Turnstile click solver） |

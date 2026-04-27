# Mimicry 项目文档中心

> **状态**: Draft / Reality-aligned | **最后更新**: 2026-04-27

Mimicry 是一款基于 Tauri v2 + Vue 3 + Python Sidecar 的跨平台浏览器自动化桌面应用，内置 Camoufox 浏览器自动化运行时，支持可视化工作流编辑、录制回放、隔离 Profile 和 JSON 直驱执行。

> 说明：本文档目录同时包含“已实现能力”和“设计方向”。带有 **Partial / Planned / Deferred** 标记的文档或章节不应被理解为当前已完整交付能力。

---

## 📖 文档索引

### 状态标记

| 标记 | 含义 |
|------|------|
| Implemented | 当前代码已有主体实现 |
| Partial | 当前代码已有部分实现，但文档描述包含未完成设计 |
| Planned | 产品/架构方向，尚未完整落地 |
| Deferred | 暂缓或历史参考 |

### 概述

| 文档 | 状态 | 说明 |
|------|------|------|
| [架构概览](./architecture.md) | Partial | 整体架构、技术栈、模块关系、IPC 通信；部分打包/日志持久化能力仍在完善 |

### 设计文档

| 文档 | 状态 | 说明 |
|------|------|------|
| [设计决策记录](./design/decisions.md) | Partial | 6 项核心设计决策（ADR 格式），部分决策仍处于实现中 |
| [Block 体系设计](./design/block-system.md) | Partial | Block 分类、canonical JSON Schema、兼容规则；连接执行语义仍未完整落地 |
| [数据流设计](./design/data-flow.md) | Planned | WorkflowContext、变量系统、表达式引用和节点 IO 的目标设计 |
| [元素选择器设计](./design/element-selector.md) | Partial | 录制/选择器基础已有，智能分析与自愈机制仍为规划方向 |
| [调试系统设计](./design/debug-system.md) | Planned | 三层调试体系、Data Inspector、执行日志的目标设计 |
| [Package 系统设计](./design/package-system.md) | Planned | Block 封装复用、输入输出端口、存储格式的目标设计 |
| [UI 设计描述](./design/ui-description.md) | Partial | UI 方向描述；具体交互以当前 Vue 实现为准 |

### 工作流编辑器

| 文档 | 状态 | 说明 |
|------|------|------|
| [画布交互设计](./workflow/canvas-interaction.md) | Partial | 缩放平移、拖拽连线、快捷键、右键菜单；以现有组件实现为准 |
| [Monaco Editor 集成](./workflow/monaco-integration.md) | Partial | JSON 编辑已有，Schema 验证和双向同步仍需完善 |

### 开发指南

| 文档 | 状态 | 说明 |
|------|------|------|
| [CI/CD 指南](./cicd-guide.md) | Partial | 持续集成与部署配置；质量门禁仍在收敛 |

> **已归档 / Deferred**: [伪代码规范](./pseudocode-spec.md) 已弃用（ADR-001: JSON 直驱取代 DSL），仅作历史参考。

### 调研资料

| 文档 | 说明 |
|------|------|
| [方案对比](./research/solution-comparison.md) | Automa / n8n / ComfyUI 方案分析调研 |

### 计划

| 文档 | 说明 |
|------|------|
| [MVP 实施计划](./plans/mimicry-mvp.md) | MVP 阶段任务拆分与里程碑 |

---

## 技术栈一览

| 层 | 技术 |
|----|------|
| 桌面框架 | Tauri v2 (Rust) |
| 前端 | Vue 3 + Vite + TailwindCSS |
| 画布 | Vue Flow |
| 代码编辑 | Monaco Editor |
| 状态管理 | Pinia |
| 浏览器引擎 | Camoufox (Playwright) |
| Sidecar | Python + PyInstaller |
| IPC | JSON-RPC over stdio |
| 存储 | SQLite (rusqlite) |
| 日志 | tracing (Rust) / loguru (Python) |

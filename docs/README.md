# Mimicry 项目文档中心

> **状态**: Draft | **最后更新**: 2026-04-17

Mimicry 是一款基于 Tauri v2 + Vue 3 + Python Sidecar 的跨平台浏览器自动化桌面应用，内置 Camoufox 反检测浏览器引擎，支持可视化工作流编辑、录制回放与 JSON 直驱执行。

---

## 📖 文档索引

### 概述

| 文档 | 说明 |
|------|------|
| [架构概览](./architecture.md) | 整体架构、技术栈、模块关系、IPC 通信 |

### 设计文档

| 文档 | 说明 |
|------|------|
| [设计决策记录](./design/decisions.md) | 6 项核心设计决策（ADR 格式） |
| [Block 体系设计](./design/block-system.md) | Block 分类、JSON Schema、连接规则 |
| [数据流设计](./design/data-flow.md) | WorkflowContext、变量系统、表达式引用 |
| [元素选择器设计](./design/element-selector.md) | 多策略选择器、智能分析、自愈机制 |
| [调试系统设计](./design/debug-system.md) | 三层调试体系、Data Inspector、执行日志 |
| [Package 系统设计](./design/package-system.md) | Block 封装复用、输入输出端口、存储格式 |
| [UI 设计描述](./design/ui-description.md) | 完整 UI 布局、交互流程、视觉风格自然语言描述 |

### 工作流编辑器

| 文档 | 说明 |
|------|------|
| [画布交互设计](./workflow/canvas-interaction.md) | 缩放平移、拖拽连线、快捷键、右键菜单 |
| [Monaco Editor 集成](./workflow/monaco-integration.md) | JSON 编辑、Schema 验证、画布双向同步 |

### 开发指南

| 文档 | 说明 |
|------|------|
| [CI/CD 指南](./cicd-guide.md) | 持续集成与部署配置 |

> **已归档**: [伪代码规范](./pseudocode-spec.md) 已弃用（ADR-001: JSON 直驱取代 DSL），仅作历史参考。

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

# 设计决策记录（ADR）

> **状态**: Implemented（ADR-001/002/003/005/006）+ Partial（ADR-004 全功能）+ Active（ADR-007 至 ADR-010）| **最后更新**: 2026-05-02

本文档记录 Mimicry 项目的核心设计决策。每项决策采用 ADR（Architecture Decision Record）格式。

---

## ADR-001: Block 底层格式 — JSON 节点图直驱

### 背景

Mimicry 最初设计了一套 DSL 伪代码层（见 [pseudocode-spec.md](../pseudocode-spec.md)），作为工作流的中间表示。但在实际开发中发现 DSL 带来额外的解析/序列化成本，且与 LLM 的交互不如结构化 JSON 直接。

### 方案选项

| 方案 | 优点 | 缺点 |
|------|------|------|
| A. DSL 伪代码层 | 人类可读性好 | 解析复杂、与节点图双向转换有损 |
| B. JSON 节点图直驱 | 结构明确、LLM 友好、无中间损耗 | JSON 可读性略差 |
| C. YAML 描述层 | 可读性较好 | 同样需要解析，优势不明显 |

### 决策结果

**选择方案 B：JSON 节点图直驱执行**

### 理由

1. **去掉 DSL 伪代码层**，工作流底层统一为 JSON 节点图
2. **Monaco Editor 面向 LLM**：LLM 直接生成/修改结构化 JSON，无需学习自定义 DSL 语法
3. **Vue Flow 画布面向人类**：人类通过拖拽 Block、连线来构建工作流
4. **画布 ↔ JSON 双向实时转换**：编辑画布自动更新 JSON，编辑 JSON 自动更新画布
5. 消除 DSL 解析/序列化开销，减少 Bug 面

---

## ADR-002: 元素选择器 — 多策略 + 自愈

### 背景

浏览器自动化的核心痛点是元素定位的稳定性。网页结构经常变化，单一选择器策略容易失效。

### 方案选项

| 方案 | 优点 | 缺点 |
|------|------|------|
| A. 单一 CSS 选择器 | 实现简单 | 脆弱，易失效 |
| B. 多策略 + 手动编辑 | 更稳定 | 用户门槛高 |
| C. 多策略 + 自愈 + 智能分析面板 | 稳定且易用 | 实现复杂度高 |

### 决策结果

**选择方案 C：录制自动生成 + Block 内手动编辑 + 智能分析面板**

### 理由

三个触发入口：
1. **录制模式**：自动捕获用户操作，智能生成选择器
2. **Block 配置面板**：手动编辑选择器，实时测试匹配
3. **智能分析面板**：展示多策略选择器候选列表

选择器生成策略（优先级从高到低）：
- `text=` / `role=`（Playwright 原生语义定位）
- `id` / `data-testid` / `data-*`（稳定属性）
- `class` 组合
- `xpath` / `css path`（兜底）

配套机制：
- **唯一性检测**：检查选择器是否唯一匹配目标元素
- **稳定性评分**：基于选择器策略类型 + DOM 深度打分
- **快速操作按钮**：一键从选择器生成对应 Block
- **选择器自愈**：执行时主选择器失败，自动尝试备选策略

---

## ADR-003: 循环模型 — Loop + Breakpoint 配对

### 背景

工作流需要支持多种循环模式，参考 Automa 的 Loop + Breakpoint 配对模式和 n8n 的自动迭代模式。

### 方案选项

| 方案 | 优点 | 缺点 |
|------|------|------|
| A. 自动迭代（n8n 风格） | 简单 | 灵活度低 |
| B. Loop + Breakpoint 配对（Automa 风格） | 灵活、直观 | 需理解配对概念 |
| C. 纯代码循环 | 最灵活 | 失去可视化优势 |

### 决策结果

**选择方案 B：Loop + Breakpoint 配对（Automa 风格）**

### 理由

支持 4 种循环类型：

| 类型 | 说明 | 数据源 |
|------|------|--------|
| **Loop Data** | 遍历数据集合 | 变量 / JSON 数组 / 表格 |
| **Loop Elements** | 遍历页面元素 | CSS/XPath 匹配的元素列表 |
| **Repeat** | 固定次数重复 | 指定数字 N |
| **While Loop** | 条件循环 | 布尔表达式 |

每个 Loop Block 通过 `loopId` 与对应的 Breakpoint Block 配对，定义循环作用域。循环体内的 Block 在两者之间的连线路径上。

---

## ADR-004: 调试粒度 — 三层调试体系

### 背景

工作流调试需要不同粒度的观察能力，从快速预览到深度排查。

### 方案选项

| 方案 | 优点 | 缺点 |
|------|------|------|
| A. 仅执行日志 | 实现简单 | 排查效率低 |
| B. 断点 + 日志 | 基本够用 | 缺少实时观察 |
| C. 三层体系（观察/断点/步进） | 覆盖全场景 | 实现工作量大 |

### 决策结果

**选择方案 C：三层调试体系，MVP 先做 A + C 层**

### 理由

| 层级 | 代号 | 功能 | MVP | 当前状态（5/2） |
|------|------|------|-----|---|
| A | Block 级断点 | 在指定 Block 设置断点，运行至此暂停 | ✅ | ✅ Implemented（commit `7a459d6`：完整 UI 含断点指示器、Debug 面板、右键菜单） |
| B | 步进模式 | 逐 Block 单步执行，每步暂停 | ❌ | ✅ Implemented（commit `b9c4714`：Toolbar 暂停/继续/单步按钮 + F9/F5/F10 快捷键） |
| C | 实时观察 | 节点高亮执行状态 + 数据摘要浮窗 | ✅ | ✅ Implemented（commit `55f52ff`：连线流动动画 + 节点 Tooltip 数据摘要） |

MVP 阶段计划仅 A + C；实际 5/1 已把 B 一并补齐。Tauri commands `workflow_pause / unpause / step / set_breakpoint / remove_breakpoint / list_breakpoints / state / inject` 提供完整调试控制面；前端通过 `stores/execution.ts` 同步状态。

---

## ADR-005: 错误处理 — Block 级独立配置

### 背景

工作流执行中，不同 Block 对错误的容忍度不同。例如截图失败可继续，但登录失败必须停止。

### 方案选项

| 方案 | 优点 | 缺点 |
|------|------|------|
| A. 全局统一策略 | 简单 | 不够灵活 |
| B. Block 级独立配置 | 灵活精确 | 配置项多 |

### 决策结果

**选择方案 B：每个 Block 独立配置错误处理策略**

### 理由

每个 Block 的 `settings.onError` 支持以下策略：

| 策略 | 说明 |
|------|------|
| `inherit` | 继承父分组 / 工作流级设置（默认值） |
| `stop` | 停止整个工作流 |
| `continue` | 忽略错误，继续执行下一个 Block |
| `retry` | 重试当前 Block（配合 `retryCount` / `retryInterval`） |
| `fallback` | 走 fallback 边分支（`sourceHandle="fallback"`） |

完整的 `WorkflowNodeSettings` 字段（来自 `src/types/workflow.ts`）：

| 字段 | 说明 |
|---|---|
| `onError` | 上表 5 选 1 |
| `retryOnFail` | `onError: retry` 的 bool 简写 |
| `retryCount` | 重试次数（默认 3） |
| `retryInterval` | 重试间隔毫秒（默认 1000） |
| `note` | 节点注释（不参与执行） |
| `disabled` | 禁用此节点（执行跳过） |

---

## ADR-006: Package 系统 — 完整 Package

### 背景

工作流复杂化后，需要将一组 Block 封装为可复用的单元。

### 方案选项

| 方案 | 优点 | 缺点 |
|------|------|------|
| A. 简单分组（仅视觉） | 实现简单 | 无法复用 |
| B. 子工作流引用 | 可复用 | 无法内联查看/调试 |
| C. 完整 Package（视觉封装 + 可展开） | 可复用、可调试 | 实现最复杂 |

### 决策结果

**选择方案 C：完整 Package — 视觉打包为单节点，可展开查看/调试内部子 Block**

### 理由

1. **视觉封装**：多个 Block 打包后在画布上呈现为单个节点，减少视觉复杂度
2. **可展开**：双击 Package 节点可展开查看内部 Block 结构，支持调试
3. **底层透明**：执行引擎看到的仍是展平后的 Block 列表，执行逻辑不变
4. **自定义 IO**：Package 可定义输入/输出端口，作为独立 Block 使用
5. **复用机制**：Package 存入库中，可从库拖入其他工作流画布

---

## 相关文档

- [架构概览](../architecture.md)
- [Block 体系设计](./block-system.md)
- [数据流设计](./data-flow.md)
- [元素选择器设计](./element-selector.md)
- [调试系统设计](./debug-system.md)
- [Package 系统设计](./package-system.md)

---

## ADR-007: 工作流静态校验器（37 条规则）

### 背景

`workflow_execute` 在 dispatch 到 sidecar 之前需要发现结构性错误：缺 `id`、未定义的 `action`、悬空 edge、循环引用、`kind` / `data` 不匹配等。运行时报错虽可恢复，但用户体验差且可能产生副作用（已点击、已下载）。

### 决策结果

**实现 Rust 侧 `workflow_validator.rs`，37 条静态规则在 `workflow_execute` 前拦截。**

规则编码：`W001–W014`（Warning）+ `I001–I011`（Info）。规则结果在 IPC 回前端 `validation` store，BottomPanel.vue 的 Problems 面板列出错误，节点本身显示诊断徽标（commit `897b4e4`）。

### 后果

- Bug 在编辑期就拦下，避免无效执行
- Validator 是 sidecar 真正执行前的最后一道关卡，CI/CD 也复用该检查
- 新增 action 时需要同步更新 validator 与 `shared/action-map.json`

---

## ADR-008: Rust 工作流转化层

### 背景

工作流有 4 种合法表示：

| 格式 | 用途 |
|---|---|
| **Canonical** | 仓库 / 数据库 / 跨层契约（`{kind, action, data, settings}`） |
| **Backend** | sidecar 执行用（snake_case action 名） |
| **Compact** | 单文件持久化（树状嵌套，体积小） |
| **Legacy** | 旧 flat 格式 `{type, action, url}`，仅作迁移 |

格式间互转放在前端会跨语言反复实现，放在 sidecar 又会增加 Tauri 命令往返。

### 决策结果

**`src-tauri/src/transform/` 提供 4 格式互转 + 自动布局**，作为 Rust 侧公共组件，供 Tauri 命令 `workflow_transform_import / export_compact / detect_format` 调用，前端 `useFileOps` 通过 `invoke()` 使用。

转化层组件（5/1 升级了 layout）：

- `detect.rs` — 自动识别输入格式
- `legacy.rs` / `compact.rs` / `backend.rs` — 三方互转 ↔ canonical
- `layout.rs` — Dagre 自动布局，**支持 condition/loop 分支偏移**（commit `f064821`）
- `action_map.rs` — 解析 `shared/action-map.json` 的 Rust 引用

### 后果

- 前端文件 import / export / 多格式识别全部走 Rust，零冗余
- Compact 格式让单文件工作流尺寸缩小约 60%
- 自动布局让无坐标的导入文件直接在画布上呈现合理排版

---

## ADR-009: Sidecar 三种入口模式（共享内核）

### 背景

Sidecar 既要给 Tauri 应用用（stdio JSON-RPC），又要给 LLM agent / 开发者用（CLI），还要给 MCP 客户端用（stdio MCP）。三套实现会发散。

### 决策结果

**三入口共享 `browser/actions.py` + `rpc/methods.py`**：

1. `main.py` — Tauri stdio 入口
2. `cli.py` ↔ `daemon.py` — CLI/Daemon UDS 模式
3. `mcp_server.py`（或 `cli.py --mcp`） — MCP stdio 模式

新增 RPC 方法时只在 `@rpc_method` 装饰器注册一次，三入口自动可见。MCP server 自动从 `@rpc_method` 描述生成 schema（commit `4615d7c` `f08887c`）。

### 后果

- 任何 RPC 方法变更同时作用于三模式，无重复
- 三模式都通过 isError 协议规范化错误（commit `f08887c`）
- 当前注册 71 个方法（扣除 `test.*` 过滤后即 MCP 工具数）

---

## ADR-010: 并行 Worktree 协议（任务级隔离）

### 背景

多 LLM agent / 多 session 同时开发时，共享 main 仓库会冲突 `.trellis/.current-task`，互相覆盖任务状态。

### 决策结果

**每任务一个 git worktree**：`task.py worktree create <slug>` 自动 commit 任务目录到 base_branch 后 `git worktree add` 到 `.trellis/worktrees/<slug>/` 上 `feat/<slug>` 分支（commit `0a09e9c` `eb246b1`）。每个 worktree 独立 `.current-task`（gitignored），SessionStart hook 注入对应 worktree 的状态。

### 后果

- 多 session 互不打扰；统一通过 `task.py worktree list/status/remove` 管理
- 仍共享：Vite :1420 / SQLite / Sidecar venv（运行时单实例约束）
- 完整协议见 [docs/parallel-agents.md](../parallel-agents.md) 与 [.trellis/spec/cross-layer/parallel-development.md](../../.trellis/spec/cross-layer/parallel-development.md)

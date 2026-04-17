# Monaco Editor 集成

> **状态**: Draft | **最后更新**: 2026-04-17

---

## 概述

Mimicry 集成 Monaco Editor 作为工作流 JSON 的文本编辑器，与 Vue Flow 画布实现双向实时同步。Monaco 侧重面向 LLM 的 JSON 交互，画布侧重面向人类的可视化拖拽。

参考 [设计决策 ADR-001](../design/decisions.md#adr-001-block-底层格式--json-节点图直驱)。

```
┌──────────────────────────────────────────────────┐
│              工作流编辑器                           │
│                                                  │
│  ┌─────────────────────┐  ┌───────────────────┐  │
│  │   Vue Flow 画布      │  │  Monaco Editor    │  │
│  │   (人类拖拽)         │  │  (JSON / LLM)    │  │
│  │                     │  │                   │  │
│  │  ┌───┐  ┌───┐      │  │  {                │  │
│  │  │ A │─►│ B │      │◄─┼─►  "nodes": [...] │  │
│  │  └───┘  └───┘      │  │    "edges": [...] │  │
│  │                     │  │  }                │  │
│  └─────────────────────┘  └───────────────────┘  │
│         ▲                        ▲               │
│         └──── 双向实时同步 ────────┘               │
└──────────────────────────────────────────────────┘
```

---

## JSON 编辑模式

### 编辑视图切换

工具栏提供视图切换按钮（`Ctrl+E`）：

| 视图 | 说明 |
|------|------|
| 画布模式 | Vue Flow 可视化编辑（默认） |
| JSON 模式 | Monaco Editor 文本编辑 |
| 分屏模式 | 左画布 + 右 JSON，实时同步 |

### Monaco 配置

```typescript
const editorOptions: monaco.editor.IStandaloneEditorConstructionOptions = {
  language: 'json',
  theme: 'vs-dark',
  minimap: { enabled: true },
  formatOnPaste: true,
  formatOnType: true,
  tabSize: 2,
  wordWrap: 'on',
  folding: true,
  foldingStrategy: 'indentation',
  scrollBeyondLastLine: false,
  automaticLayout: true,
};
```

### 编辑的 JSON 内容

Monaco 中编辑的是完整的工作流 JSON 结构：

```json
{
  "id": "wf_abc123",
  "name": "示例工作流",
  "version": "1.0.0",
  "settings": { ... },
  "variables": { ... },
  "nodes": [ ... ],
  "edges": [ ... ],
  "groups": [ ... ],
  "packages": [ ... ]
}
```

用户可直接编辑任何字段——添加节点、修改连线、调整配置等。

---

## 面向 LLM 的设计意图

Monaco Editor + JSON 直驱架构的核心目标是让 LLM 能高效参与工作流创建和修改：

### LLM 工作流程

```
用户描述需求 → LLM 生成工作流 JSON → 粘贴到 Monaco → 画布自动渲染
     ↓
用户在画布调整 → JSON 自动更新 → 复制 JSON → 发给 LLM 修改
     ↓
LLM 返回修改后 JSON → 粘贴覆盖 → 画布自动更新
```

### 设计要点

1. **结构化 JSON**：LLM 天然擅长生成和修改 JSON，比自定义 DSL 准确率更高
2. **Schema 约束**：JSON Schema 让 LLM 在生成时有明确的格式规范
3. **完整自描述**：每个节点的 `type` 字段即为行为定义，LLM 无需额外上下文即可理解
4. **粘贴即用**：LLM 生成的 JSON 粘贴到编辑器后立即渲染为画布节点

---

## JSON Schema 验证

Monaco Editor 加载 Mimicry 工作流 JSON Schema，提供实时验证：

### Schema 注册

```typescript
monaco.languages.json.jsonDefaults.setDiagnosticsOptions({
  validate: true,
  schemas: [
    {
      uri: 'mimicry://workflow-schema',
      fileMatch: ['*'],
      schema: workflowJsonSchema,
    },
  ],
});
```

### 验证规则

| 规则 | 说明 |
|------|------|
| 必填字段 | `id`, `name`, `nodes`, `edges` 不可缺少 |
| 节点类型 | `type` 必须为已注册的 Block 类型标识 |
| 端口匹配 | edge 的 `sourceHandle`/`targetHandle` 必须存在于对应节点 |
| 变量引用 | `{{$var.xxx}}` 中 `xxx` 须在 `variables` 中声明 |
| Loop 配对 | Loop Block 和 Breakpoint 的 `loopId` 必须配对 |
| ID 唯一 | 所有 `id` 字段不可重复 |

### 错误提示

验证错误在编辑器中以红色波浪线标注，hover 显示错误信息：

```
  "nodes": [
    {
      "id": "node_1",
      "type": "browser/Navigate",
      "data": {
        "url": "https://example.com"
~~~~~~  ← ⚠ Missing required field: "waitUntil"
      }
    }
  ]
```

---

## 画布 ↔ JSON 实时双向同步

### 同步机制

```
画布操作 → Vue Flow 事件 → 更新 Pinia Store → 序列化 JSON → 推送到 Monaco
Monaco 编辑 → onChange 回调 → 解析 JSON → 验证 → 更新 Pinia Store → 推送到 Vue Flow
```

### 防抖处理

- **画布 → JSON**：即时同步（画布操作后 0ms 延迟更新 JSON）
- **JSON → 画布**：300ms 防抖（用户停止输入 300ms 后更新画布）

### 冲突处理

- 同一时刻只有一个编辑源活跃（画布或 Monaco）
- 当用户在 Monaco 中编辑时，画布为只读状态（显示灰色遮罩）
- 当用户在画布中操作时，Monaco 为只读状态
- 切换焦点时自动同步最新状态

### 同步数据流

```typescript
// Pinia Store 作为单一数据源
const workflowStore = defineStore('workflow', {
  state: () => ({
    workflow: null as Workflow | null,
  }),

  actions: {
    // 画布操作调用
    updateFromCanvas(nodes: Node[], edges: Edge[]) {
      this.workflow.nodes = nodes;
      this.workflow.edges = edges;
      // Monaco 自动响应 state 变化
    },

    // Monaco 编辑调用
    updateFromJson(json: string) {
      const parsed = JSON.parse(json);
      if (validateWorkflow(parsed)) {
        this.workflow = parsed;
        // Vue Flow 自动响应 state 变化
      }
    },
  },
});
```

---

## 语法高亮和自动补全

### 语法高亮

Monaco 的 JSON 语言模式提供默认高亮。额外自定义：

- Block 类型字符串（如 `"browser/Navigate"`）高亮为蓝色
- 表达式（`{{$var.xxx}}`）高亮为绿色
- 注释字段（`"note"`）高亮为灰色

### 自动补全

基于 JSON Schema 提供上下文感知的自动补全：

| 上下文 | 补全内容 |
|--------|---------|
| `"type": "` | 所有可用的 Block 类型标识 |
| `"onError": "` | `stop`, `continue`, `retry`, `fallback`, `inherit` |
| `"waitUntil": "` | `load`, `domcontentloaded`, `networkidle` |
| `"sourceHandle": "` | 源节点的可用输出端口名 |
| `"{{$` | 表达式前缀：`$var.`, `$prev.`, `$loop.`, `$browser.` |

### 代码片段

提供常用结构的 Snippet：

| 触发词 | 生成内容 |
|--------|---------|
| `node` | 新节点骨架 |
| `edge` | 新连线骨架 |
| `loop` | Loop + Breakpoint 配对骨架 |
| `condition` | Condition 节点 + true/false 连线骨架 |

---

## 相关文档

- [设计决策 ADR-001](../design/decisions.md#adr-001-block-底层格式--json-节点图直驱)
- [画布交互设计](./canvas-interaction.md)
- [数据流设计](../design/data-flow.md)
- [Block 体系设计](../design/block-system.md)

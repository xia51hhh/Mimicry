# 数据流设计

> **状态**: Draft | **最后更新**: 2026-04-17

---

## 核心数据结构

### WorkflowContext

工作流执行时的全局上下文对象，贯穿整个执行生命周期：

```typescript
interface WorkflowContext {
  /** 工作流级变量存储 */
  variables: Map<string, unknown>;

  /** 浏览器实时状态 */
  browser: {
    connected: boolean;
    pages: number;
    activePageUrl: string;
    activePageTitle: string;
  };

  /** 循环上下文栈（支持嵌套循环） */
  loopStack: LoopFrame[];

  /** 数据表（可选，用于结构化数据收集） */
  table: {
    columns: TableColumn[];
    rows: Record<string, unknown>[];
  };

  /** 执行元数据 */
  execution: {
    workflowId: string;
    startTime: string;
    currentNodeId: string;
    status: 'running' | 'paused' | 'completed' | 'error';
  };
}

interface LoopFrame {
  loopId: string;
  current: unknown;       // 当前迭代的数据项
  index: number;          // 当前迭代索引（从 0 开始）
  total: number;          // 总迭代次数
  data: unknown[];        // 完整数据源
}

interface TableColumn {
  id: string;
  name: string;
  type: 'string' | 'number' | 'boolean' | 'any';
}
```

---

## 节点间数据传递

Block 之间通过连线自动传递数据：

```
┌──────────┐   output    ┌──────────┐   output    ┌──────────┐
│ Get Text │────────────►│ Transform│────────────►│  Export  │
│          │  {text:"hi"}│          │ {upper:"HI"}│          │
└──────────┘             └──────────┘             └──────────┘
```

### 传递规则

1. **前节点输出 → 后节点输入**：连线建立数据通道，前节点执行完成后将 `output` 自动传入后节点
2. **多输入合并**：当一个节点有多条入边时，按连线顺序合并为数组
3. **多输出分发**：当一个输出连接多个节点时，每个目标节点收到相同的数据副本

### 节点 IO 结构

```typescript
/** 每个节点的执行输入 */
interface NodeInput {
  /** 来自前驱节点的输出数据 */
  prev: Record<string, unknown> | null;

  /** 工作流上下文引用 */
  context: WorkflowContext;
}

/** 每个节点的执行输出 */
interface NodeOutput {
  /** 传递给后继节点的数据 */
  data: Record<string, unknown>;

  /** 输出端口（用于条件分支等） */
  port?: string;
}
```

---

## 变量系统

### 变量作用域

工作流提供统一的变量 Map，所有 Block 共享读写：

```typescript
// 工作流级变量
variables: Map<string, unknown>

// 在 Set Variable Block 中设置
{ "name": "baseUrl", "value": "https://example.com" }

// 在任意 Block 中通过表达式引用
"url": "{{$var.baseUrl}}/login"
```

### 预定义变量

工作流 JSON 中可声明默认变量：

```json
{
  "variables": {
    "baseUrl": { "type": "string", "default": "https://example.com" },
    "maxRetry": { "type": "number", "default": 3 },
    "debug": { "type": "boolean", "default": false }
  }
}
```

---

## 表达式引用

Mimicry 使用 `{{}}` Mustache 风格的表达式语法，在 Block 的 `data` 字段中引用动态数据。

### 表达式前缀

| 前缀 | 含义 | 示例 |
|------|------|------|
| `$var` | 工作流变量 | `{{$var.name}}` |
| `$prev` | 前驱节点输出 | `{{$prev.text}}` |
| `$loop` | 当前循环帧 | `{{$loop.current}}`, `{{$loop.index}}` |
| `$browser` | 浏览器状态 | `{{$browser.activePageUrl}}` |
| `$env` | 环境变量 | `{{$env.API_KEY}}` |

### 示例

```json
{
  "type": "interaction/Type",
  "data": {
    "selector": "#search-input",
    "text": "{{$loop.current.keyword}}"
  }
}
```

```json
{
  "type": "control/Condition",
  "data": {
    "conditions": [
      {
        "group": "AND",
        "rules": [
          { "left": "{{$prev.status}}", "operator": "==", "right": "success" },
          { "left": "{{$var.retry}}", "operator": "<", "right": "3" }
        ]
      }
    ]
  }
}
```

### 嵌套访问

表达式支持点号链式访问和数组索引：

```
{{$prev.items[0].name}}
{{$var.config.proxy.host}}
{{$loop.current.children[2].text}}
```

---

## 循环数据访问

循环内通过 `$loop` 前缀访问当前迭代数据。嵌套循环时可通过 `loopId` 访问外层循环：

```
当前循环:   {{$loop.current}}        当前数据项
           {{$loop.index}}          当前索引
           {{$loop.total}}          总数

指定循环:   {{$loop.loop_1.current}} 指定 loopId 的数据项
           {{$loop.loop_1.index}}   指定 loopId 的索引
```

### 循环执行流程

```
┌─────────┐     ┌───────────────┐     ┌───────────────┐     ┌────────────────┐
│ Loop    │────►│ Block A       │────►│ Block B       │────►│ Loop           │
│ Data    │     │ (循环体内)     │     │ (循环体内)     │     │ Breakpoint     │
│ loopId=1│     │               │     │               │     │ loopId=1       │
└─────────┘     └───────────────┘     └───────────────┘     └───────┬────────┘
     ▲                                                              │
     └──────────── 未完成时回到 Loop ─────────────────────────────────┘
                                                                    │
                                                              完成时继续 ▼
                                                          ┌─────────────────┐
                                                          │ 后续 Block       │
                                                          └─────────────────┘
```

---

## 工作流 JSON 完整 Schema

参考 [方案对比](../research/solution-comparison.md) Section E.3（注：最终方案采用了简化的单值传递模型而非 E.2 推荐的 Items 流），Mimicry 工作流 JSON 完整结构如下：

```json
{
  "id": "wf_abc123",
  "name": "商品数据采集",
  "version": "1.0.0",
  "metadata": {
    "createdAt": "2026-04-17T00:00:00Z",
    "updatedAt": "2026-04-17T12:00:00Z",
    "description": "从电商网站采集商品信息",
    "tags": ["scraping", "ecommerce"]
  },
  "settings": {
    "onError": "stop",
    "timeout": 300000,
    "browserProfile": "default",
    "debugMode": false
  },
  "variables": {
    "baseUrl": { "type": "string", "default": "https://shop.example.com" },
    "maxPages": { "type": "number", "default": 10 }
  },
  "table": {
    "columns": [
      { "id": "col_1", "name": "title", "type": "string" },
      { "id": "col_2", "name": "price", "type": "number" },
      { "id": "col_3", "name": "url", "type": "string" }
    ]
  },
  "nodes": [
    {
      "id": "node_1",
      "type": "trigger/Manual",
      "position": { "x": 100, "y": 200 },
      "data": {},
      "settings": { "onError": "inherit", "note": "手动启动" }
    },
    {
      "id": "node_2",
      "type": "browser/Navigate",
      "position": { "x": 350, "y": 200 },
      "data": {
        "url": "{{$var.baseUrl}}/products",
        "waitUntil": "networkidle"
      },
      "settings": { "onError": "stop" }
    },
    {
      "id": "node_3",
      "type": "control/LoopElements",
      "position": { "x": 600, "y": 200 },
      "data": {
        "loopId": "loop_products",
        "selector": ".product-card",
        "maxIterations": 50
      },
      "settings": { "onError": "continue" }
    },
    {
      "id": "node_4",
      "type": "data/GetText",
      "position": { "x": 850, "y": 150 },
      "data": {
        "selector": "{{$loop.current}} >> .title",
        "output": "title"
      },
      "settings": {}
    },
    {
      "id": "node_5",
      "type": "data/GetText",
      "position": { "x": 850, "y": 300 },
      "data": {
        "selector": "{{$loop.current}} >> .price",
        "output": "price"
      },
      "settings": {}
    },
    {
      "id": "node_6",
      "type": "control/LoopBreakpoint",
      "position": { "x": 1100, "y": 200 },
      "data": { "loopId": "loop_products" },
      "settings": {}
    },
    {
      "id": "node_7",
      "type": "data/Export",
      "position": { "x": 1350, "y": 200 },
      "data": {
        "format": "csv",
        "filename": "products.csv",
        "source": "table"
      },
      "settings": {}
    }
  ],
  "edges": [
    { "id": "e1", "source": "node_1", "target": "node_2", "sourceHandle": "output", "targetHandle": "input" },
    { "id": "e2", "source": "node_2", "target": "node_3", "sourceHandle": "output", "targetHandle": "input" },
    { "id": "e3", "source": "node_3", "target": "node_4", "sourceHandle": "loop-body", "targetHandle": "input" },
    { "id": "e4", "source": "node_3", "target": "node_5", "sourceHandle": "loop-body", "targetHandle": "input" },
    { "id": "e5", "source": "node_4", "target": "node_6", "sourceHandle": "output", "targetHandle": "input" },
    { "id": "e6", "source": "node_5", "target": "node_6", "sourceHandle": "output", "targetHandle": "input" },
    { "id": "e7", "source": "node_3", "target": "node_7", "sourceHandle": "completed", "targetHandle": "input" }
  ],
  "groups": [],
  "packages": []
}
```

---

## 相关文档

- [Block 体系设计](./block-system.md)
- [设计决策记录](./decisions.md)
- [画布交互设计](../workflow/canvas-interaction.md)

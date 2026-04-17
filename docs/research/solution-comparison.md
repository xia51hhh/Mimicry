# Automa / n8n / ComfyUI 方案对比报告

> 调研日期: 2026-04-17 | 目标项目: Mimicry (Tauri + Vue Flow + Python Sidecar)
>
> 本文档为调研阶櫥的方案分析资料，最终设计方案请参见 [docs/design/](../design/) 下各文档。

---

## A. Automa 完整功能清单

### A.1 Block（模块）分类及功能描述

Automa 的 Block 分为以下 **8 大类**，共 **40+ 个 Block**：

#### 1. 触发器 / 流程控制
| Block | 功能 |
|-------|------|
| **Trigger** | 工作流入口，支持手动触发、定时触发、快捷键触发、浏览器事件触发 |
| **Execute Workflow** | 调用另一个工作流作为子流程 |
| **Delay** | 在执行下一个 Block 前添加延迟（毫秒） |
| **Repeat Task** | 重复执行一段 Block 链，定义重复次数，第二输出口连接重复起点 |
| **Wait Connections** | 等待所有分支执行完毕后再继续（汇合节点），支持超时和指定流 |
| **Workflow State** | 获取/设置工作流运行状态 |

#### 2. 浏览器导航
| Block | 功能 |
|-------|------|
| **New Tab** | 打开新标签页并导航到指定 URL |
| **Active Tab** | 激活当前标签页（许多操作的前置条件） |
| **Switch Tab** | 切换到指定标签页 |
| **New Window** | 打开新浏览器窗口 |
| **Go Back** | 返回上一页 |
| **Go Forward** | 前进到下一页 |
| **Close Tab/Window** | 关闭标签页或窗口 |
| **Reload Tab** | 刷新当前标签页 |
| **Switch Frame** | 切换到 iframe 内部执行操作 |
| **Proxy** | 设置代理 |

#### 3. 页面交互
| Block | 功能 |
|-------|------|
| **Click Element** | 点击页面元素，支持 CSS/XPath 选择器 |
| **Forms** | 填写表单（输入文本、选择下拉、勾选复选框等） |
| **Trigger Event** | 触发 DOM 事件 |
| **Press Key** | 模拟键盘按键或组合键 |
| **Hover Element** | 悬停在元素上 |
| **Scroll Element** | 滚动页面或元素 |
| **Upload File** | 上传文件到 `<input type="file">` 元素 |
| **Create Element** | 在页面上创建新的 DOM 元素 |

#### 4. 数据提取
| Block | 功能 |
|-------|------|
| **Get Text** | 获取元素文本内容，可插入表格或赋值变量 |
| **Attribute Value** | 获取元素属性值（href、src 等） |
| **Get Tab URL** | 获取当前标签页 URL |
| **Cookie** | 读写浏览器 Cookie |

#### 5. 循环与条件
| Block | 功能 |
|-------|------|
| **Loop Data** | 遍历表格、变量、数字范围、Google Sheets、元素或自定义 JSON 数组 |
| **Loop Elements** | 遍历匹配选择器的元素，支持加载更多（点击/滚动） |
| **Loop Breakpoint** | 定义循环作用域的终点，通过 Loop ID 关联 |
| **While Loop** | 条件循环，满足条件时持续执行 |
| **Conditions** | 条件分支，使用 Condition Builder 构建多条件，有 fallback 输出 |
| **Element Exists** | 检查元素是否存在 |

#### 6. 数据操作
| Block | 功能 |
|-------|------|
| **Insert Data** | 向表格插入数据 |
| **Delete Data** | 删除表格数据 |
| **Export Data** | 导出表格/变量为 JSON、CSV 或纯文本 |
| **Slice Variable** | 截取变量值 |
| **Increase Variable** | 变量自增 |
| **Regex Variable** | 正则处理变量 |
| **Data Mapping** | 数据映射转换 |
| **Sort Data** | 排序数据 |

#### 7. 系统/浏览器操作
| Block | 功能 |
|-------|------|
| **Take Screenshot** | 截图（页面/全页/元素），支持存文件或 DataURL |
| **Handle Dialog** | 处理 alert/confirm/prompt 弹窗 |
| **Handle Download** | 处理下载文件，可重命名、等待完成、获取路径 |
| **Save Assets** | 保存图片/视频/音频资源 |
| **Clipboard** | 读写剪贴板 |
| **Browser Event** | 监听浏览器事件 |
| **Notification** | 发送桌面通知 |

#### 8. 集成 & 高级
| Block | 功能 |
|-------|------|
| **JavaScript Code** | 执行自定义 JS，提供 `automaNextBlock()`、`automaSetVariable()`、`automaRefData()` 等 API |
| **HTTP Request** | 发送 HTTP 请求，支持所有方法，响应可存入变量/表格 |
| **Google Sheets** | 读写 Google Sheets |
| **Google Drive** | 操作 Google Drive 文件 |
| **Blocks Group** | 将多个 Block 编组 |
| **Parameter Prompt** | 运行前弹出参数输入框 |
| **AI Workflow** | AI 辅助工作流 |

### A.2 工作流数据结构（JSON Schema 概览）

Automa 工作流以 **JSON 格式**导出/导入，核心结构：

```json
{
  "name": "Workflow Name",
  "description": "...",
  "version": "1.x.x",
  "globalData": "{}",          // 全局数据（JSON字符串）
  "table": [                    // 表格列定义
    { "name": "title", "type": "text", "id": "col-1" }
  ],
  "drawflow": {                 // 节点图数据
    "nodes": [
      {
        "id": "node-1",
        "label": "trigger",
        "data": { /* block 特定配置 */ },
        "position": { "x": 100, "y": 200 }
      }
    ],
    "edges": [
      {
        "id": "edge-1",
        "sourceHandle": "output-1",
        "targetHandle": "input-1",
        "source": "node-1",
        "target": "node-2"
      }
    ]
  },
  "settings": {
    "onError": "stop",          // stop | restart-workflow | continue
    "executedBlockOnWeb": false,
    "debugMode": false,
    "reuseLastState": false
  },
  "variables": [                // 预定义变量
    { "name": "myVar", "value": "" }
  ],
  "includedWorkflows": {}       // 子工作流引用
}
```

### A.3 调试模式工作机制

- **Debug Mode** = 使用 **Chrome DevTools Protocol (CDP)** 代替 JavaScript API
- 两种启用方式：**工作流级**（全局）或**Block 级**（单个节点）
- 解决场景：
  - WYSIWYG 编辑器输入（Twitter、Discord 等）
  - 基于坐标的点击（Trigger Event block）
  - JS API 无法模拟的真实用户行为
- 仅在 Chromium 版本可用
- 另有 **Testing Mode**：可在不实际执行操作的情况下预览数据流

### A.4 元素选择器设计方案

- **选择器类型**：CSS Selector / XPath 表达式
- **自定义语法扩展**：
  - `iframe-selector |> element-selector` — 选择 iframe 内元素
  - `:contains(TEXT)` — 按文本内容选择
  - `shadow-dom-selector >> element-selector` — 选择 Shadow DOM 内元素
- **Element Picker**：可视化选择器工具，注入页面，点击或空格选择元素，自动生成选择器
- **Block 级选项**：
  - **Multiple**：选择所有匹配元素（默认只选第一个）
  - **Mark Element**：标记已选元素避免重复选择
  - **Wait For Selector**：等待元素出现，支持超时

### A.5 循环/分支实现方式

**循环三种模式**：
1. **Loop Data Block**：遍历 Table/变量/Google Sheets/自定义数组/数字范围，需配合 **Loop Breakpoint** 定义作用域
2. **Loop Elements Block**：遍历页面匹配元素，支持动态加载更多（点击/滚动），同样需要 Breakpoint
3. **Repeat Task Block**：简单重复 N 次，第二输出口指向重复起点

**循环数据访问**：`{{loopData.loopId}}` 返回 `{ data: ..., $index: N }`

**分支**：
- **Conditions Block**：通过 Condition Builder 定义多个条件，每个条件一个输出口，有 fallback 输出
- **Element Exists**：检查元素存在与否进行分支
- **Wait Connections**：分支汇合，等待所有分支完成

### A.6 变量/表格数据系统

**Table（表格）**：
- 类似电子表格，每列有严格类型（Text/Number/Boolean/Array/Any）
- 数据按行追加，内部存储为 `Array<Object>`
- 可通过 Get Text / Attribute Value 等 Block 插入
- 支持 Export Data 导出为 JSON/CSV/Text

**Variables（变量）**：
- 键值对存储，整个工作流可访问
- 特殊前缀：
  - `$$varName` — 存入持久化 Storage，跨工作流可用
  - `$push:varName` — 追加模式，值自动变为数组

**Expressions（表达式）**：
- Mustache 语法：`{{variables.name}}`、`{{table.0.column}}`
- JavaScript 表达式：`!!{{variables.name.toUpperCase()}}`
- 内置函数：`$stringify()`、`$getLength()` 等

### A.7 Package 系统设计

- **Package** = 可复用的 Block 集合（前身为 Block Folders）
- **创建方式**：
  1. 在工作流编辑器中 Shift+拖选 Block → 右键 → "Set as package"
  2. 在 Package 页面点击 "New package"
- **编辑**：与工作流编辑器相同，但没有 Table 和 Global Data
- **Package as Block**：可设为单个 Block 使用，在设置中启用
  - 自定义输入/输出：右键 Block 的端口 → 设为 Package Input/Output
  - 使用时在工作流中呈现为单个节点，带自定义 IO 端口

---

## B. n8n 节点系统分析

### B.1 节点分类体系

n8n 节点分为 **4 大类**：

| 类型 | 说明 | 示例 |
|------|------|------|
| **Core Nodes** | 内置核心节点（约50+个） | Code, If, Switch, Merge, HTTP Request, Filter, Sort, Loop Over Items, Webhook, Schedule Trigger, Manual Trigger |
| **App Nodes (Actions)** | 第三方服务集成（300+个） | Gmail, Slack, GitHub, Postgres, Airtable, Salesforce, Stripe, Discord 等 |
| **Trigger Nodes** | 事件触发器（100+个） | Webhook Trigger, Schedule Trigger, Gmail Trigger, GitHub Trigger, Kafka Trigger 等 |
| **Cluster Nodes** | AI/LangChain 相关 | AI Agent, Basic LLM Chain, Summarization Chain, Chat Models, Vector Stores, Memory 等 |

**核心流程控制节点**：
- **If** — 二分支条件判断
- **Switch** — 多分支路由
- **Merge** — 多路数据合并
- **Filter** — 数据过滤
- **Loop Over Items (Split in Batches)** — 批量循环处理
- **Execute Sub-workflow** — 调用子工作流
- **Wait** — 暂停等待（时间/webhook回调）
- **Stop And Error** — 停止并抛错
- **Code** — 自定义 JavaScript/Python 代码

### B.2 节点数据流转模型（Input/Output）

n8n 的核心数据模型：

```typescript
interface IDataItem {
  json: {                    // 结构化数据
    [key: string]: any;
  };
  binary?: {                 // 二进制数据（文件等）
    [key: string]: IBinaryData;
  };
}
// 节点输入/输出 = IDataItem[]（items 数组）
```

**关键特性**：
- **自动迭代**：大多数节点自动对所有 items 逐一处理
- **Item Linking**：每个 item 保持与源数据的链接关系，便于追溯
- **表达式引用**：`{{ $json.fieldName }}` 引用当前 item，`{{ $('NodeName').item.json.field }}` 引用其他节点
- **Data Pinning**：可固定节点输出数据用于调试
- **Dirty Nodes**：编辑后标记为"脏"，提示需要重新执行

**节点操作类型**：
- **Trigger** — 启动工作流（bolt ⚡ 图标）
- **Action** — 执行具体操作

**节点设置**：
- Always Output Data — 即使无数据也输出空 item
- Execute Once — 只处理第一个 item
- Retry On Fail — 失败自动重试
- On Error — Stop / Continue / Continue (using error output)

### B.3 分支与循环的实现

**分支**：
- **If Node** — 二路分支（true/false）
- **Switch Node** — 多路分支（多个 output）
- **Merge Node** — 合并分支数据（Join, Combine, Choose branch 等模式）

**循环**：
- **自动循环**：绝大多数节点自动迭代所有 items，无需手动建循环
- **Loop Over Items (Split in Batches)**：将 items 分批处理
- **手动循环**：将输出连回之前节点 + If 节点做终止条件
- **例外节点**需手动设计循环：CrateDB(insert/update)、Code(Run Once 模式)、HTTP Request(分页)

### B.4 工作流 JSON 结构

```json
{
  "name": "My Workflow",
  "nodes": [
    {
      "id": "uuid-xxx",
      "name": "HTTP Request",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4,
      "position": [250, 300],
      "parameters": {
        "method": "GET",
        "url": "https://api.example.com/data"
      },
      "credentials": {
        "httpBasicAuth": { "id": "1", "name": "My Creds" }
      }
    }
  ],
  "connections": {
    "Start": {
      "main": [                     // main output
        [
          { "node": "HTTP Request", "type": "main", "index": 0 }
        ]
      ]
    }
  },
  "settings": {
    "executionOrder": "v1",
    "saveExecutionProgress": true,
    "callerPolicy": "workflowsFromSameOwner"
  },
  "staticData": null,
  "tags": [],
  "pinData": {}
}
```

---

## C. ComfyUI 节点架构

> 注：ComfyUI 文档页面为 JS 渲染，以下基于 ComfyUI 开源代码和公开架构知识。

### C.1 节点定义方式

ComfyUI 采用 **Python 类注册** 方式定义节点：

```python
class KSampler:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),                     # 类型化输入
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "steps": ("INT", {"default": 20, "min": 1, "max": 10000}),
                "cfg": ("FLOAT", {"default": 8.0, "min": 0.0, "max": 100.0}),
                "sampler_name": (["euler", "euler_ancestral", "dpm_2", ...],),
                "scheduler": (["normal", "karras", "exponential", ...],),
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
                "latent_image": ("LATENT",),
            },
            "optional": {
                "denoise": ("FLOAT", {"default": 1.0}),
            }
        }

    RETURN_TYPES = ("LATENT",)        # 输出类型
    RETURN_NAMES = ("samples",)       # 输出名称
    FUNCTION = "sample"               # 执行方法名
    CATEGORY = "sampling"             # 节点分类

    def sample(self, model, seed, steps, cfg, sampler_name, scheduler, 
               positive, negative, latent_image, denoise=1.0):
        # 执行逻辑
        return (result_latent,)

NODE_CLASS_MAPPINGS = { "KSampler": KSampler }
NODE_DISPLAY_NAME_MAPPINGS = { "KSampler": "KSampler" }
```

### C.2 连接（Connection）类型系统

ComfyUI 使用**强类型连接**：

| 类型 | 含义 | 颜色 |
|------|------|------|
| `MODEL` | 模型对象 | 紫色 |
| `CLIP` | CLIP 编码器 | 黄色 |
| `VAE` | VAE 编解码器 | 红色 |
| `CONDITIONING` | 条件数据 | 橙色 |
| `LATENT` | 潜空间数据 | 粉色 |
| `IMAGE` | 图像张量 | 蓝色 |
| `MASK` | 遮罩 | 绿色 |
| `INT`/`FLOAT`/`STRING` | 基本类型 | 灰色系 |

**关键特性**：
- **类型匹配**：只有相同类型的端口才能连接
- **一对多**：一个输出可连接多个输入
- **多对一**：部分类型支持（通过 Combine 节点）
- **Reroute Node**：路由节点用于整理连线
- **Convert Widget to Input**：可将内部参数暴露为输入端口

### C.3 工作流序列化格式

ComfyUI 使用两种格式：

**1. API 格式（精简）**：
```json
{
  "3": {
    "class_type": "KSampler",
    "inputs": {
      "model": ["4", 0],          // [源节点ID, 输出索引]
      "positive": ["6", 0],
      "negative": ["7", 0],
      "latent_image": ["5", 0],
      "seed": 42,                  // 直接值
      "steps": 20,
      "cfg": 8.0,
      "sampler_name": "euler",
      "scheduler": "normal",
      "denoise": 1.0
    }
  }
}
```

**2. 完整格式（含 UI 信息）**：
```json
{
  "last_node_id": 10,
  "last_link_id": 12,
  "nodes": [
    {
      "id": 3,
      "type": "KSampler",
      "pos": [800, 200],
      "size": [300, 400],
      "inputs": [
        { "name": "model", "type": "MODEL", "link": 1 },
        { "name": "positive", "type": "CONDITIONING", "link": 2 }
      ],
      "outputs": [
        { "name": "LATENT", "type": "LATENT", "links": [5], "slot_index": 0 }
      ],
      "widgets_values": [42, 20, 8.0, "euler", "normal", 1.0]
    }
  ],
  "links": [
    [1, 4, 0, 3, 0, "MODEL"]     // [linkId, srcNode, srcSlot, dstNode, dstSlot, type]
  ],
  "groups": [],
  "config": {},
  "extra": { "ds": { "scale": 1, "offset": [0, 0] } }
}
```

---

## D. 三者对比表

| 特性 | Automa | n8n | ComfyUI |
|------|--------|-----|---------|
| **定位** | 浏览器自动化扩展 | 通用工作流自动化平台 | AI 图像生成节点编辑器 |
| **编辑器** | 内嵌 Drawflow 画布 | 自研 Canvas 编辑器 | LiteGraph.js |
| **节点数量** | ~45 个 Block | 300+ (含集成) | 50+ 核心 + 社区扩展 |
| **节点分类** | 8 大类（浏览器导向） | 4 大类（Trigger/Action/Core/Cluster） | 按 AI 管线阶段分类 |
| **数据流模型** | 表格 + 变量（全局共享） | Items 数组（逐节点传递） | 强类型端口直连 |
| **类型系统** | 弱类型（表格列有类型约束） | 弱类型（JSON + Binary） | **强类型端口匹配** |
| **表达式** | Mustache `{{}}` + JS | `{{ $json.field }}` JS 表达式 | 无（参数值或连线） |
| **循环** | Loop Data/Elements + Breakpoint / Repeat Task / While | 自动迭代 / Loop Over Items / 手动连线 | **DAG 无环** — 无循环概念 |
| **分支** | Conditions + fallback | If(二路) / Switch(多路) | 无显式分支，按连线拓扑 |
| **调试** | Debug Mode (CDP) + Testing Mode | 逐节点执行 + Data Pinning + Execution Log | 队列执行 + 节点高亮 + 预览图 |
| **代码扩展** | JS Code Block | Code Node (JS/Python) | Python 自定义节点 |
| **Package/复用** | Package 系统（可封装为 Block） | Sub-workflow | Custom Nodes + Node Packs |
| **元素选择器** | CSS/XPath + 可视化 Picker + 自定义语法 | N/A | N/A |
| **序列化** | JSON (drawflow nodes/edges) | JSON (nodes/connections) | JSON (nodes/links/widgets_values) |
| **部署形态** | 浏览器扩展 | Web 应用（Self-host/Cloud） | 桌面 Python 应用 |

---

## E. 对 Mimicry 的设计启示

> **注意**：以下为调研阶櫥的初步建议，最终设计方案已经调整，请参见：
> - Block 体系: [docs/design/block-system.md](../design/block-system.md)
> - 数据流: [docs/design/data-flow.md](../design/data-flow.md)
> - 调试系统: [docs/design/debug-system.md](../design/debug-system.md)
> - 元素选择器: [docs/design/element-selector.md](../design/element-selector.md)

基于 Mimicry 的技术栈（Tauri + Vue Flow + Python Sidecar）和浏览器自动化定位，以下是具体设计建议：

### E.1 推荐的节点分类体系

采用 **Automa 的浏览器导向分类** + **n8n 的清晰层次结构**：

```
mimicry/nodes/
├── trigger/          # 触发器
│   ├── ManualTrigger
│   ├── ScheduleTrigger
│   └── EventTrigger
├── browser/          # 浏览器导航
│   ├── Navigate
│   ├── NewTab
│   ├── GoBack
│   ├── SwitchTab
│   └── WaitForPage
├── interaction/      # 页面交互
│   ├── Click
│   ├── Type
│   ├── Hover
│   ├── PressKey
│   ├── Scroll
│   ├── SelectOption
│   └── UploadFile
├── extraction/       # 数据提取
│   ├── GetText
│   ├── GetAttribute
│   ├── GetHTML
│   ├── Screenshot
│   └── ExtractTable
├── flow/             # 流程控制
│   ├── Condition
│   ├── Loop
│   ├── ForEach
│   ├── WhileLoop
│   ├── TryCatch
│   └── Parallel
├── data/             # 数据操作
│   ├── SetVariable
│   ├── Transform
│   ├── Filter
│   ├── Merge
│   └── Export
├── integration/      # 外部集成
│   ├── HttpRequest
│   ├── RunScript (Python/JS)
│   └── Database
└── utility/          # 工具
    ├── Delay
    ├── Log
    ├── Notify
    └── Comment (Sticky Note)
```

### E.2 推荐的数据流转模型

**混合模型**：借鉴 n8n 的 Items 流 + Automa 的全局变量：

```typescript
// 节点间数据流 - 采用 n8n 的 Items 模式
interface FlowItem {
  json: Record<string, unknown>;      // 结构化数据
  binary?: Record<string, Buffer>;    // 二进制数据（截图等）
  meta?: {
    sourceNodeId: string;
    index: number;
  };
}

// 节点输入/输出
interface NodeIO {
  items: FlowItem[];                  // 流式数据
}

// 全局上下文 - 借鉴 Automa 的变量/表格
interface WorkflowContext {
  variables: Map<string, unknown>;    // 工作流级变量
  table: Array<Record<string, unknown>>;  // 数据表（可选）
  browser: BrowserState;              // 浏览器状态
  loopStack: LoopContext[];           // 循环上下文栈
}
```

**数据引用方式**：
- 连线传递：前一节点的 `items` 自动传入下一节点
- 表达式引用：`{{$node["GetText"].items[0].json.text}}` 或简写 `{{$prev.text}}`
- 变量引用：`{{$var.myVariable}}`
- 循环数据：`{{$loop.current}}` / `{{$loop.index}}`

### E.3 推荐的工作流 JSON 结构

```json
{
  "id": "wf_uuid",
  "name": "My Workflow",
  "version": "1.0.0",
  "metadata": {
    "createdAt": "2026-04-17T00:00:00Z",
    "updatedAt": "2026-04-17T00:00:00Z",
    "tags": ["scraping"]
  },
  "settings": {
    "onError": "stop",
    "timeout": 300000,
    "browserProfile": "default"
  },
  "variables": {
    "baseUrl": { "type": "string", "default": "" }
  },
  "table": {
    "columns": [
      { "id": "col_1", "name": "title", "type": "string" },
      { "id": "col_2", "name": "price", "type": "number" }
    ]
  },
  "nodes": [
    {
      "id": "node_1",
      "type": "trigger/ManualTrigger",
      "position": { "x": 100, "y": 200 },
      "data": {},
      "settings": {
        "onError": "inherit",
        "retryOnFail": false,
        "note": ""
      }
    },
    {
      "id": "node_2",
      "type": "browser/Navigate",
      "position": { "x": 350, "y": 200 },
      "data": {
        "url": "{{$var.baseUrl}}",
        "waitUntil": "networkidle"
      }
    }
  ],
  "edges": [
    {
      "id": "edge_1",
      "source": "node_1",
      "target": "node_2",
      "sourceHandle": "output",
      "targetHandle": "input"
    }
  ],
  "groups": [
    {
      "id": "group_1",
      "name": "Data Extraction",
      "nodeIds": ["node_3", "node_4"],
      "color": "#e3f2fd"
    }
  ]
}
```

### E.4 推荐的调试模式设计

结合三者优点，设计 **分层调试体系**：

| 层级 | 功能 | 参考来源 |
|------|------|----------|
| **Step Debug** | 逐节点单步执行，暂停在每个节点查看 IO 数据 | n8n Execution Debug |
| **Data Inspector** | 每个节点的输入/输出数据实时可视化面板 | n8n Data Pinning |
| **Breakpoint** | 在指定节点设置断点，运行到断点暂停 | 通用调试概念 |
| **CDP Mode** | 切换到 CDP 协议模拟真实用户操作 | Automa Debug Mode |
| **Replay** | 从执行日志中回放/重新执行某个节点 | n8n Execution Log |
| **Watch Variables** | 实时监控变量/表格值的变化 | IDE Watch |
| **Visual Feedback** | 执行时节点高亮、连线动画显示数据流向 | ComfyUI 执行高亮 |

### E.5 推荐的元素选择器方案

基于 Mimicry 的 Camoufox Sidecar 架构：

```
选择器分层设计：
┌─────────────────────────────────────────┐
│  Visual Picker (Overlay on browser)     │  ← 用户可视化选择
│  - 鼠标悬停高亮元素                       │
│  - 点击选择，显示元素信息                  │
│  - 生成候选选择器列表（按优先级排序）       │
├─────────────────────────────────────────┤
│  Smart Selector Generator               │  ← 智能生成
│  - 优先 data-testid / aria-label        │
│  - 次选 unique id / class               │
│  - 兜底 CSS path / XPath               │
│  - 组合策略（text + structure）          │
├─────────────────────────────────────────┤
│  Selector Engine (Python Sidecar)       │  ← Playwright 执行
│  - CSS Selector                         │
│  - XPath                                │
│  - Playwright 专属: text=, role=         │
│  - 自定义 >> (iframe/shadow DOM)         │
└─────────────────────────────────────────┘
```

**关键设计决策**：
1. **多策略生成**：为每个元素生成多个候选选择器，按稳定性评分排序
2. **录制集成**：录制时自动生成选择器，存入节点配置
3. **选择器测试**：编辑器中可实时测试选择器，高亮匹配元素
4. **自愈机制**：执行时主选择器失败自动尝试备选选择器
5. **Playwright 原生语法**：直接利用 Playwright 的 `page.locator()` 能力，支持 `text=`、`role=`、`has-text=` 等高级定位

---

## F. 补充调研数据

### F.1 Automa Trigger Block 完整触发方式

基于最新文档补充：
- **Manually**: 手动点击播放按钮
- **Interval**: 按时间间隔执行
- **On a specific date**: 特定日期执行
- **On a specific day**: 特定星期几执行
- **On browser startup**: 浏览器启动时执行
- **Cron job**: Cron 表达式调度
- **Context menu**: 右键菜单触发（注入 `$ctxElSelector`、`$ctxTextSelection`、`$ctxMediaUrl`、`$ctxLink`）
- **When visiting a website**: URL/正则匹配时触发
- **Keyboard shortcut**: 快捷键触发（支持 "Active while in input" 选项）
- **JS CustomEvent**: `automa:execute-workflow` 或 `__automaExecuteWorkflow`
- **URL 触发**: `chrome-extension://...id.../execute.html#/workflowId?var=val`

### F.2 ComfyUI 核心特性补充

基于 GitHub README：
- **异步队列系统**: Ctrl+Enter 加入队列，Ctrl+Shift+Enter 优先队列
- **增量执行**: 仅重新执行从上次执行以来变更的部分
- **智能内存管理**: 1GB VRAM 也能运行（自动 offloading）
- **从输出恢复**: PNG/WebP/FLAC 文件嵌入完整工作流（含 seed）
- **节点旁路(Bypass)**: Ctrl+B 跳过节点但保持连线
- **节点静默(Mute)**: Ctrl+M 静默节点
- **节点固定(Pin)**: P 键固定节点位置
- **快速搜索**: 双击画布打开节点搜索面板
- **分组**: Ctrl+G 将选中节点编组
- **ComfyUI-Manager**: 官方节点包管理器

### F.3 n8n 流程逻辑补充

- **隐式自动迭代**: 大多数节点自动遍历所有 items，无需手动循环
- **Loop Over Items (SplitInBatches)**: 分批处理，可设置 batch size
- **条件循环**: IF 节点连接回前置节点形成环路
- **Node settings**: Always Output Data / Execute Once / Retry On Fail / On Error (Stop/Continue/Continue with error output)
- **Execution order**: 多分支时按拓扑顺序执行

---

*调研完成时间: 2026-04-17*
*数据来源: Automa Extension Docs (docs.extension.automa.site), n8n Docs (docs.n8n.io), ComfyUI GitHub (Comfy-Org/ComfyUI)*
  "nodes": [
    {
      "id": "node_1",
      "type": "trigger/ManualTrigger",
      "position": { "x": 100, "y": 200 },
      "data": {},
      "settings": {
        "onError": "inherit",
        "retryOnFail": false,
        "note": ""
      }
    },
    {
      "id": "node_2",
      "type": "browser/Navigate",
      "position": { "x": 350, "y": 200 },
      "data": {
        "url": "{{$var.baseUrl}}",
        "waitUntil": "networkidle"
      }
    }
  ],
  "edges": [
    {
      "id": "edge_1",
      "source": "node_1",
      "target": "node_2",
      "sourceHandle": "output",
      "targetHandle": "input"
    }
  ],
  "groups": [
    {
      "id": "group_1",
      "name": "Data Extraction",
      "nodeIds": ["node_3", "node_4"],
      "color": "#e3f2fd"
    }
  ]
}
```

### E.4 推荐的调试模式设计

结合三者优点，设计 **分层调试体系**：

| 层级 | 功能 | 参考来源 |
|------|------|----------|
| **Step Debug** | 逐节点单步执行，暂停在每个节点查看 IO 数据 | n8n Execution Debug |
| **Data Inspector** | 每个节点的输入/输出数据实时可视化面板 | n8n Data Pinning |
| **Breakpoint** | 在指定节点设置断点，运行到断点暂停 | 通用调试概念 |
| **CDP Mode** | 切换到 CDP 协议模拟真实用户操作 | Automa Debug Mode |
| **Replay** | 从执行日志中回放/重新执行某个节点 | n8n Execution Log |
| **Watch Variables** | 实时监控变量/表格值的变化 | IDE Watch |
| **Visual Feedback** | 执行时节点高亮、连线动画显示数据流向 | ComfyUI 执行高亮 |

### E.5 推荐的元素选择器方案

基于 Mimicry 的 Camoufox (Playwright) sidecar 架构：

```
选择器分层设计：
┌─────────────────────────────────────────┐
│  Visual Picker (Overlay on browser)     │  ← 用户可视化选择
│  - 鼠标悬停高亮元素                       │
│  - 点击选择，显示元素信息                  │
│  - 生成候选选择器列表（按优先级排序）       │
├─────────────────────────────────────────┤
│  Smart Selector Generator               │  ← 智能生成
│  - 优先 data-testid / aria-label        │
│  - 次选 unique id / class               │
│  - 兜底 CSS path / XPath               │
│  - 组合策略（text + structure）          │
├─────────────────────────────────────────┤
│  Selector Engine (Python Sidecar)       │  ← Playwright 执行
│  - CSS Selector                         │
│  - XPath                                │
│  - Playwright 专属: text=, role=         │
│  - 自定义 >> (iframe/shadow DOM)         │
└─────────────────────────────────────────┘
```

**关键设计决策**：
1. **多策略生成**：为每个元素生成多个候选选择器，按稳定性评分排序
2. **录制集成**：录制时自动生成选择器，存入节点配置
3. **选择器测试**：编辑器中可实时测试选择器，高亮匹配元素
4. **自愈机制**：执行时主选择器失败自动尝试备选选择器
5. **Playwright 原生语法**：直接利用 Playwright 的 `page.locator()` 能力，支持 `text=`、`role=`、`has-text=` 等高级定位

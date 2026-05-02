# Mimicry Block API 参考

> 本参考覆盖 **canonical block 格式**与 **42 个 action**。Action 在三处文件保持同步（`shared/action-map.json`、`sidecar/engine/action_map.py`、`src/types/action-map.ts`），由 `scripts/sync-action-map.py` 强制校验。修改 action 名后 **必须** 跑该脚本（CI 强制）。

## 概述

Mimicry 工作流是 **JSON 节点图**，由 `nodes` 与 `edges` 组成。每个节点是一个 Block，按 `kind` 分四类：

| kind | 用途 | 必填字段 |
|---|---|---|
| `action` | 浏览器操作（点击、导航、提取…） | `action`（PascalCase） |
| `condition` | 条件分支 | `data.condition`（表达式或类型） |
| `loop` | 循环 | `data.loopType` |
| `group` | 视觉分组（不影响执行） | — |

- **前端** 用 PascalCase（如 `Navigate`），**后端** 用 snake_case（如 `open`）
- 映射层自动转换；用户/文档全部使用前端 PascalCase
- 前端 `WorkflowNode.action` 字段与后端 `node.action` 字段值通过 `action_map` 互转

### 变量系统

- 变量以 `$` 开头（`$myVar`）
- 由 `SetVariable` 或带 `into` 字段的提取类 Block 写入
- 任意字符串字段中 `$myVar` 会在执行时自动替换
- 默认结果变量：`$_result`

---

## Canonical envelope（节点 JSON 形态）

```json
{
  "id": "node-1",
  "kind": "action",
  "action": "Navigate",
  "position": { "x": 100, "y": 80 },
  "data": {
    "url": "https://example.com",
    "sessionId": "default"
  },
  "settings": {
    "onError": "stop",
    "retryCount": 3,
    "retryInterval": 1000,
    "note": "可选注释",
    "disabled": false
  },
  "runtime": {
    "sessionId": "default"
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | ✅ | 节点唯一 ID（前端生成） |
| `kind` | `'action' \| 'condition' \| 'loop' \| 'group'` | ✅ | 节点种类 |
| `action` | string | 仅 `kind=action` | PascalCase action 名 |
| `position` | `{x, y}` | ✅ | 画布坐标 |
| `data` | object | ✅ | action 特定参数（见下文每个 action） |
| `settings` | `WorkflowNodeSettings` | ❌ | 错误处理与节点元信息 |
| `runtime` | object | ❌ | 运行时字段（如 `sessionId` 路由） |

> **历史 flat 格式**（`{type, action, url}`）已在 `2026-04-27` 全面切换到 canonical（commit `fd53189` `0d8810d` `0f072ee`）。Sidecar 接受 canonical；前端 `Workflow.nodes` 使用 `CanonicalWorkflowNode[]`。Rust transform 层 `legacy.rs` 仅作迁移使用。

### 多浏览器 / Session 路由

每个节点可在 `data.sessionId`（或 `runtime.sessionId`）指定目标 session，缺省 `"default"`。Session 由 `Profile` 决定（持久化 cookies/storage）。这是**多浏览器隔离的当前实现方式**，不需要专门的 `UseBrowser` block。

```json
{
  "id": "n1",
  "kind": "action",
  "action": "Navigate",
  "position": { "x": 0, "y": 0 },
  "data": { "url": "https://a.com", "sessionId": "shopper" }
}
```

### Settings（错误处理 + 元信息）

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `onError` | `'inherit' \| 'stop' \| 'continue' \| 'retry' \| 'fallback'` | `inherit` | 失败处理策略，`inherit` 沿用父分组/全局设置 |
| `retryOnFail` | bool | `false` | `onError='retry'` 的简写 |
| `retryCount` | number | `3` | 重试次数 |
| `retryInterval` | number | `1000` | 重试间隔（毫秒） |
| `note` | string | — | 节点注释（不参与执行） |
| `disabled` | bool | `false` | 禁用此节点（执行时跳过） |

---

## Action 全清单（42 个）

按功能分类。所有示例使用 canonical envelope。`position` / `id` 在示例中省略以聚焦参数。

### 🌐 浏览器导航

| Action | 后端 | 说明 |
|---|---|---|
| `Navigate` | `open` | 打开 URL |
| `NewTab` | `new_tab` | 新建标签页 |
| `SwitchTab` | `switch_tab` | 切换标签页（梯度匹配） |
| `CloseTab` | `close_tab` | 关闭标签页 |
| `GoBack` | `back` | 后退 |
| `GoForward` | `forward` | 前进 |
| `Reload` | `reload` | 刷新 |
| `WaitForPage` | `wait_for_page` | 等待页面状态 |

#### Navigate

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `url` | string | ✅ | 目标地址，需 `http://` 或 `https://` 开头 |

```json
{ "kind": "action", "action": "Navigate", "data": { "url": "https://example.com" } }
```

#### NewTab

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `url` | string | ❌ | 新标签页地址；缺省打开空白页 |

```json
{ "kind": "action", "action": "NewTab", "data": { "url": "https://example.com" } }
```

#### SwitchTab — Tab 梯度匹配

切换到指定标签页。识别多种匹配字段，**按下面优先级逐级降级**（来自 `executor.py::switch_tab`）：

1. `tabId`（运行时分配的稳定 ID）
2. `seq`（录制时的顺序号）
3. `urlOrigin` + `urlPath`（URL 部分匹配）
4. `title`（页面标题）
5. `tabIndex`（旧版兼容，从 0 起）

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tabId` | string | ❌ | 优先级 1 |
| `seq` | number | ❌ | 优先级 2 |
| `urlOrigin` | string | ❌ | 优先级 3，需配合 `urlPath` |
| `urlPath` | string | ❌ | 优先级 3 |
| `title` | string | ❌ | 优先级 4 |
| `tabIndex` | number | ❌ | 优先级 5（fallback） |

```json
{
  "kind": "action",
  "action": "SwitchTab",
  "data": { "urlOrigin": "https://github.com", "urlPath": "/issues" }
}
```

> 录制器（`recorder.py`）在用户切换 tab 时自动插入 `SwitchTab` 节点，包含上述全部识别字段（commit `956bfd3`）。

#### CloseTab

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tabId` | string | ❌ | 优先级 1 |
| `tabIndex` | number | ❌ | 旧版索引；缺省关闭当前页 |

```json
{ "kind": "action", "action": "CloseTab", "data": { "tabIndex": 1 } }
```

#### GoBack / GoForward / Reload

无 data 参数。

```json
{ "kind": "action", "action": "GoBack", "data": {} }
```

#### WaitForPage

等待页面达到指定加载状态。

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `state` | string | ❌ | `load` | `load` / `domcontentloaded` / `networkidle` |
| `timeout` | number | ❌ | `30000` | 毫秒 |

```json
{ "kind": "action", "action": "WaitForPage", "data": { "state": "networkidle", "timeout": 15000 } }
```

### 🖱️ 元素交互

| Action | 后端 | 说明 |
|---|---|---|
| `Click` | `click` | 点击 |
| `DblClick` | `dblclick` | 双击 |
| `Type` | `type` | 输入文本 |
| `Hover` | `hover` | 悬停 |
| `Scroll` | `scroll` | 滚动 |
| `SelectOption` | `select` | 下拉选择 |
| `PressKey` | `press_key` | 按键 |
| `Clear` | `clear` | 清空输入框 |
| `Focus` | `focus` | 聚焦 |
| `UploadFile` | `upload_file` | 上传文件 |
| `HandleDownload` | `handle_download` | 处理下载 |

#### Click / DblClick / Hover / Clear / Focus

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `selector` | string | ✅ | CSS 选择器或 `text=…` |

`Click` 额外支持 `force` (bool) 跳过 actionability 检查。

```json
{ "kind": "action", "action": "Click", "data": { "selector": "#submit-btn" } }
```

#### Type

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `selector` | string | ✅ | 输入框选择器 |
| `value` | string | ✅ | 输入内容，支持 `$var` |
| `humanize` | bool | ❌ | 默认 `true`（模拟敲键），`false` 用 `fill()` |

```json
{ "kind": "action", "action": "Type", "data": { "selector": "#email", "value": "$email" } }
```

#### SelectOption

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `selector` | string | ✅ | `<select>` 选择器 |
| `value` | string | ✅ | option 的 value 值 |

```json
{ "kind": "action", "action": "SelectOption", "data": { "selector": "#country", "value": "CN" } }
```

#### PressKey

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `selector` | string | ❌ | `body` | 目标，`body` = 全局 |
| `key` | string | ✅ | — | `Enter` / `Tab` / `Control+a` 等 |

```json
{ "kind": "action", "action": "PressKey", "data": { "selector": "#search", "key": "Enter" } }
```

#### Scroll

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `selector` | string | ❌ | window | 滚动目标 |
| `direction` | `'up' \| 'down' \| 'left' \| 'right'` | ❌ | `down` | 方向 |
| `amount` | number | ❌ | `300` | 像素 |

```json
{ "kind": "action", "action": "Scroll", "data": { "direction": "down", "amount": 500 } }
```

#### UploadFile

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `selector` | string | ✅ | `<input type="file">` 选择器 |
| `filePath` | string | ✅ | 本地文件绝对路径 |

```json
{ "kind": "action", "action": "UploadFile", "data": { "selector": "input[type=file]", "filePath": "/tmp/data.csv" } }
```

#### HandleDownload

监听下一次浏览器下载事件，落盘到指定路径。**应在触发下载的 Click/Navigate 之前**安排此节点。

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `savePath` | string | ❌ | `download` | 保存路径 |
| `timeout` | number | ❌ | `30000` | 等待下载触发的毫秒数 |
| `into` | string | ❌ | `$_result` | 实际保存路径写入此变量 |

```json
{ "kind": "action", "action": "HandleDownload", "data": { "savePath": "/tmp/file.pdf", "into": "$path" } }
```

### ⏳ 等待与同步

| Action | 后端 | 说明 |
|---|---|---|
| `Wait` | `wait` | 多模式等待 |
| `Delay` | `sleep` | 固定时长延时 |
| `WaitConnections` | `wait_connections` | 并行同步点（顺序模式下空操作） |

#### Wait — 三种模式

**等待元素出现**：

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `selector` | string | ✅ | — | 目标元素 |
| `timeout` | string | ❌ | `5s` | 如 `2s` / `500ms` |

**等待 URL 包含字符串**：

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `url_contains` | string | ✅ | — | URL 子串 |
| `timeout` | string | ❌ | `10s` | — |

**纯延时**：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `time` | string | ✅ | 等同于 `Delay` |

```json
{ "kind": "action", "action": "Wait", "data": { "selector": "#loaded", "timeout": "10s" } }
```

#### Delay

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `duration` | string | ✅ | 如 `1s` / `500ms` / `2.5s` |

```json
{ "kind": "action", "action": "Delay", "data": { "duration": "2s" } }
```

#### WaitConnections

并行执行模式的同步点。当前 sequential 模式下是 no-op（来自 `executor.py:718` 注释）。**用于未来并行执行**保持节点拓扑一致。

```json
{ "kind": "action", "action": "WaitConnections", "data": {} }
```

### 📊 数据提取与变量

| Action | 后端 | 说明 |
|---|---|---|
| `GetText` | `extract_text` | 元素文本 |
| `GetAttribute` | `extract_attr` | 元素属性 |
| `GetURL` | `get_url` | 当前 URL |
| `Screenshot` | `screenshot` | 截图 |
| `ExtractTable` | `extract_table` | 表格 → 二维数组 |
| `ElementExists` | `element_exists` | 元素是否存在 → bool |
| `SetVariable` | `set` | 设置变量 |
| `Export` | `export` | 导出全部变量 |
| `Transform` | `transform` | 变量转换 |

#### GetText / GetAttribute / GetURL

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `selector` | string | `GetText/GetAttribute` 必填 | — | 目标元素 |
| `attrName` | string | `GetAttribute` 必填 | — | 属性名 |
| `into` | string | ❌ | `$_result` | 写入变量 |

```json
{ "kind": "action", "action": "GetText", "data": { "selector": ".price", "into": "$price" } }
```

#### Screenshot

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `filename` | string | ❌ | `screenshot.png` | 保存路径 |

#### ExtractTable

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `selector` | string | ✅ | — | `<table>` 选择器 |
| `into` | string | ❌ | `$_result` | 写入变量（二维数组） |

#### ElementExists

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `selector` | string | ✅ | — | 目标元素 |
| `into` | string | ❌ | `$_result` | 写入变量（bool） |

#### SetVariable

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `variable` | string | ✅ | 变量名（带或不带 `$`） |
| `value` | any | ✅ | 任意值 |

```json
{ "kind": "action", "action": "SetVariable", "data": { "variable": "$counter", "value": 0 } }
```

#### Export

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `format` | `'json' \| 'csv'` | ❌ | `json` | 导出格式 |
| `path` | string | ❌ | `export.json` | 输出路径 |

> CSV 模式下：二维数组类型变量（如 `ExtractTable` 结果）逐行写入；其他变量以 `[key, value]` 行形式写入。

#### Transform

对变量做 list 转换。

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `source` | string | ❌ | `$_result` | 源变量 |
| `into` | string | ❌ | `$_result` | 目标变量 |
| `operation` | `'map' \| 'filter' \| 'sort' \| 'flatten' \| 'unique' \| 'identity'` | ❌ | `identity` | 操作 |
| `expression` | string | `map/filter` 时使用 | — | 内含 `$item` 占位符 |
| `reverse` | bool | ❌ | `false` | `sort` 时使用 |

```json
{ "kind": "action", "action": "Transform", "data": { "source": "$rows", "operation": "unique", "into": "$rows" } }
```

### 🍪 Cookie / Frame / Dialog

| Action | 后端 | 说明 |
|---|---|---|
| `Cookie` | `cookie` | 读/写/删 cookie |
| `SwitchFrame` | `switch_frame` | 切入 iframe |
| `HandleDialog` | `handle_dialog` | 拦截浏览器弹窗 |

#### Cookie

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `operation` | `'get' \| 'set' \| 'delete'` | ❌ | `get` | 操作 |
| `name` | string | `get/delete` 时使用 | — | cookie 名（缺省=全部） |
| `cookies` | array | `set` 时使用 | — | Playwright cookie 对象数组 |
| `into` | string | ❌ | `$_result` | `get` 时写入变量 |

```json
{ "kind": "action", "action": "Cookie", "data": { "operation": "get", "name": "session", "into": "$cookie" } }
```

#### SwitchFrame

切入 iframe 上下文。后续节点在该 iframe 内执行。`selector` 缺省时切回主 frame。

```json
{ "kind": "action", "action": "SwitchFrame", "data": { "selector": "iframe#payment" } }
```

#### HandleDialog

需在弹窗触发节点 **之前** 安排，对下一次 dialog 生效。

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `accept` | bool | ❌ | `true` | true=确认 |
| `text` | string | ❌ | `""` | prompt 输入文本 |

```json
{ "kind": "action", "action": "HandleDialog", "data": { "accept": true, "text": "ok" } }
```

### ⚙️ 高级 / 工具

| Action | 后端 | 说明 |
|---|---|---|
| `RunScript` | `run_script` | 执行 JS |
| `HttpRequest` | `http_request` | HTTP 请求 |
| `Log` | `log` | 输出日志 |
| `Comment` | `comment` | 注释（无操作） |
| `ExecuteWorkflow` | `execute_workflow` | 嵌套执行子工作流 |
| `Stop` | `stop` | 停止当前工作流 |
| `Fail` | `fail` | 抛错（触发 onError） |
| `LoopBreakpoint` | `loop_breakpoint` | 跳出当前循环 |

#### RunScript

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `script` | string | ✅ | JS 表达式 |
| `into` | string | ❌ | 返回值写入变量 |

```json
{ "kind": "action", "action": "RunScript", "data": { "script": "return document.title", "into": "$title" } }
```

#### HttpRequest

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `url` | string | ✅ | — | 请求地址 |
| `method` | string | ❌ | `GET` | HTTP 方法 |
| `headers` | object | ❌ | `{}` | 请求头 |
| `body` | string | ❌ | — | 请求体 |
| `timeout` | number | ❌ | `30` | 秒 |
| `into` | string | ❌ | `$_result` | 响应写入变量 |

> 响应若为 JSON 自动解析为对象；否则为字符串。

#### Log

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `parts` | string[] | ✅ | 消息片段，支持 `$var` |

```json
{ "kind": "action", "action": "Log", "data": { "parts": ["price=", "$price"] } }
```

#### Comment

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `comment` | string | ❌ | 备注内容（仅显示） |

#### ExecuteWorkflow

嵌套执行另一个工作流 JSON。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `workflow` | object | ✅ | canonical workflow JSON |
| `into` | string | ❌ | 子工作流结果写入变量 |

#### Stop / Fail

`Stop` 优雅停止；`Fail` 抛错（参与 `onError` 处理链）。

| 参数（仅 Fail） | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `message` | string | ❌ | `Workflow failed` | 错误消息 |

```json
{ "kind": "action", "action": "Fail", "data": { "message": "validation failed: $reason" } }
```

#### LoopBreakpoint

跳出包围的 `Loop`（仅在 `kind=loop` 子节点中有效）。

```json
{ "kind": "action", "action": "LoopBreakpoint", "data": {} }
```

---

## 流程控制（kind ≠ action）

### Condition（`kind: "condition"`）

```json
{
  "kind": "condition",
  "position": { "x": 0, "y": 0 },
  "data": { "condition": "exists(\"#login-btn\")" }
}
```

| 字段 | 说明 |
|---|---|
| `condition` | 条件表达式（见下） |
| `selector` | 部分条件需要 |
| `matchValue` | 部分条件需要 |

| 表达式形式 | 说明 |
|---|---|
| `exists("sel")` | 元素存在 |
| `not_exists("sel")` | 不存在 |
| `visible("sel")` | 元素可见 |
| `text("sel") == "foo"` | 文本相等 |
| `url_contains("path")` | URL 包含 |
| 任意 JS 表达式 | 自定义；`$var` 会被替换 |

边的 `sourceHandle` 用 `true` / `false` 区分两个分支。

### Loop（`kind: "loop"`）

```json
{
  "kind": "loop",
  "position": { "x": 0, "y": 0 },
  "data": {
    "loopType": "elements",
    "selector": ".product",
    "variable": "$item",
    "max": 100
  }
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `loopType` | `'count' \| 'items' \| 'while' \| 'elements'` | 循环类型 |
| `count` | number | 仅 `loopType=count`：固定次数 |
| `selector` | string | 仅 `loopType=elements/items`：列表元素选择器 |
| `condition` | string | 仅 `loopType=while`：条件表达式 |
| `variable` | string | 当前迭代写入此变量 |
| `max` | number | 安全上限 |

`LoopElements`（action）等同于 `kind=loop, loopType=elements`，编辑器优先用后者。

### Group（`kind: "group"`）

```json
{
  "kind": "group",
  "position": { "x": 0, "y": 0 },
  "data": { "label": "登录流程", "color": "#3b82f6" }
}
```

不参与执行，仅画布分组。

---

## 错误处理（settings.onError）

`settings.onError` 五个值：

| 值 | 含义 |
|---|---|
| `inherit` | 继承父分组/全局策略（默认） |
| `stop` | 失败立刻停止整个工作流 |
| `continue` | 失败跳过此节点继续下一节点 |
| `retry` | 重试本节点（配合 `retryCount` / `retryInterval`） |
| `fallback` | 走 fallback 分支（边的 `sourceHandle="fallback"`） |

```json
{
  "kind": "action",
  "action": "Click",
  "data": { "selector": "#btn" },
  "settings": { "onError": "retry", "retryCount": 5, "retryInterval": 2000 }
}
```

`retryOnFail: true` 是 `onError: "retry"` 的简写。

---

## 校验

`workflow_validator.rs` 在 `workflow_execute` 之前做静态校验，37 条规则（W001-W014 + I001-I011，参考 `docs/design/decisions.md` ADR-002 与 `src-tauri/src/workflow_validator.rs`）。常见错误：

- 缺少 `id` / 重复 `id`
- `kind=action` 但 `action` 为空
- 边的 `source/target` 引用不存在的节点
- 不支持的 `action`（不在 action map）

前端 Problems 面板（BottomPanel.vue）订阅 `validation` store，节点本身显示诊断徽标。

---

## 相关文档

- [block-system.md](design/block-system.md) — schema 设计原理与三层契约
- [data-flow.md](design/data-flow.md) — 工作流执行链路（前端→Rust→sidecar）
- [decisions.md](design/decisions.md) — ADR-001 JSON 直执行
- [`shared/action-map.json`](../shared/action-map.json) — action 名映射源

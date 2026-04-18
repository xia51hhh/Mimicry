# Mimicry Block API 参考

## 概述

Mimicry 使用 **Block（节点）** 构建自动化工作流。每个 Block 代表一个操作步骤，通过流程图连接执行。

- **前端**使用 PascalCase 命名（如 `Navigate`）
- **后端**使用 lowercase 命名（如 `open`）
- 映射层自动转换，用户只需关注前端名称

### 变量系统

- 变量以 `$` 开头，如 `$myVar`
- 通过 `SetVariable` 或提取类 Block 的 `into` 参数设置
- 在任意字符串字段中使用 `$myVar` 引用，运行时自动替换

---

## 🌐 浏览器导航

| Block | 说明 |
|-------|------|
| Navigate | 打开 URL |
| NewTab | 新建标签页 |
| SwitchTab | 切换标签页 |
| CloseTab | 关闭标签页 |
| GoBack | 后退 |
| GoForward | 前进 |
| Reload | 刷新页面 |
| HandleDialog | 处理弹窗 |

### Navigate

打开指定 URL。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| url | string | ✅ | 目标地址，需以 `http://` 或 `https://` 开头 |

```json
{ "type": "action", "action": "Navigate", "url": "https://example.com" }
```

### NewTab

在新标签页中打开页面。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| url | string | ❌ | 新标签页地址，留空则打开空白页 |

```json
{ "type": "action", "action": "NewTab", "url": "https://example.com" }
```

### SwitchTab

切换到指定标签页。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| tabIndex | number | ✅ | 标签页序号（从 0 开始） |

```json
{ "type": "action", "action": "SwitchTab", "tabIndex": 1 }
```

### CloseTab

关闭指定标签页。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| tabIndex | number | ❌ | 标签页序号，省略则关闭当前页 |

```json
{ "type": "action", "action": "CloseTab", "tabIndex": 0 }
```

### GoBack / GoForward / Reload

无参数，直接执行浏览器后退/前进/刷新。

```json
{ "type": "action", "action": "GoBack" }
```

### HandleDialog

处理浏览器弹窗（alert/confirm/prompt）。需在弹窗触发 **前** 设置。

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| accept | boolean | ❌ | true | true=确认，false=取消 |
| text | string | ❌ | "" | prompt 弹窗的输入文本 |

```json
{ "type": "action", "action": "HandleDialog", "accept": true, "text": "输入内容" }
```

---

## 🖱️ 元素交互

| Block | 说明 |
|-------|------|
| Click | 点击 |
| DblClick | 双击 |
| Type | 输入文本 |
| Hover | 悬停 |
| Scroll | 滚动 |
| SelectOption | 选择下拉项 |
| PressKey | 按键 |
| Clear | 清空输入框 |
| Focus | 聚焦 |
| UploadFile | 上传文件 |

### Click / DblClick / Hover / Clear / Focus

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| selector | string | ✅ | CSS 选择器或 `text=...` |

```json
{ "type": "action", "action": "Click", "selector": "#submit-btn" }
```

### Type

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| selector | string | ✅ | 输入框选择器 |
| value | string | ✅ | 输入内容，支持 `$var` 引用 |

```json
{ "type": "action", "action": "Type", "selector": "#email", "value": "user@example.com" }
```

### SelectOption

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| selector | string | ✅ | `<select>` 元素选择器 |
| value | string | ✅ | option 的 value 值 |

```json
{ "type": "action", "action": "SelectOption", "selector": "#country", "value": "CN" }
```

### PressKey

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| selector | string | ❌ | body | 目标元素，`body` 表示全局 |
| key | string | ✅ | — | 按键名，如 `Enter`、`Tab`、`Control+a` |

```json
{ "type": "action", "action": "PressKey", "selector": "#search", "key": "Enter" }
```

### Scroll

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| selector | string | ❌ | window | 滚动目标 |
| direction | string | ❌ | down | `down` 或 `up` |
| amount | number | ❌ | 300 | 滚动像素 |

```json
{ "type": "action", "action": "Scroll", "direction": "down", "amount": 500 }
```

### UploadFile

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| selector | string | ✅ | `<input type="file">` 选择器 |
| filePath | string | ✅ | 本地文件绝对路径 |

```json
{ "type": "action", "action": "UploadFile", "selector": "input[type=file]", "filePath": "C:\\data\\file.csv" }
```

---

## 📊 数据提取

| Block | 说明 |
|-------|------|
| Wait | 等待条件 |
| GetText | 获取元素文本 |
| GetAttribute | 获取元素属性 |
| GetURL | 获取当前 URL |
| Screenshot | 截图 |
| ExtractTable | 提取表格数据 |
| SetVariable | 设置变量 |
| Export | 导出数据 |

### Wait

支持三种等待模式：

**等待元素：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| selector | string | ✅ | 等待该元素出现 |
| timeout | string | ❌ | 超时，默认 `5s` |

**等待 URL：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| url_contains | string | ✅ | URL 包含此字符串时通过 |
| timeout | string | ❌ | 超时，默认 `10s` |

**等待时间：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| time | string | ✅ | 等待时长，如 `2s`、`500ms` |

```json
{ "type": "action", "action": "Wait", "selector": "#loaded", "timeout": "10s" }
```

### GetText

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| selector | string | ✅ | — | 目标元素 |
| into | string | ❌ | $_result | 存入变量名 |

```json
{ "type": "action", "action": "GetText", "selector": ".price", "into": "$price" }
```

### GetAttribute

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| selector | string | ✅ | — | 目标元素 |
| attrName | string | ✅ | — | 属性名（href, src, class 等） |
| into | string | ❌ | $_result | 存入变量名 |

```json
{ "type": "action", "action": "GetAttribute", "selector": "a.link", "attrName": "href", "into": "$link" }
```

### GetURL

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| into | string | ❌ | $_result | 存入变量名 |

```json
{ "type": "action", "action": "GetURL", "into": "$currentUrl" }
```

### Screenshot

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| filename | string | ❌ | screenshot.png | 保存路径 |

```json
{ "type": "action", "action": "Screenshot", "filename": "result.png" }
```

### ExtractTable

提取 `<table>` 为二维数组。

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| selector | string | ✅ | — | 表格选择器 |
| into | string | ❌ | $_result | 存入变量名 |

```json
{ "type": "action", "action": "ExtractTable", "selector": "table.data", "into": "$tableData" }
```

### SetVariable

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| variable | string | ✅ | 变量名（如 `$counter`） |
| value | any | ✅ | 变量值 |

```json
{ "type": "action", "action": "SetVariable", "variable": "$counter", "value": 0 }
```

### Export

导出当前所有变量到文件。

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| format | string | ❌ | json | `json` 或 `csv` |
| path | string | ❌ | export.json | 输出文件路径 |

```json
{ "type": "action", "action": "Export", "format": "csv", "path": "output.csv" }
```

> **CSV 导出规则**：二维数组类型的变量（如 ExtractTable 的结果）逐行写入；其他变量以 `[key, value]` 形式写入。

---

## ⚙️ 高级操作

| Block | 说明 |
|-------|------|
| RunScript | 执行 JavaScript |
| HttpRequest | HTTP 请求 |
| Delay | 延时等待 |
| Log | 输出日志 |
| Comment | 注释 |

### RunScript

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| script | string | ✅ | JavaScript 表达式 |
| into | string | ❌ | 将返回值存入变量 |

```json
{ "type": "action", "action": "RunScript", "script": "return document.title", "into": "$title" }
```

### HttpRequest

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| url | string | ✅ | — | 请求地址 |
| method | string | ❌ | GET | GET/POST/PUT/DELETE |
| headers | object | ❌ | {} | 请求头 |
| body | string | ❌ | — | 请求体（POST/PUT） |
| timeout | number | ❌ | 30 | 超时秒数 |
| into | string | ❌ | $_result | 响应存入变量 |

```json
{
  "type": "action",
  "action": "HttpRequest",
  "url": "https://api.example.com/data",
  "method": "POST",
  "body": "{\"key\": \"$value\"}",
  "into": "$response"
}
```

> 响应为 JSON 时自动解析为对象，否则存为字符串。

### Delay

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| duration | string | ✅ | 时长，如 `1s`、`500ms`、`2.5s` |

```json
{ "type": "action", "action": "Delay", "duration": "2s" }
```

### Log

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| parts | string[] | ✅ | 消息片段，支持 `$var` 引用 |

```json
{ "type": "action", "action": "Log", "parts": ["当前价格:", "$price"] }
```

### Comment

无参数，不执行任何操作。用于在流程图中添加说明。

```json
{ "type": "action", "action": "Comment", "comment": "以下步骤处理登录流程" }
```

---

## 🔀 流程控制

### Condition（条件节点）

| 参数 | 类型 | 说明 |
|------|------|------|
| condition | string | 条件类型 |
| selector | string | 目标元素（部分条件需要） |
| matchValue | string | 匹配值（部分条件需要） |

**支持的条件：**

| 条件 | 格式 | 说明 |
|------|------|------|
| exists | `exists("selector")` | 元素存在 |
| not_exists | `not_exists("selector")` | 元素不存在 |
| visible | `visible("selector")` | 元素可见 |
| text_contains | `text("selector") == "value"` | 文本匹配 |
| url_contains | `url_contains("path")` | URL 包含 |
| expression | JS 表达式 | 自定义条件 |

满足条件执行 `children`，否则执行 `elseChildren`。

### Loop（循环节点）

| 参数 | 类型 | 说明 |
|------|------|------|
| loopType | string | `count` / `items` / `while` |
| count | number | 固定次数（loopType=count） |
| selector | string | 元素列表（loopType=items） |
| condition | string | 条件表达式（loopType=while） |
| variable | string | 循环变量名 |
| max | number | 最大迭代次数（安全上限） |

### Group（分组节点）

| 参数 | 类型 | 说明 |
|------|------|------|
| label | string | 分组名称 |
| color | string | 颜色（hex） |

---

## ❌ 错误处理

每个节点都支持 `onError` 参数：

| 值 | 说明 |
|----|------|
| stop | 停止整个工作流（默认） |
| continue | 跳过当前步骤，继续下一步 |
| retry | 重试当前步骤 |

配合 `retryCount`（默认 3）控制重试次数。

```json
{ "type": "action", "action": "Click", "selector": "#btn", "onError": "retry", "retryCount": 5 }
```

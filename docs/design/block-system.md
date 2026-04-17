# Block 体系设计

> **状态**: Draft | **最后更新**: 2026-04-17

---

## Block 分类体系

Mimicry 的 Block 分为 **5 大类**，基于 [方案对比](../research/solution-comparison.md) Section E.1 的建议调整而来。

```
Block 分类
├── 🎯 触发与控制 (Trigger & Control)
├── 🌐 浏览器操作 (Browser)
├── 👆 页面交互 (Page Interaction)
├── 📊 数据处理 (Data)
└── ⚡ 高级 (Advanced)
```

---

### 1. 触发与控制（Trigger & Control）

| Block | 类型标识 | 功能说明 |
|-------|---------|---------|
| Manual Trigger | `trigger/Manual` | 手动触发工作流入口 |
| Schedule Trigger | `trigger/Schedule` | 定时/Cron 触发 |
| Condition | `control/Condition` | 条件分支（if/else），支持多条件 + fallback |
| Loop Data | `control/LoopData` | 遍历数据集合（变量/JSON 数组/表格） |
| Loop Elements | `control/LoopElements` | 遍历页面匹配元素 |
| Repeat | `control/Repeat` | 固定次数重复 |
| While Loop | `control/WhileLoop` | 条件循环 |
| Loop Breakpoint | `control/LoopBreakpoint` | 循环作用域终点标记 |
| Delay | `control/Delay` | 延时等待（毫秒） |
| Wait Connections | `control/WaitConnections` | 等待所有分支完成（汇合节点） |
| Stop | `control/Stop` | 停止工作流执行 |

### 2. 浏览器操作（Browser）

| Block | 类型标识 | 功能说明 |
|-------|---------|---------|
| Navigate | `browser/Navigate` | 导航到 URL |
| New Tab | `browser/NewTab` | 打开新标签页 |
| Switch Tab | `browser/SwitchTab` | 切换标签页 |
| Go Back | `browser/GoBack` | 浏览器后退 |
| Go Forward | `browser/GoForward` | 浏览器前进 |
| Reload | `browser/Reload` | 刷新页面 |
| Close Tab | `browser/CloseTab` | 关闭标签页 |
| Switch Frame | `browser/SwitchFrame` | 切换到 iframe |
| Wait For Page | `browser/WaitForPage` | 等待页面加载完成 |
| Handle Dialog | `browser/HandleDialog` | 处理 alert/confirm/prompt |

### 3. 页面交互（Page Interaction）

| Block | 类型标识 | 功能说明 |
|-------|---------|---------|
| Click | `interaction/Click` | 点击元素 |
| Type | `interaction/Type` | 输入文本 |
| Hover | `interaction/Hover` | 悬停元素 |
| Press Key | `interaction/PressKey` | 模拟键盘按键 |
| Scroll | `interaction/Scroll` | 滚动页面/元素 |
| Select Option | `interaction/SelectOption` | 下拉选择 |
| Upload File | `interaction/UploadFile` | 上传文件 |
| Clear | `interaction/Clear` | 清空输入框 |
| Focus | `interaction/Focus` | 聚焦元素 |

### 4. 数据处理（Data）

| Block | 类型标识 | 功能说明 |
|-------|---------|---------|
| Get Text | `data/GetText` | 获取元素文本内容 |
| Get Attribute | `data/GetAttribute` | 获取元素属性值 |
| Get URL | `data/GetURL` | 获取当前页面 URL |
| Screenshot | `data/Screenshot` | 截图（页面/元素） |
| Extract Table | `data/ExtractTable` | 提取表格数据 |
| Set Variable | `data/SetVariable` | 设置变量值 |
| Transform | `data/Transform` | 数据转换（映射/过滤/排序） |
| Export | `data/Export` | 导出数据（JSON/CSV） |
| Cookie | `data/Cookie` | 读写 Cookie |

### 5. 高级（Advanced）

| Block | 类型标识 | 功能说明 |
|-------|---------|---------|
| Run Script | `advanced/RunScript` | 执行自定义 JS/Python 脚本 |
| HTTP Request | `advanced/HttpRequest` | 发送 HTTP 请求 |
| Execute Workflow | `advanced/ExecuteWorkflow` | 调用子工作流 |
| Package | `advanced/Package` | 封装的 Block 集合（见 [Package 系统](./package-system.md)） |
| Log | `advanced/Log` | 输出日志 |
| Comment | `advanced/Comment` | 画布备注（不执行） |

---

## Block JSON Schema

每个 Block 节点在工作流 JSON 中的结构：

```json
{
  "id": "node_abc123",
  "type": "interaction/Click",
  "position": { "x": 350, "y": 200 },
  "data": {
    "selector": "#submit-btn",
    "selectorFallbacks": [
      "text=Submit",
      "[data-testid='submit']"
    ],
    "clickType": "single",
    "button": "left",
    "waitBefore": 0
  },
  "settings": {
    "onError": "inherit",
    "retryOnFail": false,
    "retryCount": 1,
    "retryInterval": 1000,
    "note": "点击提交按钮"
  }
}
```

### data 字段（Block 特定配置）

不同类型的 Block 有不同的 `data` 字段。示例：

**Navigate Block**：
```json
{
  "url": "https://example.com/{{$var.path}}",
  "waitUntil": "networkidle",
  "timeout": 30000
}
```

**Condition Block**：
```json
{
  "conditions": [
    {
      "group": "AND",
      "rules": [
        { "left": "{{$prev.status}}", "operator": "==", "right": "200" },
        { "left": "{{$var.retry}}", "operator": "<", "right": "3" }
      ]
    }
  ]
}
```

**Loop Data Block**：
```json
{
  "loopId": "loop_1",
  "source": "variable",
  "variableName": "items",
  "maxIterations": 100
}
```

---

## Block 设置

每个 Block 均具备以下通用设置（`settings` 字段）：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `onError` | `string` | `"inherit"` | 错误处理策略：`stop` / `continue` / `retry` / `fallback` / `inherit` |
| `retryOnFail` | `boolean` | `false` | 失败时是否重试 |
| `retryCount` | `number` | `1` | 重试次数 |
| `retryInterval` | `number` | `1000` | 重试间隔（ms） |
| `note` | `string` | `""` | 用户备注，不影响执行 |
| `disabled` | `boolean` | `false` | 是否禁用（跳过执行） |

详见 [设计决策 ADR-005](./decisions.md#adr-005-错误处理--block-级独立配置)。

---

## Block 连接规则

### 端口定义

每个 Block 有固定的输入/输出端口：

```
标准 Block:        [input] ──Block── [output]
Condition Block:   [input] ──Block── [true] [false] [fallback]
Loop Block:        [input] ──Block── [loop-body] [completed]
Loop Breakpoint:   [input] ──Block── [output]
```

### 连接约束

| 规则 | 说明 |
|------|------|
| 单入多出 | 一个输出端口可连接多个输入端口（并行分支） |
| 多入单出 | 一个输入端口可接收多条连线（汇合） |
| 无自环 | Block 不可连接自身 |
| 类型兼容 | Trigger Block 只有输出端口，不可作为目标 |
| Loop 配对 | Loop Block 必须有对应的 Loop Breakpoint（相同 `loopId`） |

### 连线数据

```json
{
  "id": "edge_1",
  "source": "node_1",
  "target": "node_2",
  "sourceHandle": "output",
  "targetHandle": "input",
  "label": ""
}
```

---

## 相关文档

- [设计决策记录](./decisions.md)
- [数据流设计](./data-flow.md)
- [Package 系统设计](./package-system.md)
- [方案对比](../research/solution-comparison.md)

# Block 体系设计

> **状态**: Partial | **最后更新**: 2026-04-28

> 现实边界：canonical node schema 已开始围绕 `kind + action + data + settings` 落地，前端导入/导出和 Python executor 已支持 canonical / legacy 兼容；完整 graph execution、Package IO 和 selector self-healing 仍是后续任务。

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

> **Status (2026-04-27)**: Canonical schema is being standardized around `kind + action + data + settings`. Legacy workflow JSON may still contain Vue Flow-style `type` plus `data.action`; import/execution code should normalize both shapes during migration.

每个 Block 节点在工作流 JSON 中的结构：

```json
{
  "id": "node_abc123",
  "kind": "action",
  "action": "Click",
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

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `string` | 节点唯一 ID |
| `kind` | `action \| condition \| loop \| group` | 运行时语义类别；Vue Flow 组件渲染也可使用该值作为 UI node type |
| `action` | `string` | `kind = action` 时的动作名，例如 `Navigate` / `Click` / `SetVariable` |
| `position` | `{ x, y }` | 画布位置 |
| `data` | `object` | Block 特定配置，不再承载运行时类别本身 |
| `settings` | `object` | 通用错误处理、重试、禁用、备注等配置 |
| `runtime` | `object` | 运行期绑定信息，例如 `{ "sessionId": "profile-a" }` |

### 兼容说明

历史数据可能仍使用以下形态：

```json
{
  "id": "node_abc123",
  "type": "action",
  "position": { "x": 350, "y": 200 },
  "data": {
    "action": "Click",
    "selector": "#submit-btn"
  }
}
```

迁移期规则：

1. 前端导出应输出 canonical schema。
2. 前端导入应接受 canonical schema 和 legacy Vue Flow schema。
3. Python executor 应在执行前 normalize canonical / legacy 节点。
4. `type` 只作为 Vue Flow UI 渲染概念保留，不再作为跨层运行时 Block 类型规范。

### Action 映射源头

`shared/action-map.json` 是前端 PascalCase action 与 Python backend action 名称的共享源头：

- TypeScript 映射：`src/types/action-map.ts`
- Python 映射：`sidecar/engine/action_map.py`
- 同步脚本：`scripts/sync-action-map.py`
- Python 同步测试：`sidecar/tests/test_action_map.py`

新增或重命名 action 时，应先修改 `shared/action-map.json`，再用同步脚本生成 TS/Python 映射，并运行 action map 测试。

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

## Block 反检测行为模拟

与页面元素交互的 Block 需要模拟真实用户行为，避免被反爬系统检测。详见 [反检测体系文档](../anti-detection.md)。

### 行为模拟覆盖

| 行为 | 实现层 | Block 影响 |
|------|--------|-----------|
| 鼠标轨迹 | Camoufox C++ (`humanize=True`) | Click, DblClick, Hover |
| 逐字符输入 | Controller `type_text()` | Type |
| 滚轮分步 | Controller `scroll()` via `mouse.wheel()` | Scroll |
| 下拉前置 click | Controller `select_option()` | SelectOption |
| 动作间延迟 | Executor `_human_delay()` | 所有 action 类型 |
| 导航等待 | Controller `navigate()` `wait_until=networkidle` | Navigate, GoBack, GoForward, Reload |

### 延迟控制

执行时可配置：
- **延迟开关**: 启用/关闭动作间随机延迟
- **延迟倍率**: 0.1x - 5.0x 全局倍率系数

传递方式：`workflow_execute` 命令的 `humanize: bool` + `delay_multiplier: float` 参数。

---

## 相关文档

- [设计决策记录](./decisions.md)
- [数据流设计](./data-flow.md)
- [Package 系统设计](./package-system.md)
- [方案对比](../research/solution-comparison.md)

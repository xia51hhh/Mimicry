# 工作流静态分析与实时验证系统

## 目标
在 Rust 端（src-tauri）建立通用的工作流 JSON 静态分析框架，在执行前拦截配置错误，减少运行时崩溃。

## 技术方案
- **实现语言**: Rust（`src-tauri/src/workflow_validator.rs`）
- **数据格式**: 输入 `serde_json::Value`（workflow nodes 数组），输出 `Vec<Diagnostic>`
- **触发时机**: `workflow_execute` Tauri 命令前调用；Phase 3 扩展到编辑器实时
- **行为**: Error 级阻止执行并返回错误列表；Warning/Info 仅记录日志+前端展示

## 输出格式
```rust
pub struct Diagnostic {
    pub level: DiagLevel,       // Error | Warning | Info
    pub rule_id: String,        // "E001", "W002", etc.
    pub node_id: Option<String>,// workflow node id
    pub action: Option<String>, // action 名称
    pub message: String,        // 人类可读消息
    pub suggestion: Option<String>,
}

pub enum DiagLevel { Error, Warning, Info }
```

JSON 序列化示例：
```json
{
  "level": "error",
  "ruleId": "E001",
  "nodeId": "node_xxx",
  "action": "Click",
  "message": "\"Click\" 节点缺少必填字段 \"selector\"",
  "suggestion": "添加 CSS 选择器或 text= 选择器"
}
```

---

## 完整规则集（37 条）

### Error 级规则（阻止执行）

| ID | 名称 | 检测条件 | 涉及 Action |
|----|------|---------|------------|
| E001 | 缺少 selector | `data.selector` 为空/未定义 | Click, DblClick, Type, Clear, Hover, Focus, SelectOption, GetText, GetAttribute, ExtractTable, ElementExists, UploadFile |
| E002 | 缺少 url | `data.url` 为空/未定义 | Navigate, HttpRequest |
| E003 | 缺少 key | `data.key` 为空/未定义 | PressKey |
| E004 | 缺少 script | `data.script` 为空/未定义 | RunScript |
| E005 | 缺少 variable | `data.variable` 为空/未定义 | SetVariable |
| E006 | 缺少 filePath | `data.filePath` 为空/未定义 | UploadFile |
| E007 | Loop items/elements 缺少 selector | `kind=loop`, `loopType` 为 items/elements, `data.selector` 空 | Loop |
| E008 | While Loop 缺少条件 | `kind=loop`, `loopType=while`, `data.whileCondition` 空 | Loop |
| E009 | Condition 缺少条件表达式 | `kind=condition`, `data.condition` 空 | Condition |
| E010 | HttpRequest URL 协议无效 | `data.url` 不以 http(s):// 开头且不含 `{{` 模板 | HttpRequest |
| E011 | 未知 action 类型 | `kind=action` 但 `action` 不在 action-map 43 个合法值中 | 所有 |

### Warning 级规则（不阻止执行）

| ID | 名称 | 检测条件 | 涉及 Action |
|----|------|---------|------------|
| W001 | 变量引用未定义 | data 字段含 `$varName` 但上游无对应 Set 操作 | 所有使用 ctx.resolve() 的 |
| W002 | Tab 不对称：Condition 分支 | children vs elseChildren 中 NewTab/CloseTab 数量不对称 | Condition+NewTab/CloseTab |
| W003 | Loop 内 Tab 泄漏 | Loop children 有 NewTab 无对应 CloseTab | Loop+NewTab/CloseTab |
| W004 | SwitchTab seq 超范围 | `data.seq` > 上游 NewTab 数量 + 1 | SwitchTab |
| W005 | While Loop 无条件变更 | while 循环体无副作用 action | Loop(while) |
| W006 | tabIndex 类型错误 | `data.tabIndex` 为 string 而非 number | SwitchTab, CloseTab |
| W007 | count/max 类型错误 | `data.count` 或 `data.max` 为 string | Loop |
| W008 | 空 Condition 分支 | children 或 elseChildren 为空 | Condition |
| W009 | 空 Loop 体 | children 为空 | Loop |
| W010 | 未使用的 Loop 变量 | `data.variable` 定义了但 children 中未引用 `$variable` | Loop |
| W011 | GetAttribute 缺少 attrName | `data.attrName` 为空 | GetAttribute |
| W012 | LoopBreakpoint 不在 Loop 内 | 祖先节点无 Loop | LoopBreakpoint |
| W013 | 条件表达式语法错误 | condition/whileCondition tokenize 失败 | Condition, Loop(while) |
| W014 | Export 路径遍历风险 | 路径含 `..` 或绝对路径 | Export, Screenshot |
| W015 | ExecuteWorkflow 缺少定义 | `data.workflow` 为空 | ExecuteWorkflow |

### Info 级规则（改善建议）

| ID | 名称 | 检测条件 | 涉及 Action |
|----|------|---------|------------|
| I001 | Fail/Stop 后死代码 | 线性序列中 Fail/Stop 之后有后续节点 | Fail, Stop |
| I002 | 连续重复 action | 连续两节点 action+data 完全相同 | 所有 |
| I003 | 选择器太通用 | selector 为单标签 (div, body...) | 使用 selector 的 |
| I004 | 选择器为空（有默认值）| Scroll/PressKey selector 空 | Scroll, PressKey |
| I005 | Comment 不参与执行 | Comment 节点存在 | Comment |
| I006 | WaitConnections 空操作 | WaitConnections 在顺序模式下无效 | WaitConnections |
| I007 | Delay 时间过长 | duration > 30s | Delay |
| I008 | Loop maxIterations 过大 | max > 1000 | Loop |
| I009 | 节点已禁用 | settings.disabled = true | 所有 |
| I010 | Navigate URL 缺少协议 | url 非空但不以 http(s)://或 {{ 开头 | Navigate, NewTab |
| I011 | Transform source 未验证 | data.source 引用的变量上游无定义 | Transform |

---

## Action 必填字段速查

| Action | 必填字段 | 默认值字段 |
|--------|---------|-----------|
| Navigate | url | waitUntil, timeout |
| Click/DblClick/Clear/Hover/Focus | selector | — |
| Type | selector | value(""), humanize |
| SelectOption | selector | value |
| PressKey | key | selector("body") |
| Scroll | — | selector("window"), direction, amount |
| GetText | selector | into("$_result") |
| GetAttribute | selector | attrName, into |
| ExtractTable | selector | into |
| GetURL | — | into |
| Screenshot | — | filename |
| SetVariable | variable | value |
| RunScript | script | into |
| HttpRequest | url | method, headers, body, timeout, into |
| UploadFile | selector, filePath | — |
| Export | — | format, path |
| HandleDialog | — | accept, text |
| SwitchTab | — | seq, urlOrigin, urlPath, title, tabIndex |
| CloseTab | — | tabId, tabIndex |
| NewTab | — | url |
| ElementExists | selector | into |
| Fail | — | message |

---

## 实施阶段

### Phase 1: P0+P1（当前）
- `workflow_validator.rs`: Diagnostic struct + validate() 入口
- E001-E011: 单节点必填字段 + 类型检查
- W002-W004: Tab 分支一致性（需要树遍历）
- W008-W009: 空分支/空循环体
- W012: LoopBreakpoint 位置检查
- 集成到 `workflow_execute` 命令前

### Phase 2: 跨节点分析
- W001: 变量作用域（需要拓扑排序）
- W005: While 无条件变更
- W010: 未使用 Loop 变量
- W013: 条件语法预检
- I001: 死代码检测

### Phase 3: 编辑器集成
- Tauri command `workflow_validate` 独立调用
- 前端侧边栏问题面板
- 画布节点 warning 图标
- PropertyPanel 字段级实时验证

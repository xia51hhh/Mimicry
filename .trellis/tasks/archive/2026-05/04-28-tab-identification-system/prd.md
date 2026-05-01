# Tab 标识与匹配系统

## 目标
实现一套可靠的 Tab 标识机制，支持录制回放、分支工作流、多 tab 场景。

## Tab 数据结构

```typescript
interface TabInfo {
  tabId: string;        // 后端随机 UUID，运行时唯一标识
  seq: number;          // 创建序号（第 N 个打开的 tab = N，永不改变）
  urlOrigin: string;    // 当前 URL origin
  urlPath: string;      // 当前 URL pathname
  title: string;        // 当前页面标题
}
```

## SwitchTab block data

```json
{
  "kind": "action",
  "action": "switch_tab",
  "data": {
    "tabId": "t_a7f3...",
    "seq": 2,
    "urlOrigin": "https://example.com",
    "urlPath": "/login",
    "title": "Login Page"
  }
}
```

## 匹配梯度（回放时优先级）

1. `tabId` 精确匹配（同会话实时操作）
2. `seq` 创建序号匹配（跨会话回放标准路径）
3. `urlOrigin + urlPath` 匹配（辅助 + 手写 workflow）
4. `title` 兜底

## 后端实现要点

### BrowserController
- 维护 `_tab_registry: dict[str, TabInfo]`（tabId → TabInfo）
- 维护 `_seq_counter: int`（递增，不回退）
- `new_tab()` 时分配 tabId + seq
- `context.on("page")` 检测弹出窗口，同样分配
- `switch_tab()` 按梯度匹配
- `close_tab()` 从 registry 删除但不影响其他 tab 的 seq

### Recorder
- 检测 tab 切换事件（`page` 变化）
- 自动插入 SwitchTab 节点
- 捕获切换目标 tab 的完整 TabInfo

### Executor
- `_page_registry: dict[int, Page]`（seq → Page）
- `switch_tab` 按梯度匹配
- `new_tab` 注册新 page 到 registry

## 工作流分支 Tab 一致性检测（Rust）

### 规则
当 Condition/Loop 的 true/false/body 分支中：
- 创建 tab 数量不一致
- 删除 tab 数量不一致

触发 **warning** 级别检测：
- 日志警报：提示 seq 匹配可能不准确
- 建议：使用 URL 作为第二匹配特征
- 编辑器：在合流节点处显示黄色警告图标

### 实现位置
`src-tauri/src/` 中新增 workflow validator 模块，对 workflow JSON 做静态分析。

## 前端实现要点
- PropertyPanel：SwitchTab 属性编辑支持 seq + URL
- RecordingPreview：显示 SwitchTab 的目标 tab 信息
- 编辑器 validator：实时检测分支 tab 不一致警告

## 里程碑
1. 后端 TabInfo 数据结构 + registry
2. Recorder tab 切换检测
3. Executor 梯度匹配
4. Rust workflow validator
5. 前端属性编辑

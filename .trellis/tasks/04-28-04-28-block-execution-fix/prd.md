# Block 执行与录制修复 — 三层格式统一

## Goal

修复多次合并重构后 block 节点无法执行（`Session 'default' not found`）和录制无反应的问题，并趁此机会将三层（前端 Vue Flow / Rust IPC / Python Sidecar）的 block 数据格式统一为 canonical schema，消除 legacy 兼容层和双重转换。

## 现状问题

### P0: Session 路由断裂

- `execution.ts` 调用 `invoke("workflow_execute", { workflow })` 时**不传 `session_id`**
- Rust 层 fallback 到 `"default"`，但浏览器通过 Profile 启动时 session key 是 profileId
- 录制失败时异常被 `catch` 静默吞掉，用户无 UI 反馈

### P1: Block 三层格式不一致

| 层 | 当前格式 | 问题 |
|---|---|---|
| 前端 canonical | `{kind, action(PascalCase), data: {selector, ...}, settings}` | 正确但只用于序列化/反序列化 |
| 前端→Python | `convertNodesToBackend()` 展平为 flat：`{type, action(snake_case), selector, ...}` | 丢失 `data` 命名空间 |
| Python 执行器 | `_normalize_node()` 重新结构化 | 冗余归一化，meta_keys 脆弱 |
| 录制器输出 | `{type: "action", action: "Click", selector: ...}` legacy flat | 与 canonical 不兼容 |

### P2: action 名称双重转换

- 前端 `convertNodesToBackend` 调用 `toBackend()` 转为 snake_case
- Python `_execute_action` 内部再次调用 `to_backend()`
- 当前恰好 pass-through 无害，但架构脆弱

## 设计决策

1. **三层统一 canonical 格式**（方案C）：全链路使用同一 schema，零转换
2. **action 名称统一为 snake_case**：`click`, `open_url`, `type_text` 等
3. **消除 `convertNodesToBackend`**：前端直接发送 canonical 节点
4. **消除 Python `_normalize_node`**：executor 直接读取 canonical 字段
5. **录制器输出 canonical 格式**：`events_to_workflow_nodes()` 输出含 `kind`/`data` 的结构

## Canonical Schema（统一规范）

```typescript
interface CanonicalNode {
  id: string
  kind: "action" | "condition" | "loop" | "group"
  action?: string               // snake_case: "click", "open_url", "type_text"
  position: { x: number, y: number }
  data: Record<string, unknown>  // 业务参数: { selector, url, value, ... }
  settings?: {
    timeout?: number
    retryCount?: number
    continueOnError?: boolean
    description?: string
  }
  runtime?: {
    sessionId?: string           // 节点级 session 路由
  }
  // condition/loop 专用
  children?: CanonicalNode[]
  elseChildren?: CanonicalNode[] // condition only
}
```

全链路传输此格式，不做展平/重构化。

## 修改范围

### Phase A: Session 路由修复（让功能跑通）

| 文件 | 修改内容 |
|------|---------|
| `src/stores/execution.ts` | `execute()` 传递 `browserStore.activeSessionId` 给 Rust |
| `src-tauri/src/commands/browser.rs` | `workflow_execute` 确保 session_id 从前端传入 |
| `src/stores/browser.ts` | `startRecording()` 的 catch 块增加 UI 错误反馈 |

### Phase B: 三层格式统一

| 文件 | 修改内容 |
|------|---------|
| `src/stores/execution.ts` | 删除 `convertNodesToBackend()`，直接发送 canonical 节点 |
| `src/utils/workflowSchema.ts` | canonical 节点中 action 统一为 snake_case |
| `shared/action-map.json` | 确保 id 字段使用 snake_case 作为权威名 |
| `sidecar/engine/executor.py` | 删除 `_normalize_node()`，直接读取 `kind`/`action`/`data` |
| `sidecar/engine/action_map.py` | `to_backend()`/`to_frontend()` 简化或删除 |
| `sidecar/browser/recorder.py` | `events_to_workflow_nodes()` 输出 canonical 格式 |
| `src/stores/workflow.ts` | `importRecordedNodes()` 适配 canonical 输入 |

### Phase C: 清理 legacy

| 文件 | 修改内容 |
|------|---------|
| `src/utils/workflowSchema.ts` | 评估 `migrateLegacyNode` 是否仍需保留 |
| `docs/design/block-system.md` | 更新文档反映 canonical 统一格式 |

## 验收标准

1. ✅ 浏览器启动后能执行工作流，不报 session 错误
2. ✅ 录制按钮可用，录制后生成的节点能被执行
3. ✅ action 名称全链路为 snake_case
4. ✅ 前端→Python 无格式转换层（无 `convertNodesToBackend`，无 `_normalize_node`）
5. ✅ `pnpm lint` + `pnpm typecheck` 通过
6. ✅ `python -m pytest sidecar/tests/ -v` 通过
7. ✅ `cargo clippy` 通过

## Out of Scope

- Schema 版本管理 / 格式迁移工具
- Rust 层 block schema 验证
- 新 block 类型添加

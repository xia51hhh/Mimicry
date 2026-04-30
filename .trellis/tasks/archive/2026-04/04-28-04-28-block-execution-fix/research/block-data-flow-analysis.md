# Block 三层数据流与格式调研

## 调研日期
2026-04-28

## 三层 Block 数据结构对比

| 字段 | 前端 Canonical | 前端→Python (convertNodesToBackend) | Python (_normalize_node 后) |
|------|---------|---------|---------|
| **ID** | `id: string` | `id` (透传) | `id` |
| **类型** | `kind: "action"\|"condition"\|"loop"\|"group"` | `type: kind ?? type` (改名) | `type` |
| **动作** | `action?: string` (PascalCase, 顶层) | `action: toBackend(action)` (snake_case) | `action` (顶层优先) |
| **位置** | `position: {x, y}` | `position` (透传) | 不关心 |
| **数据** | `data: Record<string, unknown>` | `...data` (展平到顶层!) | `data` (从非meta字段重组) |
| **设置** | `settings?: WorkflowNodeSettings` (顶层) | `settings` (透传) | `settings` (顶层优先) |
| **Session** | `runtime?.sessionId` | `session_id` (映射) | `session_id` |
| **子节点** | `data.children` | `flat.children` (提升) | `children` (顶层) |

## 执行链路

```
execution.ts execute()
  → convertNodesToBackend(canonical) → flat format
  → invoke("workflow_execute", { workflow: flat })
  → Rust: JSON 透传 → sidecar_call("workflow.execute")
  → Python actions.py: workflow_execute(workflow, session_id="default")
  → _get_executor(session_id) → WorkflowExecutor
  → executor.execute(workflow)
  → _normalize_node() 对每个节点
  → _execute_nodes() → _execute_action() / _execute_condition() / _execute_loop()
```

## 录制链路

```
browser.ts startRecording()
  → invoke("recording_start", { sessionId })
  → Rust → Python recording.start()
  → RecordingEngine.start() → _inject_recorder() 注入JS

browser.ts stopRecording()
  → invoke("recording_stop")
  → Python recording.stop() → events_to_workflow_nodes()
  → 输出 legacy flat: { type: "action", action: "Click", selector: "#btn" }
  → 返回前端
  → workflow.importRecordedNodes() → 创建 VueFlow Node
```

## 核心问题

### 1. Session 路由断裂
- `execution.ts` 不传 session_id
- Rust fallback 到 "default"
- 浏览器用 profileId 注册 session → 找不到 "default"
- 录制失败被 catch 静默吞掉

### 2. 双层归一化冗余
- 前端 convertNodesToBackend: canonical → flat
- Python _normalize_node: flat → 结构化
- 两次转换互为逆操作，应该消除

### 3. action 名称双重转换
- 前端 toBackend(): PascalCase → snake_case
- Python _execute_action 内 to_backend(): 再次调用（pass-through）
- 统一为 snake_case 后可消除所有映射逻辑

### 4. 录制输出格式陈旧
- recorder.py 输出 legacy flat 格式
- 无 kind/data/settings 结构
- importRecordedNodes 将 type 混入 data 造成污染

## 关键文件清单

| 文件 | 角色 |
|------|------|
| `src/stores/execution.ts` | 前端执行入口，convertNodesToBackend |
| `src/stores/browser.ts` | 前端浏览器/录制管理 |
| `src/stores/workflow.ts` | Vue Flow 节点管理，importRecordedNodes |
| `src/utils/workflowSchema.ts` | canonical 定义，vueNodeToCanonical |
| `src/types/workflow.ts` | 前端类型定义 |
| `src-tauri/src/commands/browser.rs` | Rust IPC 命令 |
| `sidecar/engine/executor.py` | Python 执行器，_normalize_node |
| `sidecar/engine/action_map.py` | action 名称映射 |
| `sidecar/browser/actions.py` | RPC 方法处理 |
| `sidecar/browser/recorder.py` | 录制器 |
| `sidecar/browser/controller.py` | SessionManager |
| `shared/action-map.json` | action 定义权威源 |

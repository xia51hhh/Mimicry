# Cross-Layer Block Schema Contract

## Scope

Canonical workflow node schema shared across Frontend (Vue/TS), Rust IPC (JSON passthrough), and Python Sidecar (executor/recorder).

## Canonical Node Schema

```typescript
interface CanonicalNode {
  id: string
  kind: "action" | "condition" | "loop" | "group"
  action?: string          // snake_case: "click", "open_url", "type"
  position?: { x: number, y: number }  // frontend-only, omitted in execution
  data: Record<string, unknown>         // business params: selector, url, value...
  settings?: {
    timeout?: number
    retryCount?: number
    continueOnError?: boolean
    description?: string
  }
  runtime?: {
    sessionId?: string     // per-node session routing
  }
  children?: CanonicalNode[]      // condition/loop body
  elseChildren?: CanonicalNode[]  // condition else-branch
}
```

## Action Name Convention

| Layer | Format | Example | Authority |
|-------|--------|---------|-----------|
| Vue Flow internal (`data.action`) | PascalCase | `Click`, `OpenUrl` | i18n display |
| Canonical serialization / IPC | snake_case | `click`, `open_url` | `shared/action-map.json` |
| Python executor | snake_case | `click`, `open_url` | match branches |

- `toBackend()` / `toFrontend()` are **idempotent** — safe to call on already-converted names.
- Frontend converts PascalCase → snake_case in `canonicalNodesToBackend()` before `invoke()`.
- Python `to_backend()` called in `_normalize_node()` as defense-in-depth.

## Session ID Flow

```
execution.ts → invoke("workflow_execute", { workflow, sessionId: activeSessionId })
  → Rust: session_id = sessionId || "default"
  → Python: WorkflowExecutor(default_session_id=session_id)
  → Per-node override: node.runtime.sessionId (canonical) or node.session_id (legacy)
```

**Rule**: Frontend MUST pass `sessionId` explicitly. Do not rely on the `"default"` fallback.

## Recorder Output

Recorder outputs canonical nodes **without** `position` (layout is a frontend concern):
```python
{"kind": "action", "action": "click", "data": {"selector": "#btn"}}
```

`importRecordedNodes()` auto-generates position with vertical layout.

## Legacy Compatibility

Python `_normalize_node()` detects format via `"kind" in node`:
- **Canonical path**: reads `kind`, `action`, `data`, `settings`, `runtime` directly
- **Legacy path**: reconstructs from flat `{type, action, selector, ...}` format

Legacy fallback is retained for backward compatibility with saved JSON workflows.

## Common Mistakes

| Wrong | Correct | Why |
|-------|---------|-----|
| `convertNodesToBackend()` flattens `data` to top-level | `canonicalNodesToBackend()` preserves `data` namespace | Python expects `data` as a dict, not scattered keys |
| Recorder outputs `position: {x:0, y:0}` | Recorder omits `position` | Causes all imported nodes to stack at origin |
| `_execute_action()` calls `to_backend(action)` | Action already snake_case from normalize | Double conversion is harmless but wasteful |
| `startRecording` swallows errors silently | Set `setupError.value` in catch block | User sees "no response" with no feedback |
| `execute()` omits `sessionId` in invoke | Always pass `browserStore.activeSessionId` | Rust fallback to "default" won't match Profile sessions |

## Init Scripts (workflow-level)

Optional top-level `init_scripts: list[str | {name, script}]` on a workflow JSON object. The Python executor registers them on the session's `BrowserContext` via `add_init_script` BEFORE running the first node, so every page (current and future) loads with the snippets pre-applied.

Strings get auto-name `init_<n>`; dicts must carry `script` and may carry `name`. Storage is workflow-scoped only (NOT the SQLite `profiles` table).

Runtime authoring is exposed through `browser.add_init_script` / `browser.list_init_scripts` / `browser.get_init_script` / `browser.remove_init_script` / `browser.clear_init_scripts`. Playwright cannot un-inject already-loaded pages; remove/clear only stop re-application to future contexts.

See `docs/design/block-system.md` § "Init Scripts" for examples.

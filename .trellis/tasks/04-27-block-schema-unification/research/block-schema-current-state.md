# Block Schema Current State

Date: 2026-04-27

## Current representations
- Design docs: `type` values such as `browser/Navigate`, `interaction/Click`, `control/LoopData`.
- Vue Flow render type: coarse node types such as `action`, `condition`, `loop`, `group`.
- Runtime action: action names such as `Navigate`, `Click`, `SetVariable`, often carried in node data or top-level action fields depending on source.
- Python executor: reads `node.get("type", "action")` and `node.get("action", "")`, then maps action names through `engine.action_map.to_backend()`.
- Shared metadata: `shared/action-map.json` exists, but is not yet the single source of truth across layers.

## Confirmed direction
Use canonical `kind + action + data + settings`:

```json
{
  "id": "node_abc123",
  "kind": "action",
  "action": "Navigate",
  "position": { "x": 100, "y": 200 },
  "data": { "url": "https://example.com" },
  "settings": { "onError": "inherit", "disabled": false },
  "runtime": { "sessionId": "optional-session-id" }
}
```

## Migration principle
- Keep Vue Flow `type` only as UI rendering kind if required by Vue Flow.
- Export/import canonical workflow JSON.
- Python executor should normalize legacy and canonical nodes to avoid breaking old workflows.

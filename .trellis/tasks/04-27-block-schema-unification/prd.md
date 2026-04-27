# Canonical Block Schema Unification

## Goal
Unify workflow Block representation around a canonical `kind + action + data + settings` schema so frontend canvas, JSON editor, shared action map, Rust IPC, Python executor, tests, and documentation describe the same thing.

## Confirmed Direction
Use canonical schema shape:

```json
{
  "id": "node_abc123",
  "kind": "action",
  "action": "Navigate",
  "position": { "x": 100, "y": 200 },
  "data": {
    "url": "https://example.com"
  },
  "settings": {
    "onError": "inherit",
    "disabled": false
  },
  "runtime": {
    "sessionId": "optional-session-id"
  }
}
```

## Problem
The project currently has multiple competing representations:

- Design docs use type strings such as `browser/Navigate` and `interaction/Click`.
- Vue Flow node type uses coarse UI kinds such as `action`, `condition`, `loop`, `group`.
- Runtime action is often stored in `data.action` or top-level `action` depending on source.
- Python executor reads `type` and `action`, then maps action names through `engine/action_map.py`.
- Shared metadata exists in `shared/action-map.json`, but it is not yet the clear source of truth.

This creates fragile cross-layer translation and makes every new Block prone to drift.

## Scope

### In scope
- Define TypeScript canonical workflow node types.
- Add conversion helpers between Vue Flow nodes and canonical workflow JSON.
- Keep Vue Flow component `type` as UI rendering kind if needed, but do not treat it as runtime Block type.
- Ensure JSON export/import uses canonical `kind + action + data + settings`.
- Update Python executor to accept canonical nodes while preserving backward compatibility for existing workflows.
- Update `shared/action-map.json` usage or document it as the source of action metadata.
- Update docs to describe canonical schema.
- Add tests for conversion and executor backward compatibility.

## Strictness rules

The canonical shape is the **only** accepted shape inside the running app.
To keep that contract honest, the codebase enforces:

- `validateCanonicalNode` / `validateCanonicalEdge` / `validateCanonicalWorkflow`
  in `src/utils/workflowSchema.ts` reject unknown top-level fields and wrong
  types. Any node carrying e.g. `selector` at the top level is a hard error.
- Legacy / Vue-Flow / recorder JSON does not get silently absorbed by the
  parser. Importers go through an **explicit** `migrateLegacyWorkflow()`
  pre-pass; the result is then validated.
- The Python executor preserves `data` as the parameter namespace.
  `_execute_action` / `_execute_condition` / `_execute_loop` read parameters
  via `node["data"][...]`. Legacy flat fields are absorbed *into* `data` by
  `_normalize_node` rather than the other way around, so both layers agree
  on the shape of a canonical node.

## Out of scope

- Full graph execution semantics.
- Package / sub-workflow IO implementation.
- Selector self-healing implementation.
- Large UI redesign.

## Implementation Notes
1. Canonical TypeScript interfaces live in `src/types/workflow.ts`.
2. `src/utils/workflowSchema.ts` exposes `toCanonicalWorkflow()`,
   `validateCanonicalWorkflow()`, and `migrateLegacyWorkflow()`.
3. `src/stores/workflow.ts` always serializes through `toCanonicalWorkflow`
   and round-trips imports through `migrateLegacyWorkflow` +
   `validateCanonicalWorkflow`.
4. Recorder imports produce canonical action nodes via the same migration
   path.
5. Python `WorkflowExecutor._normalize_node` keeps `data` intact;
   `_execute_*` reads from `node["data"]`.
6. `pnpm test` covers the schema surface (round-trip + rejection paths);
   `sidecar/tests/test_executor.py` covers canonical and legacy executor input.
7. `docs/design/block-system.md` and `docs/design/data-flow.md` describe the
   canonical schema and the explicit migration boundary.

## Completion Criteria
- [x] One canonical Block schema is documented.
- [x] Frontend export produces `kind + action + data + settings` nodes.
- [x] Frontend import accepts canonical nodes; legacy goes through an
      explicit `migrateLegacyWorkflow()` step before validation.
- [x] `validateCanonicalWorkflow` rejects unknown top-level fields and wrong types.
- [x] Existing old workflows continue to load through `migrateLegacyWorkflow`.
- [x] Python executor tests cover canonical action, condition, loop, and legacy nodes.
- [x] Python executor reads parameters from `node["data"]`, preserving the
      `data` namespace.
- [x] README Roadmap narrows the Block schema item to follow-up validation /
      migration diagnostics work.
- [x] `pnpm typecheck`, `pnpm test`, and sidecar tests pass in the configured
      environment.

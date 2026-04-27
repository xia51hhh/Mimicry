# Current Documentation vs Code Gap

Date: 2026-04-27

## Observed gaps
- Design docs describe graph execution semantics with handles, branch ports, loop-body/completed ports, node IO, and data propagation.
- Current Python executor mostly executes ordered `nodes` arrays and nested `children` / `elseChildren`.
- `edges` are preserved by frontend serialization but do not appear to drive runtime graph traversal.
- Block docs use typed IDs like `browser/Navigate`, while frontend and executor use `type/action` style nodes.
- Package/sub-workflow, selector self-healing, and full debug system are architectural direction but not fully implemented.

## Recommended doc treatment
- Add status labels: Implemented / Partial / Planned / Deferred.
- Preserve long-term design direction but clearly separate it from shipped behavior.
- Link major planned items to Trellis tasks.

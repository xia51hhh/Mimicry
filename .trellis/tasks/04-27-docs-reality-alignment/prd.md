# Documentation Reality Alignment

## Goal
Audit the project documentation and move capabilities that are described as complete but are not yet implemented into explicit roadmap/task language.

## Problem
Current design docs describe a mature workflow engine with graph execution semantics, node IO, port-aware branches, loop ports, package reuse, selector self-healing, and full debug behavior. The actual code currently supports many primitives, but execution is still closer to sequential node execution than full graph semantics.

## Scope

### In scope
- Review docs under `docs/` for claims that exceed current implementation.
- Add status markers where appropriate:
  - Implemented
  - Partial
  - Planned
  - Deferred
- Make design docs distinguish architecture direction from shipped behavior.
- Convert large unimplemented areas into Trellis tasks or Roadmap sections.
- Cross-link related tasks:
  - Block schema unification;
  - graph execution semantics;
  - workflow validation;
  - selector self-healing;
  - package/sub-workflow system;
  - quality gates.

### Out of scope
- Implementing code changes.
- Rewriting all design docs from scratch.
- Removing useful long-term design direction.

## Candidate Documents
- `docs/README.md`
- `docs/architecture.md`
- `docs/design/block-system.md`
- `docs/design/data-flow.md`
- `docs/design/debug-system.md`
- `docs/design/element-selector.md`
- `docs/design/package-system.md`
- `docs/workflow/canvas-interaction.md`
- `docs/workflow/monaco-integration.md`

## Completion Criteria
- [x] Docs no longer present planned graph semantics as fully implemented.
- [x] Major planned features are clearly labeled as planned or partial.
- [x] README Roadmap and design docs use consistent terminology.
- [x] Follow-up Trellis tasks exist for major implementation gaps.
- [x] No implemented capability is accidentally downgraded to planned.

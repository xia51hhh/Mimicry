# Parallel Task Thinking Guide

> **Purpose**: Help decide when/how to split work across parallel worktrees, and avoid common pitfalls.

---

## The Problem

**Serial development is safe but slow.** Parallel development is fast but risky:

- Merge conflicts from concurrent edits
- Hot files modified by multiple agents
- Integration regressions when combining work
- Wasted effort from duplicated or divergent changes

This guide helps you **make good fan-out decisions and avoid parallel pitfalls**.

---

## When to Fan Out (Checklist)

All boxes should be checked before creating child tasks:

- [ ] Work splits into ≥2 independent sub-modules
- [ ] Each sub-module requires ≥30 minutes of coding (small tasks are faster serial)
- [ ] Hot files ≤2 and each can have a clear single owner
- [ ] No mid-task data exchange needed between children
- [ ] Integration branch can be validated with existing tests

If any box is unchecked, **strongly prefer serial execution**.

---

## When NOT to Fan Out

| Scenario | Why Serial is Better |
|----------|---------------------|
| Pure refactoring | Hot files are everywhere — ownership impossible |
| Urgent bugfix | Speed from focus, not parallelism |
| Total work < 1 hour | Overhead of worktree setup > time saved |
| Research / exploration | Output is knowledge, not code — no merge needed |
| Tightly coupled changes | Every child would need every other child's output |

---

## Splitting Principles

### Best: Split by Package

```
Child A: frontend (src/)
Child B: sidecar (sidecar/)
Child C: rust backend (src-tauri/src/)
```

Natural boundaries. Minimal hot files. Each child runs its own test suite.

### Good: Split by Feature Slice

```
Child A: feature X (touches src/components/X/ + sidecar/x.py)
Child B: feature Y (touches src/components/Y/ + sidecar/y.py)
```

Works when features don't share files.

### Avoid: Split by Code Layer

```
Child A: all types/interfaces
Child B: all implementations
Child C: all tests
```

Creates dependency chains. Child B can't start until A finishes.

---

## Before Creating Worktrees

### Step 1: Identify Hot Files

List every file that multiple children might need to edit:

```
shared/action-map.json     → owner: child-A
src-tauri/src/lib.rs       → owner: child-B (command registration)
sidecar/rpc/methods.py     → owner: child-C
```

### Step 2: Assign Ownership

Each hot file gets exactly ONE owner. Document in parent `prd.md`:

```yaml
parallel:
  integration_branch: feat/my-feature
  children:
    - slug: child-a
      hotfiles_owned: [shared/action-map.json]
    - slug: child-b
      hotfiles_owned: [src-tauri/src/lib.rs]
```

### Step 3: Define Merge Order

If child-B depends on child-A's hot file changes, child-A merges first:

```
child-A ──merge──► integration ──then──► child-B rebases ──merge──► integration
```

---

## Common Mistakes

| # | Mistake | Consequence | Prevention |
|---|---------|-------------|------------|
| 1 | No hot-file analysis before fan-out | Merge conflicts on every PR | Always do Step 1 above |
| 2 | Two children own the same file | Conflicting edits, one child's work gets overwritten | One owner per file, enforced by `trellis-check` |
| 3 | Forgetting to rebase before PR | Stale base causes silent regressions | Always rebase child onto latest integration before PR |
| 4 | Running full-stack dev in multiple worktrees | Port/DB conflicts | One `cargo tauri dev` at a time |
| 5 | Creating too many children | Overhead exceeds benefit | Max 3-4 children per parent |
| 6 | Skipping integration testing | Children work individually but break together | Parent must run full-stack smoke after each merge |

---

## Quick Decision Flowchart

```
Start
  │
  ├─ Work < 1 hour? ────────────────── Yes → Serial
  │
  ├─ Can split into ≥2 independent parts? ── No → Serial
  │
  ├─ Hot files > 2? ────────────────── Yes → Serial (or redesign split)
  │
  ├─ Each part > 30 min? ───────────── No → Serial
  │
  └─ All checks pass → Fan out with worktrees
```

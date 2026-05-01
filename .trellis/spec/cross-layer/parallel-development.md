# Parallel Development Contract

## Scope

Conventions and hard rules for running multiple Trellis tasks in parallel via `git worktree`, ensuring isolation, clear ownership, and conflict-free integration.

---

## Worktree Placement

| Rule | Value |
|------|-------|
| Root directory | `.trellis/worktrees/` (gitignored) |
| Per-task path | `.trellis/worktrees/<task-slug>/` |
| Creation command | `python3 .trellis/scripts/task.py worktree create <slug>` |
| Removal command | `python3 .trellis/scripts/task.py worktree remove <slug> [--force]` |

**Constraint**: Worktrees MUST live under `.trellis/worktrees/`. Paths outside this directory are forbidden.

---

## Branch Naming

| Scenario | Branch Pattern | base_branch |
|----------|---------------|-------------|
| Parent task (integration) | `feat/<parent-slug>` | `main` |
| Child task | `feat/<parent-slug>/<child-slug>` | `feat/<parent-slug>` |
| Standalone task (no fan-out) | `feat/<task-slug>` | `main` |

---

## Lifecycle State Machine

```
planning → in_progress → pr_open → merged_to_parent → archived
             (worktree       (child PR to         (in integration
              active)         integration)          branch)
```

1. **planning** — PRD and context files created, no worktree yet
2. **in_progress** — `worktree create` done, active development
3. **pr_open** — Child PR opened against integration branch
4. **merged_to_parent** — PR merged into integration; worktree can be removed
5. **archived** — `task.py archive` moves task to archive/

---

## Parent PRD Required Sections

When a parent task fans out to children, its `prd.md` MUST contain:

```yaml
parallel:
  integration_branch: feat/<parent-slug>
  children:
    - slug: <child-slug>
      scope: <one-line description>
      hotfiles_owned:
        - <path/relative/to/repo>
    - slug: <another-child>
      scope: <one-line description>
      hotfiles_owned:
        - <path/relative/to/repo>
  hotfiles:
    - <path/relative/to/repo>
```

---

## Hot-File Ownership Rules

| # | Rule |
|---|------|
| 1 | Parent `prd.md` lists ALL hot files (files likely edited by multiple children) |
| 2 | Each hot file has exactly ONE owner child task (via `hotfiles_owned`) |
| 3 | Non-owner children MUST NOT modify hot files in their worktree |
| 4 | `trellis-check` MUST report a violation if a non-owner modifies a hot file |
| 5 | When rebasing onto integration after owner merges, non-owner must rebase AFTER the owner's changes |

---

## Shared Resource Constraints

Only ONE worktree at a time may use each of these:

| Resource | Reason |
|----------|--------|
| Vite/Tauri dev server (port 1420) | Port conflict |
| SQLite database `<app-data>/com.mimicry.app/mimicry.db` | Write lock |
| `cargo tauri dev` | Combines both above |

**Practical rule**: Run `cargo tauri dev` or `pnpm dev` in at most ONE worktree. Other worktrees can run offline checks (`pnpm typecheck`, `cargo test`, `pytest`).

---

## Merge Order Contract

```
child branches ──PR──► integration branch (feat/<parent>) ──PR──► main
```

| Step | Actor | Target |
|------|-------|--------|
| 1 | Child task | PR → integration branch |
| 2 | Parent task reviewer | Merge child PR into integration |
| 3 | Parent task | PR → main (after all children merged) |

---

## Testing Tiers

| Tier | Where | What |
|------|-------|------|
| Child worktree | Own worktree | `pnpm typecheck` + `pnpm lint` + relevant package tests |
| Integration | Parent worktree | Full-stack: `cargo tauri dev` smoke + three-layer tests |
| Pre-main | CI or manual | `pnpm test && cd src-tauri && cargo test --all-targets --all-features && python -m pytest sidecar/tests/` |

---

## Forbidden Patterns

| # | Pattern | Why |
|---|---------|-----|
| 1 | Worktree path outside `.trellis/worktrees/` | Breaks gitignore isolation, pollutes repo |
| 2 | Non-owner child editing a hot file | Guaranteed merge conflict, ownership violation |
| 3 | Child PR targeting `main` directly | Bypasses integration branch review |
| 4 | Two worktrees running `cargo tauri dev` simultaneously | Port/DB conflict |
| 5 | Child task modifying integration branch directly (not via PR) | Breaks audit trail |
| 6 | Skipping `worktree remove` after merge (stale worktrees) | Disk waste, confusing `worktree list` output |
| 7 | Creating worktree without `task.json` on base branch | Worktree won't see task metadata |

# Parallel Task Thinking Guide

> **Purpose**: Decide whether to open a parallel worktree task, and how to enter the workflow as a fresh agent.

---

## How to Start Parallel Work (5 steps)

You're a fresh agent in a fresh terminal joining a project that already uses Trellis + worktrees:

```bash
# 1. Read the protocol — every time you start, content evolves
cat .trellis/spec/cross-layer/parallel-development.md

# 2. See what other agents are doing
python3 .trellis/scripts/task.py worktree list
python3 .trellis/scripts/task.py list --status in_progress

# 3. Pick (or be assigned) a task in `planning` status; read its PRD
python3 .trellis/scripts/task.py list --status planning
cat .trellis/tasks/<MM-DD>-<slug>/prd.md

# 4. (If you'll touch hot files) Check peer claims for each hot file
python3 .trellis/scripts/task.py list --hotfile shared/action-map.json
python3 .trellis/scripts/task.py list --hotfile .trellis/spec/cross-layer/block-schema.md

# 5. Create your worktree, enter it, mark task in_progress
python3 .trellis/scripts/task.py worktree create <slug>
cd .trellis/worktrees/<slug>
python3 ../../scripts/task.py start <slug>

# 6. Code → test → commit (use feat(<slug>): 中文 format) → PR to main
git add <files>
git commit -m "feat(<slug>): <中文描述>"
git push -u origin feat/<slug>
gh pr create --base main
```

After step 5, every prompt in this session shows peer worktree status automatically — no need to re-run `task.py worktree list` manually unless you want detail.

---

## When to Open a Parallel Task

Open a separate worktree task when ALL of these hold:

- [ ] The work is self-contained — won't depend on another in-flight task to make progress
- [ ] No peer task currently claims your hot files (`task.py list --hotfile <path>` returns empty for each)
- [ ] At least one OTHER agent (separate terminal/session) is working on something concurrently — otherwise serial in `main` is faster
- [ ] You can finish without consuming another in-progress task's output mid-way

If all four hold → open task, create worktree, code in isolation.

If any fails → either work serially in `main`, or wait for the conflicting tasks to PR first.

---

## When NOT to Open a Parallel Task

| Situation | Reason |
|---|---|
| Urgent bugfix | Setup time exceeds the fix |
| Total work <30 min | Coordination overhead dominates |
| Touches contracts being edited by another in-progress task | Contract instability spreads errors across tasks |
| Pure refactor across many shared files | Hot-file conflicts everywhere |
| Research / exploration | You don't know yet what files you'll touch |
| Touches the parallel-protocol files themselves | Bootstrap problem; do in `main` |

---

## Splitting Principles

### Best: split by package boundary

The repo's package layout (frontend / sidecar / rust) maps cleanly onto separate test stacks, separate hot-file domains, and separate language toolchains. A frontend-only task rarely conflicts with a sidecar-only task.

### Acceptable: split by feature slice within one package

Two unrelated features in the same package, with disjoint files. Declare `hotfiles_touched` carefully — work-in-progress can grow beyond your initial estimate.

### Avoid: split a single feature across layers

"Add new node type X" decomposed into 3 worktrees (frontend / rust / sidecar) sounds parallelizable but isn't — every layer needs the cross-layer contract first. Land the contract in one task; THEN the layers can parallelize against the frozen contract.

---

## Common Mistakes

### Mistake 1: Skipping the peer check before starting

**Bad**: open worktree, start coding, only check peers when PR fails to merge.

**Why it fails**: silent collision until merge time, by which point both branches have invested work.

**Good**: run `task.py list --hotfile <path>` for each hot file BEFORE creating the worktree. Coordinate or wait if peers claim overlap.

### Mistake 2: Resolving merge conflicts unilaterally

**Bad**: `git checkout --ours .` or `--theirs .` to clear conflicts and move on.

**Why it fails**: silently overwrites the other task's intent; bug surfaces days or weeks later.

**Good**: trace the commit's `<task-slug>` from `git log`, read that task's PRD, decide what "respecting both intents" looks like; ask the user when intents truly contradict.

### Mistake 3: Forgetting commit format

**Bad**: `git commit -m "fixed stuff"`.

**Why it fails**: peers cannot trace your task from the file's `git log` — Merge Conflict Resolution Step 2 breaks for everyone after you.

**Good**: `feat(my-task-slug): 加入登录页面布局`. The `<task-slug>` is what makes the protocol work.

### Mistake 4: Phantom parallelism

**Bad**: one developer with one terminal opens 3 worktrees and switches between them.

**Why it fails**: no actual concurrency — just context-switch overhead added to serial work. Coordination cost paid, parallelism benefit not realized.

**Good**: either run on `main` serially, or have ≥2 actual concurrent agents/terminals.

### Mistake 5: Stale `hotfiles_touched`

**Bad**: PRD declares `[shared/action-map.json]`; mid-task you also start editing `package.json`; don't update PRD.

**Why it fails**: another agent claiming `package.json` (via `--hotfile`) won't see your hidden claim.

**Good**: update PRD's `hotfiles_touched` BEFORE the first edit on a new hot file; treat it as a contract that peers query.

### Mistake 6: PR straight to main without rebase

**Bad**: `gh pr create --base main` without rebasing first.

**Why it fails**: PR sits with stale conflicts; reviewer asks you to rebase anyway.

**Good**: `git fetch origin && git rebase origin/main` immediately before push. Resolve any conflicts per the Merge Conflict Resolution protocol.

---

## Decision Tree

```
"Is the work self-contained (no in-flight cross-task data flow)?"
        │
   ┌────┴────┐
   │         │
  YES        NO  →  serial in main; or wait for the blocking task to PR
   │
"Does any peer task claim your hot files now?"
   │   (run `task.py list --hotfile <path>` for each path you'll touch)
   ┌────┴────┐
   │         │
  NO        YES  →  coordinate; let conflicting task PR first; then start
   │
"≥2 agents working concurrently right now?"
   │
   ┌────┴────┐
   │         │
  YES        NO  →  serial in main is faster
   │
   ▼
OPEN PARALLEL TASK
```

---

## Update This Guide When

- A peer collision happened despite the protocol — root cause needs codifying
- A new hot file emerged in regular workflow (also add to the spec's hot-files list)
- A decision rule helped catch an issue before it became a bug

---

**Core Principle**: Parallel = N agents on N independent tasks. The moment two tasks touch the same file at the same time, you're paying serial-merge overhead anyway — better to wait, serialize, or split differently.

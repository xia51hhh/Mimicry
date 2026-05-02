# Parallel Development Contract

## Scope

Conventions and hard rules for running multiple Trellis tasks in parallel via `git worktree`, ensuring isolation, clear ownership, and conflict-free integration.

**集成方式**：默认 **本地 merge**（无 PR 中间环节）。外部 fork 贡献者才走 PR，详见 [docs/parallel-agents.md §五](../../../docs/parallel-agents.md#五外部贡献pr-流程备用)。

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
planning → in_progress → ready_to_merge → merged → archived
             (worktree     (本地门禁通过、     (本地 merge
              active)        rebase 完毕)       完成 + 推送)
```

1. **planning** — PRD 与 context 文件创建，未开 worktree
2. **in_progress** — `worktree create` 完成，活跃开发中
3. **ready_to_merge** — worktree 内 typecheck/lint/test 通过、已 rebase 到最新 base_branch
4. **merged** — 在主仓库（或 base 分支 worktree）本地 `git merge --no-ff` 完成 + push
5. **archived** — `task.py archive` 把任务目录移到 `archive/`

> 子任务 `merged_to_parent`：本地 `feat/<parent>` 上 merge 子分支，无需 PR。

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

## Merge Order Contract（本地 merge 优先）

```
child branches ──local merge──► integration branch (feat/<parent>) ──local merge──► main
```

| Step | Actor | Action | Target |
|------|-------|--------|--------|
| 1 | Child task | rebase 到 integration branch + 本地通过门禁 → ready_to_merge | — |
| 2 | Integration owner（或同一开发者）| `git -C <integration-worktree> merge --no-ff feat/<parent>/<child>` | integration branch |
| 3 | Parent task | 全部 children merged 后，rebase 到 main + 跑全栈集成测试 → ready_to_merge | — |
| 4 | Maintainer | `git -C <main-repo> merge --no-ff feat/<parent>` + `git push origin main` | main |
| 5 | Maintainer | `task.py worktree remove <slug>` + `task.py archive <slug>`（child + parent 都 archive） | filesystem + tasks/ |

**完整流程命令**见 [docs/parallel-agents.md §四](../../../docs/parallel-agents.md#四完成后本地-merge--清理)。

### 多 worktree 并发 merge 的串行约束

```
T1 finish → T1 merge → push origin main
T2 finish → T2 git fetch && git rebase origin/main → 解决冲突 → T2 merge → push
```

后 merge 者必须先 rebase 到含先 merge 者 commit 的 main，否则 `push` 会被远端拒绝（non-fast-forward）。这是天然的串行点；hot-file 所有权规则就是为了 **降低这个串行点的冲突概率**。

---

## Pre-Merge Local Verification（替代 PR review）

merge 前在 worktree 或主仓库内人工跑过：

| 检查 | 命令 | 阻断 merge？ |
|---|---|---|
| 工作区 clean | `git status` | ✅ 必须 |
| Rebase 最新 base | `git fetch && git rebase origin/<base>` | ✅ 必须 |
| Action map 同步 | `python3 scripts/sync-action-map.py` | ✅ 必须（CI 强制） |
| 三方版本锁 | 手动核对 `package.json` / `Cargo.toml` / `tauri.conf.json` | ✅ 必须 |
| 前端门禁 | `pnpm typecheck && pnpm lint` | 改 src/ 时必须 |
| Rust 门禁 | `cargo check && cargo clippy --all-targets --all-features -- -D warnings` | 改 src-tauri/ 时必须 |
| Sidecar 测试 | `cd sidecar && python -m pytest tests/ -v -m "not e2e"` | 改 sidecar/ 时必须 |
| Diff 范围 review | `git log --oneline main..feat/<slug>` + `git diff main...feat/<slug>` | 推荐 |

CI 兜底（push 后跑），但本地通过是 ready_to_merge 的硬条件。

---

## Testing Tiers

| Tier | Where | What |
|------|-------|------|
| Child worktree | Own worktree | `pnpm typecheck` + `pnpm lint` + relevant package tests |
| Integration | Parent worktree | Full-stack: `cargo tauri dev` smoke + three-layer tests |
| Pre-main | Main 仓库 / CI | `pnpm test && cd src-tauri && cargo test --all-targets --all-features && python -m pytest sidecar/tests/` |

---

## Forbidden Patterns

| # | Pattern | Why |
|---|---------|-----|
| 1 | Worktree path outside `.trellis/worktrees/` | Breaks gitignore isolation, pollutes repo |
| 2 | Non-owner child editing a hot file | Guaranteed merge conflict, ownership violation |
| 3 | Skip Pre-Merge Local Verification（直接 merge 未跑门禁的分支）| CI 兜底但本地通过是 ready_to_merge 硬条件，跳过=回滚噪音 |
| 4 | Two worktrees running `cargo tauri dev` simultaneously | Port/DB conflict |
| 5 | Force-push to `main`（即使本地 merge 失败要重做）| 破坏其他开发者已 fetch 的 main 历史；改用 revert commit |
| 6 | Skipping `worktree remove` after merge (stale worktrees) | Disk waste, confusing `worktree list` output |
| 7 | Creating worktree without `task.json` on base branch | Worktree won't see task metadata |
| 8 | Merge 时不带 `--no-ff`（除非明确选 `--ff-only` 走线性历史）| 丢失 feat 分支边界，audit 变难 |
| 9 | 把外部 fork PR 直接 squash merge 到 main | squash 丢失贡献者的 commit 颗粒度；改用 `--no-ff` 保留作者 |

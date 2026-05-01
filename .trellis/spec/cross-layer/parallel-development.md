# Cross-Layer Parallel Development Protocol

## Scope

Hard contract for multiple agents (separate Claude / Codex / etc. sessions in their own terminals) working on the same repo concurrently via git worktrees + Trellis tasks. Every task is a top-level peer — there is no parent / child / integration branch. Each agent owns one task, one worktree, one branch; PRs go directly to `main`.

This protocol replaces the older parent-fanout model. Read it in full before opening a parallel task.

## Worktree Placement

| Aspect | Rule | Why |
|--------|------|-----|
| Location | `.trellis/worktrees/<task-slug>/` (repo-internal) | Tracked alongside task metadata; both `git worktree list` and `task.py worktree list` find it |
| Gitignored | yes — `.gitignore` excludes `.trellis/worktrees/` | Worktree contents are themselves git-managed; the parent worktree must not re-track them |
| Out-of-repo paths | forbidden | Breaks `task.py worktree list` discovery and IDE-jump conventions |
| Creator | `python3 .trellis/scripts/task.py worktree create <task-slug>` | Single source of truth; writes `task.json.worktree_path` atomically |

## Branch Naming

| Branch | Base | Example |
|--------|------|---------|
| `feat/<task-slug>` | `main` | `feat/parallel-protocol-peer` |

All tasks use the same convention. There is no integration / parent branch.

## Lifecycle

```
   task.py create               task.py worktree create               PR opened + merged
─────────────────► planning ─────────────────────────► in_progress ────────────────────► (status stays in_progress)
                   + branch                            + worktree_path                          │
                   + base_branch                       (active)                                 │
                                                                                                ▼
                                                                                          task.py archive
                                                                                                │
                                                                                                ▼
                                                                                            archived
```

`task.json.status` only tracks `planning / in_progress / completed`. Open `pr_url` in `task.json` to record the PR; archive moves to `completed`.

## Per-Task PRD `parallel:` Section (mandatory if you'll touch hot files)

If your task will modify any file in the [Hot Files](#hot-files-in-this-repo) list, your `prd.md` MUST include this YAML block — it's how peers discover your claims via `task.py list --hotfile <path>`:

```yaml
parallel:
  hotfiles_touched:
    - shared/action-map.json
    - .trellis/spec/cross-layer/block-schema.md
```

If the task adds a new hot file mid-flight, update `prd.md` BEFORE the first edit and re-run the peer check (Step 2 of the entry flow).

Tasks that touch zero hot files may omit the `parallel:` block entirely.

## Hot Files in this Repo

Files where concurrent edits in different tasks reliably collide. Always declare in `hotfiles_touched` if you'll touch them:

- `shared/action-map.json`
- `.trellis/spec/cross-layer/*.md`
- `.trellis/spec/guides/*.md`
- `CHANGELOG.md`
- `package.json`, `src-tauri/Cargo.toml`, `src-tauri/tauri.conf.json` (the version-locked triple)
- `.gitignore`
- `CLAUDE.md`, `AGENTS.md`
- `.trellis/workflow.md`

## Hot-File Coordination (peer model)

**Before opening a worktree**:

1. `python3 .trellis/scripts/task.py worktree list` — see all peer worktrees, their branches, dirty / ahead status
2. `python3 .trellis/scripts/task.py list --hotfile <path>` for each hot file you plan to touch — see who else has claimed it
3. Conflict found → coordinate (notes / chat / direct comm). First PR wins; later tasks rebase. The `hotfile` filter is informational, not a lock — do not race past a peer claim
4. No conflict → declare `hotfiles_touched` in your PRD (commit the PRD edit), then create the worktree

**Before opening a PR**:

1. `git fetch origin && git rebase origin/main`
2. If rebase reports conflicts → see [Merge Conflict Resolution](#merge-conflict-resolution) below

## Merge Conflict Resolution

When rebasing onto `main` (or any merge) reports conflicts, the agent MUST follow this protocol — **NEVER blind-resolve with `--ours` / `--theirs`**:

```bash
# 1. Identify conflicting files
git status      # shows: both modified: <path>

# 2. Find the OTHER task that touched each conflicting file
git log --all --oneline -- <path> | head -20
# Commit messages follow `<type>(<task-slug>): <desc>` (see Commit Format below).
# Pick the most recent commit whose <task-slug> is NOT yours.

# 3. Read that task's PRD to understand its intent
ls .trellis/tasks/ | grep <task-slug>
cat .trellis/tasks/<MM-DD>-<task-slug>/prd.md

# (If the task is already archived:)
find .trellis/tasks/archive -name "*<task-slug>*" -type d
cat .trellis/tasks/archive/<YYYY-MM>/*-<task-slug>/prd.md
```

Then resolve based on intent:

| Both intents | Resolution |
|---|---|
| Add disjoint content (e.g. new fields, new entries) | Keep both |
| Same key, different new values | **STOP** — ask user; do not pick a winner unilaterally |
| Strict superset (your change subsumes theirs) | Take yours; cite their commit hash in your commit message |
| Contradictory contracts (e.g. opposite renaming) | **STOP** — surface to user; one of the tasks needs a redesign |

After resolving:

```bash
git diff                             # sanity-check the merge
<run task-relevant tests>            # at minimum: pnpm typecheck if frontend changed
git add <resolved files>
git rebase --continue
```

**Forbidden**: `git checkout --ours <path>` or `--theirs <path>` without performing Steps 2-3 above. This is the #1 source of silent regression in parallel work.

## Commit Format

All commits on a task's worktree use Conventional Commits prefix + Chinese description:

```
<type>(<task-slug>): <中文 description>
```

| type | usage |
|---|---|
| `feat` | new feature / capability |
| `fix` | bug fix |
| `docs` | documentation only |
| `refactor` | code change that neither fixes a bug nor adds a feature |
| `test` | adding / updating tests |
| `chore` | tooling, deps, config, task lifecycle |
| `style` | formatting (no code change) |
| `perf` | performance improvement |

Examples:

```
feat(parallel-protocol-peer): 加入对等并行协议与热点文件协调
fix(profile-isolation): 修正多 profile 共享 cookie 导致的会话泄漏
docs(workflow): 编写热点文件冲突解决流程
chore(task): archive 04-28-block-execution-fix
```

The `<task-slug>` field is what enables Merge Conflict Resolution Step 2 — peers need it to find your task's PRD when their rebase conflicts on a file you touched.

Commits without the `<type>(<task-slug>):` prefix break the conflict-tracing protocol — they will be flagged in code review.

## Test Strategy

Each task's worktree must pass before its PR opens:

- `pnpm typecheck` and `pnpm lint` (always, cheap)
- Package-relevant unit tests:
  - frontend touch → `pnpm test`
  - sidecar touch → `python -m pytest sidecar/tests/`
  - rust touch → `cd src-tauri && cargo test --all-targets --all-features`
- Triple-stack changes → all three of the above

CI on the PR runs the full triple-stack — that is the gate to `main`. Agents are NOT required to run `cargo tauri dev` locally before PR (it's a singleton resource; see below).

## Shared Resource Constraints

The following are global / process-singleton resources. At most one worktree may use each at a time:

| Resource | Coordination |
|---|---|
| Vite / Tauri dev server port `1420` | Only one worktree may run `cargo tauri dev`; check `task.py worktree list` and peer notes before starting |
| SQLite database `<app-data>/com.mimicry.app/mimicry.db` | Same — one running app instance at a time |
| Sidecar venv `<app-data>/com.mimicry.app/venv/` | Serialize `pip install`; concurrent installs corrupt the env |
| Camoufox browser process | Multiple instances OK if each profile has separate `user_data_dir` |

## Merge Order

```
your worktree (feat/<task-slug>)
        │
        │  PR → main (CI gates the merge)
        ▼
       main
```

No integration branch. Every task PRs to `main` directly. The CI on `main` PRs is the verification gate; conflicts at PR time → rebase per [Merge Conflict Resolution](#merge-conflict-resolution).

## Forbidden Patterns

| Pattern | Why wrong |
|---|---|
| Worktree placed outside `.trellis/worktrees/` | Breaks `task.py worktree list` discovery; violates `.gitignore` plan |
| Skipping `task.py list --hotfile <path>` before claiming a hot file | Silent peer collision discovered only at merge time |
| Resolving conflicts via `git checkout --ours` / `--theirs` without reading the other task's PRD | #1 source of silent regression in parallel work |
| Commit without `<type>(<task-slug>):` prefix | Breaks Merge Conflict Resolution Step 2 — peers cannot trace your changes |
| PR opened without `git fetch origin && git rebase origin/main` first | Forces reviewer to deal with stale conflicts |
| Two worktrees running `cargo tauri dev` simultaneously | Port 1420 + SQLite write-write race |
| Removing a worktree with `--force` while it has unpushed commits | Loses work-in-progress (commits stay on branch but disk state is gone) |
| `parallel:` block in PRD claims hot files but the actual edits drift outside that list | Peers querying `--hotfile <unlisted-path>` won't see your hidden claim |
| Single-developer "parallel" work with one terminal switching between worktrees | No actual concurrency; coordination cost paid, parallelism benefit not realized |

## Tooling

| Command | Purpose |
|---|---|
| `python3 .trellis/scripts/task.py worktree create <task-slug>` | Create `.trellis/worktrees/<slug>/` checked out to `feat/<slug>`; record `worktree_path` in task.json |
| `python3 .trellis/scripts/task.py worktree remove <task-slug> [--force]` | Refuse if dirty / ahead of base; clear `worktree_path` (branch retained) |
| `python3 .trellis/scripts/task.py worktree list` | Table: task / branch / path / ahead-behind / dirty for every active worktree |
| `python3 .trellis/scripts/task.py worktree status <task-slug>` | Detailed `git status` + commit log for one worktree |
| `python3 .trellis/scripts/task.py list --hotfile <path>` | List active tasks whose PRD declares `<path>` in `hotfiles_touched` — used by peer-claim checks |

## Observability (auto-injected)

Every agent's `SessionStart` hook injects a `<peer-worktrees>` block listing all currently-active worktrees with branch / dirty / ahead-behind status. The `UserPromptSubmit` hook re-injects a compact one-liner per turn so every prompt sees the latest peer state.

You don't have to run `task.py worktree list` yourself unless you need detail beyond the injected summary — but you MUST act on it (claim, rebase, ask) when a peer's claims overlap with yours.

---

See `.trellis/spec/guides/parallel-task-thinking-guide.md` for *when* to open a parallel worktree task vs. just code in `main`.

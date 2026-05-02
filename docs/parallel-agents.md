# 并行 Agent 使用说明

> **用途**：多个 AI agent 在独立终端、独立 git worktree 里并行开发。每个 agent 一个 worktree、一个分支、独立 `.trellis/.current-task`（gitignored），**互不打扰**。
>
> **集成方式**：本仓库默认 **本地 merge** 回 `main`（无 PR 中间环节）。外部 fork 贡献者才走 PR — 详见末节"外部贡献"。

---

## 一、Git 原生方式（一次性 / ad-hoc 并行）

```bash
# 创建 worktree 并新建分支
git worktree add ../mimicry-feat-a -b feat-a

# 用已有分支创建 worktree
git worktree add ../mimicry-bugfix bugfix-123

# 进入 worktree 启动 agent
cd ../mimicry-feat-a && claude

# 干活 → commit

# 在主仓库本地 merge 回 main（不走 PR，详见 §四）
git -C /path/to/Mimicry checkout main
git -C /path/to/Mimicry pull --ff-only            # 同步远端
git -C /path/to/Mimicry merge --no-ff feat-a \
  -m "merge: feat-a → main — <一句话总结>"
git -C /path/to/Mimicry push origin main

# 清理
git worktree list                       # 列所有 worktree
git worktree remove ../mimicry-feat-a   # 删 worktree
git branch -d feat-a                    # 删分支（已 merge）
```

适合：临时分一个工作区、不想跟 Trellis 任务绑定时。

---

## 二、Trellis 联动方式（任务-worktree 1:1 绑定，批量准备）

跟 Trellis 任务绑定后，每个 worktree 写到 `task.json.worktree_path`，可以 `task.py worktree list/status` 集中管理。

```bash
# 主终端在 main 分支上 — 一次性批量准备 N 个环境
python3 .trellis/scripts/task.py create "登录页重做" --slug login-redesign
python3 .trellis/scripts/task.py worktree create login-redesign
# ↑ 自动把任务目录 commit 到 base_branch（保证 worktree 能读到自己的 task），
#   再 git worktree add 到 .trellis/worktrees/login-redesign/ 上 feat/login-redesign 分支

python3 .trellis/scripts/task.py create "导出 CSV" --slug csv-export
python3 .trellis/scripts/task.py worktree create csv-export

# 终端 A
cd .trellis/worktrees/login-redesign
python3 ../../scripts/task.py start login-redesign
claude

# 终端 B（与 A 完全隔离）
cd .trellis/worktrees/csv-export
python3 ../../scripts/task.py start csv-export
claude
```

| 命令 | 作用 |
|---|---|
| `task.py worktree create <slug>` | 创建 `.trellis/worktrees/<slug>/`、自动 commit 任务目录、新建/复用分支 |
| `task.py worktree list` | 列所有活跃 worktree（含 ahead/behind/dirty） |
| `task.py worktree status <slug>` | 单个 worktree 详情 + commit log |
| `task.py worktree remove <slug> [--force]` | 删 worktree（脏树或 ahead 拒绝；--force 跳过） |

---

## 三、隔离原理

| 资源 | 是否隔离 |
|---|---|
| 工作目录文件 | ✅ git 天然，每个 worktree 独立 |
| 分支 | ✅ 每个 worktree 一个，互不影响 |
| `.trellis/.current-task` | ✅ gitignored，每个 worktree 自己一份 |
| Trellis hook 注入（任务状态/workflow-state）| ✅ 每个 session 读自己 worktree 的 |
| `node_modules`、Rust `target/`、Python venv | ⚠️ 大部分独立；仅 Sidecar venv 在 OS app-data 下共享 |
| **运行时端口/DB**：Vite 1420、SQLite、Sidecar venv | ❌ 全机共享，**只能一个 worktree 同时跑 `cargo tauri dev`** |

### 避免的反模式

- ❌ 两个 session 都把 cwd 设成主仓库（main worktree）→ 共享同一个 `.current-task`，`task.py start` 互相覆盖
- ❌ 单人多 worktree 之间手动切 → 不是真并行，只是 context-switch 开销
- ❌ 多个 worktree 同时 `cargo tauri dev` → 端口 1420 冲突 + SQLite 写写竞争

---

## 四、完成后：本地 merge → 清理

> **本仓库默认不走 PR**。worktree 完成开发后，在主仓库直接 `git merge` 回 `main` 并推送。流程比 PR 简短，commit 历史保留 `feat/<slug>` 分支足迹（用 `--no-ff`），review 在本地通过 `git log -p` / `git diff` 进行。

### 标准流程

```bash
# === 1. worktree 内：确认无未提交改动 + 跑基本检查 ===
git status                                # 必须 clean
pnpm typecheck && pnpm lint               # 前端门禁（如改了前端）
cd src-tauri && cargo check               # Rust 门禁（如改了 Rust）

# === 2. rebase 到最新 main，避免 merge commit 噪音（推荐）===
git fetch origin
git rebase origin/main                    # 或 git rebase main 如果本地 main 已最新
# ↑ 如有冲突：解决 → git add → git rebase --continue

# === 3. 在主仓库本地 merge ===
git -C /path/to/Mimicry checkout main
git -C /path/to/Mimicry pull --ff-only    # 同步远端 main，确保不落后
git -C /path/to/Mimicry merge --no-ff feat/<slug> \
  -m "merge: feat/<slug> → main — <一句话总结：交付了什么>"
# ↑ --no-ff 保留分支历史，方便后续审计这条 feature 的 commit 范围

# === 4. 推送 ===
git -C /path/to/Mimicry push origin main

# === 5. 清理 worktree + 归档任务 ===
python3 .trellis/scripts/task.py worktree remove <slug>
python3 .trellis/scripts/task.py archive <slug>

# git 原生方式（无 Trellis 绑定时）
git -C /path/to/Mimicry worktree remove ../mimicry-<slug>
git -C /path/to/Mimicry branch -d feat-<slug>
```

### Merge 策略选择

| 选择 | 命令 | 适用 |
|---|---|---|
| **`--no-ff`（推荐）** | `git merge --no-ff feat/<slug>` | 保留 `feat/<slug>` 分支历史；merge commit 标记一段相关 commit 的边界，便于追溯 |
| `--ff`（线性）| `git merge --ff-only feat/<slug>` | 强制保持线性历史；要求事先 rebase 到 main 顶部 |
| `squash` | `git merge --squash feat/<slug>` + `git commit` | 把多个 commit 合并成一个；丢失分支历史，仅在 commit 颗粒度过细时考虑 |

本仓库默认 **`--no-ff`**：feature 通常含 ≥3 个 commit，保留分支边界对 audit 与回滚都有价值。

### Merge commit message 模板

```
merge: feat/<slug> → main — <交付主旨>
```

例：

```
merge: feat/docs-refresh-audit → main — 全量审计 + 22 篇文档刷新（吞并 04-28-block-doc-update）
```

### 本地 review checklist（替代 PR review）

merge 前在主仓库或 worktree 内对照过一遍：

```bash
# 看本次 merge 范围（feat 分支 vs main）
git log --oneline main..feat/<slug>

# 看实际 diff
git diff main...feat/<slug>            # 三点 diff：仅 feat 引入的变化
git diff main...feat/<slug> --stat     # 文件级摘要

# 高风险检查
git diff main...feat/<slug> -- shared/action-map.json    # 跨层契约
git diff main...feat/<slug> -- src-tauri/Cargo.toml package.json src-tauri/tauri.conf.json   # 三方版本锁
```

如有 spec / 跨层 contract 改动，建议本地跑：

```bash
python3 scripts/sync-action-map.py
pnpm typecheck && pnpm lint
cd src-tauri && cargo check && cargo clippy --all-targets --all-features -- -D warnings
```

---

## 五、外部贡献（PR 流程，备用）

> 来自 fork 的贡献者无法直接 merge 到主仓库的 main —— 这种情况走 PR 流程。

```bash
# 在 fork 的 worktree 内
git push -u origin <branch>
gh pr create --base main --head <fork-owner>:<branch>
```

主仓库维护者收到 PR 后：

```bash
# 把 PR 拉到本地分支
gh pr checkout <pr-number>

# 本地验证（同 §四 review checklist）

# 通过后本地 merge（同 §四 步骤 3-4）
git checkout main
git pull --ff-only
git merge --no-ff <pr-branch> \
  -m "merge: PR #<num> → main — <总结>"
git push origin main

# gh 会自动把 PR 标记为 merged
```

---

## 排错

| 症状 | 原因 / 解 |
|---|---|
| `task.py start <slug>` 在 worktree 内报 "Task not found" | 任务目录没在 base_branch 上 commit。`worktree create` 会自动处理；旧 worktree 需要手动 rebase 把任务目录拉到自己分支 |
| `worktree remove` 拒绝 | 工作树脏 or 有未 merge 的 commit。真不要了用 `--force`，否则先完成 §四 merge |
| `worktree create` 报 "branch already exists" | 旧分支没删 → `git branch -D feat/<slug>` 后重试，或用 `--branch other-name` |
| 两个 session 显示同一个 current-task | 它们 cwd 在同一个 worktree（含主仓库），不是不同 worktree |
| `git merge --no-ff` 弹出 commit message 编辑器卡住 | 用 `-m` 参数提前提供 message；或设置 `git config core.editor` 为 `true` 临时跳过 |
| merge 后 main 推不上去（rejected, non-fast-forward）| 本地 main 落后远端 → `git pull --rebase origin main` 后再推；冲突时按 §四 重新 rebase 自己的 feat 分支 |
| 多个 worktree 都准备 merge，谁先谁后？| 后 merge 者必须 `git rebase origin/main`（main 已含先 merge 者的 commit），有冲突解决；hot-file 冲突参考 [.trellis/spec/cross-layer/parallel-development.md](../.trellis/spec/cross-layer/parallel-development.md) 的 hot-file 所有权规则 |

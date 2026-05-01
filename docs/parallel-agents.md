# 并行 Agent 使用说明

> **用途**：多个 AI agent 在独立终端、独立 git worktree 里并行开发。每个 agent 一个 worktree、一个分支、独立 `.trellis/.current-task`（gitignored），**互不打扰**。

---

## 一、Git 原生方式（一次性 / ad-hoc 并行）

```bash
# 创建 worktree 并新建分支
git worktree add ../mimicry-feat-a -b feat-a

# 用已有分支创建 worktree
git worktree add ../mimicry-bugfix bugfix-123

# 进入 worktree 启动 agent
cd ../mimicry-feat-a && claude

# 干活 → commit → push → PR

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

## 四、完成后清理

```bash
# 在 worktree 内
git push -u origin <branch>
gh pr create --base main
# PR merged 之后

# 主终端 — Trellis 联动方式
python3 .trellis/scripts/task.py worktree remove <slug>
python3 .trellis/scripts/task.py archive <slug>

# 主终端 — git 原生方式
git worktree remove ../mimicry-<X>
git branch -d <branch>
```

---

## 排错

| 症状 | 原因 / 解 |
|---|---|
| `task.py start <slug>` 在 worktree 内报 "Task not found" | 任务目录没在 base_branch 上 commit。`worktree create` 会自动处理；旧 worktree 需要手动 rebase 把任务目录拉到自己分支 |
| `worktree remove` 拒绝 | 工作树脏 or 有未推送 commit。真不要了用 `--force`，否则先 push |
| `worktree create` 报 "branch already exists" | 旧分支没删 → `git branch -D feat/<slug>` 后重试，或用 `--branch other-name` |
| 两个 session 显示同一个 current-task | 它们 cwd 在同一个 worktree（含主仓库），不是不同 worktree |

# 并行 Agent 使用说明

> 操作者视角：怎么让多个 AI agent（Claude Code / Codex / Gemini 等）在不同终端、不同 git worktree 里并行干活而不打架。

---

## 30 秒总览

**模型**：每个 agent = 一个 Trellis 任务 + 一个 git worktree + 一个分支 `feat/<task-slug>`，PR 直接到 `main`。**没有父子任务，没有 integration 分支**。Agent 之间通过 hook 自动注入的 `<peer-worktrees>` 块互相看见。

**底层契约**：

- 硬规则：[`.trellis/spec/cross-layer/parallel-development.md`](../.trellis/spec/cross-layer/parallel-development.md)
- 软指南：[`.trellis/spec/guides/parallel-task-thinking-guide.md`](../.trellis/spec/guides/parallel-task-thinking-guide.md)

---

## 启动 N 个并行 agent

假设你想让 2 个 Claude Code session 并行做 2 个独立任务。

### 1. 在主终端创建任务

```bash
# 主终端，main 分支
python3 .trellis/scripts/task.py create "Login UI 重做"   --slug login-ui-redesign
python3 .trellis/scripts/task.py create "导出 CSV 功能"   --slug csv-export

# 关联分支
python3 .trellis/scripts/task.py set-branch login-ui-redesign feat/login-ui-redesign
python3 .trellis/scripts/task.py set-branch csv-export        feat/csv-export
```

每个任务的 `.trellis/tasks/MM-DD-<slug>/prd.md` 应该写清楚要做什么。如果要改热点文件（`shared/action-map.json` / `.trellis/spec/**` / 版本三件套等），在 PRD 顶部加：

```yaml
parallel:
  hotfiles_touched:
    - shared/action-map.json
```

声明后，其他 agent 用 `task.py list --hotfile shared/action-map.json` 能查到你。

### 2. 在主终端创建 worktree

```bash
python3 .trellis/scripts/task.py worktree create login-ui-redesign
python3 .trellis/scripts/task.py worktree create csv-export
```

得到：

```
.trellis/worktrees/login-ui-redesign/   ← checkout 在 feat/login-ui-redesign
.trellis/worktrees/csv-export/          ← checkout 在 feat/csv-export
```

### 3. 开 N 个终端，各启一个 agent

**终端 A**：

```bash
cd .trellis/worktrees/login-ui-redesign
python3 ../../scripts/task.py start login-ui-redesign
claude          # 或 codex / gemini
```

**终端 B**（与 A 完全并行）：

```bash
cd .trellis/worktrees/csv-export
python3 ../../scripts/task.py start csv-export
claude
```

每个 session 启动时，SessionStart hook 会自动注入：

- `workflow.md` 概览
- 当前任务状态（PRD、隐含的 next-action）
- 协议指针（自动让 agent 知道有 `parallel-development.md` 这份硬契约）
- **`<peer-worktrees>` 块** —— 其他 agent 的 worktree、分支、ahead/behind、dirty 状态

后续每个 prompt，UserPromptSubmit hook 又刷新一次 `<peer-worktrees>`，所以 agent 不用手动查就能持续看到同伴。

### 4. agent 自己走标准流程

每个 agent 在自己的 worktree 里：

1. 改代码
2. 跑相关测试（typecheck、lint、对应 package 的单测）
3. commit 用规定格式 `<type>(<task-slug>): <中文描述>`
4. `git push -u origin feat/<slug>`
5. `gh pr create --base main`
6. PR 触发 CI 全栈，merge 到 main

### 5. PR 合并后回主终端清理

```bash
python3 .trellis/scripts/task.py worktree remove <slug>
python3 .trellis/scripts/task.py archive <slug>
```

---

## 插入新规范（你自己加规则）

按规则的"生效层"放：

| 规则类型 | 放哪 | 例 |
|---|---|---|
| **硬契约**（违反就拒）| `.trellis/spec/cross-layer/parallel-development.md` 的 Forbidden Patterns 表 | "改 `shared/action-map.json` 必须在 PRD 声明 BREAKING" |
| **软指南**（决策辅助）| `.trellis/spec/guides/parallel-task-thinking-guide.md` 的 Common Mistakes / 决策树 | "单 task diff 别超 500 行" |
| **每会话上下文**（启动时一次）| `.claude/hooks/session-start.py`（在 `_build_peer_worktrees_block` 旁边加）| "启动时显示今日 P0 任务清单" |
| **每轮上下文**（每 prompt）| `.claude/hooks/inject-workflow-state.py`（在 `get_peer_worktrees` 旁边加）| "每轮显示 main 分支最新 commit" |
| **平台入口指针**（哪些文件该读）| `CLAUDE.md` / `AGENTS.md` | "agent 启动时先读 X.md" |

写完静态规则后**不需要重启 agent** —— 下次 SessionStart 自动加载。改 hook 后，新 session 自动生效（旧 session 不会重读）。

---

## 当前完整流程（一个 agent 视角）

```
会话启动
  ↓
SessionStart hook 注入：
  - workflow.md 概览
  - 当前 task 状态
  - <peer-worktrees>（其他 agent 在干啥、什么分支、dirty?）
  - 指向硬契约 parallel-development.md
  ↓
Agent 读 prd.md → 理解自己任务
  ↓
(若动热点文件) task.py list --hotfile <path> 查冲突
  ↓
改代码、跑测试
  ↓
每轮 prompt：
  UserPromptSubmit hook 刷新 <peer-worktrees> + 当前 task flow 提示
  ↓
git fetch origin && git rebase origin/main
  ├─ 冲突 →
  │    1. git log --oneline -- <冲突文件> 找最近的别人的 commit
  │    2. 提取 commit 里的 (task-slug)
  │    3. cat .trellis/tasks/*-<task-slug>/prd.md  # 读对方意图
  │    4. 按意图解决冲突（绝不 --ours/--theirs 盲解）
  │    5. git rebase --continue
  └─ 无冲突 → 继续
  ↓
git commit -m "feat(<slug>): <中文描述>"
git push -u origin feat/<slug>
gh pr create --base main
  ↓
CI 全栈 → merge → main
  ↓
主终端：worktree remove + task archive
```

---

## 命令速查表

```bash
# 任务管理
task.py create "<title>" --slug <slug>           # 新建
task.py set-branch <slug> feat/<slug>            # 关联分支
task.py start <slug>                             # 设为 current-task（在 worktree 内跑）
task.py finish                                   # 清当前任务指针
task.py archive <slug>                           # 归档
task.py list                                     # 所有
task.py list --status in_progress                # 活跃任务
task.py list --status planning                   # 待领的任务
task.py list --hotfile <path>                    # 谁声明了某热点文件

# Worktree 管理（必须在主 worktree / main 分支跑）
task.py worktree create <slug>                   # 创建
task.py worktree list                            # 列所有活跃 worktree（branch / ahead-behind / dirty）
task.py worktree status <slug>                   # 单个详情 + commit log
task.py worktree remove <slug>                   # 删（脏树或 ahead 拒绝）
task.py worktree remove <slug> --force           # 强删
```

> 所有命令都接受**任务 slug**或**完整 task 目录路径**两种形式，由 `resolve_task_dir` 统一处理。

---

## 常见问题排错

| 症状 | 原因 / 解法 |
|---|---|
| Agent 看不到 peer worktree | 跑 `python3 .claude/hooks/session-start.py < <(echo '{"hook_event_name":"SessionStart"}')` 直接看输出，确认 hook 没崩 |
| `worktree create` 报"branch already exists" | 旧分支没删 → `git branch -D feat/<slug>` 后重试，或加 `--branch other-name` |
| `worktree remove` 拒绝 | 有未提交改动 / commit 还没推上去 → 真的不要了用 `--force`；否则先 push |
| Rebase 冲突找不到对方 task | 对方 commit 没用 `(task-slug)` 格式 → `git log -- <file>` 看 author / message 凭经验判断 |
| 两个 worktree 同时跑 `cargo tauri dev` | 端口 1420 单一资源，第二个失败 → 一个跑 dev，其他用 `cargo check`/`cargo test` |
| `task.py list --hotfile X` 漏了某任务 | 该任务的 `prd.md` 里没声明 `hotfiles_touched: - X` 或格式错 → 修 PRD |
| Hook 没生效（peer 块没出现）| 1) 先看 `.claude/settings.json` hook 注册没掉 2) `.trellis/tasks/<slug>/task.json` 的 `worktree_path` 字段为空 → `worktree create` 没成功 |

---

## 何时**不该**开并行 agent

不是所有任务都该并行。具体判断见 [`parallel-task-thinking-guide.md`](../.trellis/spec/guides/parallel-task-thinking-guide.md) 的决策树，这里给最常见 4 种反例：

1. 紧急 bugfix（启动 worktree 比改完还慢）
2. 总工时 <30 分钟
3. 一个 feature 跨 frontend/rust/sidecar，但 cross-layer 契约还没定（先单 task 把契约定了，再并行实现）
4. 你只有一个终端 / 一个人 —— 切换 worktree 不是并行，是 context-switch

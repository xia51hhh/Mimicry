# PRD: Trellis 并行 Agent 开发协议（基于 git worktree）

## 背景

当前 Trellis 是单任务、单工作树流程：`.trellis/.current-task` 只能指向一个任务，多个 agent 想同时干活就会争抢工作树、分支、热点文件。

数据模型已经为多 worktree 留了位但没启用：

- `task.json` 已有 `worktree_path: str | None` 字段（`.trellis/scripts/common/task_store.py:218`，`.trellis/scripts/common/types.py:43`）
- `.trellis/scripts/common/types.py:100-108` 定义了 `AgentRecord` registry shape（含 `worktree_path/branch/pid/task_dir/started_at/status`）
- `cmd_add_subtask` / `cmd_remove_subtask` + `task.json.parent`/`children` 已支持父子结构（`.trellis/scripts/common/task_store.py:408-501`）
- `cmd_create` 自动把当前 git branch 记成 `base_branch`（同文件 198-200 行）
- Hooks 在 worktree 内透明工作：`.claude/hooks/inject-subagent-context.py:73-78` 通过 `.git` 文件存在性找 repo_root，git worktree 的 `.git` 是 file 而非 dir，`.exists()` 仍 True，所以 sub-agent 派发进 worktree 后能读到该 worktree 自己的 `.current-task`

本任务在以上既有数据模型上补齐"工作树管理 + 协议契约"，让父任务能把工作 fan-out 成多个 worktree 内的子任务。

## 范围 / 已确认决策

| 决策 | 取值 |
|---|---|
| 交付 | 文档（约定/规则）+ 最小 `task.py worktree {create, remove, list, status}` 子命令 |
| worktree 路径 | 仓库内 `.trellis/worktrees/<task-slug>/`，加 `.gitignore` |
| 合并模型 | Integration 分支：父任务持 `feat/<parent-slug>`，子任务 PR 先合到它，最后父 PR 到 main |
| 热点文件冲突 | 父任务在 `prd.md` 显式声明每个热点文件的 owner 子任务，其他子任务禁止改 |

## 交付物

### 1. 协议契约文档（硬约定）

**新建** `.trellis/spec/cross-layer/parallel-development.md`

风格参照 `.trellis/spec/cross-layer/block-schema.md`（对照表 + Forbidden Patterns）。必须包含：

- **Worktree 放置**：`.trellis/worktrees/<task-slug>/`；禁止仓库外路径
- **分支命名**：
  - 父任务：`feat/<parent-slug>`（即 integration 分支）
  - 子任务：`feat/<parent-slug>/<child-slug>`，`base_branch = feat/<parent-slug>`
  - 单任务（非 fan-out）：保留现有 `feat/<task-slug>` 习惯
- **生命周期状态机**：planning → in_progress（worktree active）→ pr_open → merged_to_parent → archived
- **父任务 prd.md 必填段落 schema**：
  ```yaml
  parallel:
    integration_branch: feat/<parent-slug>
    children:
      - slug: <child-slug>
        scope: <一句话描述>
        hotfiles_owned: [<path>, ...]   # 该子任务独占编辑权
    hotfiles:
      - <hot-file-path>
  ```
- **Hot-file owner 规则**：
  - 父任务 `prd.md` 列举所有受影响的热点文件 + 唯一 owner 子任务
  - 非 owner 子任务在自己 worktree 里碰这些文件 → `trellis-check` 必须报错（写到 `check.jsonl` 引用本契约文件）
  - rebase 子任务到 integration 时若 owner 已合入新版本，非 owner 子任务必须先 rebase 到 owner 之后再 PR
- **测试分层**：
  - 子任务在自己 worktree：`pnpm typecheck` + `pnpm lint` + 相关 package 单元测试（frontend → vitest，sidecar → pytest，rust → cargo test）
  - 父任务在自己 worktree（integration 分支）：全栈联调 `cargo tauri dev` 至少冒烟一次 + 三端全测（`pnpm test && cd src-tauri && cargo test --all-targets --all-features && python -m pytest sidecar/tests/`）
- **共享资源限制**（同一时间只能一个 worktree 占用）：
  - Vite/Tauri 端口 1420
  - SQLite 数据库 `<app-data>/com.mimicry.app/mimicry.db`
- **合并顺序契约**：子 PR → integration → 父 PR → main。**禁止子 PR 直接打 main**
- **Forbidden Patterns 表**（≥5 行）：
  - worktree 在 `.trellis/worktrees/` 之外
  - 非 owner 子任务改热点文件
  - 子任务 PR 直接打 main
  - 两个 worktree 同时跑 `cargo tauri dev`
  - 子任务跨过父任务直接修父分支

### 2. 思考指南

**新建** `.trellis/spec/guides/parallel-task-thinking-guide.md`

风格参照 `.trellis/spec/guides/cross-layer-thinking-guide.md`（流程类、checklist 风格）。必须包含：

- **何时该 fan-out** checklist：
  - [ ] 工作可切成 ≥2 个互不依赖的子模块
  - [ ] 每个子模块预计 ≥30min 编码量（小任务串行更快）
  - [ ] 热点文件 ≤2 个、且能明确划分 owner
  - [ ] 不需要中途跨子任务交换数据
- **何时不要 fan-out**：纯重构（热点文件遍布）、紧急 bugfix、工作量 <1h、研究型任务
- **拆分原则**：按 package（frontend/sidecar/rust）拆是天然边界 → 按 feature 切片次之 → 避免按"代码层"拆
- **Common Mistakes** 对照表（与 cross-layer-thinking-guide.md 同结构）

### 3. 最小工具：`task.py worktree` 子命令组

**新建** `.trellis/scripts/common/worktree.py`

实现 4 个 handler：
```python
def cmd_worktree_create(args)  # task.py worktree create <task-slug> [--branch <name>]
def cmd_worktree_remove(args)  # task.py worktree remove <task-slug> [--force]
def cmd_worktree_list(args)    # task.py worktree list
def cmd_worktree_status(args)  # task.py worktree status <task-slug>
```

**修改** `.trellis/scripts/task.py`：在 argparse 主 parser 上加 `worktree` 子命令组（仿现有 `add-subtask` / `remove-subtask` 的注册方式），dispatch 到 worktree.py。

**强制复用现有工具**（不要重写）：
- `common/git.py::run_git` —— 所有 git 调用必须走它
- `common/paths.py::get_repo_root, get_tasks_dir` —— 路径解析
- `common/io.py::read_json, write_json` —— task.json 读写
- `common/task_utils.py::resolve_task_dir, find_task_by_name` —— task slug → 目录解析（同 set-branch）
- `common/log.py::Colors, colored` —— 输出风格
- `common/tasks.py::iter_active_tasks` —— list 命令枚举

**`worktree create <task-slug>` 行为**：
1. `resolve_task_dir(task_slug)` → task_dir
2. 读 task.json：取 `branch`（无则用 `feat/<task-slug>` 作默认）和 `base_branch`
3. `git worktree add .trellis/worktrees/<task-slug> -b <branch> <base_branch>`（分支已存在则去掉 `-b`）
4. 写回 task.json：`worktree_path = ".trellis/worktrees/<task-slug>"`，若 branch 之前为 None 则补写
5. stdout 输出 worktree 绝对路径供脚本链式调用

**`worktree remove <task-slug>` 行为**：
1. 读 task.json.worktree_path，无则报错退出
2. 在 worktree 内 `git status --porcelain` —— 有未提交改动则拒绝（`--force` 跳过）
3. `git log <branch> ^<base_branch> --oneline` —— 有未推送 commit 则拒绝（`--force` 跳过）
4. `git worktree remove [--force] <path>`
5. task.json.worktree_path = None（branch 字段保留）

**`worktree list` 行为**：
1. `iter_active_tasks()` 枚举所有任务
2. 过滤 `worktree_path != None`
3. 对每个 worktree 跑 `git rev-list --left-right --count <base>...<branch>` 取 ahead/behind
4. 输出表：`task_slug | branch | path | ahead/behind | dirty?`

**`worktree status <task-slug>` 行为**：单 task 版的 list，详细 `git status` + `git log <base>..<branch>`。

### 4. 配套小改动

- **修改** `.gitignore`：追加 `.trellis/worktrees/`
- **修改** `.trellis/spec/cross-layer/index.md`：在 Files 表加 `parallel-development.md` 入口
- **修改** `.trellis/spec/guides/index.md`：在 Available Guides 表加 `parallel-task-thinking-guide.md` 入口；Quick Reference 段加触发条件
- **修改** `.trellis/workflow.md`：在 "Phase Index" 之后加一段 "Parallel Development"，链接到上面两份新文档；不动现有 phase 内容
- **修改** `CLAUDE.md`：在 "Trellis workflow" 段末追加一句 "并行开发协议见 `.trellis/spec/cross-layer/parallel-development.md`"

## 不在范围（显式推迟）

- `task.py spawn-children`（一键 fan-out）
- `registry.json` 写入与 `AgentRecord` 消费
- pre-commit hook 自动校验 hot-file owner 越权（先靠 trellis-check 兜底）
- `cargo tauri dev` 端口 / SQLite 路径隔离方案（短期靠"同一时间只一个 worktree 跑"约定）
- 父任务自动收 child PR 状态的 helper

## 验收标准

```bash
# 1. 工具层验证（新建 demo 任务跑全流程）
python3 .trellis/scripts/task.py create "Demo parent" --slug demo-parent
python3 .trellis/scripts/task.py create "Demo child A" --slug demo-child-a --parent .trellis/tasks/$(date +%m-%d)-demo-parent
python3 .trellis/scripts/task.py set-branch .trellis/tasks/$(date +%m-%d)-demo-child-a feat/demo-parent/demo-child-a
python3 .trellis/scripts/task.py set-base-branch .trellis/tasks/$(date +%m-%d)-demo-child-a feat/demo-parent

# create
python3 .trellis/scripts/task.py worktree create demo-child-a
test -d .trellis/worktrees/demo-child-a                                # 工作树存在
git worktree list | grep demo-child-a                                   # git 注册
python3 -c "import json;d=json.load(open('.trellis/tasks/$(date +%m-%d)-demo-child-a/task.json'));assert d['worktree_path']=='.trellis/worktrees/demo-child-a'"

# list
python3 .trellis/scripts/task.py worktree list                          # 列出 demo-child-a 一行

# status
python3 .trellis/scripts/task.py worktree status demo-child-a           # clean tree

# remove (clean)
python3 .trellis/scripts/task.py worktree remove demo-child-a
test ! -d .trellis/worktrees/demo-child-a                               # 已删除
python3 -c "import json;d=json.load(open('.trellis/tasks/$(date +%m-%d)-demo-child-a/task.json'));assert d['worktree_path'] is None"

# remove (with uncommitted changes — must refuse without --force)
python3 .trellis/scripts/task.py worktree create demo-child-a
echo dirty > .trellis/worktrees/demo-child-a/test-dirty.txt
python3 .trellis/scripts/task.py worktree remove demo-child-a           # 应拒绝
python3 .trellis/scripts/task.py worktree remove demo-child-a --force   # 应成功

# 收尾
python3 .trellis/scripts/task.py archive demo-child-a
python3 .trellis/scripts/task.py archive demo-parent

# 2. Hook 兼容性（手动验证）
python3 .trellis/scripts/task.py worktree create demo-child-a
cd .trellis/worktrees/demo-child-a && python3 ../../scripts/task.py start demo-child-a
cat .trellis/.current-task                                              # 应是 demo-child-a
cd ../../.. && cat .trellis/.current-task                               # 主 worktree 不受影响

# 3. 文档冒烟（人工）
# 让全新 Claude session 只读 .trellis/spec/cross-layer/parallel-development.md，
# 问四问：worktree 放哪？子 PR 打哪？热点文件谁能改？整合分支何时合 main？
# 全对则文档合格。

# 4. 静态检查（应不受影响，因本任务不动 src/）
pnpm typecheck                                                          # 应通过
python3 .trellis/scripts/task.py --help | grep worktree                 # 应输出 worktree 子命令
```

**全部通过 = 验收通过。**

## 与现有任务的关系

- ci-mcp-captcha 已 archive
- 本任务独占 main 分支推进，本身不 fan-out（结构性变更，热点文件密集，是反例）
- 落地后才是后续任务可享受 fan-out 的起点

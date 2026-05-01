# PRD: 对等并行 agent 协议（peer 模型）

## 背景

上一任务 `05-01-parallel-worktrees-protocol` 引入了 worktree 工具 + 父子分层协议。实际使用反馈：父子模型对单人多 agent 场景过度复杂——每个 agent 在各自终端独立运作，根本没有"父任务编排"的实体存在。

因此把协议改写成**对等模型**：N 个 agent，N 个对等任务，N 个 worktree，每个 PR 直打 `main`。同时补足两块缺口：

1. 观测能力：每个 agent 自动看到其他 agent 在干什么（hook 注入）
2. 冲突解决：标准化 commit 格式 + 通过 commit 中的 task-slug 反查冲突任务的 PRD

## 范围 / 已确认决策

| 决策 | 取值 |
|---|---|
| 协议模型 | 对等（peer），无父子层级、无 integration 分支 |
| 分支命名 | `feat/<task-slug>` 一律相同，base 一律 `main` |
| 热点文件协调 | 每任务自报 `hotfiles_touched`；其他 agent 用 `task.py list --hotfile <path>` 查 |
| 合并冲突 | 必须读冲突 commit 的 `<task-slug>` → 找到对方任务 PRD → 理解意图 → 解决 |
| Commit 格式 | `<type>(<task-slug>): <中文描述>` |
| 观测 | SessionStart + UserPromptSubmit hook 自动注入 `<peer-worktrees>` 块 |

## 交付物

### 1. 协议契约文档（重写）

**修改** `.trellis/spec/cross-layer/parallel-development.md` —— 完全重写为对等模型，删父子部分，新增：
- Hot-file 自报协调流程（before-worktree / before-PR 两段）
- Merge Conflict Resolution 强制流程（找 commit slug → 读 PRD → 解决）
- Commit Format 强制规范（feat/fix/etc + Chinese 描述 + slug scope）
- 仓库内热点文件清单
- Forbidden Patterns 表更新

### 2. 思考指南（重写）

**修改** `.trellis/spec/guides/parallel-task-thinking-guide.md` —— 删父子决策树，新增：
- 5 步进入流程（每个 agent 启动时跑的命令清单）
- 何时不该开 parallel 任务表格
- 6 个 Common Mistakes（含合并冲突盲解、commit 格式遗漏、stale hotfiles_touched）
- 决策树重写为 peer-aware

### 3. Hook 观测注入

**修改** `.claude/hooks/inject-workflow-state.py` —— 在 `<workflow-state>` 之后追加 `<peer-worktrees>` 块（每轮 prompt 都更新）。读 task.json 而不是调 git，保持速度。

**修改** `.claude/hooks/session-start.py` —— 在 `<task-status>` 之后注入 `<peer-worktrees>` 块（一次启动可承受 git 调用，输出 dirty/ahead-behind 状态）。

### 4. `task.py list --hotfile <path>` 过滤器

**修改** `.trellis/scripts/task.py` —— `cmd_list` 新增 `--hotfile <path>` 参数；解析每个 active 任务的 `prd.md`，匹配 `hotfiles_touched:` YAML list（含 inline `[a, b]` 形式）。

### 5. 配套指针更新

**修改** `.trellis/workflow.md` —— Parallel Development 段重写为 peer 模型，删父子表述
**修改** `CLAUDE.md` —— 协议指针段重写
**修改** `AGENTS.md` —— 末尾新增 Parallel Multi-Agent Development 段

## 不在范围

显式推迟：

- `task.py spawn-children` —— peer 模型下不需要
- `registry.json` 写入 + `AgentRecord` 消费 —— 当前用 task.json.worktree_path 已足够
- pre-commit hook 自动校验 commit 格式 —— 暂时靠人工 + code review

## 受影响的热点文件

```yaml
parallel:
  hotfiles_touched:
    - .trellis/spec/cross-layer/parallel-development.md
    - .trellis/spec/guides/parallel-task-thinking-guide.md
    - .trellis/workflow.md
    - CLAUDE.md
    - AGENTS.md
    - .gitignore
```

> 备注：`.claude/hooks/*.py` 和 `.trellis/scripts/task.py`、`.trellis/scripts/common/worktree.py` 也被本任务修改，但它们当前不在仓库通用热点清单内（其他任务通常不会同时改）。如未来出现频繁并发改动，再加入清单。

## 验收标准

```bash
# A. 静态注册
python3 .trellis/scripts/task.py list --help | grep -- --hotfile
# 期望：--hotfile <path> ... 出现

# B. --hotfile 过滤功能
python3 .trellis/scripts/task.py list --hotfile CLAUDE.md
# 期望：列出本任务（hotfiles_touched 中含 CLAUDE.md）

python3 .trellis/scripts/task.py list --hotfile nonexistent/path.txt
# 期望：列表为空 / 0 task(s)

# C. UserPromptSubmit hook 注入 peer 块
echo '{"cwd": "/home/rick/desktop/Mimicry"}' | python3 .claude/hooks/inject-workflow-state.py
# 期望：JSON 输出的 additionalContext 包含 <peer-worktrees>

# D. SessionStart hook 注入 peer 块（如有 worktree 时）
# 创建一个临时 worktree
python3 .trellis/scripts/task.py create "Demo peer" --slug peer-demo
python3 .trellis/scripts/task.py set-branch peer-demo feat/peer-demo
python3 .trellis/scripts/task.py worktree create peer-demo

echo '{"hook_event_name": "SessionStart", "session_id": "test"}' | python3 .claude/hooks/session-start.py | python3 -c "import json,sys;d=json.load(sys.stdin);print('peer-worktrees' in d['hookSpecificOutput']['additionalContext'])"
# 期望：True

# 清理
python3 .trellis/scripts/task.py worktree remove peer-demo --force
rm -rf .trellis/tasks/05-01-peer-demo
git branch -d feat/peer-demo

# E. 不破坏现有命令
python3 .trellis/scripts/task.py list
python3 .trellis/scripts/task.py worktree list

# F. 前端不受影响
pnpm typecheck
```

全部通过 = 验收通过。

## 与之前任务的关系

- `05-01-parallel-worktrees-protocol`（已 archive）—— 引入 worktree 工具 + v1 父子协议；本任务的 `worktree.py` 在那之上
- 本任务在同一 main 分支线上推进，即将合入 `main`

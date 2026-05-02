# 项目状态审计 + 全量文档刷新

## Goal

审计 Mimicry 当前 git 历史与代码实现进度，将所有过时文档更新为反映 main 当前真实状态。重点不是写新文档，而是 **修正与现实漂移**：示例、API、架构图、版本号、特性清单、已弃用项的标记。**顺手吸收 04-28-block-doc-update 任务**（升级 block-api.md 到 canonical 格式）。

## What I already know

- main 工作区干净，HEAD = `f86f4a4`（feat/ux-engine-polish 合并）
- 最近 commit 集中在 UX/Engine polish、debug UI、parallel protocol、自动布局、tabs 持久化
- 三层栈：Vue 3 (`src/`) + Rust Tauri v2 (`src-tauri/src/`) + Python sidecar (`sidecar/`)
- Sidecar 三入口：Tauri stdio JSON-RPC / CLI+UDS / MCP — 共用 `browser/actions.py` + `rpc/methods.py`
- ADR-001：JSON 直执行；`sidecar/dsl/` 已弃用但仍在仓库
- 三处版本三方锁：package.json / tauri.conf.json / Cargo.toml
- `04-28-tab-identification-system` 已归档（commit `3ebd717`）→ 04-28-block-doc-update 依赖满足
- 其他两个 active 任务（i18n-log-normalization、log-panel-enhancement）面向代码，不与文档冲突

## In Scope（B + 04-28 吞并）

### A. 顶层
- `README.md`（根，英文）
- `docs/README.md` / `docs/README.zh-CN.md`
- `CHANGELOG.md`（仅核对版本与未发版变更，不强行 bump）

### B. docs/ 用户与开发者文档（9 篇）
- `architecture.md` · `project-structure.md` · `pseudocode-spec.md`
- `block-api.md`（**含 04-28 任务范围**：flat→canonical + UseBrowser/WaitForNewTab/SwitchTab/CloseTab）
- `dev-cli.md` · `llm-interactive-guide.md`
- `anti-detection.md` · `cicd-guide.md` · `parallel-agents.md`

### C. docs/design/（8 篇）
- `block-system.md` · `data-flow.md` · `debug-system.md` · `decisions.md`（ADR）
- `element-selector.md` · `package-system.md` · `transform-layer.md` · `ui-description.md`

### D. docs/workflow/（2 篇）
- `canvas-interaction.md` · `monaco-integration.md`

**合计 ~22 篇**

## Out of Scope

- `.trellis/spec/` 17 篇团队规范（spec 多为约定，不易过时）
- `docs/plans/*.md`（5 篇）— 历史 plan，是时间快照
- `docs/research/*.md`（4 篇）— 调研快照
- `docs/superpowers/specs/*.md`（1 篇）— 历史设计
- `CLAUDE.md` / `AGENTS.md`（Claude/Agent 配置，独立更新节奏）
- `.trellis/tasks/archive/*` — 归档任务

## Workflow

- worktree 隔离：`task.py worktree create docs-refresh-audit` → `.trellis/worktrees/docs-refresh-audit/` on `feat/docs-refresh-audit`
- 完成后 PR → main，归档本任务 + 04-28-block-doc-update

## Implementation Plan（分阶段）

**Phase 1 — Audit（并行）**

派遣 6 个 `trellis-research` 子代理，每个聚焦一块，结果写到 `research/audit-<topic>.md`：

1. `audit-git-history.md` — 自上次文档触动以来的所有 feat/fix/refactor commit，按子系统归类
2. `audit-frontend-state.md` — `src/` 现状 vs README/architecture/project-structure/workflow 文档的差异
3. `audit-rust-core-state.md` — `src-tauri/src/` 现状 vs architecture/data-flow/decisions 的差异
4. `audit-sidecar-state.md` — `sidecar/` 现状 + 三入口 vs dev-cli/llm-interactive-guide/architecture 的差异
5. `audit-block-and-action-map.md` — `shared/action-map.json` + `sidecar/engine/action_map.py` + `src/types/action-map.ts` vs block-api/block-system/decisions（这块覆盖 04-28-block-doc-update）
6. `audit-debug-and-design.md` — debug UI + transform layer + element selector 等 design/ 文档的差异

**Phase 2 — Update（顺序，按文档分组）**

按 audit 报告生成 diff，每个文档分组一个 commit：
- commit 1：顶层 README × 3 + CHANGELOG 核对
- commit 2：docs/architecture + project-structure + pseudocode-spec
- commit 3：docs/block-api（吞并 04-28）+ docs/design/block-system
- commit 4：docs/dev-cli + llm-interactive-guide + docs/design/data-flow
- commit 5：docs/design/{debug-system, element-selector, transform-layer, ui-description, package-system}
- commit 6：docs/workflow/{canvas-interaction, monaco-integration}
- commit 7：docs/{anti-detection, cicd-guide, parallel-agents, decisions}

**Phase 3 — Verify & PR**

- `python scripts/sync-action-map.py`
- `pnpm typecheck && pnpm lint`（确保未误改代码）
- 文档 lint：链接、相对路径、目录树准确
- `gh pr create --base main`
- merged 后：`task.py worktree remove` + `task.py archive` × 2

## Acceptance Criteria

- [ ] 6 份 audit 报告全部落盘 `research/`
- [ ] 范围内 22 篇文档每篇都有 commit（即使是"已核对、无需变更"的也写进 commit message）
- [ ] block-api.md 完成 flat→canonical 升级 + UseBrowser/WaitForNewTab/SwitchTab/CloseTab 文档（04-28 范围）
- [ ] action-map sync 脚本通过
- [ ] PR description 列出所有变更文档与对应 commit
- [ ] 两个任务（本任务 + 04-28）一同归档

## Definition of Done

- worktree 推送 + PR 合并
- 04-28-block-doc-update 标记 completed 后 archive
- 本任务 archive
- 三处版本三方锁未触动
- 任何新发现的规范走 `trellis-update-spec` 入 `.trellis/spec/`

## Decision (ADR-lite)

**Context**：3 个 active 任务中 04-28-block-doc-update 与本审计高度重叠（都触 docs/block-api.md），分两次做会造成重复 audit 与潜在合并冲突。

**Decision**：本任务范围扩到 B 并吞并 04-28，一次 PR 内完成，避免短时间内对同一批文档的双重写入。worktree+PR 流程提供回滚路径。

**Consequences**：本 PR diff 较大（~22 文件），但每个 commit 按文档分组，review 友好。04-28 任务在 PR merge 后归档，不再单独执行。

## Technical Notes

- parallel-agents.md 协议是多终端 git worktree —— 本任务用 worktree 隔离自身，但单 session 内的"并行"通过 Task 工具派遣 trellis-research 子代理
- 历史文档（plans/research）原则上不动 —— 它们是时间快照
- audit 报告持久化到 `research/`，避免污染主对话上下文
- 后续 update 阶段的每个 commit 应引用对应 audit 报告，便于 review

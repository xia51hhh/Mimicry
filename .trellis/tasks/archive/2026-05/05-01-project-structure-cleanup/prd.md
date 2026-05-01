# 整理项目文件结构

## 目标

仓库经过两个月开发后积累了多类杂乱：运行时残留、零引用死代码、未归档任务、命中现实的 sidecar 日志路径 bug、文档与现实脱节。本任务一次性修完三批（零风险清理 + sidecar 日志路径 bug + 文档更新归档），让仓库进入"打开就能干活"的状态。

不动：`sidecar/dsl/` + `dev_cli.py` + `src/components/` 重组——这些与 planned 任务有冲突风险或需要更深入设计，留作后续任务。

## 需求（按批次执行）

### 批次 1 — 零风险清理

**目标**：删除死代码、运行时残留、归档已完成任务。

- 删除磁盘上的 sidecar 运行时残留：`sidecar/daemon.log`、`sidecar/mimicry-sidecar.log`、`sidecar/screenshot.png`、`src-tauri/mimicry-sidecar.log`、`src-tauri/mimicry.db`（已 gitignored，单纯擦盘）。
- 扫掉所有 `__pycache__/` 和 `.pytest_cache/`。
- `git rm` 5 个 sidecar 测试目录开发脚本：`_bing_analysis.py`、`_check_webdriver.py`、`_gen_demos.py`、`_run_antidetect.py`、`_test_incolumitas.py`。
- `git rm` 测试输出残留：`sidecar/tests/e2e_stdout.txt`、`sidecar/tests/e2e_stderr.txt`、`sidecar/tests/screenshots/`（45 张图）。
- `git rm sidecar/cli_legacy.py`（零引用确认过）。
- 在 `.gitignore` 加：`sidecar/tests/screenshots/`、`sidecar/tests/e2e_stdout.txt`、`sidecar/tests/e2e_stderr.txt`，预防再生。
- 归档 9 个 completed 但未归档的 Trellis 任务：`00-bootstrap-guidelines`、`04-27-browser-config`、`04-27-ci-pipeline-fix`、`04-27-docs-reality-alignment`、`04-27-profile-isolation-mvp`、`04-27-readme-positioning`、`04-27-sidecar-rpc-spec`、`04-28-block-anti-detection-overhaul`、`04-28-tab-identification-system`。命令：`python3 .trellis/scripts/task.py archive <slug>`。
- 修正 `04-28-workflow-branch-tab-validator/task.json` 的 status 字段：`"done"` → `"completed"`（standardize），然后归档。

### 批次 2 — sidecar 日志路径 bug

**问题**：sidecar 进程从 Tauri shell 启动时继承了 `src-tauri/` 作为 CWD，导致日志写在 `src-tauri/mimicry-sidecar.log`、SQLite 写在 `src-tauri/mimicry.db`，跟正确位置（OS app-data）以及 `sidecar/` 自己的 log 都重复。

**修复要求**：
- 找到 sidecar 配置 loguru 的位置（约在 `sidecar/utils/`、`sidecar/main.py` 或 `sidecar/daemon.py`）。
- 把日志输出路径改成绝对路径：优先使用与 venv/db 一致的 OS app-data 目录，或退而求其次使用 `<sidecar 源码目录>/logs/`（要在 `.gitignore` 同步加上）。
- 确认修复后 `cargo tauri dev` 跑一次，sidecar 不再在 `src-tauri/` 写文件。
- **如果改动超出 50 LOC 或需要新增配置 schema**：停下来报告，本任务保守处理，深度重构留作 follow-up。

### 批次 3 — 文档更新与归档

**目标**：让 docs 反映现实，归档过时材料。

更新（修内容）：
- `docs/architecture.md`：头注 "最后更新: 2026-04-27" 改成今天日期，"Implemented" 列补上 captcha solver、profile 隔离、MCP 52 工具、auto-updater；其他状态如有变化也修正。
- `docs/design/block-system.md`：头注 "最后更新: 2026-04-28" 改成今天日期；"现实边界" 部分把 "canonical schema 正在标准化" 这种过期说法改掉（04-27 的 `block-schema-unification` 任务已归档，schema 已 canonical）。
- `docs/dev-cli.md`：重写。当前结构是把 `dev_cli.py`（旧版）和 `cli.py + daemon.py`（当前）并排介绍但谁是主推不清楚。改成：以 `cli.py + daemon.py` 为主，`dev_cli.py` 单独一节标 "开发调试场景保留" 并清楚说明它独有的 REPL / anti-detect / blocks-test 用途。

归档/删除：
- `docs/plans/` 下 5 份 pre-Trellis 时代规划：`2026-04-17-browser-integration.md`、`2026-04-20-phase1-stabilization.md`、`2026-04-20-phase2-features.md`、`mimicry-mvp.md`、`p1-core-operations.md`。整体移到 `.trellis/tasks/archive/historical-plans/`。原 `docs/plans/` 目录可删（如果空了）。
- `docs/pseudocode-spec.md`：直接 `git rm`。
- `docs/design/decisions.md` 的 ADR-001 段落里 "see [pseudocode-spec.md]" 链接：删掉或改成 git 历史指引，确保没有悬空引用。

链接（让结构文档可达）：
- `docs/project-structure.md`（已存在）链接到 `README.md` 和 `CLAUDE.md` 的 "Architecture pointers" 一节。

## 验收标准

- [ ] 所有列出的删除/归档执行完成
- [ ] `git status` 仅显示本任务预期修改，无误伤
- [ ] `pnpm typecheck && pnpm lint && pnpm test` 通过
- [ ] `cd src-tauri && cargo check && cargo clippy --all-targets --all-features -- -D warnings && cargo test --all-targets --all-features` 通过
- [ ] `cd sidecar && python -m pytest tests/ -v -m "not e2e"` 通过（test_dsl.py 还在，dsl 不动；其他不变）
- [ ] `python3 scripts/sync-action-map.py` 通过
- [ ] `python3 .trellis/scripts/task.py list` 仅显示 active 任务（约 7 项，不含 9 个已归档）
- [ ] `cargo tauri dev` 跑一次：sidecar 日志写到 OS app-data 或 `sidecar/logs/`，**不**写到 `src-tauri/`
- [ ] 不存在 `docs/pseudocode-spec.md`、`docs/plans/`（如全部移走）；ADR-001 引用已修
- [ ] `docs/architecture.md`、`docs/design/block-system.md`、`docs/dev-cli.md` 三处更新完成
- [ ] `README.md` 或 `CLAUDE.md` 含到 `docs/project-structure.md` 的链接

## Definition of Done

- 测试 / lint / typecheck 全绿
- 跨层契约同步脚本通过
- 三批改动各自独立 commit，message 清楚描述
- 不留 TODO 注释、不留 commented-out 代码

## Out of Scope

- 删除 `sidecar/dsl/` + `tests/test_dsl.py`（ADR-001 标了，但 `dev_cli.py` 还引用，需要先决定 `dev_cli.py` 命运）
- 处置 `sidecar/dev_cli.py` 与 `cli.py` 的功能重叠（需要单独设计是合并还是保留）
- `src/components/` 根级 4 个 Vue 文件分目录（与 planned 的 `04-28-i18n-log-normalization`、`04-28-log-panel-enhancement` 冲突，等那两个落地后再说）
- `src-tauri/src/workflow_validator.rs` 挪位置
- `src/utils/__tests__/` 改 `tests/`
- `block-api.md` / `block-system.md` / `.trellis/spec/cross-layer/block-schema.md` 三处 schema 描述合并

## Technical Notes

- 任务在分支 `feat/parallel-protocol-peer` 上做（当前所在），是 `peer-demo` peer 关系下的工作。**不要**把改动 PR 到 main，按 `parallel-development.md` 协议走。
- 三批之间没有耦合，可独立 commit；如果想加快可让两个 sub-agent 并行（批次 1 和批次 3 不冲突；批次 2 改 sidecar 代码，跟另两批文件路径不重）。
- `parallel-development.md` 规定的 hot files 检查：本任务不动 `shared/action-map.json`、不动版本三联锁文件，安全。

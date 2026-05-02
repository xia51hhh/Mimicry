# Git History Audit (since 2026-04-27)

## Baseline

- **Commit**: `ab03088` (2026-04-27) — `docs: align README and design docs with implemented behaviour`
- **Reason**: Last commit that explicitly aligned docs with code. Everything afterwards is potentially under-documented.
- **Archive of corresponding task**: `9e88487` (2026-05-01) archived `04-27-docs-reality-alignment`

## Commits grouped by subsystem

### Frontend (`src/`)

- `55f52ff` 2026-05-01 连线流动动画 + 节点 Tooltip + F9/F5/F10 快捷键 + MiniMap + 选择器自愈 [nodes/, useKeyboardShortcuts, locales]
- `7a459d6` 2026-05-01 调试 UI — 断点指示器 + 暂停动画 + Debug 面板 + 右键菜单 [BottomPanel, nodes/, stores/execution]
- `b9c4714` 2026-05-01 Toolbar 调试控制按钮（暂停/继续/单步）[Toolbar, stores/execution]
- `138db37` 2026-05-01 调试命令暴露 + dirty 检测 + tabs 持久化 [App.vue, TabBar, useFileOps, stores/workflow, stores/workspace]
- `844d2cc` 2026-04-28 接入多格式导入 / Compact 导出 [components/editor]
- `ab2f243` 2026-04-28 前端导入/导出多格式支持 [components/editor]
- `897b4e4` 2026-04-28 验证系统前端集成 — Problems 面板 + 节点诊断徽标 [BottomPanel, nodes/]
- `fdd6257` 2026-04-28 SwitchTab 属性面板支持梯度匹配字段 [PropertyPanel, types/]
- `25248c4` 2026-04-27 浏览器配置系统 + 多 session 管理 [CamoufoxSetup, ProfileDialog, ProfileManager]
- `c108aac/52e6d06` 2026-04-27 HiDPI 适配 + geoip UI 提示

### Rust core (`src-tauri/src/`)

- `f064821` 2026-05-01 自动布局算法升级 — condition/loop 分支偏移 [transform/compact, transform/layout, transform/mod]
- `15a8421` 2026-05-01 prettier + cargo fmt 全量格式化（13 文件）
- `e788806` 2026-04-28 transform 审查修复 Info 级 — IO 错误类型 / 路径校验 / 死变量 / 测试补全
- `b3a0eca` 2026-04-28 transform 审查修复 — Debug 依赖 / settings 丢失 / Recording 导入
- `3f58d36` 2026-04-28 transform Phase 4 — 清理废弃代码 + 更新文档
- `001c237` 2026-04-28 transform Phase 3a — 新增 3 个 Tauri Commands
- `c2741e0` 2026-04-28 transform 集成测试 — 执行/导入/往返全链路
- `9985352` 2026-04-28 transform Phase 2 — 执行链路接入 Rust 转化层
- `5f882da` 2026-04-28 transform Phase 1 — Rust 工作流转化层核心模块
- `d52f4f4` 2026-04-28 validator: 37 条 PRD 规则全实现 (W006/W007/W013/W014 + I002-I011)
- `dabc3bb` 2026-04-28 validator Phase 2 跨节点分析 — W001/W005/W010/I001
- `5ca1f21` 2026-04-28 validator P0+P1 — 18 条规则 + workflow_execute 拦截
- `d710a64` 2026-04-28 validator PRD — 37 条规则定义
- `5f7b39d` 2026-04-29 merge: 工作流转化层 — Rust 多格式转换/导入导出/验证管线

### Sidecar (`sidecar/`)

- `9c14fe6` 2026-05-01 CLI validate 输出改为 JSON + MCP 过滤 test.* 方法 [cli, mcp_server]
- `1eafb24` 2026-05-01 launch flush init_scripts + 网络捕获幂等/截断校验 + isError SDK 校验 [browser/actions, browser/controller, mcp_server, +tests]
- `7f12f2a` 2026-05-01 CLI 清理 — 删 cli_legacy/dev_cli 切到 rpc.methods / --json 一致性 / SKILL.md 漂移
- `f08887c` 2026-05-01 MCP isError 协议 + FastMCP 迁移评估 [mcp_server]
- `15bcf79` 2026-05-01 移植 network 捕获 / console 缓冲 / init scripts [browser/actions, browser/controller, engine/executor]
- `6b47444` 2026-05-01 补全所有 rpc_method 的 LLM-facing 描述 [browser/actions, rpc/methods]
- `4615d7c` 2026-05-01 修复 MCP schema 推断 / 命名映射 / **kwargs 泄漏 [browser/actions, mcp_server]
- `cb9fa6c` 2026-04-30 robust LLM interactive CLI for browser control and documentation
- `a88865a` 2026-04-29 CLI Daemon + MCP Server + Workflow Control（首次引入）
- `c330cf5` 2026-04-29 anti-detect — 消除 JS 全局变量泄漏 + 修正启动参数
- `2bed406` 2026-04-28 反检测行为模拟 + Block 体系补全
- `0f072ee` 2026-04-28 解决 Playwright greenlet 跨线程错误，**统一 block 三层 canonical 格式**（关键）
- `4d3c899` 2026-04-27 sidecar/executor: preserve data namespace; accept canonical nodes
- `4bbd741` 2026-04-28 _normalize_node 幂等性修复
- `14650dd` 2026-04-28 Fail 映射补全 + _count_nodes 性能优化
- `2ecefbd` 2026-04-28 录制无输出修复 — 用 poll 定时器替代失效的 notification 监听
- `956bfd3` 2026-04-28 录制引擎自动检测 tab 切换 + 插入 SwitchTab 节点
- `7cbc580` 2026-04-28 Tab 标识注册系统 — TabInfo + 梯度匹配 + 录制集成（关键）

### Cross-layer（`shared/`、action-map sync）

- `a8580ce` 2026-05-01 close P0 CI gaps + upgrade MCP schema + captcha solver [scripts/sync-action-map.py + src/types/action-map.ts + sidecar/captcha/]
- `fd53189` 2026-04-27 canonical block schema with explicit legacy migration（关键）
- `0d8810d` 2026-04-27 tighten canonical schema, surface mixed-input conflicts
- `0f072ee` 2026-04-28 统一 block 三层 canonical 格式（关键）

### Build / CI

- `a8580ce` 2026-05-01 .github/workflows/pipeline.yml — close P0 CI gaps
- `15efc28` 2026-05-01 batch1 cleanup — 删 sidecar test scratch + tighten gitignore
- `4a46935` 2026-05-01 sidecar log path fix + project-structure doc + remove dev db
- `b488c88` 2026-05-01 README rewrite Clippy style + tauri.conf.json + banner.png

### Docs (`docs/`、`.trellis/spec/`、README、CHANGELOG)

- `fb6c1aa` 2026-05-01 并行开发协议契约文档 + 思考指南 + 索引（add `.trellis/spec/cross-layer/parallel-development.md` + `guides/parallel-task-thinking-guide.md`）
- `a6ad9a4` 2026-05-01 简化为单一 worktree 工具，**删过度设计的协议层**（重写 docs/parallel-agents.md）
- `444e0b5` 2026-05-01 对等并行协议、思考指南与用户使用说明（**首次创建** docs/parallel-agents.md，后被 a6ad9a4 简化）
- `7d52290` 2026-05-01 沉淀 sidecar MCP/RPC/CLI 硬契约到 spec（add `.trellis/spec/sidecar/mcp-rpc-cli.md` + `index.md`）
- `bf431fe` 2026-05-01 docs/superpowers/specs/2026-05-01-conversion-layer-fixes-design.md
- `4a46935` 2026-05-01 add `docs/project-structure.md`
- `b488c88` 2026-05-01 README.md + docs/README.zh-CN.md Clippy rewrite + banner
- `2949a90` 2026-05-01 add CLAUDE.md + external projects research and analysis
- `15bcf79` 2026-05-01 docs/design/block-system.md updated（network/console/init_scripts）
- `9b20096` 2026-04-29 anti-detection 12 维模型 + Symbol key injection + multi-site 测试结果
- `2e6ed1b/10febb0` 2026-04-29 anti-detection 真实测试结果更新
- `ab03088` 2026-04-27 **baseline** — align README and design docs

### Trellis tasks/process

- `0a09e9c` 2026-05-01 worktree 子命令组 + list --hotfile 过滤（task.py 引入 worktree subcommand）
- `eb246b1` 2026-05-01 worktree create 自动 commit 任务目录
- `6f27a67` 2026-05-01 hook 自动注入 peer worktree 观测
- 大量 archive 任务（2026-05-01 一天集中归档了 10+ 任务）

## High-impact features that landed

1. **Rust 工作流转化层（Transform Layer）** — `5f882da` `9985352` `001c237` `ab2f243` `3f58d36` `b3a0eca` `e788806` `c2741e0` `5f7b39d` `f064821`
   多 Phase 实现 JSON 工作流的 Rust 侧转化、导入/导出（含 Compact 格式）、自动布局（含 condition/loop 分支偏移）。

2. **工作流静态验证器（37 条规则）** — `d710a64` `5ca1f21` `dabc3bb` `d52f4f4` `897b4e4`
   后端 P0+P1+P2 全规则 + workflow_execute 拦截 + 前端 Problems 面板 + 节点诊断徽标。

3. **Sidecar 三入口体系** — `a88865a` `cb9fa6c` `7f12f2a` `f08887c` `4615d7c` `15bcf79` `1eafb24` `9c14fe6` `6b47444`
   首次引入 CLI Daemon + MCP Server；后续大量 polish — schema 推断、isError 协议、network/console/init_scripts、--json 一致性、cli_legacy 删除。

4. **Tab 标识 + 梯度匹配系统** — `7cbc580` `956bfd3` `fdd6257` `eba7eec`
   TabInfo + 梯度匹配 + 录制自动检测 tab 切换 + 属性面板支持。**04-28-block-doc-update 的依赖已在此 PR 满足**。

5. **Canonical Block 格式三层统一** — `fd53189` `0d8810d` `4d3c899` `0f072ee`
   从 flat `{type, action, url}` 升级到 `{kind, action, data, settings}`，sidecar/Rust/前端三层一致。

6. **完整调试 UI** — `138db37` `b9c4714` `7a459d6` `55f52ff`
   调试命令暴露、Toolbar 按钮（暂停/继续/单步）、断点指示器 + 暂停动画 + Debug 面板 + 右键菜单、加上后续连线动画/Tooltip/F9-F5-F10/MiniMap/选择器自愈。

7. **多浏览器/Profile + 反检测** — `25248c4` `c330cf5` `2bed406` `9b20096` `c108aac` `52e6d06`
   浏览器配置系统、多 session 管理、12 维反检测模型、Symbol key injection、HiDPI/geoip。

8. **CI 闭环 + 验证码 click solver** — `a8580ce`
   pipeline.yml 关掉 P0 缺口、MCP schema 升级、`sidecar/captcha/cloudflare.py` 引入。

9. **并行开发协议（worktree-based）** — `0a09e9c` `eb246b1` `6f27a67` `444e0b5` `a6ad9a4` `fb6c1aa`
   `.trellis/scripts/task.py worktree create/list/status/remove` + hook 自动注入 + `docs/parallel-agents.md` + `.trellis/spec/cross-layer/parallel-development.md`。

10. **README/营销定位重写** — `b488c88`
    Clippy marketing style + banner.png + release URL 修正。

## Removed / deprecated items

- `sidecar/cli_legacy.py` — 删除（`7f12f2a`）；`sidecar/dev_cli.py` 部分清理但未删
- `sidecar/screenshot.png` 与 `sidecar/tests/screenshots/*.png`（30+ 文件） — 测试 scratch 清理（`15efc28`）
- `sidecar/tests/_*.py` ad-hoc 调研脚本删除（`15efc28`）
- `src-tauri/mimicry.db` 开发数据库从仓库清理（`4a46935`）
- `.trellis/spec/cross-layer/parallel-development.md` 与 `guides/parallel-task-thinking-guide.md` 经历过删除→重建（`a6ad9a4` → `fb6c1aa`），**最终保留 fb6c1aa 版**

注意：**`sidecar/dsl/` 仍在仓库，依然标 deprecated**，与 ADR-001 一致。

## Suggested doc impact

| 文档 | 影响来源 | 必改 |
|---|---|---|
| README × 3 | transform / validator / MCP+CLI / tab / 反检测 / 验证码 / 并行协议 | ✅ 高 |
| docs/architecture.md | Rust transform 层 + workflow_validator 模块 + sidecar 三入口最新状态 | ✅ 高 |
| docs/project-structure.md | 5/1 新建，需核对：sidecar/captcha 新增、cli_legacy 删除、dev_cli 状态 | ⚠️ 中 |
| docs/block-api.md | flat→canonical（吞并 04-28）+ Tab 块 + 反检测块（如有） | ✅ 必改（吞并） |
| docs/dev-cli.md | CLI 改造（cli_legacy 删 / --json 一致 / validate 改 JSON） | ✅ 高 |
| docs/llm-interactive-guide.md | MCP isError + schema 推断 + init_scripts + console buffer | ✅ 高 |
| docs/anti-detection.md | 12 维模型已加；近期未变；可能仅小校对 | ⚠️ 低 |
| docs/cicd-guide.md | pipeline.yml P0 闭环 + 验证码 CI | ✅ 中 |
| docs/parallel-agents.md | 已被 `a6ad9a4` 简化重写；与 task.py 实际行为校对 | ⚠️ 中 |
| docs/pseudocode-spec.md | 校对是否仍在 ADR-001 范围内（JSON 直执行）；可能 stale | ⚠️ 中 |
| docs/design/block-system.md | 5/1 已 touch（network/console/init_scripts） | ⚠️ 中 |
| docs/design/data-flow.md | 加 transform 层 + validator 拦截 | ✅ 高 |
| docs/design/debug-system.md | 5/1 已 touch；校对 UI 元素是否齐全 | ⚠️ 中 |
| docs/design/decisions.md | ADR-001 仍 OK；考虑新增 ADR for transform / validator / parallel-protocol / tab-system | ⚠️ 中 |
| docs/design/element-selector.md | 加选择器自愈 | ✅ 中 |
| docs/design/package-system.md | tauri.conf.json 改了 + 三方版本锁 | ⚠️ 中 |
| docs/design/transform-layer.md | 是否新建 / 是否反映 Rust 实现状态 | ✅ 高 |
| docs/design/ui-description.md | 加 Toolbar 调试按钮、Tooltip、MiniMap、Problems 面板 | ✅ 中 |
| docs/workflow/canvas-interaction.md | 调试快捷键 F9/F5/F10 + 右键菜单 + 选择器自愈 | ✅ 高 |
| docs/workflow/monaco-integration.md | 校对当前 monaco 集成状态 | ⚠️ 低 |
| CHANGELOG.md | 校对 0.1.0 版段是否齐全；不强行 bump | ⚠️ 校对 |

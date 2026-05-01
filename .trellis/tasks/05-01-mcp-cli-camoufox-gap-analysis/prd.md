# MCP/CLI 与 camoufox examples 对比分析

## Goal

对比 Mimicry 现有 `sidecar/mcp_server.py` + `sidecar/cli.py` 与两个外部参考实现（`examples/external/camoufox-mcp`、`examples/external/camoufox-reverse-mcp`），识别能力 / 工具描述 / 架构 / LLM-facing UX 上的差距，给出可执行的改进方向。任务以**独立 worktree** 形式承载，便于在主开发线之外平行展开。

## What I already know

### Mimicry 现状

- `sidecar/mcp_server.py`（136 行）= 通用桥：遍历 `METHOD_REGISTRY` 把所有 RPC 方法（39+ 个 `browser.*` / `workflow.*` / `recording.*` / `camoufox.*`）自动暴露成 MCP tool。
  - 工具命名：`browser.navigate` → `browser_navigate`（首个 `_` 还原成 `.`）。
  - Schema 来源：`inspect.signature` + `METHOD_METADATA[name]["param_descriptions"]`。
  - 描述来源：metadata.description → 函数 docstring 首行 → fallback `Mimicry: <name>`。
  - 跳过 `shutdown` / `echo`。
- `sidecar/cli.py`（488 行）：argparse 多级子命令，UDS 连接 `daemon.py`，发 JSON-RPC 帧；自动拉起 daemon。子命令覆盖 daemon 生命周期、浏览器原子动作、workflow 调度、断点、`--mcp` 入口。
- 三入口共享同一 `browser/actions.py` adapter + `rpc/methods.py` 注册表（架构原则在 CLAUDE.md「Sidecar has three entry modes」一节）。

### `examples/external/camoufox-mcp`（TS, 295 行）

- **单 tool 设计**：只暴露一个 `browse(url, ...)`，参数极丰富（OS rotate、headless、humanize、proxy、block_webgl/images/webrtc、disable_coop、locale、viewport、firefox_user_prefs、exclude_addons…）。
- 每个参数 `z.describe(...)` 给出**面向 LLM 的语义说明**（"Use this when users ask to visit / browse / scrape…"）。
- **无状态**：每次调用现拉浏览器、回 HTML+可选 base64 截图、关闭。
- 没有 daemon、没有 session、没有 workflow，纯"发一个 URL 拿内容"。

### `examples/external/camoufox-reverse-mcp`（Python FastMCP, ~1000 行）

- **领域分组的 toolkit**：`tools/` 下按职责切分文件 — `navigation`, `script_analysis`, `hooking`, `network`, `storage`, `jsvmp`, `instrumentation`, `environment`, `verification`, `trace`, `cookie_analysis`, `debugging`, `fingerprint`。
- 用 `@mcp.tool()` 装饰器逐个注册，每个 tool 显式声明描述与签名。
- 自带一组 `hooks/*.js`（cookie、crypto、fetch/xhr、websocket、jsvmp、property_access、debugger_trap、font_fallback、runtime_probe）—— 这是 Mimicry 完全没有的 JS 逆向能力。
- 持久化单例 `BrowserManager`（与 Mimicry 多 session 的 `controller.py` 思路接近，但聚焦逆向：脚本搜索、属性访问追踪、JSVMP 字节码分析、网络捕获/查询）。

### 第一层观察到的 gap（待与用户对齐范围后细化）

1. **Tool 描述/语义贫乏**：Mimicry 的 MCP tool 描述来自 docstring 首行或 fallback；camoufox-mcp 每个参数都有面向 LLM 的"什么时候用"语义。LLM 选择正确性可能因此差异显著。
2. **Tool 粒度**：我们暴露 39+ 细粒度原子 tool；camoufox-mcp 一个 `browse` 抓全；reverse-mcp 中粒度 + 领域分组。LLM 在我们这看到的 surface 太大、且名字带 `browser_` / `workflow_` 前缀但缺 grouping description。
3. **能力缺口**：JS hooking、网络捕获/查询、property access trace、JSVMP 分析、storage 导出/导入、fingerprint/env check、verify_signer_offline——这些 reverse-mcp 提供，Mimicry 无对等接口。
4. **MCP 入口与 CLI 入口对称性**：CLI 提供了 `breakpoint`、`step`、`inject`、`pause/resume` 等调试链路；MCP 自动桥接也暴露了，但 LLM 视角的 description/工作流（什么时候 step）缺指引。
5. **错误返回格式**：Mimicry MCP 把异常包成 `{"error": str(e)}` 文本；examples 走 MCP 的 `isError: true` 协议字段，对 LLM 更友好。
6. **Schema 推断弱**：未注解参数全 fallback 成 `string`，复杂结构（`Optional[dict]`、proxy union、viewport object）无法表达 — `_build_tool_schema` 没读 `Optional`/`Union`/typing 泛型。
7. **CLI vs Example CLI**：camoufox-reverse-mcp 走 `pyproject.scripts` entry；我们 cli 自带 daemon 启停 + UDS 帧；本质不同（守护进程 vs 一次性进程）。是否需要对齐 `mimicry-mcp` 独立 entry？

## Assumptions (temporary)

- 用户希望产出**可执行的改进路线**而不仅是文档。
- 此任务在 `feat/mcp-cli-camoufox-gap-analysis` 分支 + `.trellis/worktrees/mcp-cli-camoufox-gap-analysis/` worktree 跑。
- 范围聚焦在 LLM-facing 接口（MCP tool 设计、CLI 命令 UX），不动 `browser/actions.py` 内部实现细节。

## Locked Scope (2026-05-01)

**LLM CLI 定位**：方便用户用 LLM 调试 workflow —— 读取录制的工作流、操作页面测试、编写工作流、调试/测试。**不做 JS 逆向**，因此 reverse-mcp 的 hook/JSVMP/property trace 工具集不进 Mimicry。

**Init script 存储**：进 workflow JSON（不进 DB / Profile schema），跟随 workflow 走。

## Long-term Execution Plan (phased)

### Phase 1 — P0 critical MCP bugs（先执行）
- 重写 `_build_tool_schema`：识别 `Optional` / `Union` / `list[X]` / `dict[K,V]` / `Literal` / `Enum` / 嵌套 dataclass/TypedDict / `**kwargs`（VAR_KEYWORD 跳过）。
- 修 `actions.py:327` `**match_hints` 泄漏成字符串属性的问题。
- 命名 round-trip：在 `rpc_method` 注册时建立双向 map（dotted ↔ tool name），淘汰 `replace("_", ".", 1)` heuristic（mcp_server.py:109-117）。
- `Server("mimicry", instructions=<整体说明>)`。

### Phase 2 — P0 描述补全
- 给 39 个 `@rpc_method` 全部补 `description=` + `param_descriptions=`，全部走 `t(...)` 风格的稳定英文（LLM-facing）。

### Phase 3 — 三个 Top 移植
- `network.capture / network.list / network.get`（抄 reverse-mcp `browser.py:226-292` + `tools/network.py`）。
- `console.list / console.clear`（环形缓冲，~30 LOC，`browser/controller.py` 内挂 `console` 事件）。
- workflow JSON 里支持 `init_scripts: [...]` 字段，浏览器启动 / 新页面时自动注入；动作 `browser.add_init_script` / `browser.list_init_scripts` 操作运行时副本。

### Phase 4 — CLI 清理
- 删 `sidecar/cli_legacy.py`（`export-report` 若仍需要 → 移到 `cli.py` 一个 `report` 子命令；否则一并删）。
- 修 `sidecar/dev_cli.py`：去掉 `dsl.rpc_methods` import，改用 `rpc/methods.py` 的 `METHOD_REGISTRY`；废弃 `dsl/` 全目录的 import 关系。
- 修 `--json` 一致性：`cmd_run` 流式 / `cmd_validate` 硬编码 / `cmd_breakpoint` 未知分支 / `main()` 末尾的 hack（cli.py 行号见 research/cli-ux.md）。

### Phase 5 — P1 错误协议 & FastMCP 评估（可选）
- 异常 → MCP `isError: true`。
- 评估迁 `FastMCP`（领域分组 + 自动 schema），与 Phase 1 重写后的桥比较 ROI 再决定。

## Open Questions

- 无（范围已锁定）

## Requirements (evolving)

- 产出 `research/` 下分主题的对比文档（mcp-tool-design / cli-ux / capability-gap）。
- 至少给出 3 类 gap 与每类的 2–3 候选改进方案 + 工作量评估。
- 任务以独立 worktree 承载，不污染当前 `feat/parallel-protocol-peer` 分支。

## Acceptance Criteria (evolving)

- [ ] worktree 创建、分支命名、SessionStart 注入 peer 块均符合 `parallel-development.md` 硬契约
- [ ] PRD 收敛到具体范围（产出物 + 边界）
- [ ] research/ 下至少包含：
  - [ ] `mcp-tool-design.md`（grouping、命名、description、schema 推断）
  - [ ] `capability-gap.md`（reverse-mcp 独有的 JS hook / 网络捕获 / 追踪能力清单）
  - [ ] `cli-ux.md`（与 example 对比，含或不含 CLI 视范围而定）
- [ ] 给出落地建议优先级 (P0/P1/P2)

## Definition of Done

- 上述 research 文档提交，PRD 引用
- 若有代码改动：lint / typecheck / 相关 pytest 通过；commit 用 `<type>(mcp-cli-camoufox-gap-analysis): <中文描述>`
- PR 直接对 `main`，CI 全栈通过

## Out of Scope (explicit)

- 真正实现 JS hooking / JSVMP / property trace（如有需要拆为后续独立任务）
- 改 `browser/actions.py` 的方法集合
- 修改 daemon 通信协议或 CLI 守护进程模型

## Technical Notes

- 关键文件：
  - `sidecar/mcp_server.py:32` `_build_tool_schema`（schema 推断弱点所在）
  - `sidecar/mcp_server.py:77` `_make_description`（描述退化点）
  - `sidecar/cli.py:353` `build_parser`（CLI 命令面）
  - `sidecar/rpc/methods.py:5` `METHOD_REGISTRY` / `METHOD_METADATA`
  - `sidecar/browser/actions.py`（39 个 `@rpc_method` 注册点）
- 参考：
  - `examples/external/camoufox-mcp/src/index.ts`（单 tool + 富 zod describe）
  - `examples/external/camoufox-reverse-mcp/src/camoufox_reverse_mcp/server.py`（领域分组 FastMCP）
  - `examples/external/camoufox-reverse-mcp/src/camoufox_reverse_mcp/tools/` & `hooks/`（能力清单）
- Worktree 入口：`docs/parallel-agents.md`、`.trellis/spec/cross-layer/parallel-development.md`

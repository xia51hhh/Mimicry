# Mimicry 工程现状审计 (2026-04-30)

> 这份档案是综合阶段的"对照基线"。给 5 个外部项目深度档案做参考用，避免锐评时凭印象。
> 所有断言都基于本仓库当时 `b7653bb` HEAD 的实际代码/配置，而不是 README/docs 的宣称。

## 1. 仓库与构建

### 1.1 总览

| 指标 | 现状 |
|---|---|
| 主语言 | TypeScript (前端) + Rust (Tauri 内核) + Python 3.10+ (sidecar) |
| 包管理器 | pnpm 10.12.1（`packageManager` 字段锁定）+ Cargo + pip (requirements.txt) |
| 桌面框架 | Tauri v2 |
| 浏览器引擎 | Camoufox + Playwright |
| LICENSE | **缺失**（README L246 自承认） |
| 国际化 | en / zh-CN（仅这两种） |

### 1.2 关键模块体量（行数）

```
sidecar/browser/actions.py      456    # RPC 方法注册表，~50 个 browser.* 方法
sidecar/engine/executor.py      762    # 工作流执行引擎
sidecar/cli.py                  488    # CLI 入口（25+ 子命令）
sidecar/daemon.py               392    # UDS daemon
sidecar/mcp_server.py           128    # MCP 自动映射 RPC → Tool
src-tauri/src/ipc/sidecar.rs    269    # sidecar 进程管理 + JSON-RPC 客户端
src-tauri/src/workflow_validator.rs  1917  # JSON Schema 校验器（庞大）
```

`workflow_validator.rs` 1917 行是个值得注意的体量信号——schema 校验做得很彻底，但也意味着维护成本高。

## 2. 架构亮点（值得保留 / 别动）

### 2.1 Sidecar 三入口模式共享 actions 层
- 入口分发：`sidecar/main.py:31-37` 通过 `--daemon` / `--mcp` argv 切换
- Tauri sidecar / Daemon / MCP 三种模式共用 `sidecar/browser/actions.py` + `sidecar/rpc/methods.py`
- 模式之间无代码重复，新加一个 RPC 方法三种入口都自动获得

### 2.2 MCP 自动映射 RPC → Tool（亮点 + 隐患）
- `sidecar/mcp_server.py:32-69` 用 `inspect.signature` 从函数签名生成 JSON Schema
- 优点：写一个 `@rpc_method` 装饰器就同时获得 RPC + MCP 两个入口
- **隐患**（写在锐评清单）:
  - 类型映射粗：`List[str]` / `Optional[X]` / `Union` / `Literal` 全部退化为 `string`（`mcp_server.py:56-57`）
  - 没有 description per param（只有方法级单行 docstring）
  - `name.replace(".", "_")` 然后回转有歧义 bug：`profile_list` 既可能是 `profile.list` 也可能是 `profile_list`（`mcp_server.py:101-109` 的 fallback 逻辑能解决但不优雅）

### 2.3 跨层 action map 单源
- `shared/action-map.json` 是真理来源
- `scripts/sync-action-map.py` 在 CI 之外手工跑（CI 没集成 ⚠️），校验 `sidecar/engine/action_map.py` 和 `src/types/action-map.ts` 一致

### 2.4 Rust 错误处理
- `src-tauri/src/error.rs` 用 `thiserror` 派生，自定义 `Serialize` 把错误序列化为前端友好 JSON：`{kind, message, display, diagnostics?}`
- 这种"错误模型对前端透明"的设计很干净，比直接 `to_string()` 强

### 2.5 Release 流程严格
- `release.yml:30-46` 校验 `package.json` / `tauri.conf.json` / `Cargo.toml` 三处版本与 tag 一致
- `release.yml:55-61` 强制要求 `CHANGELOG.md` 含 `## vX.Y.Z` 段
- PyInstaller 单文件 + tauri-action 双阶段构建
- 支持 Tauri 签名（`TAURI_SIGNING_PRIVATE_KEY` secret）

## 3. 工程实践短板（"锐评"清单）

### 3.1 CI 覆盖不全（严重）

`.github/workflows/pipeline.yml` 实际跑的检查：
- ✅ `pnpm typecheck`
- ✅ `cargo clippy -- -D warnings`
- ✅ `cargo test`
- ✅ `pytest -m "not e2e"`

**没跑**：
- ❌ `pnpm lint`（README L209 说 "frontend lint passes" 但 CI 不跑——本地通过 ≠ 持续保持）
- ❌ `pnpm build`（构建产物验证；只有 typecheck）
- ❌ `pnpm format:check` / Prettier
- ❌ Python lint（无 ruff/black/mypy 配置）
- ❌ `cargo fmt --check`
- ❌ `scripts/sync-action-map.py`（跨层契约校验脚本未在 CI 中跑！）
- ❌ E2E 测试（`-m "not e2e"` 显式排除，`tests/test_blocks_e2e.py` 在 CI 不跑）
- ❌ 构建产物 smoke test
- ❌ 覆盖率报告

### 3.2 测试规模与分布

| 层 | 测试文件数 | 评价 |
|---|---|---|
| 前端 | 1 个（`src/utils/__tests__/workflowSchema.test.ts`）| **极度不足**——Pinia stores、组件、composables 都没测 |
| Rust | ~7 个文件含 `#[test]`（transform/* + workflow_validator + integration test）| 集中在 transform 层和 schema 校验，commands 层、ipc 层、db 层无测试 |
| Python | ~10 个 `test_*.py`（executor / action_map / anti_detect / blocks_e2e / cli / condition_parser / env_check / google_search / rpc / dsl）| 算合格，但 e2e 不在 CI 跑等于失效 |

README L209 的 "currently no Rust unit tests" 是**过时信息**——实际有，但 commands/ipc/db 层缺。

### 3.3 安全 / Secrets

- `sidecar/fetch_browser.py:21` 读 `GITHUB_TOKEN` env，但全仓没有 `.env.example` / 统一 secret 管理约定
- 没有第三方 API key 管理设计（如果未来接 2captcha / OpenAI / 代理服务，目前无承载）
- `key/` 目录已 gitignore（Tauri 签名密钥）但目录存在容易误操作

### 3.4 依赖与发布

- 三处版本号（package.json / tauri.conf.json / Cargo.toml）靠 release CI 校验，但**开发期没有自动同步脚本**——容易在本地构建时不一致
- `pnpm-lock.yaml` 提交，但 `requirements.txt` 没有版本钉死（看 sidecar/pyproject.toml 用 `>=` 范围）——不可重现
- PyInstaller 嵌入 Camoufox 二进制方案 README L177 标 "groundwork"，未完整落地

### 3.5 文档/Spec 漂移

- `docs/architecture.md` 自标 "Partial"
- `docs/design/data-flow.md` / `debug-system.md` / `package-system.md` 标 "Planned"
- `docs/pseudocode-spec.md` 已被 ADR-001 弃用（DSL→JSON 直驱），但文件仍在
- README 与代码现实存在轻微漂移（前述测试覆盖、PyInstaller 完整度等）

### 3.6 功能层缺口（用户提到的 5 类对标方向）

| 方向 | Mimicry 现状 | 对位项目 |
|---|---|---|
| 验证码自动处理 | 无 | techinz/playwright-captcha |
| JS 逆向工具链（网络拦截、JSVMP 追踪、AST 插桩、Hook） | 无 | WhiteNightShadow/camoufox-reverse-mcp |
| 平台化（Dashboard / Queue / Remote MCP / 多租户） | 无 | saifyxpro/HeadlessX |
| Workflow → REST API 发布 | 无 | foxhui/WebAI2API |
| VNC / 浏览器画面回传 | 无（用 Tauri 内嵌 webview，不能远程） | foxhui/WebAI2API |
| Humanize（拟人鼠标 / 打字节奏） | 部分（依赖 Camoufox `humanize=True` 参数，没有自己的轨迹生成） | foxhui/WebAI2API、playwright-captcha 的 click solver |
| MCP 工具丰富度 | 52 个但偏 UI 操作 | camoufox-reverse-mcp 35+ 逆向工具、camoufox-mcp 单 mega-tool 设计 |

### 3.7 MCP 工具表面薄

`mcp_server.py` 自动映射看起来很省事，但：
- 没有给 LLM 足够的语义信息（每个 tool 只有方法名 docstring 一行）
- 参数没有 description（LLM 必须猜）
- 没有 examples（OpenAI tool spec / MCP 都支持示例）
- 错误响应只是 `{"error": str(e)}`——没有 error code / suggested next action

### 3.8 已知功能债（对照 CHANGELOG / docs）

- 执行日志持久化：标 Planned（`docs/architecture.md` L168）
- 完整 PyInstaller 嵌入：标 Partial
- 高级 workflow 语义（边-句柄-分支-Join-loop port 的执行语义）：未完整落地
- 选择器自愈：仍是规划方向（README Roadmap）
- Package 子工作流系统：标 Planned
- Workflow schema migration helpers：标 Planned

## 4. 综合阶段使用提示

写"锐评 Mimicry 短板"时：
- 第 3.1（CI 覆盖）和 3.2（测试规模）是**工程根基**问题，应放在最前
- 第 3.6 是用户提的 5 个对标项目能直接补的能力，对应到具体 borrow list
- 第 3.7（MCP schema 薄）是和 camoufox-mcp / camoufox-reverse-mcp 直接对位的"工程升级点"
- 第 3.8 是 README/docs 自承认的债，列出来但不算"锐评"——README 已诚实标注 Partial/Planned

写路线图时：
- "短期"应该聚焦于**填 CI 漏洞 + 第 3.6 里 priority=S 的功能**
- "中期"聚焦平台化雏形（Remote MCP、多窗口编排、Humanize 模块）
- "长期"聚焦完整平台化（Queue、Workflow→API、VNC）

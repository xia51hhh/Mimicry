# 外部生态开源项目调研与启示 (2026-04-30)

> **本文档是综合稿**，基于以下深度调研档案：
> - `.trellis/tasks/04-30-04-30-research-external-projects/research/00-mimicry-engineering-audit.md`
> - `01-camoufox-mcp.md` / `02-headlessx.md` / `03-camoufox-reverse-mcp.md` / `04-playwright-captcha.md` / `05-webai2api.md`
>
> 调研对象 5 个 GitHub 项目都已克隆到 `examples/external/`（gitignored）。
> 替代旧版 5k 字初稿，目标是给团队提供一份**工程化决策依据**——不止"借鉴清单"，还包括对 Mimicry 自身工程短板的诚实评估。

---

## 1. 对标矩阵（一图流）

### 1.1 项目定位与体量

| 项目 | 定位 | 体量 | License | 维护 | 与 Mimicry 重叠度 |
|---|---|---|---|---|---|
| whit3rabbit/camoufox-mcp | 标准 Camoufox MCP（单 mega-tool） | 295 行单文件 TS | MIT | 半年没动但稳定 | ★★ |
| saifyxpro/HeadlessX | 自托管多租户抓取平台 | Monorepo（API+Web+Go+Python） | MIT | 活跃 | ★★★ |
| WhiteNightShadow/camoufox-reverse-mcp | JS 逆向工程专用 MCP | ~5k Python+JS | MIT | 活跃 | ★★ |
| techinz/playwright-captcha | Captcha 求解库 | ~2.3k Python | MIT/Apache⚠️ | 活跃 | ★★★ |
| foxhui/WebAI2API | Web AI 转 OpenAI API | ~12k+ JS+Vue | MIT | 活跃 | ★★ |

### 1.2 功能覆盖矩阵

| 功能维度 | camoufox-mcp | HeadlessX | reverse-mcp | playwright-captcha | WebAI2API | **Mimicry 现状** |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Camoufox 集成 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| MCP 服务器 (stdio) | ✅ | ✅ | ✅ | — | — | ✅ |
| MCP 远程 (HTTP) | — | ✅ Streamable HTTP | — | — | — | ❌ |
| 工具自动映射 | — | — | — | — | — | ✅ (52 个) |
| MCP schema 描述质量 | ★★★ Zod+describe | ★★ + annotations | ★★ docstring | — | — | ★ inspect.signature |
| 反指纹参数全暴露 | ★★★ 19 个 | ★ 部分 | ★ | — | ★★ | ★★ 部分 |
| 拟人鼠标 | ✅ Camoufox humanize | ✅ Camoufox humanize | ✅ Camoufox humanize | — | ✅ ghost-cursor + bias | ★ Camoufox humanize |
| 拟人打字 | — | — | — | — | ✅ 5%错字+长文本假打 | ❌ |
| 网络/XHR Hook | — | ✅ DOM 检测 | ✅ XHR/fetch/WS Hook 完整 | — | — | ❌ |
| JS 函数 Hook | — | — | ✅ intercept+trace 统一接口 | — | — | ❌ |
| AST 重写 | — | — | ✅ esprima | — | — | ❌ |
| Property Trace（C++ 引擎） | — | — | ✅ 自定义 Camoufox build | — | — | ❌ |
| Cloudflare 检测 | — | ✅ DOM 启发式 typed error | — | ✅ 完整 | ✅ shadowRootUnl | ❌ |
| Cloudflare 自动解 | — | — | — | ✅ Click+API | ✅ Click | ❌ |
| reCAPTCHA 自动解 | — | ✅ 自托管 ONNX YOLO | — | ✅ 2captcha+tencaptcha | — | ❌ |
| Workflow / Block 系统 | — | 算子分文件 | tool 按域分文件 | 注册表式 | adapter 注册表 | ✅ JSON 节点图 |
| 并发 Worker 池 | — | ✅ BullMQ | — | — | ✅ 多策略 + 故障转移 | ★ SessionManager |
| 任务队列 | — | ✅ BullMQ + Redis | — | — | ✅ 内存队列 | ❌ |
| Worker 故障转移 | — | ✅ 重试 3 次 | — | ✅ retry/delay | ✅ failover 策略 | ❌ |
| Profile 隔离（per-worker proxy） | — | ✅ | — | — | ✅ | ✅ profile 系统 |
| 持久化（数据库） | — | ✅ Postgres | 文件 | — | ✅ SQLite | ✅ SQLite |
| API 鉴权 | — | ✅ API key 哈希 | — | — | ✅ token | — |
| Web Dashboard | — | ✅ Next.js | — | — | ✅ Vue 3 | ❌（Tauri 桌面） |
| VNC 画面回传 | — | — | — | — | ✅ x11vnc | ❌ |
| HTTP API gateway | — | ✅ REST + MCP | — | — | ✅ OpenAI 兼容 | ❌ |
| SSE 流式响应 | — | ✅ | — | — | ✅ | ❌ |
| Workflow→API 发布 | — | ✅ scrape API | — | — | ✅ adapter 模式 | ❌ |
| 容器部署 | ✅ Docker | ✅ docker-compose | — | — | ✅ docker-compose | ❌ |
| Supervisor 看门狗 | ✅ 进程级 fail-fast | ✅ Worker 重连 | — | — | ✅ 完整 supervisor | ★ Tauri 父进程管 |

> 图例：✅ 完整支持 / ★ 部分 / — 不涉及 / ❌ Mimicry 缺失

### 1.3 工程基础设施对比

| 工程项 | camoufox-mcp | HeadlessX | reverse-mcp | playwright-captcha | WebAI2API | **Mimicry** |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| 跑 lint | ESLint | Biome（更先进） | — | — | — | ESLint+Prettier（**未在 CI 跑**） |
| 跑 typecheck | tsc | tsc | — | — | — | ✅ |
| 跑 test | Python stdio 客户端（CI 加 \|\|true） | 未深扫 | pytest（6 文件） | pytest+cov | ❌ 无 | 前端 1 个、Rust 7 个、Python ~10 个 |
| Build CI | ✅ matrix Node 20/22 | — | — | — | — | ✅ |
| Cross-layer 校验 | — | — | — | — | — | sync-action-map.py（**未在 CI 跑**） |
| 死代码扫描 | — | knip | — | — | — | ❌ |
| Docker 镜像 | ✅ multi-arch | ✅ 4 个 | — | — | ✅ + x11vnc | ❌ |
| 自动 release | ✅ npm + Docker Hub + GHCR | — | — | — | ✅ Docker Hub | ✅ GitHub Releases |
| 文档双语 | — | — | ✅ 中英 | — | ✅ 中英 | — |
| Playbook（写给 LLM） | — | — | ✅ JSVMP_PLAYBOOK.md | — | — | ❌ |

---

## 2. 工程实践亮点提炼（其他项目做对、Mimicry 没做的）

### 2.1 MCP Schema 工程（最高 ROI）

**问题**：Mimicry 的 `sidecar/mcp_server.py:32-69` 用 `inspect.signature` 自动从 Python 函数签名生成 MCP 工具 schema。每个工具只有：
- 一行 docstring 当 description
- 参数 type 退化映射（List/Optional/Union 全部变 string）
- 参数级**无 description**

**对照**：
- **camoufox-mcp** 用 Zod chain 给每个参数写 `.describe(...)`，包含"用户什么时候会想用这个"的自然语言提示
- **HeadlessX** 给工具加 `READ_ONLY_TOOL_ANNOTATIONS`（MCP hints），告诉 LLM 哪些是只读 / 破坏性
- **camoufox-reverse-mcp** 用 `mode` 参数把"intercept"和"trace"合并成一个 tool，但有完整 docstring

**代价**：Mimicry MCP 工具语义信息少 → LLM 调用准确率受影响 → 需要回到 docs/llm-interactive-guide.md 用 examples 补救

### 2.2 typed Error / 结构化错误返回

**问题**：Mimicry sidecar 错误返回基本是 `{"error": str(e)}` 或抛 Python exception。**Rust 那边 `error.rs` 已经做得很好**（`{kind, message, display, diagnostics}`），但 sidecar Python 端没对齐。

**对照**：
- **HeadlessX** 有 `CloudflareChallengeError extends Error` 携带 `code='CLOUDFLARE_CHALLENGE_DETECTED'` + 结构化 detail
- **playwright-captcha** 有 `CaptchaSolvingError` / `CaptchaDetectionError` / `CaptchaApplyingError`
- **WebAI2API** 有 `server/errors.js:1-185` 完整 ERROR_CODES 枚举

### 2.3 拟人交互（不是只有 Camoufox `humanize=True`）

**问题**：Mimicry 当前依赖 Camoufox 自带的 `humanize`（鼠标层），**输入层**完全是 `page.keyboard.type(text)` 一次性。

**对照（WebAI2API 最强）**：
- 字符延迟 `random(30, 100)` ms
- **5% 概率敲错字 + backspace**
- 长文本切换为"假打 3-8 字符 → 停顿 → 全选删除 → execCommand('insertText') 粘贴"
- 6 种 click bias（input/button/random/4 角）
- ghost-cursor Bezier 鼠标轨迹
- Shift+Enter 处理换行

### 2.4 Cloudflare / Captcha 处理

Mimicry 完全没有，**playwright-captcha 是直接补缺**的库（License MIT）。

但**重要见识**：
- **HeadlessX** 选择"先检测、不自动解，告诉调用方让它决定"——比闷头解 captcha 安全得多
- **playwright-captcha** 提供"Click 优先（不花钱），失败降级 API（2captcha）"两段式
- **WebAI2API** 用了 Camoufox 独有的 `shadowRootUnl` 属性穿透 closed shadow DOM（playwright-captcha 用标准搜索）

应该的策略：**先做检测节点，再做 Click solver，API solver 作为可选**。

### 2.5 远程 MCP（Streamable HTTP transport）

**问题**：Mimicry MCP 只支持 stdio。一旦想做"多设备/多用户共用一个 Mimicry 实例"，必须切到 HTTP MCP。

**对照**：HeadlessX 用 `StreamableHTTPServerTransport`，每个 HTTP 请求创建独立 McpServer + 鉴权 → 支持远程。

**风险**：客户端兼容性。Cursor / Claude Desktop / Cline 当前主流都仍只支持 stdio，HTTP transport 还在普及中。

### 2.6 跨层契约 CI 校验

**问题**：Mimicry `scripts/sync-action-map.py` 校验 `shared/action-map.json` ↔ `sidecar/engine/action_map.py` ↔ `src/types/action-map.ts` 三处一致——**但 `.github/workflows/pipeline.yml` 不跑这个脚本**。本地容易漂移。

**对照**：所有 5 个项目都没有这种"跨层契约"，因为它们要么单层（camoufox-mcp）要么 monorepo 内同语言（HeadlessX）。**这是 Mimicry 三层架构特有的债**——必须自己解决。

### 2.7 Worker 池 / 调度策略

**问题**：Mimicry SessionManager 是一对一，没有"并发 N 个 worker"概念。

**对照**：
- **HeadlessX** BullMQ + 进程级 Worker
- **WebAI2API** PoolManager + 3 种策略（least_busy/round_robin/random）+ failover + 浏览器共享

**判断**：**Mimicry 不应该现在做**——单用户桌面应用没有"并发跑 N 个 worker"刚需。但应预留接口，等"批量执行同一 workflow"成为需求时再做。

### 2.8 Playbook / 双语 / 客户端接入指南

- **camoufox-reverse-mcp** 有 `JSVMP_PLAYBOOK.md`——专门写给 LLM 的"如何用这套工具做 JSVMP 分析"操作书
- **camoufox-mcp** README 列了 6 种 MCP 客户端的接入配置（Claude Desktop / Cursor / VS Code Continue / Cline / Windsurf / Claude Code）

Mimicry 已有 `docs/llm-interactive-guide.md`，但**缺各 MCP 客户端的"5 行 JSON 配置就能用"快速接入清单**。

---

## 3. 锐评：Mimicry 工程现在的硬短板

> 详细审计见 `research/00-mimicry-engineering-audit.md`，本节是结论性陈述。

### 3.1 CI 漏洞（P0）

`.github/workflows/pipeline.yml` 实际只跑：
- `pnpm typecheck`、`cargo clippy -D warnings`、`cargo test`、`pytest -m "not e2e"`

**没跑**：
- ❌ `pnpm lint`（README 自称通过但 CI 不强制 → 持续漂移）
- ❌ `pnpm build`（typecheck 通过 ≠ 构建通过）
- ❌ `pnpm format:check`
- ❌ Python lint（无 ruff/black/mypy）
- ❌ `cargo fmt --check`
- ❌ **`scripts/sync-action-map.py`（跨层契约校验！）**
- ❌ E2E 测试（`-m "not e2e"` 排除）
- ❌ 构建产物 smoke test
- ❌ 覆盖率

camoufox-mcp 的 CI 在测试用 `|| true`（测失败也发布）——这种是别人的债。Mimicry 自己的债是上面那 9 项。

### 3.2 测试规模严重失衡（P1）

| 层 | 测试 | 评价 |
|---|---|---|
| 前端 | **1 个文件** (`workflowSchema.test.ts`) | Pinia 4 个 store 全 0 测试，组件 0 测试，composables 0 测试 |
| Rust | 7 文件 | 集中在 transform 层，commands/ipc/db **全 0 测试** |
| Python | ~10 文件 | 算合格，但 e2e 在 CI 不跑等于失效 |

README L209 说 "currently no Rust unit tests" 是过时信息——实际有，但缺命令层。

### 3.3 MCP 表面薄（P1）

参考 2.1。Mimicry 自动映射 52 个 tool 看起来是亮点，实际是**每个 tool 信息量都很少**。Cursor / Claude Desktop 用户用起来会"猜参数"。

### 3.4 拟人交互停留在 Camoufox 自带（P2）

参考 2.3。`browser.type` 直接 `page.keyboard.type` 一次性灌字符——容易被反爬识别。

### 3.5 无验证码处理（P1，但易补）

Mimicry 当前 ROADMAP 没列 captcha——但 5 个对标项目里 2 个核心做这个，1 个把它当核心 service。**这是 Mimicry 的产品定位短板，不只是技术短板**。

### 3.6 文档与代码漂移（P2）

- `docs/architecture.md` / `data-flow.md` / `debug-system.md` / `package-system.md` 自标 Partial / Planned
- `docs/pseudocode-spec.md` ADR-001 已弃用但文件仍在
- README 关于测试和 PyInstaller 描述与实际有偏差

### 3.7 LICENSE 缺失（P2）

README L246 自承认。在 OSS 社区这是阻塞他人使用的硬伤。所有 5 个对标项目都明确 MIT/Apache。

### 3.8 三处版本号无开发期同步（P2）

`package.json` / `tauri.conf.json` / `Cargo.toml` 必须一致。release.yml 校验，但**开发期改版本要手动改三处**。容易在本地 build 时不一致。

### 3.9 secrets 体系缺失（P2）

未来集成 captcha API、远程 MCP 鉴权、第三方 LLM API 时，没有 `.env.example` / 统一管理约定。proxy 密码当前明文存 SQLite（推断，需验证）。

### 3.10 远程化路径完全没规划（P2，长期）

stdio MCP / Tauri 桌面 / 单进程 sidecar——三层都是"本地优先"。短期内没问题（这是产品定位），但任何"远程节点"愿景都没工程基础。

---

## 4. 路线建议

### 4.1 短期（0-1 个月，工程债清理 + 易补功能）

**目标**：补 CI 漏洞、补 captcha/反检测易补缺口、做 MCP schema 升级。

| # | 任务 | 模块 | 估时 | 依据档案 |
|---|---|---|---|---|
| S1 | CI 加 `pnpm lint` / `pnpm build` / `pnpm format:check` | pipeline.yml | 0.5d | 2.1, 3.1 |
| S2 | CI 加 `scripts/sync-action-map.py` | pipeline.yml | 0.5d | 2.6 |
| S3 | CI 加 `cargo fmt --check` + Python ruff | pipeline.yml | 0.5d | 3.1 |
| S4 | Cloudflare 检测 → typed error/notification | sidecar/browser/actions.py 加 `cloudflare.detect` | 1d | HeadlessX P3, captcha P2 |
| S5 | MCP schema 升级：`@rpc_method` 接受 `param_descriptions` 字典 | sidecar/rpc/methods.py + mcp_server.py | 2d | camoufox-mcp P1 |
| S6 | Camoufox 完整参数暴露（`disable_coop`、`block_webgl`、`block_images`、`exclude_addons`、`firefox_user_prefs`、`args`、`window`） | sidecar/browser/controller.py + actions.py `browser.launch` | 1d | camoufox-mcp Borrow #2 |
| S7 | typed errors（CaptchaSolvingError 等）+ ERROR_CODES 枚举 | sidecar/rpc/errors.py | 1d | playwright-captcha P5, WebAI2API P3 |
| S8 | 给 README 加 LICENSE（MIT 推荐——和所有对标项目一致） | LICENSE 文件 | 0.5d | 3.7 |
| S9 | 写 MCP 客户端接入指南（Cursor/Claude Desktop/Cline/Windsurf） | docs/llm-interactive-guide.md 扩展 | 1d | camoufox-mcp 文档实践 |
| S10 | Captcha Block MVP：集成 playwright-captcha 的 Click solver | sidecar 新增 `sidecar/captcha/`，封装 `captcha.solve_cloudflare` action | 3d | playwright-captcha P1+P2 |

**S 阶段产出**：
- CI 完整覆盖（漂移 0 容忍）
- MCP 工具变得"LLM 友好"
- 验证码处理 MVP（Click solver 路径）
- 接入文档完整（运营 / 推广基础）

### 4.2 中期（1-3 个月，能力扩展 + 工程提升）

**目标**：把 Mimicry MCP 从"UI 操作"升级到"半逆向工具"；填补拟人交互缺口；补测试覆盖率。

| # | 任务 | 模块 | 估时 | 依据档案 |
|---|---|---|---|---|
| M1 | 拟人打字（5% 错字 + 长文本假打粘贴 + 字符间停顿） | sidecar/browser/actions.py `browser_type` 增加 humanize 参数 | 3d | WebAI2API P1 |
| M2 | 6 种 click bias | `browser.click` 增加 bias 参数 | 1d | WebAI2API P2 |
| M3 | 网络抓包 + XHR/fetch hook | sidecar 新增 `network.start_capture` / `network.list_requests` action 套件 | 3d | reverse-mcp P1+P2 |
| M4 | 函数级 Hook（intercept + trace 统一接口） | sidecar 新增 `script.hook` action | 3d | reverse-mcp P3 |
| M5 | 持久化 hook（context.add_init_script + navigation re-inject） | sidecar/browser/controller.py 增强 | 3d | reverse-mcp P5 |
| M6 | 前端测试覆盖：Pinia 4 个 store + 关键组件 | src/stores 加 `__tests__` | 5d | 3.2 |
| M7 | Rust commands 层 / ipc 层测试 | src-tauri/src 加 #[cfg(test)] | 4d | 3.2 |
| M8 | Captcha API solver 接入（2captcha 可选） | 扩展 `sidecar/captcha/` | 2d | playwright-captcha Borrow #8 |
| M9 | knip 死代码扫描 + Biome 评估（替代 ESLint+Prettier） | toolchain | 2d | HeadlessX P5/P6 |
| M10 | ADR-006 Package 系统 v0：把 `cloudflare.detect + click + retry` 作为内置 Package | engine 层 | 5d | HeadlessX Operator pattern |
| M11 | 三处版本号开发期同步脚本 | scripts/sync-version.py | 1d | 3.8 |
| M12 | proxy 密码 at-rest 加密（如果验证后确实明文） | src-tauri/src/db | 2d | 3.9 / HeadlessX `CredentialEncryptionKey` |

**M 阶段产出**：
- MCP 能力翻倍（网络拦截、Hook、AST 友好）
- 拟人交互对标 WebAI2API 水平
- 测试覆盖率从极薄变为合格
- Package 系统从设计变实现

### 4.3 长期（3-6 个月，平台化 + 远程化方向探索）

**目标**：评估 Mimicry 是否要从"桌面应用"扩展到"可远程协作的工作流平台"。**这一阶段所有任务都需要先做用户访谈确认产品方向。**

| # | 任务 | 模块 | 估时 | 依据档案 | 前置 |
|---|---|---|---|---|---|
| L1 | sidecar 新增 HTTP server 模式（与 stdio/daemon/MCP 并列第 4 模式） | sidecar/http_server.py | 5d | WebAI2API + HeadlessX | 用户需求确认 |
| L2 | Streamable HTTP MCP transport | sidecar/mcp_http_server.py | 5d | HeadlessX P1 | L1 |
| L3 | API key 鉴权 + 哈希存储 | sidecar/auth.py | 3d | HeadlessX | L1 |
| L4 | Workflow → REST API 发布功能（用户在 UI 标记某个 workflow 为 "published"，自动暴露 endpoint） | Tauri command + sidecar 路由 | 7d | WebAI2API | L1+L3 |
| L5 | sidecar Worker 池调度（least_busy 等策略） | sidecar/pool/ | 7d | WebAI2API + HeadlessX | 批跑需求确认 |
| L6 | Supervisor + IPC 重启 | sidecar/daemon.py 增强 | 3d | WebAI2API P5 | 可用性需求 |
| L7 | x11vnc / VNC 画面回传（如果走 Docker server 模式） | infra/Dockerfile + 文档 | 5d | WebAI2API | L1 + 远程化方向确认 |
| L8 | 任务队列引擎（轻量内存队列，**不必上 Redis**） | sidecar | 5d | HeadlessX | L5 |
| L9 | Captcha 启发式增强：reCAPTCHA v2/v3 通过外部 API 解 | 扩展 captcha 模块 | 5d | playwright-captcha | M8 经验 |
| L10 | E2E 测试在 CI 跑（专门 stage / nightly） | pipeline.yml | 3d | 3.2 |

**L 阶段判断**：
- L1-L4 如果方向确认就做（Workflow→API 是 README Roadmap 已经提的方向）
- L5-L8 仅当真出现"批跑 / 多用户共享" 实际需求才做（不要过度工程）
- L7 仅当 Docker server 模式上线才做

---

## 5. 反向决策清单（明确不做）

下表是从 5 个调研项目里**明确判断"不该借"** 的内容，写下来防止后续讨论时重复评估。

| 不做的事 | 来源项目 | 不做的理由 |
|---|---|---|
| 自托管 ONNX YOLO captcha 模型 | HeadlessX | 工程量过大（700 行 + 模型分发），优先用 Click solver / 第三方 API |
| Postgres + Redis 强依赖 | HeadlessX | 桌面应用 SQLite 已够 |
| Next.js 浏览器访问的 Web Dashboard | HeadlessX / WebAI2API | Mimicry UI 是 Tauri，方向不一致 |
| Multi-app monorepo + Nx | HeadlessX | 已有 Tauri/Vue/Python 三层，再叠 Nx 是过度工程 |
| 自定义 Camoufox C++ 编译（PropertyTracer） | reverse-mcp | 维护成本极高，应等上游接 PR |
| JSVMP 专项工具集 | reverse-mcp | 用户面太窄，定位飘移 |
| AST 全量插桩 | reverse-mcp | 调试性质太强，普通用户用不到 |
| `tencaptcha` 内置子模块 | playwright-captcha | 不绑定特定打码服务 |
| 17 个 AI 网页 adapter | WebAI2API | 不该绑定具体 AI 站点 |
| OpenAI Chat Completions 协议适配 | WebAI2API | Mimicry 不是 LLM 网关 |
| `shadowRootUnl` 依赖 | WebAI2API | Camoufox-JS 非标属性，Python Camoufox 可能没有 |
| launch-per-call 浏览器生命周期 | camoufox-mcp | Mimicry SessionManager 持久化是更好的设计 |
| 依赖 fork 的 `2captcha-python-async` 包 | playwright-captcha | 不让 Mimicry 依赖非主流 fork |
| `FrameworkType` 多 framework shim | playwright-captcha | Mimicry 锁定 Camoufox |

---

## 6. 关键风险与开放问题

集中列出所有调研档案里"需要进一步验证"的问题，统一汇总：

1. **playwright-captcha 的 license 矛盾**：`pyproject.toml` 写 MIT，`LICENSE` 文件是 Apache 2.0 文本——集成前提 GH issue 澄清
2. **Camoufox `add_init_script` workaround**：playwright-captcha 自带 addon 解决 main world 不可达；**Mimicry 自己的 `BrowserController._init_scripts` 是否也踩到了同样的 main world 问题？需要 sidecar 实测**
3. **Streamable HTTP MCP transport 的客户端兼容性**：Cursor / Claude Desktop / Cline 当前主流支持 stdio，HTTP 还在普及；做远程 MCP 前要先调查覆盖率
4. **Mimicry SQLite proxy 字段是否明文**：`profiles` 表 schema 需要交叉检查；如果是，做 at-rest 加密的优先级要提前
5. **三处版本号一致性**：开发期是否真的频繁出现不一致？需统计
6. **`shadowRootUnl` 是 Camoufox 哪个版本引入的、Python Camoufox 是否也有**：影响 Mimicry 走哪种 captcha click 实现
7. **Captcha 测试在 CI 怎么跑**：所有 captcha 项目都没解决；Mimicry 集成时同样要面对
8. **Worker 池 + 浏览器共享是否真省资源**：WebAI2API 没有 benchmark；Mimicry 决定是否走 L5 之前要做对照试验
9. **MCP 工具自动映射 vs 手工注册的边界**：reverse-mcp 完全手工，camoufox-mcp 1 个 mega-tool，Mimicry 完全自动——三种都有得失，Mimicry 的中间路线最难调

---

## 7. 文档维护说明

- 本文 2026-04-30 撰写，对应 git HEAD `b7653bb` 时的代码现状
- 5 个深度档案 + Mimicry 工程审计 + 5 个外部仓库克隆均在任务目录下，**任务归档时仓库克隆请保留 examples/external/**（已 gitignore，不会污染 commit）
- 路线建议里的优先级 P0-P2 / S/M/L 仅为本调研结论，**最终排期需要产品决策**

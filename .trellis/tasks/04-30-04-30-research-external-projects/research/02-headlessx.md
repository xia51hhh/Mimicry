# saifyxpro/HeadlessX

## TL;DR

一个**生产级、Postgres+Redis+BullMQ 驱动**的自托管浏览器抓取平台，monorepo 包含 4 个 app（api / web / Go HTML→Markdown 服务 / Python YT 引擎）。比 Mimicry 大一个数量级——它是"平台"，Mimicry 是"桌面工具"。最值得借鉴的是**API Key + BullMQ Queue + Streamable HTTP MCP** 这套**远程化**设计；以及它**自训练 YOLO ONNX 模型解 reCAPTCHA**这种重资产路线（不是 Mimicry 该走的）。

## Repo Metadata

| | |
|---|---|
| URL | https://github.com/saifyxpro/HeadlessX |
| 最新 commit | `af2bd4b` (2026-03-25)，最近一个月内 |
| 主语言 | TypeScript（API + Web 主体） + Go (HTML→Markdown 服务) + Python (YT 引擎) |
| License | MIT |
| 体量 | API src 大约 1.5k+ 行核心 services，加 web/yt-engine/go-md-service、模型脚本，总规模 monorepo 级 |
| 维护活跃度 | 活跃 |
| 包管理 | pnpm + Nx (monorepo 编排) |
| 工程基础 | Biome (lint+format) + knip (死代码) + mise.toml (toolchain) + Prisma + BullMQ |

## Positioning

面向需要**自托管、API 化、可大规模扫站**的开发者：把 Playwright/Camoufox 服务封装成 REST API + Remote MCP 节点，前面挂 Next.js dashboard，后面挂 Postgres + Redis 队列。多个 LLM Agent 可以同时连同一个 HeadlessX 实例并发派任务。

这是**"中心化平台"**路线，与 Mimicry 当前的"本地优先桌面应用"是互补的两端。

## Tech Stack & Dependencies

| Layer | Tech |
|---|---|
| Monorepo 编排 | Nx |
| 包管理 | pnpm 10.32.1 |
| API 框架 | Express (TS) |
| ORM | Prisma + Postgres |
| 队列 | BullMQ + Redis (`services/queue/`) |
| 浏览器 | playwright-core（`packages/headfox-js` 是它们自己 fork 的 Camoufox-JS） |
| MCP | `@modelcontextprotocol/sdk` 的 **`StreamableHTTPServerTransport`**（HTTP transport，非 stdio） |
| Web | Next.js + Tailwind + MDX |
| AI 模块 | `@xenova/transformers` + `onnxruntime-web` + `sharp`（图像）— 自托管视觉模型 |
| Captcha | 自有 ONNX YOLO 模型 + 分类模型，本地推理 |
| 子服务 | Go: HTML→Markdown 转换；Python (uv): YouTube 引擎 |
| 镜像 | 多 Dockerfile（api/web/yt-engine） + docker-compose |

## Architecture

```
┌──────────────────────┐      ┌─────────────────────┐
│  Next.js Dashboard   │      │   LLM Agent / API   │
│  (apps/web)          │      │   (HTTP / MCP)       │
└──────────┬───────────┘      └─────────┬───────────┘
           │                            │
           ▼                            ▼
┌─────────────────────────────────────────────────┐
│  Express API (apps/api)  + StreamableHTTP MCP   │
│  ─ controllers / routes (v1, v2, mcp, scrape,   │
│    ai, jobs, dashboard, playground, proxy …)    │
└──────────┬───────────────────┬──────────────────┘
           │                   │
           ▼                   ▼
   ┌──────────────┐    ┌──────────────────┐
   │ Postgres     │    │ Redis + BullMQ   │
   │ (Prisma)     │    │ (Queue + Worker) │
   └──────────────┘    └──────────┬───────┘
                                  │
                                  ▼
                       ┌──────────────────────┐
                       │ Browser Pool         │
                       │ (headfox-js + pw)    │
                       └────┬───────┬──────┬──┘
                            │       │      │
                            ▼       ▼      ▼
                       Cloudflare  Captcha  YT/Markdown
                       Detector    Solver   Subservices
                                   (ONNX)
```

### 入口
- API: `apps/api/src/server_entry.ts` (40 行)
- Worker: `apps/api/src/worker_entry.ts` (21 行) — 独立进程跑 BullMQ
- 这种 **API 进程 与 Worker 进程分离**是经典的 Web/Worker 分层，比 sidecar 单进程更可扩展

### 核心 services（`apps/api/src/services/`）
- `JobManager.ts` (305 行) — 跨进程作业管理，配合 cancellationChannel
- `queue/QueueWorker.ts` (401 行) — BullMQ Worker 进程
- `queue/QueueJobService.ts` (416 行) — Worker 作业逻辑
- `scrape/StreamingScraperService.ts`、`scrape/WebsiteCrawlService.ts`、`scrape/CloudflareChallengeService.ts`
- `CaptchaSolverService.ts` (700 行) — ONNX 视觉模型自解
- `auth/ApiKeyAuthService` — API Key 哈希存储与 last_used_at 跟踪

## Key Code Patterns

### Pattern 1: Streamable HTTP MCP（远程 MCP）

- 位置：`apps/api/src/mcp/server.ts:19-48`
- 做法：每个 HTTP 请求创建一个新的 `McpServer` + `StreamableHTTPServerTransport`，调用完关闭。鉴权通过 `resolveMcpApiKey(req)`：

  ```typescript
  const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: undefined,
  });
  await server.connect(transport);
  await transport.handleRequest(req, res, req.body);
  ```

- 为什么有意思：**这是 MCP 协议的 HTTP transport 用法**。Mimicry 当前只用 stdio MCP，要做远程节点必须切到这条路径。`sessionIdGenerator: undefined` 表示**无状态 MCP 调用**，每次请求独立。
- 对 Mimicry：直接可参考。要把 Mimicry sidecar 远程化时，这是技术原型。

### Pattern 2: BullMQ Worker + 取消通道（pub/sub 模式）

- 位置：`apps/api/src/services/queue/QueueWorker.ts:55-100`
- 关键设计：
  - `probeRedisConnection()` 启动前探测 Redis；不可用则 `scheduleRetry()`，**不让 Worker 进程退出**
  - 通过 `queueCancellationChannel.subscribe(jobId => jobManager.cancelJob(jobId))` —— 把作业取消做成 **Redis pub/sub 消息**而不是 BullMQ 的 `removeJob`，这样可以中断**正在执行**的作业
  - `concurrency: queueConfig.workerConcurrency` 默认 2（环境变量可调），即一个 worker 进程最多同时跑 2 个浏览器
- 对 Mimicry：Mimicry 当前没有队列。如果要做"批量执行同一个 workflow N 次"，可以借鉴这个 pattern——但应该**先看 Mimicry 是否真需要分布式队列**，否则就是过度工程。

### Pattern 3: Cloudflare Challenge 启发式检测（不是解，是识别）

- 位置：`apps/api/src/services/scrape/CloudflareChallengeService.ts:42-90`
- 做法：在页面上 evaluate 检查 10 个 DOM 信号（Turnstile iframe、`/cdn-cgi/challenge-platform` form action、"Just a moment"、"Ray ID" 文本等），按命中数评 `low/medium/high` 置信度，命中即抛 `CloudflareChallengeError` 让上层决定如何处理。
- 为什么有意思：**它选择"先检测，让用户决定怎么办"，而不是"自动解"**。这种 detect-only 模式风险低、可解释性强。
- 对 Mimicry：直接借——Mimicry 加一个 `cloudflare.detect` action，返回结构化结果（type / confidence / indicators），让 workflow 决定下一步（switch profile? abort? wait?）。比闷头解 captcha 安全得多。

### Pattern 4: ONNX 自托管视觉 Captcha 求解器（重资产）

- 位置：`apps/api/src/services/CaptchaSolverService.ts:1-75`
- 关键：用 `@xenova/transformers` + `onnxruntime-web` 加载本地 `recaptcha_classification_57k.onnx`（14 类分类）+ `yolo26x.onnx`（COCO 80 类目标检测），单例懒加载
- 工程量：700 行，模型由 `scripts/download_models.py` 下载
- 对 Mimicry：**不要直接借**。这是把"反检测"从一个产品做成了"AI 公司业务"——模型训练、推理、维护的复杂度远超 Mimicry 当前阶段需要。**借鉴的方向**只是"如果未来要处理图像验证码，自托管 ONNX 路径在技术上是可行的"。

### Pattern 5: Tool 注册器分文件 + Zod schema + outputSchema

- 位置：`apps/api/src/mcp/tools/websiteTools.ts:11-143`
- 关键：MCP tool 用 `server.registerTool(name, { title, description, inputSchema: z.object(...), outputSchema, annotations }, handler)`
- 对每个 tool 显式给 `READ_ONLY_TOOL_ANNOTATIONS`（来自 `mcp/annotations.ts`）—— **把"幂等/只读"语义传给 LLM**，这是 MCP spec 里的 hints 字段
- 工具按业务域分文件（`websiteTools` / `googleSerpTools` / `tavilyTools` / `youtubeTools` / `exaTools` / `jobTools`）
- 对 Mimicry：值得借的是 **annotations**——告诉 LLM 哪些 action 是只读、哪些是破坏性操作；以及**按域分文件注册** vs Mimicry 的"自动映射全部"

## Operator System（HeadlessX 没有专门叫"Operator"，但有等价物）

实际上是 6 个 MCP tool group + 6 个 services 子模块：

| 域 | MCP tool | 对应 service |
|---|---|---|
| 网站抓取 | `headlessx_website_get_html`、`get_markdown`、`map_links` | `ScraperService` + `WebsiteDiscoveryService` |
| Google SERP | `googleSerpTools` | `scrape/GoogleSerpService` |
| Tavily | `tavilyTools` | 调用 Tavily API |
| Exa | `exaTools` | 调用 Exa API |
| YouTube | `youtubeTools` | Python YT engine 子服务 |
| Job 管理 | `jobTools` | `JobManager` + `QueueJobService` |

**对比 Mimicry 的 Block 模型**：HeadlessX 的 tool 都是"原子 = 一个完整的业务流"（"抓一个网站全部内容"、"映射网站链接"），粒度比 Mimicry 的 `browser.click` / `browser.type` 粗一个量级。Mimicry 应该考虑**两层设计**：底层细粒度 action（已有）+ 上层"复合 Operator"封装常见组合（如 "搜索并抓取"），这正是 ADR-006 Package 系统设计的方向。

## Queue / Concurrency Model

- **Queue 实现**：BullMQ + Redis（`services/queue/redis.ts:95` 行的连接构造器）
- **Job 类型**：`SCRAPE`、`CRAWL`、`EXTRACT`、`INDEX`（Prisma enum）
- **Job 状态**：`QUEUED`、`ACTIVE`、`COMPLETED`、`FAILED`、`CANCELLED`
- **配置**（`queueConfig.ts`）：环境变量驱动
  - `QUEUE_WORKER_CONCURRENCY`（默认 2）
  - `QUEUE_JOB_ATTEMPTS`（默认 3）
  - `QUEUE_JOB_BACKOFF_MS`（默认 5000）
  - `QUEUE_STREAM_POLL_MS`（默认 1000）
- **退避**：自动重试 3 次 + 5 秒退避
- **取消**：通过 `queueCancellationChannel`（Redis pub/sub），独立于 BullMQ 内置取消
- **Job 持久化**：双写 — BullMQ 的 Redis 状态 + Prisma 的 `QueueJob` 表（用于历史查询、审计、API 返回）
- **Worker 退出**：Redis 不通时不退出，进入 retry loop（`scheduleRetry`）

## Remote MCP / API Surface

- **HTTP transport**：`StreamableHTTPServerTransport`（MCP 1.x 新协议）
- **鉴权**：API Key 哈希存 Postgres `ApiKey` 表，请求中带 key，`resolveMcpApiKey` 校验
- **路由**：v1 + v2 双版本（`routes/v1.ts` / `v2.ts`）
- **业务路由域**：scrape / ai / jobs / dashboard / playground / proxy / config / media / keys / logs
- **Rate limit**：未在快速浏览中发现具体实现，可能依赖反向代理层（看 `infra/domain-setup`）
- **审计**：`RequestLog` 表与 ApiKey 关联（`schema.prisma`）

## Engineering Practices

### 仓库结构
- **Monorepo + Nx**：`apps/{api,web,yt-engine,go-html-to-md-service}` + `packages/{cli,headfox-js}`，nx 统一构建
- `pnpm preinstall: only-allow pnpm` 强制包管理器
- `mise.toml` 统一 toolchain（多语言版本钉死）

### CI/CD（`.github/workflows/` 这次没读到具体文件，README 只提了 Docker 镜像）
未深入。

### 测试
未在快速浏览中发现 `*.test.ts` / `__tests__/`。**测试基础设施可能薄弱**——但对一个生产部署项目这是个问号。

### 文档
- `docs/api-endpoints.md`、`setup-guide.md`、`CLI.md`、`SECURITY.md`、`ETHICS.md`、`CODE_OF_CONDUCT.md`、`CONTRIBUTING.md`、`docs/plans/`
- 公司化的文档套件，覆盖治理 / 安全 / 部署 / 路线图

### 发布/部署
- 4 个 Dockerfile（API、Web、YT engine、HTML→Markdown）
- `docker-compose.yml`（多服务编排）
- `infra/domain-setup`（域名/反代设置）
- 模型由 `scripts/download_models.py` 下载（不打进镜像）

### Config / Secrets
- `.env.example` 全套 env 变量驱动
- 关键 secret：
  - `DATABASE_URL`
  - `DASHBOARD_INTERNAL_API_KEY`（dashboard ↔ api 内部认证）
  - `CREDENTIAL_ENCRYPTION_KEY`（at-rest 加密第三方凭据）
  - `TAVILY_API_KEY` / `EXA_API_KEY`（外部 SaaS）
- "Browser and stealth defaults are managed in the dashboard settings UI" — 配置可在 UI 改而非只能 env

### Observability / 错误处理
- `RequestLog` 表
- console.error 用 emoji 前缀（`❌` / `⚠️`）
- `CloudflareChallengeError` 这种 typed error 把抓取失败原因结构化

## Gaps vs. Mimicry

Mimicry 是单用户桌面应用，HeadlessX 是多租户平台。直接对比维度：

| 维度 | HeadlessX | Mimicry |
|---|---|---|
| 部署模式 | 远程多用户服务（K8s / Docker） | 本地桌面应用（Tauri） |
| 鉴权 | API Key + 哈希存储 | 无（本地用） |
| 持久化 | Postgres + Redis | SQLite |
| MCP transport | HTTP Streamable | stdio |
| 队列 | BullMQ | 无 |
| Worker | 独立进程 | sidecar 单进程 |
| Captcha 处理 | 自托管 ONNX 模型 | 无 |
| Cloudflare 检测 | DOM 启发式 + typed error | 无 |
| 高阶 Operator | 6 类业务封装（SERP/Tavily/YouTube...） | Block 系统设计中（ADR-006） |
| Web Dashboard | Next.js | 无（Tauri 桌面 UI） |
| 子服务 | Go HTML→MD、Python YT engine | 单 Python sidecar |
| Lint 工具 | Biome（统一 lint+format，单 binary） | ESLint + Prettier |
| 死代码扫描 | knip | 无 |

**HeadlessX 做对而 Mimicry 没做的工程实践**：
1. Streamable HTTP MCP（远程能力）
2. typed error（如 `CloudflareChallengeError` 携带结构化 detail）
3. Biome 替代 ESLint+Prettier（更快、单工具）
4. knip 死代码扫描
5. 队列+Worker分离进程
6. annotations 给 MCP tool 标 read-only
7. Cloudflare 检测**只检测不解决**的策略

## Borrow List

| # | 借鉴点 | Mimicry 目标模块 | 优先级 | 成本/风险 |
|---|---|---|---|---|
| 1 | Cloudflare/Turnstile 启发式检测 → typed error/notification | `sidecar/browser/actions.py` 加 `cloudflare.detect`，sidecar 自动检测后发 `browser.warning` notification | **S** | 低，~半天，DOM 启发式逻辑可直接搬运 |
| 2 | MCP tool annotations（read-only / destructive 等） | `sidecar/mcp_server.py` + `@rpc_method` 增加 hints 元数据 | **S** | 低，~1 天 |
| 3 | typed error 模型（带 code + detail） | `sidecar/browser/actions.py` 错误返回结构化 `{kind, code, detail}` | M | 中，要重构 RPC 错误层 |
| 4 | 远程 MCP（Streamable HTTP transport） | 新增 `sidecar/mcp_http_server.py`，与 stdio 并存 | M | 中，~1 周；要先想清楚多租户/鉴权语义 |
| 5 | Biome 替代 ESLint + Prettier | 前端 toolchain | M | 低，纯工具替换；但要校验 Vue 支持是否完善（**风险点**） |
| 6 | knip 死代码扫描接 CI | `.github/workflows/pipeline.yml` | S | 低 |
| 7 | 高阶 Operator Block（"Google 搜索并抓结果"等组合 Block） | 等 Mimicry Package 系统落地后，作为内置 Package | L | 高，依赖 ADR-006 实现 |
| 8 | 任务队列引擎 | sidecar 内嵌轻量队列（不必 BullMQ） | L | 中-高，只在 Mimicry 有"批跑同一 workflow N 次"需求时做 |

## Do NOT Borrow

- **ONNX 自托管 captcha 模型** — 工程量过大，应优先用 playwright-captcha 的 click solver + 可选第三方 API 路线（见 04 档案）
- **Postgres + Redis 强依赖** — Mimicry 是桌面应用，SQLite 已够；引入 Redis 只为做队列得不偿失
- **Next.js Dashboard** — Mimicry UI 是 Tauri webview，不是浏览器访问的 web 界面，方向不一致
- **Multi-app monorepo + Nx** — Mimicry 已是 Tauri/Vue/Python 三层，再叠 Nx 是过度工程
- **`@xenova/transformers` + `onnxruntime-web`** — 重依赖、模型分发问题、推理性能问题，不要碰
- **`packages/headfox-js` (它们 fork 的 Camoufox-JS)** — Mimicry 已用 Camoufox Python，没必要再换一条 JS 路径

## Open Questions

- HeadlessX 的 BullMQ Worker concurrency 默认只有 2 — 实际生产部署常见值是多少？这反映"一个机器最多并行跑几个浏览器"的工程经验值
- `CredentialEncryptionKey` 加密的是哪些字段？这关系到 Mimicry 是否要给 profile 的 proxy 密码做 at-rest 加密（目前是明文存 SQLite）
- `Streamable HTTP` MCP transport 的客户端兼容性如何？Cursor / Claude Desktop / Cline 是否都支持？还是仅服务端实现，主流 LLM 客户端仍只支持 stdio？这决定 Mimicry 做远程 MCP 的优先级
- Mimicry 当前 SQLite 存 profile 时，`proxy.password` 是明文吗？应该交叉检查

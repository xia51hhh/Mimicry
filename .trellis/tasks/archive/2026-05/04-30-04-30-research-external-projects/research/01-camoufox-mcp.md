# whit3rabbit/camoufox-mcp

## TL;DR

一个**单文件 295 行 TypeScript** 的标准 Camoufox MCP Server，仅暴露**1 个 mega-tool `browse`**，但参数 schema 极其讲究（每个参数都有 LLM 可读的 `describe()`、Zod 严格校验、min/max 范围、自然语言触发提示）。Mimicry 最大可借鉴的不是功能而是**MCP schema 的"对 LLM 友好"工程实践**——参数描述、自然语言触发词、范围校验。

## Repo Metadata

| | |
|---|---|
| URL | https://github.com/whit3rabbit/camoufox-mcp |
| 最新 commit | `5e0ef69` (2025-10-01)，约 7 个月前 |
| 主语言 | TypeScript (单文件 `src/index.ts` 295 行) |
| License | MIT (`package.json:14`) |
| 体量 | 295 行核心 + 50 行 Dockerfile + 测试 1 个 Python 客户端 |
| 维护活跃度 | 已半年没动，但代码体量小、依赖清晰，等价于"已稳定" |
| 包名 | `camoufox-mcp-server@1.5.0` (npm) |

## Positioning

面向使用 Claude Desktop / Cursor / VS Code Continue / Cline / Windsurf 等 MCP 客户端的 LLM 用户，把 Camoufox 浏览器封装成"一句话即可使用"的 MCP 工具。设计哲学是 **"one tool, well documented"**——而不是 Mimicry 自动映射 52 个 tool 的"全暴露"。

## Tech Stack & Dependencies

| Layer | Tech |
|---|---|
| 语言 | TypeScript (ES Module) |
| MCP SDK | `@modelcontextprotocol/sdk@^1.12.1` (官方 TypeScript SDK) |
| 浏览器 | `camoufox-js@^0.4.0` (Camoufox 的 Node 绑定) |
| Schema 验证 | `zod@^3.23.8` |
| 终端日志 | `chalk@^5.4.1` |
| 测试 | Jest + 一个 Python stdio 客户端 (`tests/test_client.py`) |
| 打包 | `tsc` 直接产出 `dist/`，npm `bin` 字段提供 `camoufox-mcp-server` CLI |
| 容器化 | Dockerfile（含 xvfb-run，amd64 强制） |

总依赖只有 4 个生产依赖——极简。

## Architecture

```
LLM Client ── stdio ──► node dist/index.js ──► McpServer ──► browse() ──► Camoufox()
                                                                            │
                                                                            └─► Playwright Page
```

- **入口**：`src/index.ts:242 runServer()`，构造 `StdioServerTransport`，连接到 `McpServer`
- **唯一工具**：`server.tool("browse", { ... })` 在 `src/index.ts:63-235`
- **生命周期**：每次 `browse` 调用 = launch → goto → content/screenshot → close。**完全无状态**，没有跨调用的 session 复用
- **信号处理**：`SIGINT`/`SIGTERM`/`uncaughtException`/`unhandledRejection` 全部捕获并 `process.exit(1)` (`src/index.ts:257-290`)

这种"无状态、launch-per-call"的设计有重大缺陷（每个 LLM 工具调用都重启浏览器，巨慢），但也是 MCP 实现里最简单的范式。

## Key Code Patterns

### Pattern 1: 参数 schema 含 LLM 可读 describe + Zod 校验

- 位置：`src/index.ts:63-107`
- 做法：每个参数用 Zod chain 写 `.describe(...)`，让 MCP 客户端读取 `inputSchema` 时把描述喂给 LLM。范围校验也内建（`z.number().min(5000).max(300000)`）：

  ```typescript
  timeout: z.number().min(5000).max(300000).optional().default(60000)
    .describe("Timeout in milliseconds for page load (5-300 seconds)."),
  block_webrtc: z.boolean().optional().default(true)
    .describe("Block WebRTC entirely for enhanced privacy and stealth. Use when users want private browsing, to hide their real IP, prevent WebRTC leaks, or browse in stealth mode."),
  ```

- 为什么有意思：**describe 不只描述参数语义，还包含"用户什么时候会想用这个"——这是把 LLM 当成"无法看代码、只能看 schema 的开发者"的写法**。
- 对 Mimicry 的意义：直接可用。Mimicry 的 `mcp_server.py:32-69` 用 `inspect.signature` 自动生成 schema，丢失了所有这种语义信息。**应改造为：让 `@rpc_method` 装饰器接受可选的 param 描述 dict**。

### Pattern 2: Zod preprocess 处理 LLM 易传错的边界

- 位置：`src/index.ts:89-100`

  ```typescript
  window: z.preprocess(
    (arg) => {
      if (Array.isArray(arg) && arg.length === 0) return undefined;
      return arg;
    },
    z.tuple([z.number().min(320).max(3840), z.number().min(240).max(2160)]).optional()
  ).describe("Set fixed window size [width, height] instead of random generation. An empty array [] is accepted and treated as if the window parameter was not specified."),
  ```

- 为什么：LLM 常会传空数组 `[]` 表示"不设置"，原本会 schema 校验失败。`preprocess` 把 `[]` → `undefined` 兜住。
- 对 Mimicry：这种"为 LLM 输入习惯做兜底"的模式值得吸收，但 Python 这边可以用 Pydantic 的 `field_validator` 等价物。

### Pattern 3: OS 自动轮换 + headless 自动检测

- 位置：`src/index.ts:140-145`

  ```typescript
  const isLinux = process.platform === 'linux';
  const headlessMode = headless !== undefined ? headless : (isLinux ? 'virtual' : true);
  const osOptions = ["windows", "macos", "linux"];
  const selectedOS = os || osOptions[Math.floor(Math.random() * osOptions.length)];
  ```

- 为什么：默认行为不是"挑一个固定值"，而是"随机轮换"——对反指纹更友好。Linux 默认走 `virtual` (Xvfb)。
- 对 Mimicry：Mimicry 当前 `browser.launch` 默认 `headless=False` 由调用方决定 OS 指纹。可以加一层"profile.os = 'auto'"语义，sidecar 内部做随机轮换。

## MCP Tool Surface（完整枚举）

只有 1 个工具：**`browse`**，参数 19 个：

| # | 参数 | 类型 | 默认 | 用途 |
|---|---|---|---|---|
| 1 | url | string | (required) | 目标 URL |
| 2 | os | enum: windows/macos/linux | undefined→随机 | OS 指纹 |
| 3 | waitStrategy | enum: domcontentloaded/load/networkidle | domcontentloaded | 等待策略 |
| 4 | timeout | number 5000-300000 | 60000 | 加载超时 ms |
| 5 | humanize | boolean | true | 拟人鼠标 |
| 6 | locale | string | undefined | 浏览器 locale |
| 7 | viewport | { width, height } | undefined | 视口大小 |
| 8 | screenshot | boolean | false | 是否截图 |
| 9 | block_webrtc | boolean | true | 屏蔽 WebRTC |
| 10 | proxy | string \| { server, username, password } | undefined | 代理 |
| 11 | enable_cache | boolean | false | 启用缓存 |
| 12 | firefox_user_prefs | record | undefined | 自定义 prefs |
| 13 | exclude_addons | array<string> | undefined | 排除插件 |
| 14 | window | tuple[number, number] \| [] | undefined | 固定窗口尺寸 |
| 15 | args | array<string> | undefined | 浏览器命令行参数 |
| 16 | block_images | boolean | false | 屏蔽图像 |
| 17 | block_webgl | boolean | false | 屏蔽 WebGL |
| 18 | disable_coop | boolean | false | 禁用 COOP（iframe 操作必需） |
| 19 | geoip | boolean | true | 自动 GeoIP |

返回：`{ content: [{ type: "text", text: HTML } /*, { type: "image", data: base64, mimeType }*/] }`

## Engineering Practices

### 仓库结构（极简）
```
src/index.ts          # 295 行，全部逻辑
tests/test_client.py  # Python stdio 客户端
Dockerfile            # multi-stage，xvfb-run 运行
.github/workflows/ci.yml
package.json / tsconfig.json / eslint.config.mjs
```

### CI/CD（`.github/workflows/ci.yml`）

- **3 个 job**：`test`（matrix: Node 20/22，跑 Python 客户端 stdio 测试）、`build-and-publish-npm`（tag 触发）、`build-and-publish-docker`（amd64+arm64 buildx）
- 双仓库发布：Docker Hub + GHCR
- npm publish 用 `NODE_AUTH_TOKEN`
- **缺陷**：测试加了 `|| true`（`ci.yml:50` `python3 tests/test_client.py --mode local || true`）——**测试失败不会阻止发布**。这是个 ⚠️

### 测试

- 1 个 Python stdio 客户端 (`tests/test_client.py`)，启动 server 进程通过 stdin/stdout 发 MCP `tools/list`、`tools/call`，验证响应
- 没有单元测试（`@types/jest` 装了但没用）

### 文档

- 477 行 README，包含 6 种 MCP 客户端的接入配置（Claude Desktop / Cursor / VS Code Continue / Cline / Windsurf / Claude Code CLI）
- "Natural Language Triggers" 章节列出 LLM 触发该工具的中英文短语模式（`README.md:182-220`）——**这是写给"使用 LLM 的人类"的，不是写给 LLM 的**

### 错误处理

- `browse` 失败：返回 `{ content: [...], isError: true }`（MCP 标准模式）
- 顶层 `process.on('uncaughtException')` / `unhandledRejection` 拦截后 `exit(1)`——这种**进程级 fail-fast** 在 stdio MCP 里是合理的：客户端会 respawn

### 发布

- npm `bin` 字段 → `npx camoufox-mcp-server` 直接可跑
- Docker：`docker run -i --rm followthewhit3rabbit/camoufox-mcp:latest`
- 多平台 buildx，但 Dockerfile 强制 `--platform=linux/amd64`（Camoufox 二进制限制）

## Gaps vs. Mimicry

| 维度 | camoufox-mcp | Mimicry |
|---|---|---|
| 代码量 | 295 行单文件 | 几千行多模块 |
| 工具数 | 1 个 mega-tool | 52 个细粒度 tool（自动映射） |
| Schema 质量 | 每个参数有 describe + 范围校验 + 示例 | 仅 inspect.signature 退化映射 |
| 浏览器生命周期 | launch-per-call（无状态） | SessionManager 持久化 session |
| 部署模式 | npm + Docker + npx | 桌面端嵌入 |
| 反指纹参数 | 19 个 Camoufox 参数全部一级暴露 | `browser.launch` 仅暴露子集 |
| 拟人交互 | 仅依赖 Camoufox `humanize=True` | 同 |

**他们做对、Mimicry 没做的**：
1. **Schema 描述质量**：参数级 describe + 自然语言触发词
2. **Zod preprocess 兜底 LLM 输入习惯**
3. **Camoufox 全参数暴露**：尤其 `disable_coop`（iframe）、`block_webgl`、`exclude_addons`、`firefox_user_prefs`、`args` 这些 Mimicry 当前 `browser.launch` 没有
4. **多 MCP 客户端接入文档**：Mimicry 应该提供一份"如何在 Cursor/Claude Desktop 中接入 mimicry --mcp"的快速指引

**他们做错、Mimicry 不要学**：
1. launch-per-call（每次调用都重启浏览器）——Mimicry 的 SessionManager 持久化是更好的设计
2. CI 的 `|| true` 让测试失败也能发布

## Borrow List

| # | 借鉴点 | Mimicry 目标模块 | 优先级 | 成本/风险 |
|---|---|---|---|---|
| 1 | `@rpc_method` 装饰器扩展 `param_descriptions={}` 字典，`mcp_server.py` 注入到 inputSchema | `sidecar/rpc/methods.py` + `sidecar/mcp_server.py` | **S** | 低，~1 天，纯 Python 元数据扩展 |
| 2 | 暴露 Camoufox 完整参数：`disable_coop`、`block_webgl`、`block_images`、`exclude_addons`、`firefox_user_prefs`、`args`、`window` | `sidecar/browser/controller.py` 的 launch 入参 + `actions.py` 的 `browser.launch` | **S** | 低，参数透传，~半天 |
| 3 | OS 指纹随机轮换默认行为 | `sidecar/browser/profile.py` | M | 中，要决定何时不随机（profile 显式指定 OS 时） |
| 4 | 给 Mimicry MCP 工具加"自然语言触发词"段落到 docstring（影响 LLM 调用准确率） | 各 `@rpc_method` 函数 docstring | M | 中，覆盖面大但可渐进 |
| 5 | "MCP 客户端接入指南"文档（Cursor / Claude Desktop / Cline / Windsurf 都覆盖） | `docs/llm-interactive-guide.md` 扩展 | S | 低，文档工作 |
| 6 | Pydantic preprocess 兜底 LLM 输入（如空数组→None） | `sidecar/rpc/methods.py` 校验层 | L | 当前签名是 plain Python，要先引入 Pydantic |
| 7 | npm/npx 等价的"零安装一键启动 MCP" UX | `mimicry --mcp` 已经有，但要写好"加到 Cursor 配置"指引 | S | 已有基础 |

## Do NOT Borrow

- **launch-per-call 浏览器生命周期**——他们之所以这么做是因为没有 SessionManager 概念。Mimicry 已经有持久 session，更优。
- **单文件架构**——他们能压在 295 行因为只做一件事，Mimicry 的边界更宽。
- **`|| true` 跳过测试结果**——这是工程债不是模式。

## Open Questions

- `camoufox-js@0.4.0` 与 Mimicry 用的 Camoufox Python 包在参数命名上是否完全一致？比如 `firefox_user_prefs`、`exclude_addons` 这些参数 Camoufox Python 是否也支持。**需要查 Camoufox Python 包文档**。
- `disable_coop` 在 Camoufox 层面是怎么实现的？是 prefs 改写还是命令行参数？这关系到 Mimicry 能不能直接透传。
- `humanize=True` 在 Camoufox 内部仅做了什么？光鼠标轨迹？要不要再叠 playwright-captcha 风格的辅助层？

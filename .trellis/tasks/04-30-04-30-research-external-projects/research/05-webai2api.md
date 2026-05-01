# foxhui/WebAI2API

## TL;DR

一个**生产级 Camoufox 多账号浏览器池 + OpenAI 兼容 API gateway** 的 Node.js 项目（约 12k+ 行），把 LMArena/Gemini/ChatGPT/DeepSeek/Doubao/Sora 等 17 个 Web AI 网页 UI 包装成 OpenAI API。最值得 Mimicry 借鉴的是**Worker 池 + 调度策略 + 故障转移 + Supervisor + Xvfb/x11vnc 容器化部署 + 拟人输入（含 5% 错字模拟、长文本"假装打几个字→停顿→粘贴"）**。Mimicry 现有 SessionManager 是它的"低配版"，扩展空间巨大。

## Repo Metadata

| | |
|---|---|
| URL | https://github.com/foxhui/WebAI2API |
| 最新 commit | `84729fb` (2026-04-24)，本月 |
| 主语言 | JavaScript (ESM) + Vue 3 (webui) |
| License | MIT |
| 体量 | backend ~12k+ 行（含 17 个 adapter） + Vue webui + scripts + patches |
| 维护活跃度 | 活跃 |
| 包管理 | pnpm + workspaces (`webui` 是子 workspace) |
| 关键依赖 | `camoufox-js@0.8.3`、`playwright-core@1.57`、`fingerprint-generator`、`ghost-cursor-playwright-port`、`better-sqlite3`、`proxy-chain`、`socks-proxy-agent`、`https-proxy-agent`、`sharp` |

## Positioning

面向**用 LLM 网页版省钱/绕付费的开发者**：浏览器自动化打开 Gemini/ChatGPT/LMArena 等聊天网页，用拟人鼠标和打字模拟真人，把对话按 OpenAI Chat Completions API 格式输出。多 worker 多账号并发，每个 worker 独立 profile + 独立代理，账号间彻底隔离。

**与 Mimicry 的关系**：Mimicry 的"长期愿景里有 Workflow→API 发布"，WebAI2API 已经把这条路线工程化了——但它绑定到了"AI 网页代理"这个细分场景。

## Tech Stack & Dependencies

| Layer | Tech |
|---|---|
| 浏览器 | Camoufox-JS 0.8.3（带 patches，见下文）+ playwright-core |
| 指纹 | `fingerprint-generator` + `camoufox-js` 内置 |
| 拟人鼠标 | `ghost-cursor-playwright-port` (Bezier 轨迹) |
| 拟人输入 | 自实现（5% 错字、Bezier 时间分布、长文本假打字+粘贴） |
| 代理 | `proxy-chain` + `socks-proxy-agent` + `https-proxy-agent`，支持 HTTP/HTTPS/SOCKS5 + 鉴权链 |
| API server | Node 原生 http (`server/server.js`) + 中间件 |
| 持久化 | `better-sqlite3`（请求历史 + 媒体文件） |
| WebUI | Vue 3 + Ant Design Vue + Vite |
| Supervisor | 自实现 `supervisor.js`（IPC socket 控制） |
| 容器 | Dockerfile node:22 + xvfb + **x11vnc** + libgtk3 |
| 部署 | docker-compose（端口 3000 API+UI、5900 VNC） |

## Architecture

```
                        ┌────────────────────────────┐
                        │   Supervisor (节点 0)       │
                        │  - 启动 xvfb-run + x11vnc   │
                        │  - 监听 IPC socket          │
                        │  - 子进程崩溃自动重启        │
                        └──────────────┬─────────────┘
                                       │ spawn(server.js)
                                       ▼
        ┌──────────────────────────────────────────────────────┐
        │  HTTP Server (port 3000) + Vue WebUI                 │
        │  ── auth middleware (sk-* token)                     │
        │  ── /v1/chat/completions (OpenAI 格式)              │
        │  ── /admin/* (WebUI 管理 API)                        │
        └──────────────────────┬───────────────────────────────┘
                               │
                               ▼
              ┌────────────────────────────────────┐
              │  Queue Manager                     │
              │  ── maxConcurrent / queueBuffer    │
              │  ── keepalive: comment / content   │
              └────────────────┬───────────────────┘
                               │
                               ▼
              ┌────────────────────────────────────────────┐
              │  PoolManager (strategy: least_busy /        │
              │               round_robin / random)         │
              │  ── failover (max 2 retries)                │
              └──────┬─────┬─────┬─────────────────────────┘
                     │     │     │
                     ▼     ▼     ▼
                  Worker Worker Worker  (一个账号 = 一个 Worker)
                     │     │     │
              ┌──────┘     ▼     │
              │     ┌──────────┐ │
              ▼     ▼          ▼ ▼
              Camoufox + Playwright (per-worker context, 独立 userDataDir & 独立 proxy)
                     │
                     ▼
                  Adapter (chatgpt / gemini / lmarena / doubao / sora ...)
                  17 个，每个 ~250-500 行，封装 prompt 输入 + 流式响应抓取
```

### 关键路径
- `supervisor.js`（看门狗，三级清理 close→SIGTERM→SIGKILL）
- `src/server/server.js` (192 行) — HTTP 入口
- `src/server/queue.js` (368 行) — 队列管理 + heartbeat
- `src/backend/pool/PoolManager.js` (322 行) — Worker 池
- `src/backend/pool/Worker.js` (658 行) — 单浏览器实例封装，**支持浏览器共享给多 Worker**
- `src/backend/registry.js` (343 行) — Adapter 注册表
- `src/backend/strategies/` — least_busy / round_robin / random + failover
- `src/backend/engine/launcher.js` (434 行) — Camoufox 启动 + 指纹注入
- `src/backend/engine/utils.js` (822 行) — `safeClick` / `humanType` / `getHumanClickPoint` 等
- `src/backend/utils/CloudflareBypass.js` (164 行) — 自实现 CF Turnstile 点击

## Key Code Patterns

### Pattern 1: 拟人打字（5% 错字模拟 + 长文本假打粘贴）

- 位置：`src/backend/engine/utils.js:485-544`
- 短文本：每个字符 `delay: random(30, 100)` ms，**5% 概率敲一个 'x' 然后退格**：
  ```js
  if (Math.random() < 0.05) {
      await page.keyboard.type('x', { delay: random(50, 150) });
      await sleep(100, 300);
      await page.keyboard.press('Backspace', { delay: random(50, 100) });
  }
  await page.keyboard.type(char, { delay: random(30, 100) });
  await sleep(30, 100);  // 字符间额外停顿
  ```
- 长文本：先**假装打 3-8 个字符 → 停顿 500-1000ms → Ctrl+A 全选删除 → execCommand('insertText') 粘贴全文**。这极大模拟了"人类发现要打的太多就贴上去"的行为
- Shift+Enter 处理换行（避免触发发送）
- 对 Mimicry：**直接借**——加 `humanize_type` 选项到 `browser.type` action，配置开关 + 错字率 + 长文本阈值

### Pattern 2: 多策略 click point bias

- 位置：`src/backend/engine/utils.js:147-195` `getHumanClickPoint(box, type)`
- 6 种偏移策略：
  - `'input'`：左下区域随机（5-40% x, 60-90% y）— 模拟点输入框
  - `'button'`/`'random'`：中心 40-60% × 40-60%
  - `'top-left'` / `'top-right'` / `'bottom-left'` / `'bottom-right'`：四角偏移
- 配合 `safeClick(target, { bias: 'random' })`
- 对 Mimicry：可作为 `browser.click` 的可选 `bias` 参数

### Pattern 3: Worker 池 + 浏览器共享 + 故障转移

- 位置：`src/backend/pool/Worker.js:39-43` 三个所有权字段：
  ```js
  this._isBrowserOwner = false;
  this._browserOwner = null;
  this._sharedWorkers = [];
  ```
  Worker 可以是浏览器的"所有者"或"共享者"——多个 Worker 共享一个 Camoufox 进程节省资源，所有者负责重启
- 调度策略 `PoolManager.js:23` 由 config 选择 `least_busy` / `round_robin` / `random`
- 故障转移 `strategies/failover.js`：网络错误自动跳到支持同模型的下一个 Worker
- 对 Mimicry：Mimicry 当前 SessionManager 一对一管 session，没有"池调度"概念。**长期可演进**——但要先有"批量执行同 workflow N 次"的实际场景才值得做

### Pattern 4: 自定义 Cloudflare Turnstile 点击器（对比 playwright-captcha）

- 位置：`src/backend/utils/CloudflareBypass.js:38-164`
- 与 playwright-captcha 不同：**它用 `shadowRootUnl`** —— 这是 Camoufox 自己暴露的 closed shadow root 属性（普通 Playwright 没有），所以能穿透 closed shadow DOM
- 失败时降级到**坐标点击**（`box.x + 28, box.y + box.height/2`）
- 对 Mimicry：如果使用 Camoufox，`shadowRootUnl` 路径比 playwright-captcha 的 search 算法更高效。**应交叉对比两种实现，挑稳健的**

### Pattern 5: Supervisor + IPC socket 控制 + Xvfb + x11vnc

- 位置：`supervisor.js:1-60` + `Dockerfile:1-46`
- Supervisor 进程：
  - 在 Linux 用 `xvfb-run` 套住 server.js
  - 在 Unix socket（`/tmp/webai2api-supervisor.sock`）监听 IPC，接收"重启"指令（带新参数）
  - 子进程崩溃 → 1s 后自动 spawn 新的
- Docker 镜像安装 `xvfb` + **`x11vnc`**，暴露 5900 端口供 VNC 客户端连接看浏览器画面
- `CMD ["npm", "start", "--", "-xvfb", "-vnc"]`
- 对 Mimicry：**Mimicry 是 Tauri 桌面应用**，supervisor 模式不直接适用；**但 sidecar 自身可以借鉴 supervisor 思路**——sidecar daemon 崩溃自重启 + IPC 重启接口。**VNC 完全是另一条产品线**：要不要让 Mimicry 工作流可以"远程查看正在跑的 headless 浏览器"？这是平台化方向

### Pattern 6: Camoufox-JS patches 透出（patches/）

- 3 个 patch 文件直接覆盖 `node_modules/camoufox-js/dist/*`：
  - `locale.patched.js`
  - `pkgman.patched.js`
  - `utils.patched.js`（修复 SOCKS5 URL.origin 返回 "null" 的问题）
- 通过 `npm install` 后 postinstall 脚本覆盖
- 对 Mimicry：Mimicry 用 Python Camoufox 包，遇到 bug 时类似的 monkeypatch 路径要预留

## Humanize Strategy Detail

| 维度 | WebAI2API |
|---|---|
| 字符延迟 | `delay: random(30, 100)` ms |
| 错字率 | 5%（敲 'x' → backspace） |
| 字符间停顿 | `sleep(30, 100)` ms 额外 |
| 长文本切换阈值 | 文本长度判断（具体在 `humanType` 函数顶部，未细看） |
| 长文本策略 | 假打 3-8 字符 → 停 500-1000ms → 全选删 → execCommand('insertText') 粘贴 |
| 鼠标轨迹 | `ghost-cursor-playwright-port` (Bezier) — 通过 page._humanizeCursorMode 开关 |
| 点击 bias | 6 种区域偏好 |
| 滚动 | 未细看（`safeClick` 内 `scrollIntoViewIfNeeded` + 等稳定） |

## Web Dashboard

- Vue 3 + Ant Design Vue
- Pinia store
- 页面：dashboard / settings / tools / 历史记录 / 图片 / 监控
- WebUI 和 API 共用 3000 端口（Node http server 同时挂 UI 静态资源 + API 路由）
- Auth 中间件：用同一个 `sk-*` token 鉴权 UI 与 API
- VNC view：通过容器 5900 端口（用户用 Web VNC 客户端如 noVNC 自行接，项目本身没集成 noVNC 到 webui）

## Workflow-to-API Pattern

- 不是"用户写 workflow 发布为 API"——而是**预先封装**：作者写好 17 个 adapter（`adapter/chatgpt.js` 等），每个 adapter 负责"把 OpenAI 格式 prompt 输入到对应 AI 网页 + 抓流式响应"
- 请求路径：HTTP `/v1/chat/completions` → Queue → PoolManager 选 Worker → Worker 执行 adapter
- 流式响应：`server/respond.js` 用 SSE 把 adapter 抓的流式 token 转换为 OpenAI delta 格式
- 对 Mimicry："让用户把 Workflow 一键发布为 REST API" 的最简版：
  - sidecar 监听 HTTP 端口
  - 接收 POST → 解析 JSON 找到对应 workflow ID → 走 executor → 返回 result
  - 关键差别：WebAI2API 的"adapter"是手写的 JS，Mimicry 的"workflow"是 JSON 节点图——后者更通用但工程量大

## Engineering Practices

### 仓库结构
- `src/{backend, server, utils, config}/` 三层 + `webui/` Vue 子工作区
- `patches/`、`scripts/`、`config.example.yaml` 在根
- `supervisor.js` + `package.json` 入口

### CI/CD
- 没看到 `.github/workflows/`（本次未深扫）
- 用 `npm run init` 做项目初始化
- Docker Hub `foxhui/webai-2api:latest` 镜像

### 测试
- 没找到测试文件——**这是工程债**

### 文档
- 双语 README（中文 315 + 英文 318 行）
- `config.example.yaml` 详细注释每个字段
- `CHANGELOG.md` 维护

### Config / Secrets
- YAML 配置（`config.yaml`，从 `config.example.yaml` 复制）
- API auth token 必须 ≥10 字符
- `npm run genkey` 生成 token
- 代理凭据写在 YAML（无加密）—— at-rest 安全弱
- 浏览器 profile 存 `data/`，docker volume 持久化

### 错误处理 / 日志
- `utils/logger.js` (243 行) 自实现日志（带模块名前缀、级别）
- `utils/error.js` 标准化错误结构
- typed errors（`server/errors.js` 185 行 ERROR_CODES 枚举）

### 持久化
- `better-sqlite3` 存请求历史（`data/history/history.db`）+ 媒体文件（`data/history/media/`）
- 与 Mimicry 的 SQLite 选择一致

## Gaps vs. Mimicry

| 维度 | WebAI2API | Mimicry |
|---|---|---|
| 拟人输入 | 5% 错字 + 长文本假打粘贴 + Bezier 鼠标 | 仅 Camoufox `humanize=True`（鼠标层） |
| Worker 池 | 多策略调度 + 故障转移 + 浏览器共享 | SessionManager 一对一 |
| Multi-account 隔离 | per-Worker userDataDir + 独立代理 | profile 设计有 `user_data_dir` 字段，但没"批量并发"概念 |
| HTTP API gateway | OpenAI 兼容 + SSE 流 | 无 |
| Web Dashboard | Vue 3 完整管理 UI | Tauri 桌面 UI（不可远程访问） |
| VNC | x11vnc + 5900 端口 | 无 |
| Supervisor | 子进程崩溃自重启 + IPC 控制 | sidecar 由 Tauri 父进程管，无独立 supervisor |
| 配置加密 | 无 | 无（也是债） |
| 代理类型支持 | HTTP/HTTPS/SOCKS5 + 鉴权链 | profile 有 proxy 字段，未交叉验证 SOCKS5 鉴权链 |

## Borrow List

| # | 借鉴点 | Mimicry 目标模块 | 优先级 | 成本/风险 |
|---|---|---|---|---|
| 1 | 拟人打字（5% 错字 + 长文本假打粘贴 + 字符间停顿） | sidecar `browser/actions.py::browser_type` 增加 `humanize: bool` + `typo_rate` + `long_text_threshold` | **S** | 低-中，~3 天，纯算法移植 |
| 2 | 6 种 click bias（input/button/random/4 角） | `browser.click` 增加 `bias` 参数 | **S** | 低，~半天 |
| 3 | typed ERROR_CODES 枚举 | `sidecar/rpc/errors.py` | S | 低 |
| 4 | Worker 池 + least_busy 调度 + 故障转移 | sidecar 长期演进；SessionManager → PoolManager 重构 | M-L | 中-高，需要先有"批跑"产品需求 |
| 5 | 浏览器共享给多 Worker 模式 | 同上 | L | 高，复杂的所有权语义 |
| 6 | Supervisor + IPC restart | sidecar daemon.py 增强 | M | 中，提升可用性 |
| 7 | x11vnc 容器化（如果 Mimicry 出 docker server 模式） | 仅当 Mimicry 走"远程节点"路线时 | L | 中 |
| 8 | Workflow-as-API（HTTP gateway 服务化） | sidecar 新 HTTP server 模式 + workflow ID 路由 | L | 中-高，明确产品定位后做 |
| 9 | OpenAI SSE 流式响应模式 | 同 #8，集成在 HTTP server 里 | L | 中 |
| 10 | proxy-chain + socks-proxy-agent + 鉴权链支持 | 交叉检查 Mimicry 的 proxy 是否支持 SOCKS5 + auth | S | 低，主要是验证 |
| 11 | 拟人 click point bias 实现（`getHumanClickPoint`） | `sidecar/utils/humanize.py` 新模块 | S | 低 |

## Do NOT Borrow

- **17 个 AI 网页 adapter**：Mimicry 不该绑定具体 AI 站点
- **Camoufox-JS patches**：Mimicry 用 Python Camoufox，patches 不直接适用，但**保留"必要时 monkeypatch"的工程流程**
- **OpenAI Chat Completions 协议**：Mimicry 不是 LLM 网关
- **`shadowRootUnl` 依赖**：这是某个 Camoufox-JS 的非标准属性，Mimicry 用 Python Camoufox 不一定有；优先用 playwright-captcha 的标准 shadow DOM 搜索
- **整套 Vue webui**：Mimicry 已有 Tauri webview，重复

## Open Questions

- Mimicry 当前 `browser.type` 是直接 `page.keyboard.type(text)`，是否要把"单字符循环 + delay" 作为默认行为？这有性能权衡
- `shadowRootUnl` 是 Camoufox 哪个版本引入的？Python Camoufox 有等价物吗？需查 Camoufox 文档
- Worker 池 + 浏览器共享是否真的比"一 Worker 一浏览器"省资源？数据是多少？这个 pattern 没看到 README 里有 benchmark
- VNC 接入价值评估：Mimicry 用户场景里"远程看正在跑的浏览器画面"是真需求还是想象？需要用户访谈
- WebAI2API 没有测试是否构成"上生产风险"？还是说作者依赖 Docker 镜像稳定性 + 用户反馈做质量门禁？

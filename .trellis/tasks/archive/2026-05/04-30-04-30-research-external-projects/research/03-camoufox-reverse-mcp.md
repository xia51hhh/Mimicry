# WhiteNightShadow/camoufox-reverse-mcp

## TL;DR

一个**JS 逆向工程专用的 Camoufox MCP**，~5k 行，把 14 个 JS hook 模板（XHR、fetch、crypto、cookie、property access、jsvmp 等）+ 11 类 Python tool 模块封装为 MCP，配 Camoufox **C++ 引擎层** Property Access Tracer（对 JSVMP 不可见）。是 Mimicry 当前 MCP 表面（UI 操作）**最强力的能力扩展样板**——但要全盘借鉴需要自定义 Camoufox 编译，不现实，应**只借 JS hook 模板和 tool 组织方式**。

## Repo Metadata

| | |
|---|---|
| URL | https://github.com/WhiteNightShadow/camoufox-reverse-mcp |
| 最新 commit | `54a72d3` (2026-04-24)，本月 |
| 主语言 | Python（MCP server）+ JavaScript（hook 模板） |
| License | MIT (`pyproject.toml:5`) |
| 体量 | Python 核心 ~3.6k 行 + JS hooks 1.3k 行 ≈ 4.9k 行 |
| 依赖 | `mcp>=1.0`、`camoufox[geoip]>=0.4`、`playwright>=1.40`、`esprima>=4.0.1`（仅 4 个） |
| 维护活跃度 | 活跃（4 月有提交） |

## Positioning

面向**做爬虫/逆向工程的 LLM Agent**：让 Claude Code / Cursor / Cline 等通过 MCP 直接获得"打开指定网站、注入 hook、追踪 JSVMP 字节码、抓 XHR 请求/响应、AST 重写 JS 源码"的能力。和 chrome-devtools-mcp 比，核心卖点是**反检测 + 引擎级埋点**。

## Tech Stack & Dependencies

| Layer | Tech |
|---|---|
| MCP SDK | `mcp.server.fastmcp.FastMCP`（Python 高层 SDK，装饰器式） |
| 浏览器 | Camoufox + Playwright async API |
| AST | `esprima-python`（纯 Python ES2017 解析） |
| Hook 注入 | 通过 `page.evaluate()` 注入 JS 模板 + 通过 Camoufox 的 `init_scripts` 做持久化 |
| 数据持久化 | 文件（`~/.cache/camoufox-reverse/`） |
| 测试 | pytest + pytest-asyncio (`asyncio_mode = "auto"`) |

## Architecture

```
LLM Client ──stdio──► python -m camoufox_reverse_mcp ──► FastMCP
                                                          │
                                                          ▼
                                                BrowserManager (camoufox+pw)
                                                          │
                                  ┌───────────────────────┼─────────────────────────┐
                                  ▼                       ▼                          ▼
                          tools/* (11 类，每类     hooks/*.js (14 个 JS         property_trace.py
                          一个文件，每文件 1-3+    模板，page.evaluate 注入)    （读 Camoufox C++
                          tool)                                                  引擎写出的 JSONL）
```

### 入口
- `__main__.py:main` 启动 FastMCP stdio server
- `server.py:25` 行的小文件 import 11 个 tool 模块（侧效应注册）

### 核心组件
- **`browser.py:35-340`** — `BrowserManager`：一个进程内单 Camoufox + 多 page 池 + 网络/控制台日志双 deque（`MAX_LOG_SIZE=2000`、`MAX_BODY_SIZE=200_000`）+ persistent script 列表
- **`tools/`**（11 个文件，约 3k 行）— 每文件对应一个语义域，文件内一组 `@mcp.tool()` 函数
- **`hooks/`**（13 个 .js 文件 + 1 个 trace 模板）— 注入 JS 的源码模板，被 Python 通过 jinja-style 占位符（`'{{TARGETS}}'`）渲染后 page.evaluate
- **`property_trace.py`** — 走 Camoufox **C++ 引擎层** trace（不是 JS hook），通过文件系统通信（`~/.cache/camoufox-reverse/control/control-{pid}.cmd` 写命令，`traces/{pid}_*.jsonl` 读结果）—— **这要求自定义构建 Camoufox**，普通 Camoufox 不带这个

## Reverse-Engineering Tool Inventory

完整 tool 域（按文件）：

| 文件 | 主要 tool | 域 |
|---|---|---|
| `navigation.py` (433 行) | `launch_browser`、`navigate_to`、`new_page`、`switch_page`、`evaluate_js` 等 | 浏览器/页面控制 |
| `script_analysis.py` (302 行) | `scripts()`（列已加载脚本）、`search_code()`（grep 已加载源码） | 静态脚本分析 |
| `debugging.py` (282 行) | `evaluate_js`、断点等 | 运行时调试 |
| `hooking.py` (307 行) | **`hook_function(mode=intercept/trace, position=before/after/replace, persistent=True)`** 统一接口 | 函数级 hook（unified intercept + trace） |
| `network.py` (330 行) | `network_capture(start/stop)`、`list_requests`、`get_request_detail` | XHR/fetch 抓包 |
| `storage.py` (154 行) | `cookies()`、`get_storage`、`export_state`、`import_state` | Cookie/storage |
| `cookie_analysis.py` (140 行) | Cookie 安全分析 | Cookie 专项 |
| `jsvmp.py` (189 行) | `hook_jsvmp_interpreter`、`compare_env` | JSVMP 字节码层 |
| `instrumentation.py` (416 行) | `instrumentation(action=...)` AST 源码层重写 | AST 插桩 |
| `environment.py` (101 行) | `check_environment` | 环境校验（依赖、Camoufox 版本） |
| `verification.py` (105 行) | `verify_signer_offline` | 离线签名校验（断网验签） |
| `trace.py` (321 行) | `trace_property_access`、`list_traces`、`query_trace` | C++ 引擎级 property trace |

JS hook 文件（注入到页面上下文）：

| 文件 | 行数 | 作用 |
|---|---|---|
| `xhr_hook.js` | 57 | hook `XMLHttpRequest.prototype.open/send/setRequestHeader` |
| `fetch_hook.js` | 59 | hook `window.fetch` |
| `websocket_hook.js` | 38 | hook `WebSocket` |
| `cookie_hook.js` | 71 | hook `document.cookie` setter |
| `crypto_hook.js` | 33 | hook Web Crypto API |
| `property_access_hook.js` | 111 | Proxy + getter 双策略追踪属性访问 |
| `jsvmp_hook.js` | 380 | JSVMP 解释器埋点 |
| `jsvmp_transparent_hook.js` | 190 | JSVMP 隐形埋点（更难被检测） |
| `runtime_probe.js` | 153 | 运行时环境探测 |
| `debugger_trap.js` | 43 | 反 debugger trap（防 `debugger;` 反调试） |
| `font_fallback.js` | 26 | 字体回退（防字体指纹） |
| `trace_template.js` | 44 | 函数 trace 模板（一次性） |
| `trace_persistent_template.js` | 54 | 函数 trace 模板（持久化） |

**总计：约 35+ tool 入口**（README 说 35+，实际计数 11 文件 × 平均 3 个 tool ≈ 30+，吻合）

## Key Code Patterns

### Pattern 1: XHR Hook 三段拦截 + 反检测 toString

- 位置：`hooks/xhr_hook.js:1-57`
- 做法：
  ```js
  const _open = _origProto.open;
  const hookedOpen = function(method, url) {
      this.__mcp_info = { method, url: String(url), headers: {}, timestamp: Date.now() };
      return _open.apply(this, arguments);
  };
  Object.defineProperty(_origProto, 'open', { value: hookedOpen, writable: false, configurable: false });
  hookedOpen.toString = function() { return 'function open() { [native code] }'; };
  ```
- 关键技巧：
  1. **三段 hook**：`open`（记 method + url + headers 容器）→ `setRequestHeader`（写到容器）→ `send`（记 body + stack + 注册 load 监听记 status/length）
  2. **`Object.defineProperty(.., writable: false, configurable: false)`** 防被网站再次覆盖
  3. **`toString` 伪装** 让 `XMLHttpRequest.prototype.open.toString()` 返回 `function open() { [native code] }`，绕过常见 hook 检测
  4. **try/catch + fallback** 直接赋值（某些环境下 defineProperty 会失败）
- 对 Mimicry：直接可移植——加一个 `network.start_xhr_capture` action 把这段 JS 注入即可

### Pattern 2: Property Access Tracer（双策略）

- 位置：`hooks/property_access_hook.js:6-50`
- 两种策略二选一：
  - **`new Proxy(obj, { get(target, prop, receiver){...} })`** — 整个对象代理，能捕获所有 property read
  - **`Object.defineProperty(parent, propName, { get(){...} })`** — 单个属性的 getter 替换
- 双策略原因：Proxy 对某些原生对象（如 `Navigator`）会被检测到 `Proxy.toString()` 异常，所以提供 fallback
- 对 Mimicry：可作为"反指纹检测调试器"功能，让用户实时看到目标网站访问了哪些 `navigator.*` / `window.*` 属性

### Pattern 3: 函数 Hook 的统一接口（unified intercept + trace）

- 位置：`tools/hooking.py:10-59`
- 把"intercept (修改函数行为)" 和 "trace (旁观函数调用)" 合并到 **一个 MCP tool** `hook_function`，靠 `mode` 参数分发
- 优点：LLM 学一个 tool 而非两个；参数交集可复用（function_path、persistent、log_args 等）
- `non_overridable=True` 时用 `Object.defineProperty(parent, fn, { ... })` 锁定，防被网站绕过
- 对 Mimicry：这种"参数 mode 而非分裂工具"的设计可借鉴。但需要权衡——MCP 的 schema 描述里要把 mode 的含义讲清楚否则 LLM 容易传错

### Pattern 4: AST 源码层重写（不依赖外部 CDN）

- 位置：`utils/ast_rewriter.py:1-60`
- 用 `esprima-python`（纯 Python）解析 JS 源码 → walk AST → 把所有 member access 和 call 包成 `__mcp_tap_get` / `__mcp_tap_call` → 重新序列化为 JS
- **跑在 MCP 进程而不是页面**——这样能处理那些**屏蔽外部 CDN 的强反爬页面**（RS / AK 412 challenge），他们让加载 Acorn 也加载不了
- 对 Mimicry：高级功能，仅当 Mimicry 走逆向方向才需要

### Pattern 5: 持久化 Hook（survives navigation）

- 位置：`browser.py:52-54` `_init_scripts: list[str]` + `_persistent_scripts: list[dict]`，结合 Playwright `context.add_init_script` 和 page navigation 后自动重注入
- 设计：MCP tool 接受 `persistent=True` 参数，sidecar 把 hook JS 注册到 BrowserManager 的列表里，每次新页面/导航都重新注入
- 对 Mimicry：Mimicry 当前 `RecordingEngine` 也用 init script，但没暴露到外层 API。可以借这个 pattern 把"持久 Hook"作为 Block 的一种

## Anti-Tampering / Stealth Considerations

- `Object.defineProperty` 锁定 hook（writable=false, configurable=false）
- `hookedFn.toString = () => 'function name() { [native code] }'` 伪装原生
- **Camoufox C++ 引擎层 PropertyTracer**（`property_trace.py`）— 这是杀手锏：埋点在 C++ 层，**JS 完全看不见**，但需要自定义 build Camoufox（通过 `CAMOU_CONFIG.propertyTrace` 启用）
- 文件系统通信（控制 cmd + JSONL trace 输出）—— 进程间隔离，避免 hook 自身被页面 JS 看到

## Engineering Practices

### 仓库结构（清晰）
```
src/camoufox_reverse_mcp/
├── __main__.py           # entry
├── server.py             # FastMCP instance + import side-effects
├── browser.py            # BrowserManager
├── property_trace.py     # C++ engine integration
├── tools/{...}.py        # 11 个 tool 域
├── hooks/{...}.js        # 13 个 JS 模板
└── utils/{ast,js}_*.py
tests/
└── 6 个 test_*.py（含 ast_rewriter, browser, domain_session, evaluate_js, jsvmp, tools）
docs/
└── JSVMP_PLAYBOOK.md
```

### 测试
- pytest + asyncio_mode=auto
- **6 个测试文件覆盖 AST、browser、JSVMP、tools、evaluate_js**——比 camoufox-mcp 的"1 个 stdio 客户端"扎实很多
- 没看到 CI 配置，但测试基础在

### 文档
- 双语 README（中文 380 行 + 英文 296 行）
- `docs/JSVMP_PLAYBOOK.md` — 单独 Playbook 教 LLM 怎么用这个工具做 JSVMP 分析
- 包含 chrome-devtools-mcp 对比表

### 发布/打包
- pip 安装（`pip install -e .` / `python -m camoufox_reverse_mcp`）
- `pyproject.toml` 用 hatchling 构建
- 没有 Docker（C++ 引擎集成自带平台耦合）

### 错误处理
- 大量 `try/except` 返回 `{"error": str(e)}` —— 简单但够用
- LLM 看到错误能自己重试

## Gaps vs. Mimicry

| 维度 | camoufox-reverse-mcp | Mimicry |
|---|---|---|
| MCP 工具焦点 | JS 逆向 + 网络拦截 + AST 插桩 | UI 操作（click/type/extract） |
| Hook 体系 | 14 个预置 JS 模板 | 无 |
| 网络拦截 | 完整（XHR/fetch/WebSocket，含 body/stack） | 无（只能截图、提取 DOM） |
| 函数级 hook | `hook_function(mode=intercept/trace)` | 无 |
| AST 插桩 | 有（esprima） | 无 |
| 持久化 hook | 有（survives navigation） | 部分（RecordingEngine 内部用） |
| C++ 引擎级 trace | 有（需自定义 Camoufox build） | 无 |
| 反 hook 检测 | toString 伪装 + defineProperty 锁定 | 无 |

**Mimicry 不具备的，能直接迁移的能力**：
1. XHR/fetch/WebSocket 抓包
2. Cookie/Crypto API hook
3. 函数级 trace（不修改行为，只记调用）
4. 持久化 hook（导航后自动重注入）
5. Property access tracer（用 Proxy 或 getter）

不能直接迁移的：
- C++ 引擎层 PropertyTracer（要自定义 Camoufox build，工程成本极高）
- JSVMP 专项工具（受众太窄）

## Borrow List

| # | 借鉴点 | Mimicry 目标模块 | 优先级 | 成本/风险 |
|---|---|---|---|---|
| 1 | XHR/fetch hook + 抓包 → `network.capture` action | sidecar 新增 `sidecar/browser/network_capture.py` + 一组 `network.*` action | **S** | 低，~2 天，JS 模板可直接拷贝 |
| 2 | `hook_function(mode=intercept/trace)` 统一接口 | sidecar 新增 `script.hook` action | **S** | 低-中，~3 天 |
| 3 | 持久化 hook（context.add_init_script + navigation re-inject） | `sidecar/browser/controller.py` BrowserController 新增 `add_persistent_script` API | M | 中，~3 天，需要重写 controller |
| 4 | toString 伪装 + defineProperty 锁定 hook 的反检测套路 | 上述所有 hook 模板共用的 utility | S | 低，纯 JS 模板复用 |
| 5 | Cookie 操作的 hook 抓 setter | `cookie.*` action 增强 | S | 低 |
| 6 | 双语 README + Playbook 形式（写给 LLM 的"使用手册"） | `docs/llm-interactive-guide.md` + 新增 `docs/playbooks/` | S | 文档 |
| 7 | tool 文件按域划分（不再 mcp 全自动映射） | `sidecar/mcp_server.py` 重构：手工注册 vs 自动 | M | 中，但能解决"MCP schema 太粗"的根本问题 |
| 8 | esprima 做 AST 操作（不依赖页面 CDN） | 仅当 Mimicry 走逆向方向，否则不做 | L | 高 |

## Do NOT Borrow

- **Camoufox C++ 引擎层 PropertyTracer**：要自定义编译 Camoufox 二进制 → Mimicry 不该走这条路
- **JSVMP 专项工具**：用户面太窄，对 Mimicry 是定位飘移
- **AST 全量插桩** ：调试性质太强，普通用户用不到
- **`verify_signer_offline`**：纯逆向场景

## Open Questions

- Mimicry 沿用社区版 Camoufox（pip install），无法启用 `propertyTrace` C++ 路径——是否值得在 Camoufox 上游提 PR 把 PropertyTracer 做成可选 feature flag？
- `hook_function` 的 `mode` 参数实际能让 LLM 正确理解吗？需要看实际调用日志；否则就该拆成两个 tool
- JS hook 的"反检测套路"（toString 伪装、defineProperty 锁定）已成行业标配，Mimicry 录制器（`sidecar/browser/recorder.py`）当前是否已经做了类似处理？需要交叉检查
- esprima-python 解析速度对大文件是否够用？这关系到 AST 插桩是否能上线

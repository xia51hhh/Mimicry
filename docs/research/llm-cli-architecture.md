# LLM-Integrated CLI Architecture Research

> 研究目的：为 Mimicry 设计 LLM 驱动的 CLI 模式，支持启动任务、调试、暂停、中途插入操作、查看数据

---

## 1. 项目架构对比

### 1.1 Browser-Use (Python, 91k⭐)

**架构模式**: ReAct Loop + Function Calling

```
LLM ←→ Agent (ReAct Loop) ←→ Tools Registry ←→ Browser Session (Playwright)
                ↕
        Message Manager (对话历史)
```

**核心设计**:
- **Agent 类**是中枢，运行 step-by-step 循环：
  1. 获取浏览器状态（accessibility tree + 可选截图）
  2. 将状态注入 LLM 上下文
  3. LLM 返回结构化输出（思考 + 动作列表）
  4. 执行动作，收集结果
  5. 重复直到 `done` 动作被调用
- **动作系统**: 基于注册表的动态工具，每个动作是一个 async handler
- **CLI 模式**: 独立的持久化守护进程架构
  - 首次命令启动后台 daemon（浏览器保持打开）
  - 后续命令通过 Unix socket 通信
  - ~50ms 命令延迟（无需每次启动浏览器）
  - 支持 `--session` 多会话隔离

**工具接口（CLI 命令）**:
```bash
browser-use open <url>          # 导航
browser-use state               # 获取可交互元素列表（带索引）
browser-use click <index>       # 按索引点击
browser-use type "text"         # 输入
browser-use input <idx> "text"  # 定位+输入
browser-use screenshot [path]   # 截图
browser-use eval "js code"      # 执行 JS
browser-use python "code"       # 持久化 Python 会话
browser-use wait selector "css" # 等待元素
browser-use get html/text/value # 获取数据
browser-use close               # 关闭
```

**暂停/恢复机制**:
- `agent.pause()` / `agent.resume()` — 通过 `asyncio.Event` 实现
- 信号处理：第一次 Ctrl+C 暂停（保持浏览器开启），第二次退出
- `agent.state.paused` / `agent.state.stopped` 标志位
- `_external_pause_event` — 异步等待事件

**错误处理**:
- `max_failures` 连续失败计数器
- 循环检测器（检测重复动作/页面停滞）
- 自动 replan 建议（连续失败后注入 "REPLAN SUGGESTED" 消息）
- fallback LLM 自动切换（主 LLM 限流时）
- 浏览器断开重连逻辑

**优点**:
- 极其成熟的 ReAct 实现，处理了大量边缘情况
- CLI daemon 模式实现了低延迟交互
- 内置规划系统（plan_update）
- 支持 rerun（历史回放 + 元素重新匹配）
- 变量检测 + 替换（参数化重放）

**缺点**:
- Agent 类超过 3000 行，复杂度极高
- LLM 绑定深入（不易替换为非 LLM 控制）
- CLI 和 Agent 是两个独立模式，没有融合
- 不支持中途动态注入操作（flow 是 LLM 驱动的）

---

### 1.2 Playwright MCP (TypeScript, 31.8k⭐)

**架构模式**: MCP (Model Context Protocol) — 工具服务器

```
LLM (Claude/GPT/etc) ←→ MCP Client ←→ Playwright MCP Server ←→ Browser
                                              ↕
                                    Accessibility Tree (结构化快照)
```

**核心设计**:
- **不含 Agent 逻辑**：纯工具提供者，LLM 决定调用顺序
- 通过 accessibility snapshot 传递页面结构（非截图）
- 每个工具是一个独立的 MCP tool，有严格的 JSON Schema 参数
- 支持两种模式：
  - **MCP 模式**: 通过 stdio/SSE 暴露工具给 LLM
  - **CLI 模式**: `playwright-cli` 直接命令行操作（更省 token）

**工具接口（MCP Tools）**:

| 类别 | 工具 |
|------|------|
| Core | `browser_navigate`, `browser_click`, `browser_type`, `browser_fill_form`, `browser_hover`, `browser_drag`, `browser_select_option`, `browser_press_key`, `browser_file_upload`, `browser_handle_dialog` |
| State | `browser_snapshot` (accessibility tree), `browser_take_screenshot`, `browser_console_messages`, `browser_network_requests` |
| Tabs | `browser_tabs` (list/new/close/select) |
| Code | `browser_evaluate` (JS), `browser_run_code` (Playwright 代码) |
| Wait | `browser_wait_for` (text/time/disappear) |
| DevTools | `browser_resume` (step debugging!), `browser_start_tracing`, `browser_start_video`, `browser_highlight` |
| Network | `browser_route` (mock), `browser_network_state_set` |
| Storage | cookies, localStorage, sessionStorage 全套 CRUD |
| Testing | `browser_verify_*` (assertions) |

**调试支持**:
- `browser_resume` — 暂停/单步执行！可设置断点位置
- `browser_highlight` — 高亮元素（视觉调试）
- `browser_start_tracing` / `browser_stop_tracing` — Playwright trace 录制
- `browser_start_video` / `browser_stop_video` — 视频录制
- `--caps=devtools` 启用 DevTools 能力

**优点**:
- 标准 MCP 协议，任何 LLM 客户端可接入
- 工具设计非常清晰，每个工具单一职责
- `browser_resume` 实现了真正的断点调试
- accessibility tree 方式省 token，无需视觉模型
- codegen 能力（自动生成 TypeScript 代码）
- 区分 read-only 和 write 工具（安全性）

**缺点**:
- 没有内置 Agent 循环，依赖外部 LLM 客户端
- 每次 snapshot 仍然可能很大（复杂页面）
- 不支持 Camoufox 等反检测浏览器
- 不适合高吞吐量场景（tool schema + a11y tree 占 token）

---

### 1.3 Stagehand (TypeScript, 22.4k⭐)

**架构模式**: 混合模式 — 代码 + AI 分级

```
Developer Code ←→ Stagehand SDK ←→ CDP Engine ←→ Browser (Browserbase)
                       ↕
                  LLM (用于 act/extract/agent)
```

**核心设计**:
- **三级 API**:
  1. `page.goto()` — 直接 Playwright/CDP 操作（确定性）
  2. `stagehand.act("click login")` — 单步 AI 操作
  3. `stagehand.agent().execute("complete checkout")` — 多步 AI 任务
- `stagehand.extract(prompt, zodSchema)` — 结构化数据提取
- **自愈缓存**: 记住之前的操作，网站变化时自动修复

**工具接口**:
```typescript
// Level 1: 精确代码
await page.goto("https://example.com");
await page.click('[data-testid="login"]');

// Level 2: AI 单步
await stagehand.act("click the login button");

// Level 3: AI 多步
const agent = stagehand.agent();
await agent.execute("Find the latest PR and get its title");

// 数据提取
const data = await stagehand.extract(
  "extract product info",
  z.object({ name: z.string(), price: z.number() })
);
```

**优点**:
- "渐进式 AI" 设计 — 选择何时用代码、何时用 AI
- Zod schema 强制结构化输出
- 操作缓存（相同操作无需再次 LLM 调用）
- 适合生产环境（可预测性高）

**缺点**:
- 不支持暂停/调试/中途插入
- 绑定 Browserbase 云服务
- 没有 CLI 交互模式
- 不适合探索式自动化

---

### 1.4 Playwright CLI + SKILLS (微软新方向)

**架构模式**: CLI 命令 + SKILL 文件（LLM 读取后生成命令）

```
LLM (coding agent) → 读取 SKILL.md → 生成 CLI 命令 → Playwright CLI → Browser
```

**关键洞察**:
> "Modern coding agents increasingly favor CLI-based workflows exposed as SKILLs over MCP because CLI invocations are more token-efficient: they avoid loading large tool schemas and verbose accessibility trees into the model context."

- CLI 命令比 MCP tool schema 更省 token
- SKILL.md 文件作为 LLM 的使用手册
- 适合在大型代码库上下文中使用

---

## 2. 架构模式总结

### 2.1 ReAct Loop（Browser-Use）

```
Observe → Think → Act → Observe → Think → Act → ... → Done
```
- LLM 每步都决定下一步动作
- 适合探索式、不确定目标的任务
- Token 消耗高（每步都需要完整上下文）
- 自动错误恢复

### 2.2 MCP Tool-Calling（Playwright MCP）

```
LLM ← tool list → 选择工具 → 执行 → 返回结果 → LLM 决定下一步
```
- LLM 作为调度者，工具作为能力
- 标准协议，可插拔
- 适合需要丰富内省能力的场景

### 2.3 Plan-then-Execute（混合模式）

```
LLM → 生成计划 → 逐步执行 → 失败时回到 LLM 重规划
```
- Browser-Use 的 `plan_update` 机制
- 减少 LLM 调用次数
- 适合可预测的多步任务

### 2.4 Code-First + AI-Assist（Stagehand）

```
确定性代码 → 遇到模糊步骤 → 调用 AI → 返回代码流
```
- AI 作为辅助，不作为主控
- 最适合生产环境
- 最省 token

### 2.5 CLI-as-Interface（Browser-Use CLI, Playwright CLI）

```
Agent/Human → CLI 命令 → Daemon → Browser
```
- 命令行作为统一接口
- 适合 LLM 和人类共用
- 持久化会话降低延迟

---

## 3. 关键设计要素

### 3.1 暂停/恢复机制

| 项目 | 实现方式 |
|------|---------|
| Browser-Use | `asyncio.Event` + 信号处理（Ctrl+C 暂停） |
| Playwright MCP | `browser_resume` 工具 + step 参数（单步执行） |
| Stagehand | 不支持 |

### 3.2 动态操作注入

| 项目 | 实现方式 |
|------|---------|
| Browser-Use | `agent.add_new_task(new_task)` — 追加新任务到消息历史 |
| Playwright MCP | 天然支持 — LLM 随时可调用任何工具 |
| Stagehand | 代码级别控制，无动态注入 |

### 3.3 状态检查/调试

| 项目 | 能力 |
|------|------|
| Browser-Use CLI | `state`(元素列表), `screenshot`, `eval`, `get html/text` |
| Playwright MCP | `browser_snapshot`, `browser_console_messages`, `browser_network_requests`, `browser_highlight` |
| Stagehand | 仅通过代码 `page.content()` 等 |

### 3.4 错误处理策略

| 策略 | 使用者 |
|------|--------|
| 重试 + 指数退避 | Browser-Use (rerun) |
| 循环检测 + replan | Browser-Use (loop_detector) |
| Fallback LLM | Browser-Use |
| 元素自愈匹配 | Browser-Use (5级匹配), Stagehand (缓存自愈) |
| 页面变化检测 | Browser-Use (URL/focus 变化中断后续动作) |

---

## 4. Mimicry CLI 架构建议

### 4.1 推荐架构：混合模式（CLI Daemon + JSON-RPC + LLM Adapter）

```
┌─────────────────────────────────────────────────────┐
│                    LLM / Human                       │
│          (通过 CLI 命令或 MCP 协议交互)               │
└──────────────────────┬──────────────────────────────┘
                       │ CLI 命令 / JSON-RPC
                       ▼
┌─────────────────────────────────────────────────────┐
│              Mimicry CLI Daemon                       │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────┐  │
│  │ Command     │  │ Session      │  │ State      │  │
│  │ Parser      │  │ Manager      │  │ Inspector  │  │
│  └──────┬──────┘  └──────┬───────┘  └─────┬─────┘  │
│         │                │                 │         │
│         ▼                ▼                 ▼         │
│  ┌──────────────────────────────────────────────┐   │
│  │           Workflow Executor (existing)         │   │
│  │   ┌──────┐  ┌──────┐  ┌─────────────────┐   │   │
│  │   │Pause │  │Inject│  │ Breakpoints      │   │   │
│  │   │Control│  │Queue │  │ (block-level)    │   │   │
│  │   └──────┘  └──────┘  └─────────────────┘   │   │
│  └──────────────────────┬───────────────────────┘   │
│                         │ JSON-RPC                    │
└─────────────────────────┼───────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────┐
│            Python Sidecar (existing)                  │
│            Camoufox / Playwright                      │
└─────────────────────────────────────────────────────┘
```

### 4.2 核心设计决策

#### 1. CLI 作为统一接口（参考 Browser-Use CLI）

```bash
# 任务控制
mimicry run workflow.json          # 启动工作流
mimicry run --step                 # 单步模式
mimicry pause                      # 暂停执行
mimicry resume                     # 恢复
mimicry stop                       # 停止

# 状态检查（参考 Playwright MCP 的 inspect 能力）
mimicry state                      # 当前页面元素 + 执行位置
mimicry snapshot                   # accessibility tree
mimicry screenshot [path]          # 截图
mimicry console                    # 控制台日志
mimicry network                    # 网络请求
mimicry context                    # WorkflowContext 变量

# 动态操作（参考 Browser-Use 的 add_new_task）
mimicry inject click <selector>    # 中途插入点击
mimicry inject navigate <url>      # 中途插入导航
mimicry inject eval "js code"      # 中途执行 JS
mimicry inject block <json>        # 插入完整 Block

# 浏览器直接操作
mimicry click <index|selector>
mimicry type "text"
mimicry eval "document.title"
mimicry scroll down
```

#### 2. Daemon 架构（参考 Browser-Use）

- 首次命令启动后台进程
- 通过 Unix socket 通信（Windows 用 TCP）
- 浏览器会话持久化
- 支持多会话 (`--session`)

#### 3. 断点系统（参考 Playwright MCP 的 `browser_resume`）

```bash
mimicry run workflow.json --break-at 3    # 在 Block #3 暂停
mimicry run workflow.json --break-on-error # 错误时暂停
mimicry step                              # 执行下一个 Block
mimicry step 3                            # 执行接下来 3 个 Block
```

#### 4. LLM Adapter Layer

为 LLM 提供两种接入方式：

**方式 A: MCP Server 模式**（参考 Playwright MCP）
```json
{
  "mcpServers": {
    "mimicry": {
      "command": "mimicry",
      "args": ["--mcp"]
    }
  }
}
```
- 暴露所有 CLI 命令为 MCP tools
- 适合 Claude Desktop / Cursor / VS Code Copilot

**方式 B: CLI SKILL 模式**（参考 Playwright CLI + SKILLS）
- 提供 `SKILL.md` 文件描述所有命令
- LLM 读取 SKILL 后生成 CLI 命令
- 更省 token

#### 5. 注入队列（中途插入操作）

```python
# Executor 新增
class ExecutorState:
    inject_queue: list[Block]  # 优先执行队列
    pause_event: asyncio.Event
    breakpoints: set[int]      # Block index 断点
    step_mode: bool            # 单步模式

# 每个 Block 执行前检查
async def execute_block(self, block):
    # 1. 检查暂停
    await self.state.pause_event.wait()
    # 2. 检查断点
    if block.index in self.state.breakpoints:
        self.state.pause_event.clear()
        await self.notify_paused(block)
        await self.state.pause_event.wait()
    # 3. 检查注入队列
    while self.state.inject_queue:
        injected = self.state.inject_queue.pop(0)
        await self._execute_single(injected)
    # 4. 执行当前 Block
    result = await self._execute_single(block)
    # 5. 单步模式自动暂停
    if self.state.step_mode:
        self.state.pause_event.clear()
    return result
```

### 4.3 与现有架构的集成点

| Mimicry 现有组件 | CLI 模式中的角色 |
|-----------------|-----------------|
| Python Sidecar (`rpc/server.py`) | 已有 JSON-RPC，直接复用 |
| Workflow Executor (`engine/executor.py`) | 添加暂停/注入/断点能力 |
| Action Map (`engine/action_map.py`) | CLI 命令映射到 actions |
| Rust Backend (`src-tauri/`) | CLI daemon 可选用 Rust 或直接 Python |
| Browser Controller (`browser/controller.py`) | 底层不变 |

### 4.4 实现优先级

1. **P0**: CLI daemon + 基础命令 (run/pause/resume/stop/state/screenshot)
2. **P1**: 断点系统 + 单步执行
3. **P1**: 注入队列 (inject 命令)
4. **P2**: MCP Server 模式
5. **P2**: 网络/控制台日志查看
6. **P3**: SKILL.md + LLM 适配层
7. **P3**: 远程调试（WebSocket）

---

## 5. 关键启示

1. **Browser-Use 的 CLI daemon 模式是最佳参考** — 持久化进程 + socket 通信解决了延迟问题
2. **Playwright MCP 的工具分类值得借鉴** — core/devtools/network/storage 分层，按需加载
3. **暂停机制用 asyncio.Event 最简单** — Browser-Use 已验证这个方案
4. **MCP 和 CLI 不互斥** — `mimicry --mcp` 一个 flag 切换模式
5. **Stagehand 的 "渐进 AI" 思想适合 Mimicry** — 工作流是确定性的，LLM 仅在需要时介入
6. **不需要内置 LLM** — Mimicry 作为工具提供者，LLM 在外部（通过 CLI/MCP 调用）

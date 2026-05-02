# Dev CLI 调试接口文档

> **状态**: Implemented | **最后更新**: 2026-05-02

## 概述

Mimicry 提供两套 CLI 工具：

| 工具 | 入口 | 用途 |
|---|---|---|
| **`cli.py`**（生产） | `python cli.py <command>` | Daemon + UDS 架构，是 LLM agent / MCP / 日常调试的**主入口** |
| **`dev_cli.py`**（开发） | `python dev_cli.py <command>` | 老开发调试工具，含 REPL / anti-detect 跑分；功能逐步收敛到 `cli.py` |

### 主入口：`cli.py`

`cli.py` 是基于 Daemon + UDS Socket 的生产级 CLI。核心命令（约 25 个），完整命令表见 [`sidecar/SKILL.md`](../../sidecar/SKILL.md)。

```bash
# Daemon 与启动
python cli.py daemon start          # 启动 daemon（首次命令时自动启动）
python cli.py daemon stop           # 优雅关闭 daemon + 浏览器
python cli.py daemon status         # 守护进程状态
python cli.py launch [--headless --proxy <url>]
python cli.py close
python cli.py sessions              # 列出活跃 session

# 交互
python cli.py navigate <url>
python cli.py click <selector> [--force]            # --force 跳过 actionability 检查
python cli.py type <selector> <text> [--no-humanize] # --no-humanize 用 fill() 替代敲键
python cli.py eval <js>
python cli.py screenshot [path]
python cli.py scroll <up|down|left|right> [amount]

# 工作流执行 + 调试
python cli.py run <file.json> [--step --break-at <id> ... --no-humanize]
python cli.py pause / resume / stop
python cli.py step [N]              # 单步 N 个节点（默认 1）
python cli.py state                 # 显示执行状态（paused/running、当前节点、断点）
python cli.py context               # 显示工作流变量
python cli.py inject '<json>'       # 注入一个 block 当前节点
python cli.py breakpoint add <id>   # 别名 bp
python cli.py breakpoint rm <id>
python cli.py breakpoint list

# 工具
python cli.py validate <file.json>  # 离线 schema 校验，无需 daemon（5/1 起输出为 JSON）
python cli.py --json <command>      # 任何命令机器可解析 JSON 输出
python cli.py -s <session> <command> # 路由到指定 session
python cli.py --mcp                 # 启动 MCP stdio 服务（自动映射 RPC 注册表，扣除 test.* 后约 70 个 MCP 工具）
```

### 三种运行模式

```
1. CLI + Daemon       cli.py ──UDS──► daemon.py ──► browser/actions.py ──► Camoufox
2. MCP Server         cli.py --mcp 或 mcp_server.py ──stdio MCP──► LLM Client (Cursor/Claude Desktop)
3. Tauri Sidecar      Tauri Shell ──stdio JSON-RPC──► main.py ──► browser/actions.py ──► Camoufox
```

三模式共享 `browser/actions.py` + `rpc/methods.py`：每加一个 RPC method 都自动在三模式中可用。

---

## LLM 驱动与交互式调试

针对基于 LLM Agent 构建交互式工作流：见 **[LLM 交互式驱动与自动化开发指南](llm-interactive-guide.md)**，包含降级策略（`--force` / `--no-humanize`）与 `eval` 兜底等模式。

---

## 旧版 Dev CLI (`dev_cli.py`)

`dev_cli.py` 允许直接操控 sidecar 组件（浏览器、工作流引擎、RPC），无需 Tauri 前端，也不依赖 daemon。**主路径已迁到 `cli.py`**，本工具仅在以下场景仍有价值：

- `anti-detect` 跑分：批量跑反检测站点 + 截图归档
- `blocks-test`：直接驱动 block 引擎做单元级冒烟
- `interactive` REPL：在一个进程内连续调试，免去重复启动开销

### 安装 & 启动

```bash
cd sidecar
source .venv/bin/activate           # 或 Windows .venv\Scripts\activate
python dev_cli.py --help
```

### 命令一览

| 命令 | 说明 | 示例 |
|---|---|---|
| `launch [--headless]` | 启动 Camoufox | `python dev_cli.py launch` |
| `close` | 关闭浏览器 | `python dev_cli.py close` |
| `status` | 浏览器状态 | `python dev_cli.py status` |
| `navigate <url>` | 导航 | `python dev_cli.py navigate https://example.com` |
| `screenshot [path]` | 截图 | `python dev_cli.py screenshot shot.png` |
| `import <file>` | 导入工作流 JSON | `python dev_cli.py import workflow.mimicry.json` |
| `export <file>` | 导出执行状态 | `python dev_cli.py export state.json` |
| `run <file>` | 运行工作流文件 | `python dev_cli.py run workflow.mimicry.json` |
| `run-inline <json>` | 运行 JSON 字符串 | `python dev_cli.py run-inline '{"name":"test",...}'` |
| `exec-status` | 执行状态 | `python dev_cli.py exec-status` |
| `stop` | 停止执行 | `python dev_cli.py stop` |
| `logs [--export <file>]` | 查看 / 导出会话日志 | `python dev_cli.py logs --export run.log` |
| `rpc <method> [params]` | 调用 RPC 方法 | `python dev_cli.py rpc browser.navigate '{"url":"…"}'` |
| `anti-detect` | 反检测跑分 | `python dev_cli.py anti-detect --screenshot-dir ./out` |
| `blocks-test` | Block 功能冒烟 | `python dev_cli.py blocks-test` |
| `interactive` | 交互式 REPL | `python dev_cli.py interactive` |

### 典型场景

#### 1. 导入并运行工作流

```bash
python dev_cli.py run my-workflow.mimicry.json
python dev_cli.py exec-status
python dev_cli.py logs --export debug.log
```

#### 2. 反检测跑分

```bash
python dev_cli.py anti-detect --screenshot-dir ./anti-detect-results
# 查看 ./anti-detect-results/report.json
```

#### 3. 交互式调试

```bash
python dev_cli.py interactive
mimicry> launch
mimicry> nav https://bot.sannysoft.com
mimicry> ss sannysoft.png
mimicry> rpc browser.get_text '{"selector": "h1"}'
mimicry> vars
mimicry> quit
```

#### 4. 直接调用 RPC

```bash
python dev_cli.py rpc browser.launch '{"headless": false}'
python dev_cli.py rpc browser.navigate '{"url": "https://example.com"}'
python dev_cli.py rpc browser.screenshot '{"path": "test.png"}'
python dev_cli.py rpc workflow.execute '{"workflow": {…}}'
python dev_cli.py rpc browser.close
```

### 可用 RPC 方法

`@rpc_method` 装饰器在 `sidecar/rpc/methods.py` + `sidecar/browser/*.py` 中注册了 71 个方法，列出方式：

```bash
# 错的方法名会列出所有可用
python dev_cli.py rpc unknown_method
# Available: browser.click, browser.close, browser.dblclick, ...
```

### 反检测测试站点

| 站点 | 检测项目 | 自动判定 |
|---|---|---|
| `bot.sannysoft.com` | 通用 Bot 检测 | 红色单元格 ≤ 2 = PASS |
| `creepjs` | 高级指纹分析 | 仅截图（人工审查） |
| `browserleaks.com/webrtc` | WebRTC IP 泄露 | 无本地 IP = PASS |
| `pixelscan.net` | 指纹一致性 | 无 "inconsistent" = PASS |
| `browserscan.net` | 综合浏览器扫描 | 仅截图 |

更多反检测能力与跑分结果：[`docs/anti-detection.md`](anti-detection.md)。

---

## 工作流文件格式

工作流是 canonical 节点图（详见 [`block-api.md`](block-api.md)）。最小示例（`.mimicry.json`）：

```json
{
  "id": "wf-1",
  "name": "My Workflow",
  "nodes": [
    {
      "id": "n1",
      "kind": "action",
      "action": "Navigate",
      "position": { "x": 0, "y": 0 },
      "data": { "url": "https://example.com" }
    },
    {
      "id": "n2",
      "kind": "action",
      "action": "Click",
      "position": { "x": 200, "y": 0 },
      "data": { "selector": "#submit" }
    }
  ],
  "edges": [
    { "id": "e1", "source": "n1", "target": "n2" }
  ]
}
```

> **历史 flat 格式**（`{type: "action", data: {action, params: {url}}}`）已弃用。Sidecar 通过 Rust transform 层 `legacy.rs` 兼容旧文件，新文件一律用 canonical。


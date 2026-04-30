# Dev CLI 调试接口文档

## 概述

Mimicry 提供两套 CLI 工具：

| 工具 | 入口 | 用途 |
|------|------|------|
| **`cli.py`** (新) | `python cli.py <command>` | 生产级 CLI + Daemon 架构，LLM Agent 首选 |
| **`dev_cli.py`** (旧) | `python dev_cli.py <command>` | 开发调试，交互式 REPL |

### 新 CLI 架构 (`cli.py`)

`cli.py` 是基于 Daemon + UDS Socket 的生产级 CLI。详见 [`sidecar/SKILL.md`](../sidecar/SKILL.md)。

```bash
mimicry daemon start       # 启动守护进程
mimicry launch             # 启动浏览器
mimicry navigate <url>     # 导航
mimicry click <selector>   # 点击
mimicry type <sel> <text>  # 输入
mimicry eval <js>          # 执行 JS
mimicry screenshot [path]  # 截图
mimicry pause / resume     # 暂停/恢复工作流
mimicry step [N]           # 单步执行
mimicry inject '<json>'    # 运行时注入
mimicry breakpoint add <id># 断点
mimicry --mcp              # MCP 模式（52 个工具）
```

三种运行模式：
1. **CLI + Daemon**: `cli.py` → UDS socket → `daemon.py` → Browser
2. **MCP Server**: `cli.py --mcp` → stdio → LLM Client (Cursor/Claude Desktop)
3. **Tauri Sidecar**: `main.py` → stdio JSON-RPC → Tauri 前端（原模式）

---

### LLM 驱动与交互式调试

针对基于 LLM 与 Agent 构建交互工作流的情况，请参阅专门的 **[LLM 交互式驱动与自动化开发指南](llm-interactive-guide.md)**，介绍如何结合 CLI 和 MCP 逐步调试浏览器。

---

### 旧版 Dev CLI (`dev_cli.py`)

`dev_cli.py` 是开发调试命令行工具，允许直接操控 sidecar 组件（浏览器、工作流引擎、RPC），无需启动 Tauri 前端。

## 安装 & 启动

```bash
cd sidecar
# 激活虚拟环境
.venv\Scripts\activate   # Windows
source .venv/bin/activate # Linux/Mac

# 查看帮助
python dev_cli.py --help
```

## 命令一览

| 命令 | 说明 | 示例 |
|------|------|------|
| `launch` | 启动 Camoufox 浏览器 | `python dev_cli.py launch` |
| `launch --headless` | 无头模式启动 | `python dev_cli.py launch --headless` |
| `close` | 关闭浏览器 | `python dev_cli.py close` |
| `status` | 查看浏览器状态 | `python dev_cli.py status` |
| `navigate <url>` | 导航到指定 URL | `python dev_cli.py navigate https://example.com` |
| `screenshot [path]` | 截图 | `python dev_cli.py screenshot shot.png` |
| `import <file>` | 导入工作流 JSON | `python dev_cli.py import workflow.mimicry.json` |
| `export <file>` | 导出执行状态 | `python dev_cli.py export state.json` |
| `run <file>` | 运行工作流文件 | `python dev_cli.py run workflow.mimicry.json` |
| `run-inline <json>` | 运行 JSON 字符串 | `python dev_cli.py run-inline '{"name":"test",...}'` |
| `exec-status` | 查看执行状态 | `python dev_cli.py exec-status` |
| `stop` | 停止执行 | `python dev_cli.py stop` |
| `logs` | 查看会话日志 | `python dev_cli.py logs` |
| `logs --export <file>` | 导出日志到文件 | `python dev_cli.py logs --export run.log` |
| `rpc <method> [params]` | 调用 RPC 方法 | `python dev_cli.py rpc ping` |
| `anti-detect` | 反检测站点测试 | `python dev_cli.py anti-detect` |
| `blocks-test` | Block 功能测试 | `python dev_cli.py blocks-test` |
| `interactive` | 交互式 REPL | `python dev_cli.py interactive` |

## 典型调试流程

### 1. 导入并运行工作流
```bash
python dev_cli.py run my-workflow.mimicry.json
python dev_cli.py exec-status
python dev_cli.py logs --export debug.log
```

### 2. 反检测测试
```bash
python dev_cli.py anti-detect --screenshot-dir ./anti-detect-results
# 查看 ./anti-detect-results/report.json
```

### 3. 交互式调试
```bash
python dev_cli.py interactive
mimicry> launch
mimicry> nav https://bot.sannysoft.com
mimicry> ss sannysoft.png
mimicry> rpc browser.get_text '{"selector": "h1"}'
mimicry> vars
mimicry> quit
```

### 4. 直接调用 RPC 方法
```bash
python dev_cli.py rpc browser.launch '{"headless": false}'
python dev_cli.py rpc browser.navigate '{"url": "https://example.com"}'
python dev_cli.py rpc browser.screenshot '{"path": "test.png"}'
python dev_cli.py rpc workflow.execute '{"workflow": {...}}'
python dev_cli.py rpc browser.close
```

## 可用 RPC 方法列表

运行以下命令查看所有已注册方法：
```bash
python dev_cli.py rpc unknown_method
# 输出: Available: browser.click, browser.close, browser.dblclick, ...
```

## 反检测测试站点

| 站点 | 检测项目 | 自动判定 |
|------|---------|---------|
| bot.sannysoft.com | 通用 Bot 检测 | 红色单元格 ≤ 2 = PASS |
| creepjs | 高级指纹分析 | 仅截图（需人工审查） |
| browserleaks.com/webrtc | WebRTC IP 泄露 | 无本地 IP = PASS |
| pixelscan.net | 指纹一致性 | 无 "inconsistent" = PASS |
| browserscan.net | 综合浏览器扫描 | 仅截图（需人工审查） |

## 文件格式

工作流文件格式 (`.mimicry.json`):
```json
{
  "name": "My Workflow",
  "nodes": [
    {
      "id": "1",
      "type": "action",
      "data": {
        "action": "Navigate",
        "params": {"url": "https://example.com"}
      }
    }
  ],
  "edges": [
    {"source": "1", "target": "2"}
  ]
}
```

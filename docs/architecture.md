# Mimicry 架构概览

> **状态**: Partial | **最后更新**: 2026-04-27

> 现实边界：Tauri shell、Vue 前端、SQLite、Rust ↔ Python JSON-RPC、Camoufox 控制器、录制和执行器已有实现；执行日志持久化、完整 PyInstaller 嵌入和部分高级 workflow 语义仍在完善。

---

## 整体架构

```
┌──────────────────────────────────────────────────────────┐
│                     Tauri v2 Shell                       │
│                                                          │
│  ┌─────────────────────┐   ┌──────────────────────────┐  │
│  │     Rust Core        │   │    Vue 3 WebView         │  │
│  │                      │   │                          │  │
│  │  ┌───────────────┐  │   │  ┌────────────────────┐  │  │
│  │  │ Tauri Commands│  │   │  │ Vue Flow Canvas    │  │  │
│  │  │  - browser    │  │   │  │  - Block 拖拽编辑   │  │  │
│  │  │  - workflow   │◄─┼───┼─►│  - 连线/分组       │  │  │
│  │  │  - system     │  │   │  └────────────────────┘  │  │
│  │  └───────────────┘  │   │  ┌────────────────────┐  │  │
│  │  ┌───────────────┐  │   │  │ Monaco Editor      │  │  │
│  │  │ SQLite (DB)   │  │   │  │  - JSON 编辑       │  │  │
│  │  │  - workflows  │  │   │  │  - Schema 验证     │  │  │
│  │  │  - settings   │  │   │  └────────────────────┘  │  │
│  │  └───────────────┘  │   │  ┌────────────────────┐  │  │
│  │  ┌───────────────┐  │   │  │ Pinia Stores       │  │  │
│  │  │ Logger        │  │   │  │  - workflow store   │  │  │
│  │  │  (tracing)    │  │   │  │  - browser store    │  │  │
│  │  └───────────────┘  │   │  └────────────────────┘  │  │
│  │  ┌───────────────┐  │   │  ┌────────────────────┐  │  │
│  │  │ Sidecar Mgr   │  │   │  │ TailwindCSS + UI   │  │  │
│  │  │  - lifecycle   │  │   │  └────────────────────┘  │  │
│  │  │  - JSON-RPC   │  │   └──────────────────────────┘  │
│  │  └───────┬───────┘  │                                 │
│  └──────────┼──────────┘                                 │
│             │ stdio (JSON-RPC 2.0)                       │
│  ┌──────────▼──────────────────────┐                     │
│  │   Python Sidecar (PyInstaller)  │                     │
│  │                                 │                     │
│  │  ┌─────────────────────────┐   │                     │
│  │  │ RPC Server (stdio)      │   │                     │
│  │  │  - method registry      │   │                     │
│  │  └─────────────────────────┘   │                     │
│  │  ┌─────────────────────────┐   │                     │
│  │  │ Browser Controller      │   │                     │
│  │  │  - Camoufox lifecycle   │   │    ┌──────────┐     │
│  │  │  - Page actions ────────┼───┼───►│ Camoufox │     │
│  │  │  - Element selector     │   │    │ Browser  │     │
│  │  └─────────────────────────┘   │    └──────────┘     │
│  │  ┌─────────────────────────┐   │                     │
│  │  │ Recorder                │   │                     │
│  │  │  - DOM event capture    │   │                     │
│  │  │  - Action stream        │   │                     │
│  │  └─────────────────────────┘   │                     │
│  │  ┌─────────────────────────┐   │                     │
│  │  │ Executor (JSON 引擎)    │   │                     │
│  │  │  - 工作流 JSON 解释执行  │   │                     │
│  │  └─────────────────────────┘   │                     │
│  └─────────────────────────────────┘                     │
└──────────────────────────────────────────────────────────┘
```

---

## 模块职责

### Rust Core（src-tauri/src/）

| 模块 | 路径 | 职责 |
|------|------|------|
| Commands | `commands/` | Tauri 命令层，前端通过 `invoke()` 调用 |
| Transform | `transform/` | 工作流格式转化层：4 格式互转、格式检测、自动布局。详见 [transform-layer.md](design/transform-layer.md) |
| DB | `db/` | SQLite 数据访问，工作流 CRUD、配置存储 |
| IPC | `ipc/` | Sidecar 进程管理 + JSON-RPC 客户端 |
| Logger | `logger.rs` | tracing 日志系统，文件旋转输出 |
| Error | `error.rs` | 全局错误类型定义 |

### Vue 3 前端（src/）

| 模块 | 路径 | 职责 |
|------|------|------|
| Views | `views/` | 页面级组件（编辑器视图等） |
| Components | `components/` | Block 节点、布局、工具栏 |
| Stores | `stores/` | Pinia 状态管理（workflow / browser） |
| Types | `types/` | TypeScript 类型定义 |

### Python Sidecar（sidecar/）

| 模块 | 路径 | 职责 |
|------|------|------|
| RPC | `rpc/` | stdio JSON-RPC 服务端，方法注册 |
| RPC Protocol | `rpc/protocol.py` | 长度前缀帧协议（Daemon ↔ CLI 通信） |
| Browser | `browser/` | Camoufox 控制器、页面操作、录制器 |
| Engine | `engine/` | 工作流 JSON 解释执行引擎 |
| Engine State | `engine/executor_state.py` | 执行控制状态（暂停/单步/断点/注入队列） |
| Daemon | `daemon.py` | UDS Socket 守护进程，CLI 模式后端 |
| CLI | `cli.py` | 命令行客户端，25+ 子命令 |
| MCP Server | `mcp_server.py` | MCP stdio 服务器，52 个工具自动映射 |
| Utils | `utils/` | 日志等工具函数 |

### Sidecar 三种入口模式

```
模式 1: Tauri Sidecar（默认）
  Tauri Shell ──stdio JSON-RPC──► main.py ──► browser/actions.py ──► Camoufox

模式 2: CLI + Daemon
  LLM Agent ──shell──► cli.py ──UDS socket──► daemon.py ──► browser/actions.py ──► Camoufox

模式 3: MCP Server
  LLM Client ──stdio MCP──► mcp_server.py ──► browser/actions.py ──► Camoufox
```

三种模式共享同一个 `browser/actions.py` 适配层和 `rpc/methods.py` 方法注册表。

---

## IPC 通信

前端与 Rust、Rust 与 Python 之间采用不同的通信方式：

```
Vue 3 WebView  ──invoke()──►  Rust Core  ──stdio JSON-RPC──►  Python Sidecar
               ◄──event()──              ◄───response───
```

### 前端 ↔ Rust

Tauri v2 的 `invoke()` / `emit()` 机制：

```typescript
// 前端调用 Rust 命令
const result = await invoke('browser_navigate', { url: 'https://example.com' });

// 前端监听 Rust 事件
listen('browser-status', (event) => {
  console.log(event.payload);
});
```

### Rust ↔ Python Sidecar

JSON-RPC 2.0 over stdio：

```json
// Request (Rust → Python)
{"jsonrpc": "2.0", "id": 1, "method": "browser.navigate", "params": {"url": "https://example.com"}}

// Response (Python → Rust)
{"jsonrpc": "2.0", "id": 1, "result": {"success": true, "url": "https://example.com"}}
```

---

## 存储

使用 SQLite（rusqlite）存储：

| 表 | 内容 | 状态 |
|----|------|------|
| `workflows` | 工作流元数据 + JSON 内容 | Implemented |
| `settings` | 应用配置（键值对） | Implemented |
| `recent_files` | 最近打开文件记录 | Implemented |
| `profiles` | 浏览器 Profile 配置和隔离数据目录 | Implemented |
| `execution_logs` | 执行历史记录 | Planned |

---

## 构建与打包

```
开发模式:  cargo tauri dev
构建产物:  cargo tauri build
Sidecar:   开发期使用 Python 环境；PyInstaller 单文件打包已有 groundwork，完整嵌入仍在完善
```

---

## 相关文档

- [设计决策记录](./design/decisions.md)
- [Block 体系设计](./design/block-system.md)
- [MVP 实施计划](./plans/mimicry-mvp.md)

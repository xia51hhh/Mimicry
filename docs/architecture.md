# Mimicry 架构概览

> **状态**: Draft | **最后更新**: 2026-04-17

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
| Browser | `browser/` | Camoufox 控制器、页面操作、录制器 |
| Engine | `engine/` | 工作流 JSON 解释执行引擎 |
| Utils | `utils/` | 日志等工具函数 |

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

| 表 | 内容 |
|----|------|
| `workflows` | 工作流元数据 + JSON 内容 |
| `settings` | 应用配置（键值对） |
| `execution_logs` | 执行历史记录 |

---

## 构建与打包

```
开发模式:  cargo tauri dev
构建产物:  cargo tauri build
Sidecar:   PyInstaller → 单文件可执行文件 → 嵌入 Tauri 资源
```

---

## 相关文档

- [设计决策记录](./design/decisions.md)
- [Block 体系设计](./design/block-system.md)
- [MVP 实施计划](./plans/mimicry-mvp.md)

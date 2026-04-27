# Phase 2: 功能推进 — 从"可靠"到"可用"

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完善基础设施（错误传播、进度事件、心跳）、Profile 闭环、CLI 接口、Canvas↔JSON 双向同步、工作流执行增强、录制增强

**Architecture:**
- Sidecar 保持 Python 不变（Camoufox 硬性锁定），基础设施层优化启动速度、错误链路、进度事件
- Profile 完整 CRUD 通过 RPC → Rust SQLite → 前端 UI 闭环
- CLI 基于 argparse 独立入口，结构化 JSON 输出
- Canvas↔JSON 双向同步通过 debounced watcher + JSON Schema 校验
- 工作流执行增强：download 竞态修复、断点续执行、结构化日志
- 录制增强：实时预览、iframe 穿透、选择器评分

**Tech Stack:** Python 3.11+, Camoufox (Playwright), Rust/Tauri v2, Vue 3, TypeScript, Pinia, Vue Flow, Monaco Editor, SQLite (rusqlite), dagre

---

## 文件结构

### 新建文件

**Python sidecar:**
- `sidecar/cli.py` — 正式 CLI 入口（argparse）
- `sidecar/tests/test_cli.py` — CLI 测试
- `sidecar/tests/test_profile_rpc.py` — Profile RPC 测试

**Rust:**
- `src-tauri/src/db/profiles.rs` — Profile SQLite CRUD
- `src-tauri/src/commands/profiles.rs` — Profile Tauri commands

**前端:**
- `src/components/ProfileManager.vue` — Profile 管理 UI
- `src/components/ProfileDialog.vue` — Profile 创建/编辑对话框
- `src/stores/profiles.ts` — Profile Pinia store
- `src/components/editor/ExecutionLog.vue` — 执行日志面板
- `src/components/editor/RecordingPreview.vue` — 录制实时预览面板

### 修改文件

**Python sidecar:**
- `sidecar/main.py` — 延迟 import 优化
- `sidecar/rpc/server.py` — 添加 notification 发送能力 + 心跳
- `sidecar/rpc/methods.py` — 注册 Profile RPC 方法
- `sidecar/browser/actions.py` — 注册新 RPC 方法（profile CRUD、进度事件）
- `sidecar/browser/controller.py` — handle_download 修复（预注册 listener）
- `sidecar/browser/profile.py` — Profile 增删改查本地操作
- `sidecar/browser/recorder.py` — iframe 穿透、选择器评分
- `sidecar/engine/executor.py` — 进度 notification、断点续执行、步骤级重试

**Rust:**
- `src-tauri/src/lib.rs` — 注册新 commands、心跳线程
- `src-tauri/src/ipc/sidecar.rs` — 心跳检测 + 自动重启、强类型 RPC
- `src-tauri/src/ipc/jsonrpc.rs` — 添加 notification 类型
- `src-tauri/src/db/schema.rs` — 添加 profiles 表
- `src-tauri/src/db/mod.rs` — 导出 profiles 模块
- `src-tauri/src/commands/mod.rs` — 导出 profiles 模块
- `src-tauri/src/commands/browser.rs` — browser_launch 支持 profile 参数
- `src-tauri/src/error.rs` — 结构化错误（error_code 字段）

**前端:**
- `src/stores/workflow.ts` — Canvas↔JSON 双向同步 watcher
- `src/stores/browser.ts` — launch 传 profile、录制预览事件
- `src/stores/execution.ts` — 监听进度事件替代轮询、结构化日志
- `src/views/EditorView.vue` — 集成 ProfileManager、ExecutionLog
- `src/components/editor/BottomPanel.vue` — 日志面板集成
- `src/components/editor/PropertyPanel.vue` — JSON 编辑同步

---

# Direction 1: Sidecar 基础设施优化

## Task Group 1.1: 启动速度优化

### Task 1: Sidecar 延迟 import

**Files:**
- Modify: `sidecar/main.py`
- Modify: `sidecar/browser/actions.py`
- Test: `sidecar/tests/test_rpc.py`

- [ ] **Step 1: 写启动时间基准测试**

在 `sidecar/tests/test_rpc.py` 中追加：

```python
import time
import subprocess
import sys

def test_sidecar_startup_time():
    """Sidecar should respond to ping within 2 seconds."""
    start = time.time()
    proc = subprocess.Popen(
        [sys.executable, "-u", "main.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.join(os.path.dirname(__file__), ".."),
    )
    # Send ping
    req = '{"jsonrpc":"2.0","id":1,"method":"ping"}\n'
    proc.stdin.write(req.encode())
    proc.stdin.flush()
    line = proc.stdout.readline().decode()
    elapsed = time.time() - start
    proc.kill()
    assert '"pong"' in line
    assert elapsed < 2.0, f"Startup took {elapsed:.2f}s, expected < 2s"
```

- [ ] **Step 2: 运行测试验证当前基线**

```bash
cd sidecar && python -m pytest tests/test_rpc.py::test_sidecar_startup_time -v
```

- [ ] **Step 3: 重构 main.py 延迟 import**

将 `sidecar/main.py` 改为延迟加载重模块：

```python
import sys
import json
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="DEBUG", format="{time:HH:mm:ss} | {level:<7} | {message}")
logger.add("mimicry-sidecar.log", rotation="10 MB", retention="3 days", level="DEBUG")


def main():
    logger.info("Mimicry sidecar starting")
    # Lazy import: browser/actions imports camoufox which is heavy
    from rpc.server import JsonRpcServer
    import browser.actions  # registers browser RPC methods
    import dsl.rpc_methods  # registers DSL RPC methods
    server = JsonRpcServer()
    server.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试验证改善**

```bash
cd sidecar && python -m pytest tests/test_rpc.py::test_sidecar_startup_time -v
```

- [ ] **Step 5: Commit**

```bash
git add sidecar/main.py sidecar/tests/test_rpc.py
git commit -m "perf: lazy import in sidecar main.py to reduce startup time"
```

---

## Task Group 1.2: 错误传播链路

### Task 2: Python 结构化错误

**Files:**
- Modify: `sidecar/rpc/server.py`
- Test: `sidecar/tests/test_rpc.py`

- [ ] **Step 1: 写结构化错误测试**

在 `sidecar/tests/test_rpc.py` 中追加：

```python
def test_error_response_has_structured_fields():
    """Error responses should include error_code and context."""
    server = JsonRpcServer()

    @rpc_method("test.fail")
    def fail_method():
        raise ValueError("bad input")

    raw = '{"jsonrpc":"2.0","id":1,"method":"test.fail"}'
    resp = json.loads(server.handle_request(raw))
    assert resp["error"]["code"] == -32000
    assert "bad input" in resp["error"]["message"]
    assert "error_type" in resp["error"]["data"]
    assert resp["error"]["data"]["error_type"] == "ValueError"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd sidecar && python -m pytest tests/test_rpc.py::test_error_response_has_structured_fields -v
```

Expected: FAIL — `data` field 不存在

- [ ] **Step 3: 修改 rpc/server.py 返回结构化错误**

在 `JsonRpcServer.handle_request` 中修改错误处理：

```python
except Exception as e:
    logger.exception(f"Error in method {method}")
    return json.dumps({
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {
            "code": -32000,
            "message": str(e),
            "data": {
                "error_type": type(e).__name__,
                "method": method,
            }
        }
    })
```

对 async 方法的 `_run` 内部也做相同修改。

- [ ] **Step 4: 运行测试验证通过**

```bash
cd sidecar && python -m pytest tests/test_rpc.py -v -k "error"
```

- [ ] **Step 5: Commit**

```bash
git add sidecar/rpc/server.py sidecar/tests/test_rpc.py
git commit -m "feat: structured error responses with error_type in RPC"
```

### Task 3: Rust AppError 结构化序列化

**Files:**
- Modify: `src-tauri/src/error.rs`

- [ ] **Step 1: 修改 AppError 序列化为结构化 JSON**

```rust
impl serde::Serialize for AppError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        use serde::ser::SerializeMap;
        let mut map = serializer.serialize_map(Some(3))?;
        let (kind, message) = match self {
            AppError::Database(e) => ("database", e.to_string()),
            AppError::Sidecar(s) => ("sidecar", s.clone()),
            AppError::Json(e) => ("json", e.to_string()),
            AppError::Io(e) => ("io", e.to_string()),
        };
        map.serialize_entry("kind", kind)?;
        map.serialize_entry("message", &message)?;
        map.serialize_entry("display", &self.to_string())?;
        map.end()
    }
}
```

- [ ] **Step 2: Commit**

```bash
git add src-tauri/src/error.rs
git commit -m "feat: structured AppError serialization with kind/message/display"
```

---

## Task Group 1.3: 进度事件

### Task 4: Python 端 notification 发送能力

**Files:**
- Modify: `sidecar/rpc/server.py`
- Test: `sidecar/tests/test_rpc.py`

- [ ] **Step 1: 写 notification 发送测试**

```python
import io
from unittest.mock import patch

def test_server_send_notification():
    """Server should be able to send JSON-RPC notifications to stdout."""
    server = JsonRpcServer()
    buf = io.StringIO()
    with patch("sys.stdout", buf):
        server.send_notification("workflow.progress", {"step": 1, "total": 5, "action": "Click"})
    line = buf.getvalue().strip()
    msg = json.loads(line)
    assert msg.get("jsonrpc") == "2.0"
    assert "id" not in msg  # notifications have no id
    assert msg["method"] == "workflow.progress"
    assert msg["params"]["step"] == 1
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd sidecar && python -m pytest tests/test_rpc.py::test_server_send_notification -v
```

- [ ] **Step 3: 在 JsonRpcServer 添加 send_notification 方法**

```python
def send_notification(self, method: str, params: dict | None = None):
    """Send a JSON-RPC notification (no id, no response expected)."""
    msg = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    self._write(json.dumps(msg))
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd sidecar && python -m pytest tests/test_rpc.py::test_server_send_notification -v
```

- [ ] **Step 5: Commit**

```bash
git add sidecar/rpc/server.py sidecar/tests/test_rpc.py
git commit -m "feat: JSON-RPC notification sending capability in sidecar"
```

### Task 5: Executor 发送进度 notification

**Files:**
- Modify: `sidecar/engine/executor.py`
- Modify: `sidecar/browser/actions.py`
- Test: `sidecar/tests/test_executor.py`

- [ ] **Step 1: 写进度回调测试**

```python
def test_executor_progress_callback(self):
    """Executor should call progress_callback on each step."""
    progress_events = []

    def on_progress(event):
        progress_events.append(event)

    self.executor.progress_callback = on_progress
    workflow = {
        "name": "test",
        "nodes": [
            {"action": "Navigate", "url": "https://example.com"},
            {"action": "Screenshot", "filename": "test.png"},
        ]
    }
    self.executor.execute(workflow)
    assert len(progress_events) >= 2
    assert progress_events[0]["step"] == 0
    assert progress_events[0]["action"] == "open"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd sidecar && python -m pytest tests/test_executor.py -v -k "progress_callback"
```

- [ ] **Step 3: 给 WorkflowExecutor 添加 progress_callback**

在 `WorkflowExecutor.__init__` 中添加：
```python
self.progress_callback: callable | None = None
```

在 `_execute_node` 方法开头（logger.debug 之后）添加：
```python
if self.progress_callback:
    self.progress_callback({
        "step": self._ctx.step_index,
        "total": self._ctx.total_steps,
        "action": action,
        "nodeId": node.get("id"),
        "status": "running",
    })
```

- [ ] **Step 4: 在 browser/actions.py 中连接 notification**

在 `browser/actions.py` 中修改 workflow_execute 方法（需要先获取 server 引用）：

```python
# At module level, add a reference that will be set by main.py
_server = None

def set_server(server):
    global _server
    _server = server

@rpc_method("workflow.execute")
def workflow_execute(workflow: dict):
    def on_progress(event):
        if _server:
            _server.send_notification("workflow.progress", event)
    _executor.progress_callback = on_progress
    return _executor.execute(workflow)
```

在 `main.py` 中，server 创建后调用 `browser.actions.set_server(server)`。

- [ ] **Step 5: 运行测试验证通过**

```bash
cd sidecar && python -m pytest tests/test_executor.py -v -k "progress_callback"
```

- [ ] **Step 6: Commit**

```bash
git add sidecar/engine/executor.py sidecar/browser/actions.py sidecar/main.py sidecar/tests/test_executor.py
git commit -m "feat: workflow execution progress notifications via JSON-RPC"
```

### Task 6: 前端监听进度事件替代轮询

**Files:**
- Modify: `src/stores/execution.ts`

- [ ] **Step 1: 修改 execution store 使用 Tauri event 监听**

在 `execute()` 函数中，用 Tauri event listener 替代 `setInterval` 轮询：

```typescript
import { listen, type UnlistenFn } from "@tauri-apps/api/event";

// 在 store 内部
let progressUnlisten: UnlistenFn | null = null;

async function listenProgress() {
  progressUnlisten = await listen<{
    step: number;
    total: number;
    action: string;
    nodeId?: string;
    status: string;
  }>("sidecar:workflow.progress", (event) => {
    const p = event.payload;
    const prevNodeId = currentNodeId.value;

    step.value = p.step;
    total.value = p.total;
    currentNodeId.value = p.nodeId || null;

    if (prevNodeId && prevNodeId !== currentNodeId.value) {
      completedNodeIds.value = new Set([...completedNodeIds.value, prevNodeId]);
    }

    addLog("info", `Step ${p.step + 1}/${p.total}: ${p.action}`, p.nodeId);
  });
}

function stopListening() {
  if (progressUnlisten) {
    progressUnlisten();
    progressUnlisten = null;
  }
}
```

在 `execute()` 中调用 `await listenProgress()` 替代 `startPolling()`。
在 `stop()` 和完成后调用 `stopListening()`。
保留 `pollStatus` 作为后备（进度事件丢失时的容错）。

- [ ] **Step 2: Commit**

```bash
git add src/stores/execution.ts
git commit -m "feat: listen to sidecar progress events instead of polling"
```

---

## Task Group 1.4: 心跳检测 + 自动重启

### Task 7: Sidecar 心跳 RPC 方法

**Files:**
- Modify: `sidecar/rpc/methods.py`
- Test: `sidecar/tests/test_rpc.py`

- [ ] **Step 1: 写心跳测试**

```python
def test_heartbeat_returns_timestamp():
    """heartbeat method should return current timestamp."""
    from rpc.methods import METHOD_REGISTRY
    result = METHOD_REGISTRY["heartbeat"]()
    assert "timestamp" in result
    assert "uptime_seconds" in result
    assert isinstance(result["timestamp"], float)
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd sidecar && python -m pytest tests/test_rpc.py::test_heartbeat_returns_timestamp -v
```

- [ ] **Step 3: 实现心跳方法**

在 `sidecar/rpc/methods.py` 中添加：

```python
import time

_start_time = time.time()

@rpc_method("heartbeat")
def heartbeat():
    return {
        "timestamp": time.time(),
        "uptime_seconds": round(time.time() - _start_time, 1),
    }
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd sidecar && python -m pytest tests/test_rpc.py::test_heartbeat_returns_timestamp -v
```

- [ ] **Step 5: Commit**

```bash
git add sidecar/rpc/methods.py sidecar/tests/test_rpc.py
git commit -m "feat: heartbeat RPC method with uptime tracking"
```

### Task 8: Rust 端心跳检测 + 自动重启

**Files:**
- Modify: `src-tauri/src/ipc/sidecar.rs`
- Modify: `src-tauri/src/lib.rs`

- [ ] **Step 1: 在 Sidecar 添加 heartbeat 检测方法**

在 `sidecar.rs` 的 `Sidecar` impl 中添加：

```rust
pub async fn is_alive(&mut self) -> bool {
    match self.call("heartbeat", None).await {
        Ok(_) => true,
        Err(_) => false,
    }
}

pub async fn ensure_alive(&mut self) -> Result<(), AppError> {
    if self.child.is_some() && !self.is_alive().await {
        tracing::warn!("Sidecar heartbeat failed, restarting...");
        self.stop().await;
    }
    self.ensure_started().await
}
```

- [ ] **Step 2: 修改 sidecar_call 使用 ensure_alive**

在 `src-tauri/src/commands/browser.rs` 中：

```rust
async fn sidecar_call(
    sidecar: State<'_, Mutex<Sidecar>>,
    method: &str,
    params: Option<serde_json::Value>,
) -> Result<serde_json::Value, AppError> {
    let mut sc = sidecar.lock().await;
    sc.ensure_alive().await?;
    sc.call(method, params).await
}
```

- [ ] **Step 3: 在 lib.rs 的 setup 中启动心跳定时器**

```rust
.setup(|app| {
    let handle = app.handle().clone();
    let sidecar_state = app.state::<Mutex<Sidecar>>();
    tauri::async_runtime::block_on(async {
        sidecar_state.lock().await.set_app_handle(handle.clone());
    });

    // Heartbeat timer: check every 30s
    let sidecar_for_heartbeat = app.state::<Mutex<Sidecar>>().inner().clone();
    tauri::async_runtime::spawn(async move {
        loop {
            tokio::time::sleep(std::time::Duration::from_secs(30)).await;
            let mut sc = sidecar_for_heartbeat.lock().await;
            if sc.is_alive().await {
                continue;
            }
            tracing::warn!("Sidecar heartbeat missed, attempting restart");
            sc.stop().await;
            // Will be restarted on next call via ensure_alive
        }
    });

    Ok(())
})
```

- [ ] **Step 4: Commit**

```bash
git add src-tauri/src/ipc/sidecar.rs src-tauri/src/commands/browser.rs src-tauri/src/lib.rs
git commit -m "feat: sidecar heartbeat detection with auto-restart"
```

---

## Task Group 1.5: RPC 类型安全

### Task 9: Rust 端强类型 RPC 请求/响应

**Files:**
- Create: `src-tauri/src/ipc/types.rs`
- Modify: `src-tauri/src/ipc/mod.rs`
- Modify: `src-tauri/src/commands/browser.rs`

- [ ] **Step 1: 创建 types.rs 定义 RPC 请求参数和响应类型**

```rust
use serde::{Deserialize, Serialize};

// --- Browser Launch ---
#[derive(Debug, Serialize)]
pub struct LaunchParams {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub headless: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub proxy: Option<ProxyConfig>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub profile: Option<ProfileConfig>,
}

#[derive(Debug, Serialize)]
pub struct ProxyConfig {
    pub server: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub username: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub password: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct ProfileConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub user_data_dir: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub fingerprint: Option<serde_json::Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub proxy: Option<ProxyConfig>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub os_target: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct BrowserStatus {
    pub connected: bool,
    pub url: Option<String>,
    pub pages: u32,
}

// --- Workflow ---
#[derive(Debug, Deserialize)]
pub struct ExecutionResult {
    pub success: bool,
    pub running: bool,
    pub step: u32,
    pub total: u32,
    pub error: Option<String>,
    pub variables: Option<serde_json::Value>,
}
```

- [ ] **Step 2: 更新 ipc/mod.rs 导出 types**

```rust
pub mod jsonrpc;
pub mod sidecar;
pub mod types;
```

- [ ] **Step 3: 在 browser.rs 中使用强类型**

```rust
use crate::ipc::types::{LaunchParams, BrowserStatus};

#[tauri::command]
pub async fn browser_launch(
    sidecar: State<'_, Mutex<Sidecar>>,
    headless: Option<bool>,
    profile: Option<serde_json::Value>,
) -> Result<serde_json::Value, AppError> {
    let params = LaunchParams {
        headless,
        proxy: None,
        profile: profile.and_then(|v| serde_json::from_value(v).ok()),
    };
    sidecar_call(sidecar, "browser.launch", Some(serde_json::to_value(params)?)).await
}
```

- [ ] **Step 4: Commit**

```bash
git add src-tauri/src/ipc/types.rs src-tauri/src/ipc/mod.rs src-tauri/src/commands/browser.rs
git commit -m "feat: strongly typed RPC request/response structs in Rust"
```

---

# Direction 2: Profile 完整闭环

## Task Group 2.1: Profile 后端

### Task 10: SQLite profiles 表

**Files:**
- Modify: `src-tauri/src/db/schema.rs`

- [ ] **Step 1: 在 schema.rs 添加 profiles 表**

```rust
pub fn init(conn: &Connection) -> rusqlite::Result<()> {
    conn.execute_batch(
        "CREATE TABLE IF NOT EXISTS workflows (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            nodes TEXT NOT NULL DEFAULT '[]',
            edges TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS recent_files (
            path TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            opened_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS profiles (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            fingerprint TEXT NOT NULL DEFAULT '{}',
            user_data_dir TEXT NOT NULL DEFAULT '',
            proxy TEXT,
            os_target TEXT NOT NULL DEFAULT 'windows',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );"
    )?;
    Ok(())
}
```

- [ ] **Step 2: Commit**

```bash
git add src-tauri/src/db/schema.rs
git commit -m "feat: add profiles table to SQLite schema"
```

### Task 11: Profile Rust CRUD

**Files:**
- Create: `src-tauri/src/db/profiles.rs`
- Modify: `src-tauri/src/db/mod.rs`

- [ ] **Step 1: 创建 profiles.rs**

```rust
use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Profile {
    pub id: String,
    pub name: String,
    pub fingerprint: serde_json::Value,
    pub user_data_dir: String,
    pub proxy: Option<serde_json::Value>,
    pub os_target: String,
    pub created_at: String,
    pub updated_at: String,
}

pub fn list(conn: &Connection) -> rusqlite::Result<Vec<Profile>> {
    let mut stmt = conn.prepare(
        "SELECT id, name, fingerprint, user_data_dir, proxy, os_target, created_at, updated_at
         FROM profiles ORDER BY updated_at DESC"
    )?;
    let rows = stmt.query_map([], |row| {
        let fp_str: String = row.get(2)?;
        let proxy_str: Option<String> = row.get(4)?;
        Ok(Profile {
            id: row.get(0)?,
            name: row.get(1)?,
            fingerprint: serde_json::from_str(&fp_str).unwrap_or(serde_json::Value::Object(Default::default())),
            user_data_dir: row.get(3)?,
            proxy: proxy_str.and_then(|s| serde_json::from_str(&s).ok()),
            os_target: row.get(5)?,
            created_at: row.get(6)?,
            updated_at: row.get(7)?,
        })
    })?;
    rows.collect()
}

pub fn get(conn: &Connection, id: &str) -> rusqlite::Result<Option<Profile>> {
    let mut stmt = conn.prepare(
        "SELECT id, name, fingerprint, user_data_dir, proxy, os_target, created_at, updated_at
         FROM profiles WHERE id = ?"
    )?;
    let mut rows = stmt.query_map(params![id], |row| {
        let fp_str: String = row.get(2)?;
        let proxy_str: Option<String> = row.get(4)?;
        Ok(Profile {
            id: row.get(0)?,
            name: row.get(1)?,
            fingerprint: serde_json::from_str(&fp_str).unwrap_or(serde_json::Value::Object(Default::default())),
            user_data_dir: row.get(3)?,
            proxy: proxy_str.and_then(|s| serde_json::from_str(&s).ok()),
            os_target: row.get(5)?,
            created_at: row.get(6)?,
            updated_at: row.get(7)?,
        })
    })?;
    rows.next().transpose()
}

pub fn create(conn: &Connection, profile: &Profile) -> rusqlite::Result<()> {
    conn.execute(
        "INSERT INTO profiles (id, name, fingerprint, user_data_dir, proxy, os_target, created_at, updated_at)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
        params![
            profile.id,
            profile.name,
            serde_json::to_string(&profile.fingerprint).unwrap_or_default(),
            profile.user_data_dir,
            profile.proxy.as_ref().map(|p| serde_json::to_string(p).unwrap_or_default()),
            profile.os_target,
            profile.created_at,
            profile.updated_at,
        ],
    )?;
    Ok(())
}

pub fn update(conn: &Connection, profile: &Profile) -> rusqlite::Result<()> {
    conn.execute(
        "UPDATE profiles SET name=?2, fingerprint=?3, user_data_dir=?4, proxy=?5, os_target=?6, updated_at=?7
         WHERE id=?1",
        params![
            profile.id,
            profile.name,
            serde_json::to_string(&profile.fingerprint).unwrap_or_default(),
            profile.user_data_dir,
            profile.proxy.as_ref().map(|p| serde_json::to_string(p).unwrap_or_default()),
            profile.os_target,
            profile.updated_at,
        ],
    )?;
    Ok(())
}

pub fn delete(conn: &Connection, id: &str) -> rusqlite::Result<()> {
    conn.execute("DELETE FROM profiles WHERE id = ?", params![id])?;
    Ok(())
}
```

- [ ] **Step 2: 更新 db/mod.rs**

```rust
pub mod profiles;
pub mod recent_files;
pub mod schema;
pub mod workflow;
```

- [ ] **Step 3: Commit**

```bash
git add src-tauri/src/db/profiles.rs src-tauri/src/db/mod.rs
git commit -m "feat: Profile CRUD operations in SQLite"
```

### Task 12: Profile Tauri Commands

**Files:**
- Create: `src-tauri/src/commands/profiles.rs`
- Modify: `src-tauri/src/commands/mod.rs`
- Modify: `src-tauri/src/lib.rs`

- [ ] **Step 1: 创建 commands/profiles.rs**

```rust
use rusqlite::Connection;
use tauri::State;
use tokio::sync::Mutex;
use crate::db::profiles::{self, Profile};
use crate::AppError;

#[tauri::command]
pub async fn profile_list(conn: State<'_, Mutex<Connection>>) -> Result<Vec<Profile>, AppError> {
    let conn = conn.lock().await;
    Ok(profiles::list(&conn)?)
}

#[tauri::command]
pub async fn profile_get(conn: State<'_, Mutex<Connection>>, id: String) -> Result<Option<Profile>, AppError> {
    let conn = conn.lock().await;
    Ok(profiles::get(&conn, &id)?)
}

#[tauri::command]
pub async fn profile_create(conn: State<'_, Mutex<Connection>>, profile: Profile) -> Result<Profile, AppError> {
    let conn = conn.lock().await;
    profiles::create(&conn, &profile)?;
    Ok(profile)
}

#[tauri::command]
pub async fn profile_update(conn: State<'_, Mutex<Connection>>, profile: Profile) -> Result<Profile, AppError> {
    let conn = conn.lock().await;
    profiles::update(&conn, &profile)?;
    Ok(profile)
}

#[tauri::command]
pub async fn profile_delete(conn: State<'_, Mutex<Connection>>, id: String) -> Result<(), AppError> {
    let conn = conn.lock().await;
    profiles::delete(&conn, &id)?;
    Ok(())
}
```

- [ ] **Step 2: 更新 commands/mod.rs**

```rust
pub mod browser;
pub mod file_ops;
pub mod profiles;
pub mod system;
pub mod workflow;
```

- [ ] **Step 3: 在 lib.rs 注册新 commands**

在 `invoke_handler` 的 `generate_handler!` 中添加：

```rust
commands::profiles::profile_list,
commands::profiles::profile_get,
commands::profiles::profile_create,
commands::profiles::profile_update,
commands::profiles::profile_delete,
```

- [ ] **Step 4: Commit**

```bash
git add src-tauri/src/commands/profiles.rs src-tauri/src/commands/mod.rs src-tauri/src/lib.rs
git commit -m "feat: Profile Tauri commands (CRUD)"
```

### Task 13: browser_launch 支持 profile_id 参数

**Files:**
- Modify: `src-tauri/src/commands/browser.rs`

- [ ] **Step 1: 修改 browser_launch 接受 profile_id 并查询 DB**

```rust
#[tauri::command]
pub async fn browser_launch(
    sidecar: State<'_, Mutex<Sidecar>>,
    conn: State<'_, Mutex<Connection>>,
    profile_id: Option<String>,
) -> Result<serde_json::Value, AppError> {
    let mut params = serde_json::json!({});

    if let Some(pid) = profile_id {
        let db = conn.lock().await;
        if let Some(profile) = crate::db::profiles::get(&db, &pid)? {
            params = serde_json::json!({
                "profile": {
                    "user_data_dir": profile.user_data_dir,
                    "fingerprint": profile.fingerprint,
                    "proxy": profile.proxy,
                    "os_target": profile.os_target,
                }
            });
        }
    }

    sidecar_call(sidecar, "browser.launch", Some(params)).await
}
```

- [ ] **Step 2: Commit**

```bash
git add src-tauri/src/commands/browser.rs
git commit -m "feat: browser_launch accepts profile_id, queries SQLite for config"
```

---

## Task Group 2.2: Profile 前端

### Task 14: Profile Pinia Store

**Files:**
- Create: `src/stores/profiles.ts`

- [ ] **Step 1: 创建 profiles store**

```typescript
import { defineStore } from "pinia";
import { ref } from "vue";
import { invoke } from "@tauri-apps/api/core";

export interface Profile {
  id: string;
  name: string;
  fingerprint: Record<string, unknown>;
  user_data_dir: string;
  proxy?: { server: string; username?: string; password?: string } | null;
  os_target: string;
  created_at: string;
  updated_at: string;
}

export const useProfileStore = defineStore("profiles", () => {
  const profiles = ref<Profile[]>([]);
  const loading = ref(false);
  const selectedId = ref<string | null>(null);

  async function fetchAll() {
    loading.value = true;
    try {
      profiles.value = await invoke<Profile[]>("profile_list");
    } finally {
      loading.value = false;
    }
  }

  async function create(profile: Omit<Profile, "created_at" | "updated_at">) {
    const now = new Date().toISOString();
    const full: Profile = { ...profile, created_at: now, updated_at: now };
    const result = await invoke<Profile>("profile_create", { profile: full });
    profiles.value = [result, ...profiles.value];
    return result;
  }

  async function update(profile: Profile) {
    profile.updated_at = new Date().toISOString();
    const result = await invoke<Profile>("profile_update", { profile });
    profiles.value = profiles.value.map((p) => (p.id === result.id ? result : p));
    return result;
  }

  async function remove(id: string) {
    await invoke("profile_delete", { id });
    profiles.value = profiles.value.filter((p) => p.id !== id);
    if (selectedId.value === id) selectedId.value = null;
  }

  return { profiles, loading, selectedId, fetchAll, create, update, remove };
});
```

- [ ] **Step 2: Commit**

```bash
git add src/stores/profiles.ts
git commit -m "feat: Profile Pinia store with Tauri invoke CRUD"
```

### Task 15: Profile 管理 UI

**Files:**
- Create: `src/components/ProfileManager.vue`
- Create: `src/components/ProfileDialog.vue`
- Modify: `src/views/EditorView.vue`

- [ ] **Step 1: 创建 ProfileDialog.vue**

```vue
<script setup lang="ts">
import { ref, watch } from "vue";
import type { Profile } from "../stores/profiles";

const props = defineProps<{
  open: boolean;
  profile?: Profile | null;
}>();

const emit = defineEmits<{
  close: [];
  save: [profile: Omit<Profile, "created_at" | "updated_at">];
}>();

const form = ref({
  id: "",
  name: "",
  os_target: "windows",
  fingerprint: {} as Record<string, unknown>,
  user_data_dir: "",
  proxy: null as Profile["proxy"],
});

watch(
  () => props.profile,
  (p) => {
    if (p) {
      form.value = { ...p };
    } else {
      form.value = {
        id: `profile_${Date.now()}`,
        name: "",
        os_target: "windows",
        fingerprint: {},
        user_data_dir: "",
        proxy: null,
      };
    }
  },
  { immediate: true }
);

function onSave() {
  emit("save", { ...form.value });
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div class="bg-[var(--bg-secondary)] rounded-lg p-6 w-[480px] shadow-xl">
        <h3 class="text-lg font-medium mb-4">{{ profile ? 'Edit Profile' : 'New Profile' }}</h3>

        <div class="space-y-3">
          <div>
            <label class="block text-xs mb-1 opacity-70">Name</label>
            <input v-model="form.name" class="w-full px-3 py-1.5 rounded bg-[var(--bg-primary)] border border-[var(--border-primary)]" />
          </div>
          <div>
            <label class="block text-xs mb-1 opacity-70">OS Target</label>
            <select v-model="form.os_target" class="w-full px-3 py-1.5 rounded bg-[var(--bg-primary)] border border-[var(--border-primary)]">
              <option value="windows">Windows</option>
              <option value="macos">macOS</option>
              <option value="linux">Linux</option>
            </select>
          </div>
        </div>

        <div class="flex justify-end gap-2 mt-6">
          <button @click="emit('close')" class="px-4 py-1.5 rounded border border-[var(--border-primary)]">Cancel</button>
          <button @click="onSave" class="px-4 py-1.5 rounded bg-[var(--accent-primary)] text-white">Save</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
```

- [ ] **Step 2: 创建 ProfileManager.vue**

```vue
<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useProfileStore, type Profile } from "../stores/profiles";
import ProfileDialog from "./ProfileDialog.vue";

const store = useProfileStore();
const showDialog = ref(false);
const editingProfile = ref<Profile | null>(null);

onMounted(() => store.fetchAll());

function onCreate() {
  editingProfile.value = null;
  showDialog.value = true;
}

function onEdit(profile: Profile) {
  editingProfile.value = profile;
  showDialog.value = true;
}

async function onSave(data: Omit<Profile, "created_at" | "updated_at">) {
  if (editingProfile.value) {
    await store.update({ ...editingProfile.value, ...data });
  } else {
    await store.create(data);
  }
  showDialog.value = false;
}

async function onDelete(id: string) {
  await store.remove(id);
}
</script>

<template>
  <div class="p-4">
    <div class="flex items-center justify-between mb-3">
      <h3 class="font-medium">Profiles</h3>
      <button @click="onCreate" class="px-3 py-1 text-sm rounded bg-[var(--accent-primary)] text-white">+ New</button>
    </div>

    <div v-if="store.loading" class="text-center py-4 opacity-50">Loading...</div>

    <div v-else class="space-y-2">
      <div
        v-for="p in store.profiles"
        :key="p.id"
        class="flex items-center justify-between p-3 rounded border border-[var(--border-primary)] hover:bg-[var(--bg-hover)] cursor-pointer"
        :class="{ 'border-[var(--accent-primary)]': store.selectedId === p.id }"
        @click="store.selectedId = p.id"
      >
        <div>
          <div class="font-medium text-sm">{{ p.name }}</div>
          <div class="text-xs opacity-50">{{ p.os_target }} · {{ p.id.slice(0, 12) }}</div>
        </div>
        <div class="flex gap-1">
          <button @click.stop="onEdit(p)" class="px-2 py-1 text-xs rounded hover:bg-[var(--bg-hover)]">Edit</button>
          <button @click.stop="onDelete(p.id)" class="px-2 py-1 text-xs rounded text-red-400 hover:bg-red-500/10">Delete</button>
        </div>
      </div>
    </div>

    <ProfileDialog :open="showDialog" :profile="editingProfile" @close="showDialog = false" @save="onSave" />
  </div>
</template>
```

- [ ] **Step 3: 在 EditorView.vue 中集成 ProfileManager**

在 toolbar 区域添加 Profile 选择器按钮，点击后展示 ProfileManager 侧面板（复用现有 panel 模式）。

- [ ] **Step 4: Commit**

```bash
git add src/components/ProfileManager.vue src/components/ProfileDialog.vue src/views/EditorView.vue
git commit -m "feat: Profile management UI (list, create, edit, delete)"
```

### Task 16: 前端 Launch 传 Profile

**Files:**
- Modify: `src/stores/browser.ts`

- [ ] **Step 1: 修改 launch 接受 profileId**

```typescript
async function launch(profileId?: string) {
    if (launching.value) return;

    if (!camoufoxInstalled.value) {
      const check = await checkCamoufox();
      if (!check.installed) return;
    }

    launching.value = true;
    try {
      await invoke("browser_launch", { profileId: profileId || null });
      connected.value = true;
    } catch (e) {
      console.error("Failed to launch browser:", e);
    } finally {
      launching.value = false;
    }
  }
```

- [ ] **Step 2: Commit**

```bash
git add src/stores/browser.ts
git commit -m "feat: browser launch with profile selection"
```

---

# Direction 3: CLI 接口

## Task Group 3.1: CLI 基础

### Task 17: 创建正式 CLI 入口

**Files:**
- Create: `sidecar/cli.py`
- Create: `sidecar/tests/test_cli.py`

- [ ] **Step 1: 写 CLI 基础测试**

```python
"""Tests for the Mimicry CLI."""
import subprocess
import sys
import os
import json
import pytest

CLI_PATH = os.path.join(os.path.dirname(__file__), "..", "cli.py")
SIDECAR_DIR = os.path.join(os.path.dirname(__file__), "..")


def run_cli(*args, input_data=None):
    """Run CLI command and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, CLI_PATH, *args],
        capture_output=True,
        text=True,
        cwd=SIDECAR_DIR,
        input=input_data,
    )
    return result.returncode, result.stdout, result.stderr


class TestCLIValidate:
    def test_validate_valid_workflow(self, tmp_path):
        wf = {"name": "test", "nodes": [{"id": "1", "type": "action", "action": "Navigate", "url": "https://example.com"}], "edges": []}
        f = tmp_path / "wf.json"
        f.write_text(json.dumps(wf))
        code, stdout, _ = run_cli("validate", str(f))
        assert code == 0
        result = json.loads(stdout)
        assert result["valid"] is True

    def test_validate_invalid_json(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("not json")
        code, stdout, _ = run_cli("validate", str(f))
        assert code == 1

    def test_validate_missing_nodes(self, tmp_path):
        f = tmp_path / "empty.json"
        f.write_text(json.dumps({"name": "test"}))
        code, stdout, _ = run_cli("validate", str(f))
        result = json.loads(stdout)
        assert result["valid"] is False
        assert "nodes" in result["errors"][0].lower()


class TestCLIHelp:
    def test_help_flag(self):
        code, stdout, _ = run_cli("--help")
        assert code == 0
        assert "mimicry" in stdout.lower() or "usage" in stdout.lower()

    def test_validate_help(self):
        code, stdout, _ = run_cli("validate", "--help")
        assert code == 0
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd sidecar && python -m pytest tests/test_cli.py -v
```

- [ ] **Step 3: 创建 cli.py**

```python
#!/usr/bin/env python3
"""
Mimicry CLI — 命令行工作流执行与管理工具

Usage:
    python cli.py validate <workflow.json>
    python cli.py run <workflow.json> [--headless]
    python cli.py export-report <workflow.json> -o report.html
    python cli.py profiles list|create|delete [args]
"""
import sys
import os
import json
import argparse
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")


def cmd_validate(args):
    """Validate a workflow JSON file."""
    try:
        with open(args.workflow, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(json.dumps({"valid": False, "errors": [f"Invalid JSON: {e}"]}))
        sys.exit(1)
    except FileNotFoundError:
        print(json.dumps({"valid": False, "errors": [f"File not found: {args.workflow}"]}))
        sys.exit(1)

    errors = []
    if "nodes" not in data or not isinstance(data.get("nodes"), list):
        errors.append("Missing or invalid 'nodes' array")
    if "edges" not in data:
        errors.append("Missing 'edges' array")

    # Validate each node has required fields
    from engine.action_map import FRONTEND_TO_BACKEND
    valid_actions = set(FRONTEND_TO_BACKEND.keys()) | set(FRONTEND_TO_BACKEND.values())

    for i, node in enumerate(data.get("nodes", [])):
        if not node.get("id"):
            errors.append(f"Node {i}: missing 'id'")
        action = node.get("action", "")
        if node.get("type", "action") == "action" and action and action not in valid_actions:
            errors.append(f"Node {i}: unknown action '{action}'")

    result = {"valid": len(errors) == 0, "errors": errors, "node_count": len(data.get("nodes", []))}
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)


def cmd_run(args):
    """Run a workflow."""
    from browser.controller import BrowserController
    from engine.executor import WorkflowExecutor

    with open(args.workflow, "r", encoding="utf-8") as f:
        workflow = json.load(f)

    browser = BrowserController()
    executor = WorkflowExecutor(browser)

    try:
        browser.launch(headless=args.headless)
        result = executor.execute(workflow)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        sys.exit(0 if result.get("success") else 1)
    finally:
        browser.close()


def cmd_export_report(args):
    """Run workflow and export HTML report."""
    from browser.controller import BrowserController
    from engine.executor import WorkflowExecutor

    with open(args.workflow, "r", encoding="utf-8") as f:
        workflow = json.load(f)

    browser = BrowserController()
    executor = WorkflowExecutor(browser)
    log_entries = []

    def on_progress(event):
        event["timestamp"] = time.time()
        log_entries.append(event)

    executor.progress_callback = on_progress

    try:
        browser.launch(headless=True)
        result = executor.execute(workflow)
    finally:
        browser.close()

    # Generate HTML report
    report = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Mimicry Report - {workflow.get('name', 'unnamed')}</title>
<style>body{{font-family:system-ui;max-width:800px;margin:2rem auto;padding:0 1rem}}
table{{width:100%;border-collapse:collapse}}th,td{{padding:8px;border:1px solid #ddd;text-align:left}}
.pass{{color:green}}.fail{{color:red}}</style></head>
<body><h1>Workflow Report: {workflow.get('name', 'unnamed')}</h1>
<p class="{'pass' if result.get('success') else 'fail'}">Result: {'PASS' if result.get('success') else 'FAIL'}</p>
<table><tr><th>Step</th><th>Action</th><th>Status</th></tr>"""

    for entry in log_entries:
        report += f"<tr><td>{entry.get('step', '?')}</td><td>{entry.get('action', '?')}</td><td>{entry.get('status', '?')}</td></tr>"

    report += f"""</table>
<h2>Variables</h2><pre>{json.dumps(result.get('variables', {}), indent=2, ensure_ascii=False, default=str)}</pre>
</body></html>"""

    output = args.output or "report.html"
    with open(output, "w", encoding="utf-8") as f:
        f.write(report)
    print(json.dumps({"report": output, "success": result.get("success")}))


def cmd_profiles(args):
    """Manage profiles (file-based, no Rust/SQLite needed)."""
    from browser.profile import BrowserProfile, get_profiles_dir, get_profile_data_dir
    import glob

    profiles_dir = get_profiles_dir()
    meta_pattern = str(profiles_dir / "*/profile.json")

    if args.profiles_command == "list":
        profiles = []
        for meta_file in glob.glob(meta_pattern):
            with open(meta_file, "r") as f:
                profiles.append(json.load(f))
        print(json.dumps(profiles, indent=2))

    elif args.profiles_command == "create":
        pid = args.id or f"profile_{int(time.time())}"
        profile = BrowserProfile(
            id=pid,
            name=args.name or pid,
            os_target=args.os or "windows",
        )
        profile.user_data_dir = get_profile_data_dir(pid)
        meta_path = os.path.join(profile.user_data_dir, "profile.json")
        with open(meta_path, "w") as f:
            json.dump(profile.to_dict(), f, indent=2)
        print(json.dumps(profile.to_dict(), indent=2))

    elif args.profiles_command == "delete":
        import shutil
        target = profiles_dir / args.id
        if target.exists():
            shutil.rmtree(target)
            print(json.dumps({"deleted": args.id}))
        else:
            print(json.dumps({"error": f"Profile not found: {args.id}"}))
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(prog="mimicry", description="Mimicry CLI — Browser automation workflow tool")
    sub = parser.add_subparsers(dest="command", required=True)

    # validate
    p_validate = sub.add_parser("validate", help="Validate a workflow JSON file")
    p_validate.add_argument("workflow", help="Path to workflow JSON file")

    # run
    p_run = sub.add_parser("run", help="Execute a workflow")
    p_run.add_argument("workflow", help="Path to workflow JSON file")
    p_run.add_argument("--headless", action="store_true", help="Run in headless mode")

    # export-report
    p_report = sub.add_parser("export-report", help="Execute workflow and export HTML report")
    p_report.add_argument("workflow", help="Path to workflow JSON file")
    p_report.add_argument("-o", "--output", help="Output HTML file path", default="report.html")

    # profiles
    p_profiles = sub.add_parser("profiles", help="Manage browser profiles")
    p_profiles_sub = p_profiles.add_subparsers(dest="profiles_command", required=True)

    p_profiles_list = p_profiles_sub.add_parser("list", help="List all profiles")

    p_profiles_create = p_profiles_sub.add_parser("create", help="Create a new profile")
    p_profiles_create.add_argument("--id", help="Profile ID")
    p_profiles_create.add_argument("--name", help="Profile display name")
    p_profiles_create.add_argument("--os", help="Target OS (windows/macos/linux)", default="windows")

    p_profiles_delete = p_profiles_sub.add_parser("delete", help="Delete a profile")
    p_profiles_delete.add_argument("id", help="Profile ID to delete")

    args = parser.parse_args()

    commands = {
        "validate": cmd_validate,
        "run": cmd_run,
        "export-report": cmd_export_report,
        "profiles": cmd_profiles,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd sidecar && python -m pytest tests/test_cli.py -v
```

- [ ] **Step 5: Commit**

```bash
git add sidecar/cli.py sidecar/tests/test_cli.py
git commit -m "feat: formal CLI entry point with validate/run/export-report/profiles"
```

---

# Direction 4: Canvas ↔ JSON 双向同步

## Task Group 4.1: Canvas → JSON 实时同步

### Task 18: Workflow Store JSON 输出 watcher

**Files:**
- Modify: `src/stores/workflow.ts`

- [ ] **Step 1: 在 workflow store 中添加 jsonText computed**

```typescript
import { watch, computed } from "vue";

// 在 store 内部添加
const jsonText = computed(() => {
  return JSON.stringify(toJSON(), null, 2);
});

// 导出
return {
  // ... existing exports ...
  jsonText, toJSON, fromJSON,
};
```

这样 Canvas 的每次节点/边变更都会自动反映到 `jsonText` 中，Monaco 编辑器可以绑定这个 computed。

- [ ] **Step 2: Commit**

```bash
git add src/stores/workflow.ts
git commit -m "feat: computed jsonText for real-time Canvas→JSON sync"
```

### Task 19: JSON → Canvas 实时同步

**Files:**
- Modify: `src/stores/workflow.ts`

- [ ] **Step 1: 添加 applyJsonText 方法（带节点位置保持）**

```typescript
function applyJsonText(text: string): { success: boolean; error?: string } {
  try {
    const data = JSON.parse(text);
    if (!data.nodes || !Array.isArray(data.nodes)) {
      return { success: false, error: "Missing 'nodes' array" };
    }

    // Preserve positions for existing nodes
    const existingPositions = new Map(
      nodes.value.map((n) => [n.id, n.position])
    );

    const newNodes = data.nodes.map((n: any) => ({
      id: n.id,
      type: n.type || "action",
      position: n.position || existingPositions.get(n.id) || { x: 0, y: 0 },
      data: n.data || {},
    }));

    const newEdges = (data.edges || []).map((e: any) => ({
      id: e.id,
      source: e.source || "",
      target: e.target || "",
      sourceHandle: e.sourceHandle,
      targetHandle: e.targetHandle,
      label: e.label,
    }));

    pushSnapshot();
    nodes.value = newNodes;
    edges.value = newEdges;
    if (data.name) name.value = data.name;

    return { success: true };
  } catch (e) {
    return { success: false, error: String(e) };
  }
}

// 导出
return {
  // ... existing exports ...
  applyJsonText,
};
```

- [ ] **Step 2: Commit**

```bash
git add src/stores/workflow.ts
git commit -m "feat: applyJsonText for JSON→Canvas sync with position preservation"
```

### Task 20: Monaco 编辑器双向绑定

**Files:**
- Modify: `src/components/editor/PropertyPanel.vue` (或对应的 Monaco 编辑器组件)

- [ ] **Step 1: 在编辑器组件中实现 debounced 双向同步**

在 Monaco 编辑器所在的组件中：

```typescript
import { watch, ref } from "vue";
import { useWorkflowStore } from "../../stores/workflow";
import { useDebounceFn } from "@vueuse/core";

const store = useWorkflowStore();
const editSource = ref<"canvas" | "editor">("canvas");
const syncError = ref<string | null>(null);

// Canvas → Editor: 当 canvas 变更时更新编辑器内容
watch(
  () => store.jsonText,
  (newText) => {
    if (editSource.value === "canvas") {
      // Update Monaco editor model value
      // (具体实现取决于 Monaco 实例的引用方式)
    }
  }
);

// Editor → Canvas: 编辑器内容变更时 debounce 更新 canvas
const applyEditorChanges = useDebounceFn((text: string) => {
  editSource.value = "editor";
  const result = store.applyJsonText(text);
  syncError.value = result.error || null;
  // 使用 nextTick 恢复 editSource
  setTimeout(() => { editSource.value = "canvas"; }, 50);
}, 500);
```

- [ ] **Step 2: Commit**

```bash
git add src/components/editor/
git commit -m "feat: Monaco↔Canvas debounced bidirectional sync"
```

---

## Task Group 4.2: 自动布局

### Task 21: dagre 自动布局

**Files:**
- Modify: `src/stores/workflow.ts`
- Modify: `src/views/EditorView.vue` (添加布局按钮)

- [ ] **Step 1: 安装 dagre**

```bash
pnpm add @dagrejs/dagre
```

- [ ] **Step 2: 在 workflow store 添加 autoLayout 方法**

```typescript
import dagre from "@dagrejs/dagre";

function autoLayout(direction: "TB" | "LR" = "TB") {
  pushSnapshot();
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: direction, nodesep: 50, ranksep: 80 });

  nodes.value.forEach((node) => {
    g.setNode(node.id, { width: 200, height: 60 });
  });
  edges.value.forEach((edge) => {
    g.setEdge(edge.source, edge.target);
  });

  dagre.layout(g);

  nodes.value = nodes.value.map((node) => {
    const pos = g.node(node.id);
    return {
      ...node,
      position: { x: pos.x - 100, y: pos.y - 30 },
    };
  });
}

return {
  // ... existing exports ...
  autoLayout,
};
```

- [ ] **Step 3: 在 EditorView 添加布局按钮**

在 toolbar 中添加：
```vue
<button @click="store.autoLayout('TB')" class="toolbar-btn" title="Auto Layout">
  <!-- Layout icon -->
  ⊞
</button>
```

- [ ] **Step 4: Commit**

```bash
git add src/stores/workflow.ts src/views/EditorView.vue package.json pnpm-lock.yaml
git commit -m "feat: dagre auto-layout for workflow canvas"
```

---

# Direction 5: 工作流执行增强

## Task Group 5.1: Download 竞态修复

### Task 22: Executor 级预注册 download 监听器

**Files:**
- Modify: `sidecar/browser/controller.py`
- Modify: `sidecar/engine/executor.py`
- Test: `sidecar/tests/test_executor.py`

- [ ] **Step 1: 写 download 预注册测试**

```python
def test_handle_download_pre_registers_listener(self):
    """handle_download should be pre-registered before the triggering action."""
    events = []
    def mock_on(event_name, handler):
        events.append(("on", event_name))
    def mock_remove(event_name, handler):
        events.append(("remove", event_name))

    self.ctrl._page = MagicMock()
    self.ctrl._page.on = mock_on
    self.ctrl._page.remove_listener = mock_remove

    # Setup download context manager
    self.ctrl.setup_download_listener = MagicMock()
    self.ctrl.wait_for_download = MagicMock(return_value="/tmp/file.pdf")

    # The executor should call setup before executing handle_download
    node = {"action": "handle_download", "savePath": "/tmp/file.pdf", "timeout": 5000}
    self.executor._execute_action(node)
```

- [ ] **Step 2: 重构 controller.handle_download 为两阶段**

```python
def setup_download_listener(self, timeout: int = 30000):
    """Pre-register download listener. Call before the action that triggers download."""
    import threading
    self._download_holder = [None]
    self._download_event = threading.Event()
    self._download_timeout = timeout

    def on_download(download):
        self._download_holder[0] = download
        self._download_event.set()

    self._page.on("download", on_download)
    self._download_handler = on_download

def wait_for_download(self, save_path: str) -> str:
    """Wait for the pre-registered download to complete and save it."""
    timeout = getattr(self, "_download_timeout", 30000)
    if not self._download_event.wait(timeout=timeout / 1000):
        raise TimeoutError(f"No download within {timeout}ms")
    download = self._download_holder[0]
    download.save_as(save_path)
    self._page.remove_listener("download", self._download_handler)
    return save_path

def handle_download(self, save_path: str, timeout: int = 30000) -> str:
    """Backward-compatible: setup + wait."""
    self.setup_download_listener(timeout)
    return self.wait_for_download(save_path)
```

- [ ] **Step 3: 运行测试**

```bash
cd sidecar && python -m pytest tests/test_executor.py -v -k "download"
```

- [ ] **Step 4: Commit**

```bash
git add sidecar/browser/controller.py sidecar/engine/executor.py sidecar/tests/test_executor.py
git commit -m "fix: two-phase download handling to prevent race condition"
```

---

## Task Group 5.2: 断点续执行

### Task 23: 执行状态序列化/反序列化

**Files:**
- Modify: `sidecar/engine/executor.py`
- Test: `sidecar/tests/test_executor.py`

- [ ] **Step 1: 写状态序列化测试**

```python
def test_execution_context_serialize_deserialize(self):
    """ExecutionContext should be serializable and restorable."""
    ctx = ExecutionContext()
    ctx.set_var("$name", "alice")
    ctx.set_var("$count", 42)
    ctx.step_index = 5
    ctx.total_steps = 10
    ctx.running = True

    state = ctx.serialize()
    assert state["variables"]["$name"] == "alice"
    assert state["step_index"] == 5

    ctx2 = ExecutionContext()
    ctx2.deserialize(state)
    assert ctx2.get_var("$name") == "alice"
    assert ctx2.step_index == 5
    assert ctx2.total_steps == 10
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd sidecar && python -m pytest tests/test_executor.py -v -k "serialize"
```

- [ ] **Step 3: 实现序列化方法**

在 `ExecutionContext` 中添加：

```python
def serialize(self) -> dict:
    """Serialize execution state for persistence."""
    return {
        "variables": dict(self.variables),
        "step_index": self.step_index,
        "total_steps": self.total_steps,
        "running": self.running,
        "error": self.error,
    }

def deserialize(self, state: dict):
    """Restore execution state from serialized data."""
    self.variables = dict(state.get("variables", {}))
    self.step_index = state.get("step_index", 0)
    self.total_steps = state.get("total_steps", 0)
    self.running = state.get("running", False)
    self.error = state.get("error")
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd sidecar && python -m pytest tests/test_executor.py -v -k "serialize"
```

- [ ] **Step 5: Commit**

```bash
git add sidecar/engine/executor.py sidecar/tests/test_executor.py
git commit -m "feat: ExecutionContext serialize/deserialize for resume support"
```

### Task 24: Executor resume 方法

**Files:**
- Modify: `sidecar/engine/executor.py`
- Modify: `sidecar/browser/actions.py`
- Test: `sidecar/tests/test_executor.py`

- [ ] **Step 1: 写 resume 测试**

```python
def test_executor_resume_from_step(self):
    """Executor should resume from a given step index."""
    self.ctrl.navigate = MagicMock()
    self.ctrl.screenshot = MagicMock()
    self.ctrl.click = MagicMock()

    workflow = {
        "name": "test",
        "nodes": [
            {"id": "1", "action": "Navigate", "url": "https://example.com"},
            {"id": "2", "action": "Click", "selector": "#btn"},
            {"id": "3", "action": "Screenshot", "filename": "test.png"},
        ]
    }

    # Save state after step 1
    state = {"variables": {}, "step_index": 1, "total_steps": 3, "running": True, "error": None}
    result = self.executor.resume(workflow, state)

    # Should skip step 0 (Navigate), execute step 1 (Click) and 2 (Screenshot)
    self.ctrl.navigate.assert_not_called()
    self.ctrl.click.assert_called_once()
    self.ctrl.screenshot.assert_called_once()
    assert result["success"] is True
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd sidecar && python -m pytest tests/test_executor.py -v -k "resume"
```

- [ ] **Step 3: 实现 resume 方法**

```python
def resume(self, workflow_json: dict, saved_state: dict) -> dict:
    """Resume workflow execution from a saved state."""
    nodes = workflow_json.get("nodes", [])
    self._ctx = ExecutionContext()
    self._ctx.deserialize(saved_state)
    self._ctx.running = True
    resume_from = self._ctx.step_index

    logger.info(f"Resuming workflow from step {resume_from}")

    try:
        self._execute_nodes(nodes, skip_until=resume_from)
        self._ctx.running = False
        return {"success": True, **self._ctx.status()}
    except Exception as e:
        self._ctx.error = str(e)
        self._ctx.running = False
        return {"success": False, **self._ctx.status()}
```

修改 `_execute_nodes` 支持 `skip_until` 参数：

```python
def _execute_nodes(self, nodes: list[dict], skip_until: int = 0):
    for node in nodes:
        if not self._ctx.running:
            return
        if self._ctx.step_index < skip_until:
            self._ctx.step_index += 1
            continue
        self._execute_node(node)
        self._ctx.step_index += 1
```

- [ ] **Step 4: 添加 RPC 方法**

在 `browser/actions.py` 中：

```python
@rpc_method("workflow.resume")
def workflow_resume(workflow: dict, state: dict):
    return _executor.resume(workflow, state)
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd sidecar && python -m pytest tests/test_executor.py -v -k "resume"
```

- [ ] **Step 6: Commit**

```bash
git add sidecar/engine/executor.py sidecar/browser/actions.py sidecar/tests/test_executor.py
git commit -m "feat: workflow resume from saved execution state"
```

---

## Task Group 5.3: 结构化执行日志

### Task 25: Executor 结构化日志事件

**Files:**
- Modify: `sidecar/engine/executor.py`
- Test: `sidecar/tests/test_executor.py`

- [ ] **Step 1: 写日志事件测试**

```python
def test_executor_emits_log_events(self):
    """Executor should emit structured log events via callback."""
    log_events = []

    def on_log(entry):
        log_events.append(entry)

    self.executor.log_callback = on_log
    workflow = {
        "name": "test",
        "nodes": [
            {"action": "Navigate", "url": "https://example.com"},
        ]
    }
    self.executor.execute(workflow)

    assert len(log_events) >= 1
    entry = log_events[0]
    assert "level" in entry
    assert "message" in entry
    assert "timestamp" in entry
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd sidecar && python -m pytest tests/test_executor.py -v -k "log_events"
```

- [ ] **Step 3: 实现 log_callback**

在 `WorkflowExecutor.__init__` 中添加：
```python
self.log_callback: callable | None = None
```

添加内部日志方法：
```python
def _emit_log(self, level: str, message: str, node_id: str | None = None):
    """Emit a structured log entry."""
    if self.log_callback:
        self.log_callback({
            "level": level,
            "message": message,
            "nodeId": node_id,
            "step": self._ctx.step_index,
            "timestamp": time.time(),
        })
```

在 `_execute_node` 的关键点调用 `_emit_log`：
- 步骤开始: `self._emit_log("info", f"Executing: {action}", node.get("id"))`
- 步骤成功: `self._emit_log("info", f"Completed: {action}", node.get("id"))`
- 重试: `self._emit_log("warn", f"Retry {attempt+1}/{retry_count}: {e}", node.get("id"))`
- 失败: `self._emit_log("error", f"Failed: {action}: {last_error}", node.get("id"))`

- [ ] **Step 4: 连接 notification**

在 `browser/actions.py` 的 `workflow_execute` 中：

```python
def on_log(entry):
    if _server:
        _server.send_notification("workflow.log", entry)
_executor.log_callback = on_log
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd sidecar && python -m pytest tests/test_executor.py -v -k "log_events"
```

- [ ] **Step 6: Commit**

```bash
git add sidecar/engine/executor.py sidecar/browser/actions.py sidecar/tests/test_executor.py
git commit -m "feat: structured execution log events with notification forwarding"
```

### Task 26: 前端执行日志面板

**Files:**
- Create: `src/components/editor/ExecutionLog.vue`
- Modify: `src/stores/execution.ts`
- Modify: `src/components/editor/BottomPanel.vue`

- [ ] **Step 1: 在 execution store 中监听日志事件**

```typescript
import { listen } from "@tauri-apps/api/event";

// 在 execute() 中添加日志监听
let logUnlisten: UnlistenFn | null = null;

async function listenLogs() {
  logUnlisten = await listen<LogEntry>("sidecar:workflow.log", (event) => {
    const entry = event.payload;
    logs.value.push({
      time: new Date(entry.timestamp * 1000).toLocaleTimeString(),
      level: entry.level as LogEntry["level"],
      nodeId: entry.nodeId,
      message: entry.message,
    });
  });
}
```

- [ ] **Step 2: 创建 ExecutionLog.vue**

```vue
<script setup lang="ts">
import { ref, watch, nextTick } from "vue";
import { useExecutionStore, type LogEntry } from "../../stores/execution";

const store = useExecutionStore();
const logContainer = ref<HTMLElement | null>(null);
const autoScroll = ref(true);

watch(
  () => store.logs.length,
  async () => {
    if (autoScroll.value) {
      await nextTick();
      if (logContainer.value) {
        logContainer.value.scrollTop = logContainer.value.scrollHeight;
      }
    }
  }
);

const levelColors: Record<string, string> = {
  info: "text-blue-400",
  warn: "text-yellow-400",
  error: "text-red-400",
  debug: "text-gray-400",
};
</script>

<template>
  <div class="flex flex-col h-full">
    <div class="flex items-center justify-between px-3 py-1 border-b border-[var(--border-primary)]">
      <span class="text-xs font-medium opacity-70">Execution Log</span>
      <div class="flex gap-2">
        <label class="flex items-center gap-1 text-xs">
          <input type="checkbox" v-model="autoScroll" class="w-3 h-3" />
          Auto-scroll
        </label>
        <button @click="store.reset()" class="text-xs opacity-50 hover:opacity-100">Clear</button>
      </div>
    </div>
    <div ref="logContainer" class="flex-1 overflow-y-auto font-mono text-xs p-2 space-y-0.5">
      <div v-for="(entry, i) in store.logs" :key="i" class="flex gap-2">
        <span class="opacity-40 shrink-0">{{ entry.time }}</span>
        <span :class="levelColors[entry.level] || 'opacity-70'" class="shrink-0 w-12">{{ entry.level.toUpperCase() }}</span>
        <span>{{ entry.message }}</span>
      </div>
      <div v-if="store.logs.length === 0" class="text-center opacity-30 py-4">No logs yet</div>
    </div>
  </div>
</template>
```

- [ ] **Step 3: 在 BottomPanel 中集成 ExecutionLog**

将 ExecutionLog 作为 BottomPanel 的一个 tab。

- [ ] **Step 4: Commit**

```bash
git add src/components/editor/ExecutionLog.vue src/stores/execution.ts src/components/editor/BottomPanel.vue
git commit -m "feat: real-time execution log panel in editor"
```

---

# Direction 6: 录制增强

## Task Group 6.1: 录制事件实时预览

### Task 27: 录制事件 notification

**Files:**
- Modify: `sidecar/browser/recorder.py`
- Modify: `sidecar/browser/actions.py`

- [ ] **Step 1: 修改 RecordingEngine 支持事件回调**

在 `RecordingEngine.__init__` 中添加：
```python
self.event_callback: callable | None = None
```

修改 `poll_new_events` 在发现新事件时触发回调：

```python
def poll_new_events(self) -> list[dict]:
    """Poll for new events since last check."""
    if not self._recording:
        return []
    self._poll_events()
    new = self._events[self._last_poll_index:]
    self._last_poll_index = len(self._events)
    if new and self.event_callback:
        for event in new:
            self.event_callback(event)
    return new
```

- [ ] **Step 2: 在 actions.py 中注册 notification 转发**

```python
@rpc_method("recording.start")
def recording_start():
    def on_event(event):
        if _server:
            _server.send_notification("recording.event", event)
    _recorder.event_callback = on_event
    _recorder.start()
    return {"recording": True}
```

- [ ] **Step 3: Commit**

```bash
git add sidecar/browser/recorder.py sidecar/browser/actions.py
git commit -m "feat: recording event notifications for real-time preview"
```

### Task 28: 前端录制预览面板

**Files:**
- Create: `src/components/editor/RecordingPreview.vue`
- Modify: `src/stores/browser.ts`

- [ ] **Step 1: 在 browser store 中监听录制事件**

```typescript
import { listen, type UnlistenFn } from "@tauri-apps/api/event";

let recordingUnlisten: UnlistenFn | null = null;

async function startRecordingPreview() {
  recordingUnlisten = await listen<RecordedNode>("sidecar:recording.event", (event) => {
    const node = event.payload;
    recordedNodes.value = [...recordedNodes.value, {
      type: "action",
      action: node.type || "click",
      selector: node.selector,
      value: node.value,
      url: node.url,
    }];
  });
}

function stopRecordingPreview() {
  if (recordingUnlisten) {
    recordingUnlisten();
    recordingUnlisten = null;
  }
}
```

在 `startRecording` 中调用 `startRecordingPreview()`，在 `stopRecording` 中调用 `stopRecordingPreview()`。

- [ ] **Step 2: 创建 RecordingPreview.vue**

```vue
<script setup lang="ts">
import { useBrowserStore } from "../../stores/browser";

const browser = useBrowserStore();
</script>

<template>
  <div class="flex flex-col h-full">
    <div class="flex items-center justify-between px-3 py-1 border-b border-[var(--border-primary)]">
      <span class="text-xs font-medium opacity-70">
        Recording
        <span v-if="browser.recording" class="ml-1 text-red-400 animate-pulse">● REC</span>
      </span>
      <span class="text-xs opacity-40">{{ browser.recordedNodes.length }} events</span>
    </div>
    <div class="flex-1 overflow-y-auto text-xs p-2 space-y-1">
      <div
        v-for="(node, i) in browser.recordedNodes"
        :key="i"
        class="flex gap-2 py-1 px-2 rounded hover:bg-[var(--bg-hover)]"
      >
        <span class="text-[var(--accent-primary)] shrink-0 w-16">{{ node.action }}</span>
        <span class="opacity-60 truncate">{{ node.selector || node.url || node.value || '' }}</span>
      </div>
      <div v-if="browser.recordedNodes.length === 0" class="text-center opacity-30 py-4">
        {{ browser.recording ? 'Waiting for events...' : 'Start recording to see events' }}
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 3: Commit**

```bash
git add src/components/editor/RecordingPreview.vue src/stores/browser.ts
git commit -m "feat: real-time recording event preview panel"
```

---

## Task Group 6.2: iframe 穿透录制

### Task 29: RECORDER_JS iframe 穿透

**Files:**
- Modify: `sidecar/browser/recorder.py`
- Test: `sidecar/tests/test_executor.py` (手动验证为主)

- [ ] **Step 1: 修改 RecordingEngine 注入 iframe**

在 `_inject_recorder` 中添加 iframe 处理：

```python
def _inject_recorder(self) -> None:
    """Inject recording script into all pages and frames."""
    ctx = self._controller._context
    if not ctx:
        return
    for page in ctx.pages:
        try:
            # Inject into main page
            page.evaluate(RECORDER_JS)
            page.on("load", lambda p=page: self._safe_inject(p))
            # Inject into all frames
            for frame in page.frames:
                try:
                    frame.evaluate(RECORDER_JS)
                except Exception:
                    pass
            # Listen for new frames
            page.on("frameattached", lambda frame: self._safe_inject_frame(frame))
        except Exception as e:
            logger.warning(f"Failed to inject into page: {e}")
    ctx.on("page", self._on_new_page)
    logger.debug("Recorder JS injected into %d pages", len(ctx.pages))

@staticmethod
def _safe_inject_frame(frame) -> None:
    """Inject recorder into a frame after it loads."""
    try:
        frame.wait_for_load_state("domcontentloaded", timeout=5000)
        frame.evaluate(RECORDER_JS)
    except Exception:
        pass
```

- [ ] **Step 2: 修改 _poll_events 也从 frames 收集**

```python
def _poll_events(self) -> None:
    """Pull events from all browser pages and frames."""
    ctx = self._controller._context
    if not ctx:
        return
    all_events = []
    for page in ctx.pages:
        # Main page
        try:
            raw = page.evaluate("window.__mimicryEvents || []")
            if raw:
                all_events.extend(raw)
        except Exception:
            pass
        # Frames
        for frame in page.frames:
            if frame == page.main_frame:
                continue
            try:
                raw = frame.evaluate("window.__mimicryEvents || []")
                if raw:
                    all_events.extend(raw)
            except Exception:
                pass
    all_events.sort(key=lambda e: e.get("timestamp", 0))
    if len(all_events) > len(self._events):
        self._events = all_events
```

- [ ] **Step 3: Commit**

```bash
git add sidecar/browser/recorder.py
git commit -m "feat: iframe penetration for recording engine"
```

---

## Task Group 6.3: 选择器质量评分

### Task 30: 选择器评分函数

**Files:**
- Modify: `sidecar/browser/recorder.py`
- Test: `sidecar/tests/test_executor.py`

- [ ] **Step 1: 写选择器评分测试**

```python
def test_selector_quality_score():
    """Selector quality scoring should rank selectors appropriately."""
    from browser.recorder import score_selector

    # ID selectors are best
    assert score_selector("#submit-btn") >= 90

    # Name attribute is good
    assert score_selector('input[name="email"]') >= 70

    # Class-based is decent
    assert score_selector("button.primary-action") >= 50

    # Deep nth-of-type is fragile
    assert score_selector("div > div:nth-of-type(3) > span:nth-of-type(2)") <= 30

    # Shadow DOM combinator
    assert score_selector('#host >> button.inner') >= 60
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd sidecar && python -m pytest tests/test_executor.py::test_selector_quality_score -v
```

- [ ] **Step 3: 实现 score_selector**

在 `recorder.py` 顶部添加：

```python
def score_selector(selector: str) -> int:
    """Score a CSS selector for quality/stability (0-100).
    Higher = more stable and readable.
    """
    score = 50  # baseline

    # Bonus for ID
    if selector.startswith("#") and " " not in selector:
        score += 40

    # Bonus for name attribute
    if '[name="' in selector:
        score += 25

    # Bonus for data-testid
    if "[data-testid" in selector or "[data-test" in selector:
        score += 35

    # Penalty for nth-of-type (fragile)
    nth_count = selector.count(":nth-of-type")
    score -= nth_count * 15

    # Penalty for deep nesting
    depth = selector.count(" > ") + selector.count(" ")
    score -= depth * 5

    # Shadow DOM combinator — neutral to slightly positive (semantic boundary)
    if " >> " in selector:
        score += 10

    return max(0, min(100, score))
```

- [ ] **Step 4: 在 events_to_workflow_nodes 中附加 score**

修改 `events_to_workflow_nodes`，在每个有 selector 的 node 上附加 `selectorScore`：

```python
if "selector" in node_dict:
    node_dict["selectorScore"] = score_selector(node_dict["selector"])
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd sidecar && python -m pytest tests/ -v -k "selector_quality"
```

- [ ] **Step 6: Commit**

```bash
git add sidecar/browser/recorder.py sidecar/tests/test_executor.py
git commit -m "feat: selector quality scoring for recorded events"
```

---

## Verification

1. **Python 单元测试**

```bash
cd sidecar && python -m pytest tests/ --ignore=tests/test_blocks_e2e.py --ignore=tests/test_anti_detect.py -v
```

2. **Rust 编译检查**

```bash
cd src-tauri && cargo check
```

3. **前端类型检查**

```bash
pnpm type-check
```

4. **前端构建**

```bash
pnpm build
```

5. **E2E 验证（需要 Camoufox）**

```bash
cd sidecar && python dev_cli.py blocks-test
```

---

## Decisions

- **Python sidecar 保持不变**: Camoufox 硬性锁定 Python，不迁移核心浏览器控制
- **Profile 双存储**: CLI 用文件系统，GUI 用 SQLite。两者通过 profile.to_dict() 兼容
- **进度事件**: 使用 JSON-RPC notification（无 id 的消息）而非额外通道
- **Canvas↔JSON 同步**: debounce 500ms + editSource 标记防止循环更新
- **Download 修复**: 两阶段 API（setup_download_listener + wait_for_download），保持向后兼容
- **dagre 布局**: 仅 @dagrejs/dagre，不引入 elk（过重）

## Scope Exclusions

- 不做 Python→Rust 核心模块迁移（保留为 Phase 3）
- 不做 DSL 编译器增强
- 不做多浏览器实例并行
- 不做云端 Profile 同步
- 不做录制→工作流的智能合并（仅做选择器评分，合并留 Phase 3）

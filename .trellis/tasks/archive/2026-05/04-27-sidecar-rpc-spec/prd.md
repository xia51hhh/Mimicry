# Python↔Rust Sidecar RPC 交互规范

## 背景

Mimicry 的架构是 **Tauri (Rust)** 作为主进程，通过 **JSON-RPC over stdio** 与 **Python sidecar** 通信。sidecar 负责浏览器控制、录制、工作流执行等重操作。

当前交互逻辑存在多项设计问题，需要审查并规范化。

---

## 架构总览

```
┌──────────────┐    Tauri invoke    ┌──────────────────┐   JSON-RPC/stdio   ┌──────────────────┐
│  Vue 前端    │ ──────────────────→ │  Rust commands   │ ─────────────────→ │  Python sidecar  │
│  (renderer)  │ ←────── events ──── │  (browser.rs)    │ ←── notification ── │  (rpc/server.py) │
└──────────────┘                    └──────────────────┘                    └──────────────────┘
                                      ↑ Mutex<Sidecar>                       ↑ SessionManager
                                      ↑ Mutex<Connection>                    ↑ WorkflowExecutor
```

### 通信协议
- **请求**: `{"jsonrpc":"2.0", "id":N, "method":"xxx", "params":{...}}`
- **响应**: `{"jsonrpc":"2.0", "id":N, "result":{...}}` 或 `{"jsonrpc":"2.0", "id":N, "error":{"code":N, "message":"..."}}`
- **通知(sidecar→Rust)**: `{"jsonrpc":"2.0", "method":"xxx", "params":{...}}`（无 id）
- **传输**: 每条消息占一行（`\n` 分隔），通过 stdin/stdout

---

## 审查发现的问题

### P0 — 严重

#### 1. Mutex 长时间持锁 → 全局阻塞
**现状**: `sidecar_call()` 在 `sidecar.lock().await` 后调用 `sc.ensure_alive()` + `sc.call()`，整个 RPC 调用期间持有 Mutex。
- `browser.launch` 超时 60s
- `workflow.execute` 超时 600s

**影响**: 持锁期间所有其他 Tauri 命令（browser_status、recording_poll、心跳检测）全部排队等待。

**方案**: 
- 将 `Sidecar.call()` 改为内部使用细粒度锁（stdin 写锁 + response channel），而非外部持有整个 Sidecar Mutex
- 或引入 request/response 匹配机制，允许并发 RPC 调用

#### 2. env_check.py 直接写 stdout → 竞争条件
**现状**: `CamoufoxEnv.install()` 中 `_send_notification()` 直接 `sys.stdout.write()`，绕过了 `JsonRpcServer._write_lock`。

**影响**: 如果安装过程中有 RPC 请求响应同时写入 stdout，输出可能交错损坏。

**方案**: `CamoufoxEnv` 应接受 server 引用，通过 `server.send_notification()` 发送通知。

### P1 — 重要

#### 3. RPC id 不匹配
**现状**: Rust 端 `call()` 读到任何有 `id` 字段的响应就当做当前请求的响应返回，不校验 id 值是否匹配。

**当前风险**: 低（因为 Mutex 保证了串行），但如果未来改为并发调用会立即暴露。

**方案**: 响应 id 必须匹配请求 id。

#### 4. Sidecar 进程退出时无法清理浏览器
**现状**: Rust `Sidecar.stop()` 直接 `child.kill()`，Python 端没有机会执行 `SessionManager.destroy_all()`。Camoufox 子进程可能成为孤儿。

**方案**: 
- 优先发送 `shutdown` RPC 请求，等待优雅退出
- 超时后再 kill
- Python 端注册 `atexit` 或信号处理器清理浏览器

#### 5. 心跳与长操作互斥
**现状**: 心跳协程每 30s `sidecar.lock().await`，但如果 `workflow.execute` 持锁 600s，心跳完全失效。

**方案**: 与问题 1 的方案联动解决。

### P2 — 改进

#### 6. 错误类型单一
**现状**: 所有 sidecar 错误统一为 `AppError::Sidecar(String)`。Python 端在 error response 的 `data.error_type` 中提供了异常类名，但 Rust 端丢弃了。

**方案**: 保留 `error_type` 字段传递给前端，前端可按类型显示不同 UI。

#### 7. 通知事件名转换不透明
**现状**: Python 发送 `recording.event`，Rust 转换为 `sidecar:recording/event`（`.` → `/`，加 `sidecar:` 前缀）。

**方案**: 明确文档化转换规则，或改为 Python 端直接使用最终事件名。

#### 8. check_environment 绕过 sidecar
**现状**: `check_environment` Tauri 命令直接 spawn `venv/bin/python -c "import camoufox..."` 检测环境，不经过 sidecar RPC。

**方案**: 这是合理的（sidecar 可能还没启动），但路径逻辑需要与 sidecar 保持同步。

---

## 当前 RPC 方法注册表

### 浏览器控制
| RPC method | Rust Tauri 命令 | 超时 | 说明 |
|---|---|---|---|
| `browser.launch` | `browser_launch` | 60s | 创建 session + 启动 Camoufox |
| `browser.close` | `browser_close` | 30s | 销毁 session |
| `browser.navigate` | `browser_navigate` | 30s | 页面导航 |
| `browser.status` | `browser_status` | 5s | 查询状态 |
| `browser.list_sessions` | `browser_list_sessions` | 5s | 列出所有 session |

### 录制
| RPC method | Rust Tauri 命令 | 超时 | 说明 |
|---|---|---|---|
| `recording.start` | `recording_start` | 30s | 开始录制 |
| `recording.stop` | `recording_stop` | 30s | 停止录制，返回事件 |
| `recording.poll` | `recording_poll` | 5s | 拉取新事件 |

### 工作流执行
| RPC method | Rust Tauri 命令 | 超时 | 说明 |
|---|---|---|---|
| `workflow.execute` | `workflow_execute` | 600s | 执行工作流（Python 端后台线程） |
| `workflow.stop` | `workflow_stop_execution` | 30s | 停止执行 |
| `workflow.execution_status` | `workflow_execution_status` | 5s | 查询执行状态 |

### 环境管理
| RPC method | Rust Tauri 命令 | 超时 | 说明 |
|---|---|---|---|
| `camoufox.check` | `camoufox_check` | 60s | 检测安装状态 |
| `camoufox.install` | `camoufox_install` | 600s | 安装 Camoufox |

### 通知 (sidecar → Rust → 前端)
| Python 通知方法 | Rust 转发事件名 | 触发时机 |
|---|---|---|
| `recording.event` | `sidecar:recording/event` | 录制到新操作 |
| `workflow.progress` | `sidecar:workflow/progress` | 工作流执行进度 |
| `workflow.log` | `sidecar:workflow/log` | 工作流执行日志 |
| `camoufox.progress` | `sidecar:camoufox/progress` | Camoufox 安装进度 |

### 系统
| RPC method | 超时 | 说明 |
|---|---|---|
| `ping` | 5s | 健康检查 |
| `echo` | 默认 | 回显测试 |
| `system.info` | 默认 | 系统信息 |
| `heartbeat` | 5s | 心跳 |

---

## 规范约定

### 1. 方法命名
- 格式: `domain.action`，如 `browser.launch`、`workflow.execute`
- domain: `browser` | `recording` | `workflow` | `camoufox` | `system`

### 2. 参数约定
- 所有浏览器操作方法必须接受 `session_id: str = "default"` 参数
- 参数传递使用 named params（dict），不使用 positional args

### 3. 返回值约定
- 成功: 返回有意义的 dict（不是裸字符串或 null）
- 操作类: 返回确认字段，如 `{"clicked": selector}`
- 状态类: 返回完整状态 dict

### 4. 错误约定
- code `-32601`: 方法不存在
- code `-32700`: JSON 解析错误
- code `-32000`: 业务错误（通用）
- `error.data.error_type`: Python 异常类名（RuntimeError、ValueError 等）

### 5. 生命周期
- Sidecar 启动: Rust 端 `ensure_alive()` → 自动启动 + ping 验证
- Sidecar 重启: 心跳失败 → stop → 下次调用自动重启
- 退出: 应先发送 shutdown 通知，等待优雅退出

### 6. 并发规则
- 当前: Mutex<Sidecar> 保证串行，一次只能有一个 RPC 调用
- Python 端: `ASYNC_METHODS` 中的方法在后台线程执行，但 Rust 端仍然等待响应
- 后续: 需要引入 request/response 匹配 + 细粒度锁

---

## 修复优先级

1. **立即**: asyncio 问题（已修复）
2. **短期**: env_check.py stdout 竞争、优雅退出
3. **中期**: Mutex 细粒度化、RPC id 匹配、错误类型传递
4. **长期**: 并发 RPC 支持、全双工通信

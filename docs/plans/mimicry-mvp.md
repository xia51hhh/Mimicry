# Mimicry MVP 实施计划

## Goal
构建跨平台桌面浏览器自动化应用 Mimicry：Tauri v2 + Vue 3 + Python Sidecar + Camoufox，支持可视化工作流编辑、录制回放、工作流↔伪代码双向转换。

## Architecture
```
┌─────────────────────────────────────┐
│           Tauri v2 Shell            │
│  ┌───────────┐  ┌────────────────┐  │
│  │ Rust Core │  │  Vue 3 WebView │  │
│  │ - IPC     │  │  - Vue Flow    │  │
│  │ - SQLite  │  │  - Monaco      │  │
│  │ - Logger  │  │  - UI          │  │
│  └─────┬─────┘  └────────────────┘  │
│        │ stdio JSON-RPC              │
│  ┌─────▼──────────────────────┐     │
│  │  Python Sidecar (PyInst)   │     │
│  │  - Camoufox Controller     │     │
│  │  - Page Actions            │     │
│  │  - Recorder Script Inject  │     │
│  └────────────────────────────┘     │
└─────────────────────────────────────┘
```

## Tech Stack
- **Desktop**: Tauri v2 (Rust)
- **Frontend**: Vue 3, Vite, Vue Flow, Monaco Editor, TailwindCSS
- **Browser**: Camoufox 0.4.11+ (Python SDK, Playwright)
- **IPC**: JSON-RPC over stdio
- **Storage**: SQLite (via rusqlite)
- **Logging**: tracing (Rust), loguru (Python)
- **Testing**: vitest (frontend), pytest (Python), cargo test (Rust)

## File Structure
```
Mimicry/
├── src-tauri/
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   ├── src/
│   │   ├── main.rs
│   │   ├── lib.rs
│   │   ├── ipc/
│   │   │   ├── mod.rs
│   │   │   ├── jsonrpc.rs        # JSON-RPC client
│   │   │   └── sidecar.rs        # Sidecar lifecycle
│   │   ├── db/
│   │   │   ├── mod.rs
│   │   │   ├── schema.rs         # SQLite schema + migrations
│   │   │   └── workflow.rs       # Workflow CRUD
│   │   ├── commands/
│   │   │   ├── mod.rs
│   │   │   ├── browser.rs        # Browser Tauri commands
│   │   │   ├── workflow.rs       # Workflow Tauri commands
│   │   │   └── system.rs         # System info commands
│   │   └── logger.rs             # tracing setup
│   └── tests/
│       ├── ipc_test.rs
│       └── db_test.rs
├── src/                           # Vue frontend
│   ├── App.vue
│   ├── main.ts
│   ├── router.ts
│   ├── stores/
│   │   ├── workflow.ts            # Pinia workflow store
│   │   └── browser.ts            # Pinia browser store
│   ├── components/
│   │   ├── editor/
│   │   │   ├── WorkflowCanvas.vue # Vue Flow canvas
│   │   │   ├── NodePalette.vue    # Drag source panel
│   │   │   ├── PropertyPanel.vue  # Node config panel
│   │   │   └── nodes/
│   │   │       ├── ActionNode.vue
│   │   │       ├── ConditionNode.vue
│   │   │       ├── LoopNode.vue
│   │   │       └── GroupNode.vue
│   │   ├── code/
│   │   │   └── CodeEditor.vue     # Monaco pseudocode editor
│   │   ├── browser/
│   │   │   └── BrowserPanel.vue   # Browser status panel
│   │   └── layout/
│   │       ├── MainLayout.vue
│   │       ├── Sidebar.vue
│   │       └── Toolbar.vue
│   ├── composables/
│   │   ├── useWorkflow.ts         # Workflow logic
│   │   ├── useBrowser.ts          # Browser IPC
│   │   └── usePseudocode.ts       # Workflow ↔ pseudocode
│   ├── types/
│   │   ├── workflow.ts            # Workflow types
│   │   ├── node.ts                # Node types
│   │   └── ipc.ts                 # IPC message types
│   └── utils/
│       ├── pseudocode.ts          # Parser + serializer
│       └── validator.ts           # Workflow validation
├── sidecar/                        # Python sidecar
│   ├── pyproject.toml
│   ├── main.py                    # Entry: JSON-RPC server
│   ├── rpc/
│   │   ├── __init__.py
│   │   ├── server.py              # stdio JSON-RPC handler
│   │   └── methods.py             # RPC method registry
│   ├── browser/
│   │   ├── __init__.py
│   │   ├── controller.py          # Camoufox lifecycle
│   │   ├── actions.py             # Page actions (click, type, etc.)
│   │   └── recorder.py            # DOM event → action stream
│   ├── utils/
│   │   ├── __init__.py
│   │   └── logger.py              # loguru setup
│   └── tests/
│       ├── test_rpc.py
│       ├── test_controller.py
│       └── test_actions.py
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.js
└── docs/
    └── pseudocode-spec.md         # DSL specification
```

## Pseudocode DSL 设计
```
# Mimicry Pseudocode v1
# 人类可读 + AI 可解析的工作流描述语言

WORKFLOW "登录示例" {
  OPEN "https://example.com/login"
  WAIT selector="#username" timeout=5s
  CLICK "#username"
  TYPE "#username" "admin"
  TYPE "#password" "pass123"
  CLICK "#login-btn"
  
  IF exists("#error-msg") {
    SCREENSHOT "error.png"
    FAIL "登录失败"
  }
  
  WAIT url_contains="/dashboard" timeout=10s
  
  LOOP items=".product-card" as=$item max=10 {
    CLICK $item >> ".detail-link"
    EXTRACT text=".price" into=$price
    BACK
  }
}
```

关键字: `OPEN`, `CLICK`, `TYPE`, `WAIT`, `IF/ELSE`, `LOOP`, `EXTRACT`, `SCREENSHOT`, `SCROLL`, `BACK`, `FAIL`, `SLEEP`, `SET`, `LOG`

---

## Tasks

### Task 1: 项目脚手架 — Tauri + Vue
- [ ] Step 1: 初始化 Tauri v2 + Vue 3 项目
- [ ] Step 2: 配置 TailwindCSS + 基础样式
- [ ] Step 3: 验证 `cargo tauri dev` 可运行

### Task 2: Rust 日志与错误处理基础
- [ ] Step 1: 配置 tracing + 文件旋转日志
- [ ] Step 2: 定义全局 Error enum + Result type
- [ ] Step 3: 测试日志输出

### Task 3: SQLite 数据层
- [ ] Step 1: 添加 rusqlite 依赖，定义 schema
- [ ] Step 2: Workflow CRUD 操作
- [ ] Step 3: 导入/导出 JSON
- [ ] Step 4: 单元测试

### Task 4: Python Sidecar — JSON-RPC Server
- [ ] Step 1: pyproject.toml + 依赖
- [ ] Step 2: stdio JSON-RPC server 框架
- [ ] Step 3: ping/echo 测试方法
- [ ] Step 4: pytest 测试

### Task 5: Rust Sidecar 管理 + JSON-RPC Client
- [ ] Step 1: Sidecar 进程启动/停止/重启
- [ ] Step 2: JSON-RPC client (序列化/反序列化)
- [ ] Step 3: Tauri command 暴露给前端
- [ ] Step 4: 集成测试

### Task 6: Camoufox 浏览器控制
- [ ] Step 1: controller.py — 启动/关闭 Camoufox
- [ ] Step 2: actions.py — click/type/navigate/wait/screenshot
- [ ] Step 3: 注册为 RPC 方法
- [ ] Step 4: 测试基本操作

### Task 7: Vue 主界面布局
- [ ] Step 1: MainLayout + Sidebar + Toolbar
- [ ] Step 2: Vue Router 配置
- [ ] Step 3: Pinia stores 骨架
- [ ] Step 4: 浏览器状态面板

### Task 8: Vue Flow 工作流编辑器
- [ ] Step 1: WorkflowCanvas + Vue Flow 基础
- [ ] Step 2: 自定义节点 (Action/Condition/Loop/Group)
- [ ] Step 3: NodePalette 拖拽添加节点
- [ ] Step 4: PropertyPanel 节点属性编辑
- [ ] Step 5: 工作流序列化/反序列化 (JSON)

### Task 9: Pseudocode DSL 引擎
- [ ] Step 1: 定义 DSL 语法规范文档
- [ ] Step 2: pseudocode → workflow JSON 解析器
- [ ] Step 3: workflow JSON → pseudocode 序列化器
- [ ] Step 4: Monaco Editor 集成 + 语法高亮
- [ ] Step 5: 双向同步 (编辑器 ↔ 画布)
- [ ] Step 6: vitest 测试

### Task 10: 录制功能
- [ ] Step 1: recorder.js — DOM 注入脚本 (捕获 click/input/navigation)
- [ ] Step 2: recorder.py — 接收事件流，转换为 action 序列
- [ ] Step 3: 录制 → 工作流节点自动生成
- [ ] Step 4: 前端录制控制 UI (开始/暂停/停止)

### Task 11: 工作流执行引擎
- [ ] Step 1: Python 端 workflow runner (顺序/条件/循环)
- [ ] Step 2: 执行状态实时回传 (当前步骤/进度/错误)
- [ ] Step 3: 前端执行面板 (进度可视化、节点高亮)
- [ ] Step 4: 错误处理 + 重试机制

### Task 12: 打包与分发
- [ ] Step 1: PyInstaller 打包 sidecar
- [ ] Step 2: Tauri bundler 配置 (MSI/DMG/AppImage)
- [ ] Step 3: GitHub Actions CI/CD
- [ ] Step 4: Camoufox 首次启动自动下载

---

## 执行顺序建议
Task 1→2→3→4→5 (基础层) → Task 6→7→8 (核心功能) → Task 9→10→11 (高级功能) → Task 12 (分发)

## 执行方式选择

计划已保存至 `docs/plans/mimicry-mvp.md`。两种执行方式：

**1. Subagent-Driven（推荐）** — 每个 Task 派发独立子代理，任务间 review，快速迭代

**2. Inline Execution** — 当前会话内按批次执行，设置 checkpoint 审查

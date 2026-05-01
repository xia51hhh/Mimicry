# 转化层修复 Design — 录制智能化 + 统一布局 + Workspace + CLI/MCP CRUD

- **Date**: 2026-05-01
- **Owner**: zwx19990307
- **Status**: Approved (pending plan)
- **Related**: `docs/design/block-system.md`, `docs/llm-interactive-guide.md`, `docs/parallel-agents.md`
- **Brainstorming Q&A**: 见末尾「Decision Log」节

---

## 1. Goal

修复 Mimicry 工作流转化层的 4 类问题，把「录制 / LLM JSON / CLI / MCP」四条入口都对齐到同一条规范化流水线：

1. **录制智能化漏洞** — 点击开新窗会重复插入 `open` 节点；输入框内 Ctrl+A/C/V 与 Shift+字母被丢弃
2. **画布上不优雅** — 录制 import 用 `i*80` 手算 y，与 JSON paste / dagre 不共一套布局
3. **CLI/MCP 缺 CRUD** — 只能 `workflow.execute`，不能导入 / 保存 / 打开 / 列出
4. **没有 workspace 概念** — workflow 只能存在 SQLite 一个 `workflows` 表，不能像 VS Code 一样按文件管理

修完后，单条「录制 → 转化 → 显示 / 持久化 / CLI 重放」路径全部走同一条 normalize + layout 函数，CLI/MCP 与画布操作集合等价。

---

## 2. Non-Goals

- **不**实现完整 dagre / sugiyama Rust 端口（分支回落给前端 dagre）
- **不**迁移现有 `workflows` DB 表的数据（文件 workspace 与 DB 表共存，由用户决定单条迁移）
- **不**改 daemon 的 UDS 协议或 MCP 桥接机制（沿用现有 `METHOD_REGISTRY` 反射）
- **不**做 multi-user / 远程 workspace；workspace 是本地目录
- **不**实现真无头浏览器集成测试（自测试只跑 CLI/MCP 命令路径与文件 I/O）

---

## 3. Decisions Log（来自 Q1–Q6）

| # | 决策 | 选项 | 拍板 |
|---|---|---|---|
| Q1 | 修哪些录制 bug | A) new tab dup / B) 键盘修饰符与 Shift / C) Enter+IME | **A + B** |
| Q2 | 布局主方向 | LR / TB / 换行 | **横走 N 个换行** |
| Q3 | 分支工作流如何布局 | 全 wrap / 全 dagre / 检测分流 | **线性 wrap，分支走 dagre** |
| Q4 | "CLI/MCP 导入" 含义 | 加 RPC / 仅统一转换层 / 不动 | **加 RPC：导入 + 保存 + 运行 + 调试** |
| Q5 | 本轮范围 | 全做 / 重心录制+布局 / 仅录制 | **全做（路径闭环）** |
| Q6 | 存储位置 | DB / sidecar 文件夹 / Tauri relay / 任意路径 | **Tauri 管理的文件目录，VS Code 风格 workspace** |
| 推荐确认 | 布局算法归属 | A1 Rust 全做 / A2 Rust 线性+前端分支 / A3 全前端 | **A2** |
| 推荐确认 | DB 表去留 | C1 共存 / C2 启动迁移 / C3 删表 | **C1 共存** |
| 推荐确认 | wrap N | 6 / 8 / 10 | **8** |
| 推荐确认 | 文件扩展名 | `.mwf.json` / `.json` | **`.mwf.json`** |
| 推荐确认 | sidecar 直访 sqlite recent_files | 直访 / IPC 代写 | **直访** |
| 推荐确认 | 测试策略 | pytest 跑 daemon+UDS 命令路径 | **OK** |

---

## 4. Section 1 / 录制智能化修复

### 4.1 Bug A — 点击开新窗多送一个 `open`

**根因**：`sidecar/browser/recorder.py:412 events_to_workflow_nodes()` 用 `seen_navigations` 集合去重 URL；但每个 `emit()` 都附带 `url: location.href`（recorder.py:92）。click 事件 → 浏览器自动在新 tab 打开 → 新 tab 里的下一个事件携带新 URL → 由于该 URL 不在 `seen_navigations` 集合里，触发隐式 `open` 插入。

**修复**：进入主转换循环前先扫一遍把 `new_tab` 事件的 URL 全部预登记到 `seen_navigations`。

```python
# sidecar/browser/recorder.py:412 events_to_workflow_nodes
seen_navigations: set[str] = set()

# 新增：预扫 new_tab 事件的 url 入 seen_navigations
for ev in events:
    if ev.get("type") == "new_tab":
        if u := ev.get("url"):
            seen_navigations.add(u)

# 主循环（不变）
for event in events:
    ...
    if url and url not in seen_navigations:
        seen_navigations.add(url)
        ...nodes.append(open + wait)...
```

**验证**：`sidecar/tests/test_recorder.py` 加 case：模拟 `[click(url=A), new_tab(url=B), click(url=B)]` → assert 输出节点不含 `{"action":"open","data":{"url":"B"}}`。

### 4.2 Bug B — 键盘修饰符与 Shift

**根因**：`RECORDER_JS` keydown handler（recorder.py:154-170）两处缺陷：

- 行 159 `isInput && !['Escape','Enter','Tab'].includes(e.key) return` — 输入框里只放 Esc/Enter/Tab 通过。`Ctrl+A/C/V/Z` / `Ctrl+Shift+End` 等所有快捷组合全被丢
- 行 164 `if (e.shiftKey && e.key.length > 1) key += 'Shift+'` — Shift+字母（`e.key="A"`，length=1）不会保留 Shift 前缀，结果 `Shift+a` 被记录成纯 `A`

**修复**：

```js
// RECORDER_JS keydown 改造
document.addEventListener('keydown', (e) => {
    const tag = (e.target?.tagName) || '';
    const isInput = ['INPUT','TEXTAREA','SELECT'].includes(tag) || e.target?.isContentEditable;
    const hasMod = e.ctrlKey || e.altKey || e.metaKey;
    
    // 输入框里：带修饰符 OR 是导航/控制键 → 录入；否则交给 input 事件
    const passInInput = hasMod
        || ['Escape','Enter','Tab','ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Home','End','PageUp','PageDown','Delete','Backspace'].includes(e.key)
        || /^F\d+$/.test(e.key);
    if (isInput && !passInInput) return;
    
    if (['Shift','Control','Alt','Meta'].includes(e.key)) return;
    
    let key = '';
    if (e.ctrlKey)  key += 'Control+';
    if (e.altKey)   key += 'Alt+';
    if (e.shiftKey) key += 'Shift+';      // ← 始终保留
    if (e.metaKey)  key += 'Meta+';
    key += e.key;
    
    const sel = isInput ? getSelector(e.target) : 'body';
    emit('press_key', { selector: sel, key });
}, true);
```

**注意**：在 input 中也保留 Shift+字母快捷（如某些站的 vim 模式），但**仅**带修饰符或导航键时通过；纯字符输入仍走 `input` → `type` 节点。

**验证**：手动 + 自动测试 — pytest 注入 mock 的 keydown 事件序列，检查 `press_key` node 的 `key` 字段。

---

## 5. Section 2 / 统一布局流水线（A2）

### 5.1 算法归属（A2）

```
源（4 种）        Rust transform                前端
─────             ──────────────                 ────
Recording         compact_to_canonical
LLM Compact   ──► or                       ──►   canonicalNodeToVue
LLM Recording     legacy_to_canonical            ↓
Legacy            ↓                              检测 position 是否
Canonical         auto_layout(nodes)             有 null/sentinel
                  ├─ 无 condition/loop          ↓ 是
                  │  → 蛇形 wrap (N=8)          dagre rankdir=LR
                  │  → Vec<Position>            ↓ 否
                  └─ 有分支                      用 Rust 算的 position
                     → NeedsBranchLayout
                     → position=null sentinel
```

### 5.2 Rust 端：蛇形 wrap

`src-tauri/src/transform/layout.rs` 改造：

```rust
pub struct LayoutConfig {
    pub start_x: f64,         // 100.0
    pub start_y: f64,         // 100.0
    pub col_gap: f64,         // 220.0  (节点宽 200 + gap 20)
    pub row_gap: f64,         // 120.0  (节点高 80 + gap 40)
    pub wrap_n: usize,        // 8
}

impl Default for LayoutConfig { /* 上述默认 */ }

pub enum LayoutResult {
    Computed(Vec<Position>),
    NeedsBranchLayout,
}

pub fn auto_layout(nodes: &[CanonicalNode], cfg: &LayoutConfig) -> LayoutResult {
    if has_branches(nodes) {
        return LayoutResult::NeedsBranchLayout;
    }
    let positions = nodes.iter().enumerate().map(|(i, _)| {
        let row = i / cfg.wrap_n;
        let col_in_row = i % cfg.wrap_n;
        // S 形换行：偶数行从左到右，奇数行从右到左
        let col = if row % 2 == 0 { col_in_row } else { cfg.wrap_n - 1 - col_in_row };
        Position {
            x: cfg.start_x + col as f64 * cfg.col_gap,
            y: cfg.start_y + row as f64 * cfg.row_gap,
        }
    }).collect();
    LayoutResult::Computed(positions)
}

fn has_branches(nodes: &[CanonicalNode]) -> bool {
    nodes.iter().any(|n| matches!(n.kind, NodeKind::Condition | NodeKind::Loop))
}
```

**S 形目的**：行末到下行首的 edge 距离始终是一个 col_gap（垂直），而不是从右端到左端的横跨。读起来仍是「从左到右、然后从上到下」，符合用户表述。

### 5.3 NeedsBranchLayout sentinel

`compact_to_canonical` / `legacy_to_canonical` 调 `auto_layout`：

- `Computed(positions)` → 节点 `position = Some(pos)`
- `NeedsBranchLayout` → 节点 `position = None`（序列化为 `"position": null` 或字段省略）

**JSON wire 形态**：`Option<Position>` 序列化。`CanonicalNode` 类型改：

```rust
pub struct CanonicalNode {
    ...
    #[serde(skip_serializing_if = "Option::is_none")]
    pub position: Option<Position>,  // 之前是 Position
    ...
}
```

向后兼容：旧的 `position: {x, y}` 反序列化仍然成功。

### 5.4 前端 fallback — dagre LR

`src/stores/workflow.ts:applyJsonText` 与 `importRecordedNodes` 共用一个新 helper：

```ts
async function importCanonicalWorkflow(canonical: CanonicalWorkflow) {
    const needsBranchLayout = canonical.nodes.some(n => n.position == null);
    if (needsBranchLayout) {
        applyDagreLayout(canonical.nodes, canonical.edges, 'LR');
    }
    nodes.value = canonical.nodes.map(canonicalNodeToVue);
    edges.value = canonical.edges.map(canonicalEdgeToVue);
}
```

`applyDagreLayout` 内部用现有的 `dagre.graphlib.Graph`（autoLayout 已经在用），把 rankdir 设 `LR`，写回 `node.position`。

### 5.5 录制路径合并

**现状**：`workflow.importRecordedNodes`（workflow.ts:123-154）手算 `i*80` 不走 transform。

**修改**：录制结束时把 `RecordedNode[]` 包成 `{nodes, edges: []}` 的 Recording 格式 → `invoke('workflow_transform_import', {json})` → 走和 paste 一样的路径。

```ts
async function importRecordedNodes(recordedNodes: RecordedNode[]) {
    const recordingJson = {
        name: 'Recording',
        nodes: recordedNodes,
        edges: [],
    };
    const canonical = await invoke<CanonicalWorkflow>('workflow_transform_import', { json: recordingJson });
    await importCanonicalWorkflow(canonical);
}
```

老的手算 stack 代码删除。

---

## 6. Section 3 / Workspace 文件模型

### 6.1 目录结构

```
<dirs::data_dir()>/com.mimicry.app/
├── mimicry.db                      # 现有
├── workflows/                      # 新建（默认 workspace 根）
│   ├── default/
│   │   ├── login-flow.mwf.json
│   │   └── checkout.mwf.json
│   └── <user-named subdir>/
└── venv/                           # 现有
```

### 6.2 路径解析顺序

| 优先级 | 来源 | 说明 |
|---|---|---|
| 1 | `MIMICRY_WORKSPACE_DIR` env var | dev 用，临时覆盖 |
| 2 | `<app_data>/com.mimicry.app/workflows/` | 默认（dev 与 prod 同一路径） |

平台映射（`dirs::data_dir()` 的语义）：

| OS | Dev/Prod 路径 |
|---|---|
| Linux | `~/.local/share/com.mimicry.app/workflows/` |
| macOS | `~/Library/Application Support/com.mimicry.app/workflows/` |
| Windows | `%APPDATA%\com.mimicry.app\workflows\` |

**为什么 dev 与 prod 同路径**：`dirs::data_dir()` 在 `cargo tauri dev` 与 release bundle 下都返回相同地址，已被 `mimicry.db` 与 venv 验证。开发期想隔离时设 env var。

### 6.3 文件格式

- **扩展名 `.mwf.json`** — Mimicry workflow file，`.mwf.json` 双后缀 → 文件管理器仍按 JSON 渲染，又能挂图标 / 默认打开应用
- **JSON 内部** = canonical workflow shape（`{id, name, nodes:[...], edges:[...], createdAt, updatedAt}`），与现有 `db::workflow::Workflow` 一致
- 一个 workflow 一个文件；无嵌套 / 无 sidecar 元数据文件

### 6.4 与 DB workflows 表共存（C1）

- DB `workflows` 表保留作「内置库 / 历史」
- 画布顶部加 source switcher：「DB Library」｜「File Workspace」
- 各自维护独立列表与 CRUD UI
- 提供单条「Save to file…」与「Import to library」按钮做手动迁移
- 长期目标（**本轮不做**）：把 DB 表标记为 read-only，文件成主路径

### 6.5 `recent_files` 表复用

已存在 schema：

```sql
CREATE TABLE recent_files (
    path TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    opened_at TEXT NOT NULL
);
```

CRUD 已在 `src-tauri/src/db/recent_files.rs`。直接复用：每次 `workspace_open_file` / `workflow.open` 都 upsert 一行；列表按 `opened_at DESC LIMIT N`。

---

## 7. Section 4 / 新 RPC / CLI / MCP

### 7.1 sidecar Python RPC（`sidecar/browser/actions.py` 加）

```python
import sqlite3
from pathlib import Path

# 新增工具函数
def _resolve_workspace_dir() -> Path:
    if env := os.environ.get("MIMICRY_WORKSPACE_DIR"):
        return Path(env).expanduser().resolve()
    return _app_data_dir() / "workflows"

def _resolve_db_path() -> Path:
    return _app_data_dir() / "mimicry.db"

@rpc_method("workflow.list", description="List .mwf.json files under a workspace dir.")
def workflow_list(workspace_dir: str | None = None) -> dict:
    base = Path(workspace_dir) if workspace_dir else _resolve_workspace_dir()
    files = []
    for p in base.rglob("*.mwf.json"):
        files.append({
            "path": str(p),
            "name": p.stem.replace(".mwf", ""),
            "size": p.stat().st_size,
            "modified": p.stat().st_mtime,
        })
    return {"workspace": str(base), "files": files}

@rpc_method("workflow.open", description="Read and validate a workflow file from disk.")
def workflow_open(path: str) -> dict:
    p = Path(path).expanduser().resolve()
    workflow = json.loads(p.read_text())
    # 写 recent_files
    _record_recent(str(p), p.stem.replace(".mwf", ""))
    return workflow

@rpc_method("workflow.save", description="Persist a workflow JSON to disk.")
def workflow_save(workflow: dict, path: str) -> dict:
    p = Path(path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(workflow, indent=2, ensure_ascii=False))
    _record_recent(str(p), p.stem.replace(".mwf", ""))
    return {"path": str(p), "size": p.stat().st_size}

@rpc_method("workflow.delete", description="Delete a workflow file.")
def workflow_delete(path: str) -> dict:
    p = Path(path).expanduser().resolve()
    p.unlink()
    return {"deleted": str(p)}

@rpc_method("workflow.recent", description="List recently opened workflow files.")
def workflow_recent(limit: int = 10) -> dict:
    db = _resolve_db_path()
    if not db.exists():
        return {"files": []}
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT path, name, opened_at FROM recent_files ORDER BY opened_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return {"files": [dict(r) for r in rows]}

def _record_recent(path: str, name: str) -> None:
    db = _resolve_db_path()
    if not db.exists():
        return  # DB 还没初始化（sidecar 比 Tauri 先启）
    conn = sqlite3.connect(db, timeout=2.0)  # WAL 下并发读写 OK
    conn.execute(
        "INSERT OR REPLACE INTO recent_files (path, name, opened_at) VALUES (?, ?, ?)",
        (path, name, datetime.now(tz=timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()
```

### 7.2 CLI 子命令（`sidecar/cli.py` 加 `workflow` 子命令）

```bash
mimicry workflow list [--dir DIR]                    # 列文件
mimicry workflow open <path>                         # 读出 JSON 到 stdout
mimicry workflow save <path>                         # 从 stdin 读 JSON 写文件
mimicry workflow delete <path>
mimicry workflow recent [--limit 10]
```

样例：

```bash
# 录制 → save 到文件
mimicry --json recording.stop > nodes.json
jq '{nodes: .nodes, edges: []}' nodes.json | mimicry workflow save ~/wf/login.mwf.json

# 列出 + 跑
mimicry workflow list
mimicry workflow open ~/wf/login.mwf.json | mimicry run -
```

### 7.3 MCP 桥接

无需手改：`mcp_server.py` 自动反射 `METHOD_REGISTRY` 把上述新 RPC 暴露为 `workflow_list / workflow_open / workflow_save / workflow_delete / workflow_recent` tools。

### 7.4 Tauri commands（前端调用）

`src-tauri/src/commands/workspace.rs`（新文件）：

```rust
#[tauri::command]
pub fn workspace_default_dir() -> Result<String, AppError> { ... }

#[tauri::command]
pub fn workspace_list_files(dir: Option<String>) -> Result<Vec<WorkflowFile>, AppError> { ... }

#[tauri::command]
pub fn workspace_open_file(path: String) -> Result<CanonicalWorkflow, AppError> { ... }

#[tauri::command]
pub fn workspace_save_file(path: String, workflow: Value) -> Result<(), AppError> { ... }

#[tauri::command]
pub fn workspace_recent_files(limit: u32) -> Result<Vec<RecentFile>, AppError> { ... }
```

**两个 API 的关键差异**：

| API | 调用方 | 读盘后是否跑 layout | 返回形态 |
|---|---|---|---|
| Tauri `workspace_open_file` | 前端画布 | **跑** `transform_import` → 包含 dagre 兜底 → position 一定有值 | canonical 全字段 |
| sidecar `workflow.open` | CLI / MCP | **不跑**（返回磁盘原始 JSON） | 原样 |

前端打开文件总会拿到带 position 的工作流；CLI/MCP 打开文件只做 round-trip，不污染数据。两者**读写同一组文件 + 同一 `recent_files` 表**，所以画布操作与 CLI 操作的状态视图等价。

### 7.5 schema 演进风险

- sidecar 直访 sqlite 仅触 `recent_files`（schema：path / name / opened_at）。这张表非常稳定，5 年内变更概率极低。
- 万一变了：在 `_record_recent` 中 try/except 包住，降级为「更新失败但不中断」。
- `workflows` 表 sidecar **绝不动**，避免与 Rust schema 演进竞争。

---

## 8. Section 5 / 前端 UX

### 8.1 顶栏 / 文件菜单

```
[Mimicry] File  Edit  ...  Run
           │
           ├─ New Workflow                Ctrl+N
           ├─ Open File...                Ctrl+O
           ├─ Open Recent       ►          Submenu: 最近 10 个
           ├─ Save                        Ctrl+S
           ├─ Save As...                  Ctrl+Shift+S
           ├─ ───────
           └─ Switch Workspace...
```

### 8.2 顶栏的 Library / Workspace 切换

画布左侧栏顶部加一个 segmented control：

```
[ Library | Workspace ]    (默认 Workspace)
↓
- Workspace 模式：显示 workflows/ 目录树，文件即 workflow
- Library 模式：显示 DB 行（现状）
```

### 8.3 文件路径与「未保存」标记

`workflow.ts` 新加：

```ts
const filePath = ref<string | null>(null);  // 当前打开的文件路径
const isDirty = ref(false);                  // 内存与磁盘是否一致
const persisted = ...;                        // 已有；改语义为「绑到某个文件」
```

标题栏：`<workflow name>` ／ 含 `*` 表示 dirty ／ tooltip 显示 path。

---

## 9. Section 6 / 自测试

### 9.1 测试组织

新建 `sidecar/tests/test_e2e_conversion_layer.py`，pytest fixture：

```python
@pytest.fixture
def daemon_workspace(tmp_path, monkeypatch):
    """启 sidecar daemon + 设置临时 workspace + 隔离 mimicry.db"""
    monkeypatch.setenv("MIMICRY_WORKSPACE_DIR", str(tmp_path / "workflows"))
    monkeypatch.setenv("MIMICRY_DATA_DIR", str(tmp_path))   # 顺便隔离 DB
    # 启 daemon (独立进程)
    proc = subprocess.Popen(["python", "-m", "main", "--daemon"], ...)
    wait_for_socket(...)
    yield tmp_path
    proc.terminate()
```

### 9.2 测试矩阵

| ID | 验证内容 | 触发方式 |
|---|---|---|
| T1 | bug A — 模拟事件序列 → events_to_workflow_nodes 不再多送 open | 单元测试，纯 Python |
| T2 | bug B — keydown event mock → press_key 节点正确含 Ctrl/Shift+ 前缀 | Playwright headless 真页面 + 模拟键 |
| T3 | Rust auto_layout — 16 个线性节点 → 蛇形 wrap，行 0 col 0..7、行 1 col 7..0 | Rust unit test |
| T4 | Rust auto_layout — 含 1 个 Condition → NeedsBranchLayout sentinel | Rust unit test |
| T5 | 前端 dagre fallback — 喂 sentinel → 跑出非 null position | Vitest |
| T6 | sidecar workflow.save → workflow.open round-trip | pytest CLI |
| T7 | sidecar workflow.list 扫文件 / sidecar workflow.recent 读 sqlite | pytest CLI |
| T8 | MCP `workflow_save` tool → `workflow_open` tool 等价 T6 | pytest with MCP stdio client |
| T9 | 录制路径 — RecordedNode → transform_import → canonical 与 paste 路径等价 | Vitest |

### 9.3 端到端 happy path 脚本（CLI）

```python
def test_full_flow_cli(daemon_workspace):
    ws = daemon_workspace / "workflows"
    
    # 1. mock 一段录制结果
    nodes = [
        {"kind":"action","action":"open","data":{"url":"https://example.com"}},
        {"kind":"action","action":"click","data":{"selector":"#login"}},
        # ... 共 16 个，触发换行
    ]
    workflow = {"name": "smoke", "nodes": nodes, "edges": []}
    
    # 2. workflow.save
    p = ws / "smoke.mwf.json"
    cli_run(f"mimicry workflow save {p}", stdin=json.dumps(workflow))
    assert p.exists()
    
    # 3. workflow.open，验证 round-trip 字节一致
    # （sidecar workflow.open 不跑布局；布局由 Rust auto_layout 单测覆盖 T3/T4）
    loaded = cli_run_json(f"mimicry workflow open {p}")
    assert loaded == workflow
    
    # 4. workflow.list 看到文件
    listed = cli_run_json(f"mimicry workflow list --dir {ws}")
    assert any(f["path"] == str(p) for f in listed["files"])
    
    # 5. workflow.recent 看到刚打开的
    recent = cli_run_json("mimicry workflow recent --limit 5")
    assert any(f["path"] == str(p) for f in recent["files"])
    
    # 6. workflow.delete
    cli_run(f"mimicry workflow delete {p}")
    assert not p.exists()
```

### 9.4 验收基线

- [ ] `cargo test --all` 全过（含新 Rust unit tests T3/T4）
- [ ] `python -m pytest sidecar/tests/` 全过（含 T1/T6/T7/T8）
- [ ] `pnpm test` 全过（含 T5/T9 vitest）
- [ ] `pnpm lint` 与 `cargo clippy --all-targets -- -D warnings` 干净
- [ ] 手动跑：`cargo tauri dev` → 录制 16 步 → 看到画布上蛇形排列；点 File→Save 写到 `~/.local/share/com.mimicry.app/workflows/`；File→Open Recent 看到该文件
- [ ] CLI 等价：`mimicry workflow list / open / save / recent / delete` 全可用
- [ ] MCP 等价：`mcp tools list` 看到 `workflow_list / open / save / delete / recent`

---

## 10. 触动文件清单

### 新建

```
docs/superpowers/specs/2026-05-01-conversion-layer-fixes-design.md   ← 本文
src-tauri/src/commands/workspace.rs
sidecar/tests/test_e2e_conversion_layer.py
```

### 修改

```
sidecar/browser/recorder.py         (bug A + bug B)
sidecar/browser/actions.py          (新增 5 个 @rpc_method)
sidecar/cli.py                      (新增 workflow 子命令)
sidecar/tests/test_recorder.py      (bug A / B 单元测试)

src-tauri/src/transform/layout.rs   (蛇形 wrap + LayoutResult)
src-tauri/src/transform/types.rs    (Position → Option<Position>)
src-tauri/src/transform/compact.rs  (调用新 layout)
src-tauri/src/transform/legacy.rs   (调用新 layout)
src-tauri/src/commands/mod.rs       (加 workspace)
src-tauri/src/commands/workflow.rs  (转化使用 new layout result)
src-tauri/src/lib.rs                (注册 workspace commands)

src/types/workflow.ts               (Position 可选)
src/utils/workflowSchema.ts         (canonicalNodeToVue 处理 null position)
src/stores/workflow.ts              (importRecordedNodes 重写、importCanonicalWorkflow helper、filePath/isDirty)
src/components/layout/Toolbar.vue   (Save/Open/Recent 按钮)
src/views/Editor.vue                (workspace switcher segment)
src/locales/en.json / zh-CN.json    (新文案 i18n)
```

---

## 11. 已知风险

| 风险 | 缓解 |
|---|---|
| `Position` 由 struct 改 `Option<Position>`，serde 反序列化老 JSON | 反序列化兼容性已验：`Option<T>` 接受 `null` 与缺省 |
| sidecar 直访 sqlite 与 Tauri 写 `recent_files` 竞争 | SQLite WAL 模式开启即可（已在 `db::schema::init`，需确认） |
| 用户已有 DB workflow，不知道还能继续用 | UI 加 Library 模式开关 + 文档迁移指南 |
| 前端 dagre 在 condition+loop 嵌套深时仍可能丑 | 本轮不解决；记 follow-up issue |
| `MIMICRY_WORKSPACE_DIR` 设错路径 | 启动时验证写权限，失败回落默认 + log warn |

---

## 12. Phased Implementation Sketch

| Phase | 内容 | 可并行性 |
|---|---|---|
| P1 | 录制 bug A + B（recorder.py 与 RECORDER_JS） | 独立，无依赖 |
| P2 | Rust transform — layout.rs 重写 + Position Option 化 + compact/legacy 调整 | 独立 |
| P3 | 前端转化路径合流 — workflowSchema + workflow.ts importCanonicalWorkflow | 依赖 P2 |
| P4 | sidecar 新 RPC（workflow.list/open/save/delete/recent） | 独立 |
| P5 | CLI workflow 子命令 | 依赖 P4 |
| P6 | Tauri workspace commands + 前端 UX（File 菜单、Library 开关） | 依赖 P2 + P4 |
| P7 | E2E 测试 + 验收 | 依赖全部 |

P1 / P2 / P4 可同时跑（分支独立）；P3 / P5 / P6 各依赖前置；P7 收尾。

---

## 13. Out of Scope（再确认）

- multi-user / 网络 workspace（FTP / S3 / GitHub）
- workflow 版本控制（git 集成）
- workflow 模板 / variables manager
- recording bug C/D/E（Enter 重复 / IME composition / 其它边缘） — 用户明确放后续轮
- DB workflows 表迁移到文件 — 后续轮
- dagre Rust 端口（分支布局完全自研）— 用前端 fallback 替代
- workflow 的 schema 校验加强（JSON Schema 资源化） — 与本轮无关

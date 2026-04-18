# 浏览器端到端集成 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打通 前端 → Rust → Python → Camoufox 完整链路，实现浏览器启动/导航/状态查询/关闭的端到端最小闭环，并支持 Camoufox 自动检测安装与设置页版本显示。

**Architecture:** 前端通过 Tauri invoke 调用 Rust 命令，Rust 通过 stdio JSON-RPC 转发到 Python sidecar，Python 调用 Camoufox SDK 操控浏览器。新增 Camoufox 环境检测命令，前端设置页和首次启动弹窗联动。

**Tech Stack:** Tauri v2 (Rust), Vue 3 + Pinia, Python 3.11+, Camoufox SDK, JSON-RPC 2.0 over stdio

---

## 文件结构概览

| 操作 | 文件 | 职责 |
|------|------|------|
| Modify | `sidecar/rpc/methods.py` | 新增 `camoufox.check` 和 `camoufox.install` RPC 方法 |
| Modify | `sidecar/browser/actions.py` | 新增 `camoufox.check`/`camoufox.install`/`camoufox.version` RPC 注册 |
| Create | `sidecar/browser/env_check.py` | Camoufox 环境检测与安装逻辑 |
| Modify | `src-tauri/src/commands/browser.rs` | 新增 `camoufox_check`/`camoufox_install`/`camoufox_version` 命令 |
| Modify | `src-tauri/src/lib.rs` | 注册新命令 |
| Modify | `src/stores/browser.ts` | 新增 navigate/status 方法 + camoufox 环境状态 |
| Create | `src/components/CamoufoxSetup.vue` | Camoufox 检测/安装弹窗组件 |
| Modify | `src/views/SettingsView.vue` | 添加 Camoufox 版本显示区块 |
| Modify | `src/views/EditorView.vue` | 集成 CamoufoxSetup 弹窗 |
| Create | `sidecar/tests/test_env_check.py` | env_check 单元测试 |
| Modify | `src/locales/zh-CN.json` | 新增国际化 key |
| Modify | `src/locales/en.json` | 新增国际化 key |

---

## Phase 1: Python Sidecar — Camoufox 环境检测

### Task 1: 创建 Camoufox 环境检测模块

**Files:**
- Create: `sidecar/browser/env_check.py`
- Create: `sidecar/tests/test_env_check.py`

- [ ] **Step 1: 编写 env_check 测试**

```python
# sidecar/tests/test_env_check.py
import pytest
from browser.env_check import CamoufoxEnv


def test_check_returns_dict():
    result = CamoufoxEnv.check()
    assert isinstance(result, dict)
    assert "installed" in result
    assert "version" in result
    assert isinstance(result["installed"], bool)


def test_version_string_or_none():
    result = CamoufoxEnv.check()
    if result["installed"]:
        assert isinstance(result["version"], str)
        assert len(result["version"]) > 0
    else:
        assert result["version"] is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd sidecar && python -m pytest tests/test_env_check.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'browser.env_check'`

- [ ] **Step 3: 实现 env_check 模块**

```python
# sidecar/browser/env_check.py
import subprocess
import sys
from loguru import logger


class CamoufoxEnv:
    @staticmethod
    def check() -> dict:
        """检测 Camoufox 是否已安装及版本信息"""
        try:
            import camoufox
            version = getattr(camoufox, "__version__", None)
            if version is None:
                # 尝试从 pip 获取版本
                version = CamoufoxEnv._get_pip_version()
            return {"installed": True, "version": version}
        except ImportError:
            return {"installed": False, "version": None}

    @staticmethod
    def _get_pip_version() -> str | None:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "show", "camoufox"],
                capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.splitlines():
                if line.startswith("Version:"):
                    return line.split(":", 1)[1].strip()
        except Exception:
            pass
        return None

    @staticmethod
    def install() -> dict:
        """安装 camoufox 包并下载浏览器"""
        try:
            logger.info("Installing camoufox...")
            # Step 1: pip install
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "camoufox[geoip]"],
                capture_output=True, text=True, timeout=300
            )
            if result.returncode != 0:
                return {"success": False, "error": f"pip install failed: {result.stderr}"}

            # Step 2: 下载浏览器二进制 (camoufox fetch)
            logger.info("Fetching Camoufox browser binary...")
            result = subprocess.run(
                [sys.executable, "-m", "camoufox", "fetch"],
                capture_output=True, text=True, timeout=600
            )
            if result.returncode != 0:
                return {"success": False, "error": f"camoufox fetch failed: {result.stderr}"}

            check = CamoufoxEnv.check()
            return {"success": True, "version": check["version"]}

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Installation timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd sidecar && python -m pytest tests/test_env_check.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add sidecar/browser/env_check.py sidecar/tests/test_env_check.py
git commit -m "feat(sidecar): add Camoufox environment detection module"
```

---

### Task 2: 注册 Camoufox 环境 RPC 方法

**Files:**
- Modify: `sidecar/browser/actions.py`

- [ ] **Step 1: 在 actions.py 末尾新增 RPC 方法**

在 `actions.py` 文件末尾添加：

```python
from browser.env_check import CamoufoxEnv


@rpc_method("camoufox.check")
def camoufox_check():
    return CamoufoxEnv.check()


@rpc_method("camoufox.install")
def camoufox_install():
    return CamoufoxEnv.install()
```

- [ ] **Step 2: 手动验证 RPC 方法注册**

Run: `cd sidecar && python -c "from browser.actions import *; from rpc.methods import get_registry; print([m for m in get_registry() if 'camoufox' in m])"`
Expected: `['camoufox.check', 'camoufox.install']`

- [ ] **Step 3: Commit**

```bash
git add sidecar/browser/actions.py
git commit -m "feat(sidecar): register camoufox.check and camoufox.install RPC methods"
```

---

## Phase 2: Rust 后端 — 新增 Camoufox 命令 + 修复路径问题

### Task 3: 添加 Camoufox 环境检测 Tauri 命令

**Files:**
- Modify: `src-tauri/src/commands/browser.rs`
- Modify: `src-tauri/src/lib.rs`

- [ ] **Step 1: 在 browser.rs 中添加 camoufox 命令**

在 `browser.rs` 现有命令之后追加：

```rust
#[tauri::command]
pub async fn camoufox_check(
    sidecar: tauri::State<'_, Mutex<Sidecar>>,
) -> AppResult<serde_json::Value> {
    sidecar_call(&sidecar, "camoufox.check", None).await
}

#[tauri::command]
pub async fn camoufox_install(
    sidecar: tauri::State<'_, Mutex<Sidecar>>,
) -> AppResult<serde_json::Value> {
    sidecar_call(&sidecar, "camoufox.install", None).await
}
```

- [ ] **Step 2: 在 lib.rs 注册新命令**

在 `generate_handler!` 宏中添加：

```rust
commands::browser::camoufox_check,
commands::browser::camoufox_install,
```

- [ ] **Step 3: 修复 sidecar 工作目录问题**

当前 `sidecar.rs` 使用相对路径 `current_dir("sidecar")`，在 `cargo tauri dev` 时工作目录是项目根目录，这可以工作。但需确认此路径在开发模式下正确。

检查 `sidecar.rs:start()` 中的 `current_dir("sidecar")` — 在 Tauri dev 模式下，Rust 的 CWD 是 `src-tauri/`，所以相对路径 `"sidecar"` 是错误的。需要改为 `"../sidecar"` 或使用绝对路径。

修改 `sidecar.rs` 的 `start` 方法：

```rust
// 替换 current_dir("sidecar") 为基于 app 资源路径的动态路径
// 开发模式下 CWD 是 src-tauri/，所以 sidecar 路径为 ../sidecar
pub async fn start(&mut self, python_path: &str) -> Result<(), AppError> {
    if self.child.is_some() {
        info!("Sidecar already running");
        return Ok(());
    }

    // 确定 sidecar 目录：优先 ../sidecar（dev 模式），回退 sidecar（prod 或根目录运行）
    let sidecar_dir = if std::path::Path::new("../sidecar/main.py").exists() {
        "../sidecar"
    } else if std::path::Path::new("sidecar/main.py").exists() {
        "sidecar"
    } else {
        return Err(AppError::Sidecar("Cannot find sidecar directory".into()));
    };

    info!("Starting sidecar: {} in {}", python_path, sidecar_dir);
    let mut child = Command::new(python_path)
        .arg("-u")
        .arg("main.py")
        .current_dir(sidecar_dir)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit())
        .spawn()
        .map_err(|e| AppError::Sidecar(format!("Failed to spawn sidecar: {}", e)))?;
    // ... rest unchanged
```

- [ ] **Step 4: 编译验证**

Run: `cd src-tauri && cargo check`
Expected: 编译通过

- [ ] **Step 5: Commit**

```bash
git add src-tauri/src/commands/browser.rs src-tauri/src/lib.rs src-tauri/src/ipc/sidecar.rs
git commit -m "feat(rust): add camoufox check/install commands, fix sidecar path"
```

---

## Phase 3: 前端 — Camoufox 环境检测与安装 UI

### Task 4: 扩展 browser store 支持 Camoufox 环境检测

**Files:**
- Modify: `src/stores/browser.ts`

- [ ] **Step 1: 在 browser store 中新增 camoufox 状态和方法**

在 `useBrowserStore` 内部添加：

```typescript
// Camoufox 环境状态
const camoufoxInstalled = ref(false);
const camoufoxVersion = ref<string | null>(null);
const camoufoxChecking = ref(false);
const camoufoxInstalling = ref(false);

async function checkCamoufox() {
  camoufoxChecking.value = true;
  try {
    const result = await invoke<{ installed: boolean; version: string | null }>("camoufox_check");
    camoufoxInstalled.value = result.installed;
    camoufoxVersion.value = result.version;
    return result;
  } catch (e) {
    console.error("Failed to check camoufox:", e);
    return { installed: false, version: null };
  } finally {
    camoufoxChecking.value = false;
  }
}

async function installCamoufox() {
  camoufoxInstalling.value = true;
  try {
    const result = await invoke<{ success: boolean; version?: string; error?: string }>("camoufox_install");
    if (result.success) {
      camoufoxInstalled.value = true;
      camoufoxVersion.value = result.version ?? null;
    }
    return result;
  } catch (e) {
    console.error("Failed to install camoufox:", e);
    return { success: false, error: String(e) };
  } finally {
    camoufoxInstalling.value = false;
  }
}
```

同时在 return 中导出这些状态和方法。

- [ ] **Step 2: 在 launch 方法中加入预检**

修改 `launch()` 方法，在启动前检查 Camoufox：

```typescript
async function launch() {
  if (launching.value) return;

  // 先检查 Camoufox 是否安装
  if (!camoufoxInstalled.value) {
    const check = await checkCamoufox();
    if (!check.installed) {
      // 由 UI 层处理弹窗
      return;
    }
  }

  launching.value = true;
  try {
    await invoke("browser_launch");
    connected.value = true;
  } catch (e) {
    console.error("Failed to launch browser:", e);
  } finally {
    launching.value = false;
  }
}
```

- [ ] **Step 3: 添加 navigate 和 status 方法**

```typescript
async function navigate(url: string) {
  try {
    await invoke("browser_navigate", { url });
  } catch (e) {
    console.error("Failed to navigate:", e);
  }
}

async function fetchStatus() {
  try {
    const result = await invoke<{ connected: boolean; url: string | null; pages: number }>("browser_status");
    connected.value = result.connected;
    return result;
  } catch (e) {
    console.error("Failed to get browser status:", e);
  }
}
```

- [ ] **Step 4: Commit**

```bash
git add src/stores/browser.ts
git commit -m "feat(store): add camoufox env check, navigate, status to browser store"
```

---

### Task 5: 创建 Camoufox 安装弹窗组件

**Files:**
- Create: `src/components/CamoufoxSetup.vue`
- Modify: `src/locales/zh-CN.json`
- Modify: `src/locales/en.json`

- [ ] **Step 1: 添加国际化 key**

在 `zh-CN.json` 中添加：

```json
{
  "camoufox": {
    "notInstalled": "Camoufox 未安装",
    "notInstalledDesc": "Mimicry 需要 Camoufox 反指纹浏览器来执行自动化任务。是否立即安装？",
    "installing": "正在安装 Camoufox...",
    "installingDesc": "正在下载并安装 Camoufox 浏览器，这可能需要几分钟...",
    "installSuccess": "Camoufox 安装成功",
    "installFailed": "安装失败",
    "install": "立即安装",
    "cancel": "稍后",
    "retry": "重试",
    "version": "版本",
    "status": "状态",
    "installed": "已安装",
    "notInstalledShort": "未安装"
  }
}
```

在 `en.json` 中添加对应英文。

- [ ] **Step 2: 创建 CamoufoxSetup.vue 弹窗**

```vue
<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useBrowserStore } from '../stores/browser'
import { Download, CheckCircle, XCircle, Loader2 } from 'lucide-vue-next'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const { t } = useI18n()
const browser = useBrowserStore()
const installError = ref<string | null>(null)

const state = computed(() => {
  if (browser.camoufoxInstalling) return 'installing'
  if (browser.camoufoxInstalled) return 'success'
  if (installError.value) return 'error'
  return 'prompt'
})

async function handleInstall() {
  installError.value = null
  const result = await browser.installCamoufox()
  if (!result.success) {
    installError.value = result.error ?? 'Unknown error'
  }
}
</script>
```

模板使用对话框样式，展示状态切换（prompt / installing / success / error）。

- [ ] **Step 3: Commit**

```bash
git add src/components/CamoufoxSetup.vue src/locales/zh-CN.json src/locales/en.json
git commit -m "feat(ui): add CamoufoxSetup dialog component"
```

---

### Task 6: 集成弹窗到编辑器视图

**Files:**
- Modify: `src/views/EditorView.vue`

- [ ] **Step 1: 在 EditorView 中引入 CamoufoxSetup**

在 EditorView 的 `<script setup>` 中：

```typescript
import CamoufoxSetup from '../components/CamoufoxSetup.vue'
import { useBrowserStore } from '../stores/browser'
import { ref, onMounted } from 'vue'

const browser = useBrowserStore()
const showCamoufoxSetup = ref(false)

onMounted(async () => {
  // 应用启动时检查 Camoufox 环境
  const result = await browser.checkCamoufox()
  if (!result.installed) {
    showCamoufoxSetup.value = true
  }
})
```

在模板中添加：

```html
<CamoufoxSetup
  :visible="showCamoufoxSetup"
  @close="showCamoufoxSetup = false"
/>
```

- [ ] **Step 2: 修改 launch 触发弹窗逻辑**

当用户点击启动浏览器但未安装 Camoufox 时，弹出安装弹窗：

```typescript
// 在 browser store 的 launch 方法返回状态后，EditorView 可以 watch
// 或直接在 toolbar 的 launch 按钮处检查
```

- [ ] **Step 3: Commit**

```bash
git add src/views/EditorView.vue
git commit -m "feat(ui): integrate CamoufoxSetup check on app startup"
```

---

### Task 7: 设置页添加 Camoufox 版本显示

**Files:**
- Modify: `src/views/SettingsView.vue`

- [ ] **Step 1: 在设置页新增 Browser 区块**

在 Appearance 区块之后添加新的 section：

```vue
<!-- Browser Engine -->
<section class="settings-section">
  <h2 class="section-title">{{ t('settings.browser') }}</h2>

  <div class="setting-row">
    <div class="setting-info">
      <Globe :size="16" class="setting-icon" />
      <span class="setting-label">Camoufox</span>
    </div>
    <div class="setting-control">
      <div class="camoufox-info">
        <span class="camoufox-status" :class="{ installed: browser.camoufoxInstalled }">
          {{ browser.camoufoxInstalled ? t('camoufox.installed') : t('camoufox.notInstalledShort') }}
        </span>
        <span v-if="browser.camoufoxVersion" class="camoufox-version">
          v{{ browser.camoufoxVersion }}
        </span>
        <button
          v-if="!browser.camoufoxInstalled"
          class="install-btn"
          :disabled="browser.camoufoxInstalling"
          @click="showCamoufoxSetup = true"
        >
          {{ t('camoufox.install') }}
        </button>
      </div>
    </div>
  </div>
</section>
```

- [ ] **Step 2: 在 settings i18n 中添加 browser key**

```json
{
  "settings": {
    "browser": "Browser Engine"
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add src/views/SettingsView.vue src/locales/zh-CN.json src/locales/en.json
git commit -m "feat(settings): show Camoufox version and install button"
```

---

## Phase 4: 端到端集成验证

### Task 8: 验证 stdio JSON-RPC 通信链路

**Files:** 无新文件

- [ ] **Step 1: 单独启动 Python sidecar 验证 RPC**

Run: `cd sidecar && echo '{"jsonrpc":"2.0","id":1,"method":"ping","params":{}}' | python -u main.py`
Expected: `{"jsonrpc": "2.0", "id": 1, "result": "pong"}`

- [ ] **Step 2: 验证 camoufox.check RPC**

Run: `cd sidecar && echo '{"jsonrpc":"2.0","id":2,"method":"camoufox.check","params":{}}' | python -u main.py`
Expected: `{"jsonrpc": "2.0", "id": 2, "result": {"installed": false, "version": null}}` 或 installed=true

- [ ] **Step 3: cargo tauri dev 启动全应用**

Run: `cargo tauri dev`

验证：
1. 应用启动后自动检测 Camoufox 环境
2. 如果未安装，弹出安装弹窗
3. 设置页显示 Camoufox 状态
4. 安装后可启动浏览器

- [ ] **Step 4: Commit 集成修复**

修复此阶段发现的任何问题后：

```bash
git add -A
git commit -m "fix: end-to-end integration fixes for browser pipeline"
```

---

### Task 9: 浏览器 launch → navigate → status 闭环

**Files:** 无新文件，验证已有功能

- [ ] **Step 1: 确认 Camoufox 已安装**

如果 Task 8 中 camoufox.check 返回 installed=false，先安装：

Run: `cd sidecar && python -c "from browser.env_check import CamoufoxEnv; print(CamoufoxEnv.install())"`

- [ ] **Step 2: 测试浏览器启动链路**

在运行中的 Tauri 应用中：
1. 点击工具栏的「启动浏览器」按钮
2. 验证 Camoufox 浏览器窗口弹出
3. DevTools Console 中无错误

- [ ] **Step 3: 测试导航功能**

在前端调用 `browser.navigate("https://example.com")`：
1. 浏览器导航到目标页面
2. `browser.fetchStatus()` 返回正确 URL

- [ ] **Step 4: 测试关闭功能**

点击关闭浏览器按钮：
1. Camoufox 窗口关闭
2. store 中 `connected` 变为 false

- [ ] **Step 5: 最终 commit**

```bash
git add -A
git commit -m "feat: browser launch/navigate/status end-to-end working"
```

---

## Phase 5: 工作流持久化对接（并行可选）

### Task 10: 前端 workflow store 对接 Rust CRUD

**Files:**
- Modify: `src/stores/workflow.ts`
- Modify: `src/stores/workspace.ts`

- [ ] **Step 1: 读取现有 workflow.ts 和 workspace.ts 结构**

了解当前 store 的 node/edge 管理方式，确定持久化注入点。

- [ ] **Step 2: 在 workflow store 或 workspace store 中添加持久化方法**

```typescript
async function loadWorkflows(): Promise<void> {
  const list = await invoke<Array<{ id: string; name: string; nodes: string; edges: string; created_at: string; updated_at: string }>>("workflow_list");
  // 映射到前端类型
}

async function saveWorkflow(): Promise<void> {
  const data = {
    id: currentWorkflow.value.id,
    name: currentWorkflow.value.name,
    nodes: JSON.stringify(nodes.value),
    edges: JSON.stringify(edges.value),
  };
  await invoke("workflow_save", data);
}

async function createWorkflow(name: string): Promise<string> {
  const id = await invoke<string>("workflow_create", { name, nodes: "[]", edges: "[]" });
  return id;
}

async function deleteWorkflow(id: string): Promise<void> {
  await invoke("workflow_delete", { id });
}
```

- [ ] **Step 3: 添加自动保存**

使用 `watchDebounced` 在 nodes/edges 变化后自动保存（debounce 1s）。

- [ ] **Step 4: Commit**

```bash
git add src/stores/workflow.ts src/stores/workspace.ts
git commit -m "feat(store): connect workflow CRUD to Rust backend"
```

---

## 执行顺序总结

```
并行路径 A (浏览器接入):           并行路径 B (工作流持久化):
Task 1 → Task 2 → Task 3          Task 10 (可与 A 同时进行)
      ↓
Task 4 → Task 5 → Task 6 → Task 7
      ↓
Task 8 → Task 9 (端到端验证)
```

Phase 1-2 (Python + Rust) 和 Phase 5 (工作流持久化) 可并行执行。
Phase 3 (前端 UI) 依赖 Phase 2 完成。
Phase 4 (集成验证) 依赖 Phase 1-3 全部完成。

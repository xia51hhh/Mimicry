# P1: 核心操作端到端跑通 + 命名映射层

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 确保现有 ~20 种 action 端到端可执行，建立前后端命名映射层，使画布节点→JSON→executor 全链路畅通。

**Architecture:** 添加 `ACTION_MAP` 映射表将前端 PascalCase 名称（Navigate/GoBack）与后端 lowercase 名称（open/back）双向转换。映射层放在 `sidecar/engine/action_map.py`（后端）和 `src/types/action-map.ts`（前端），两侧各自维护一份，保证前后端解耦。同时将 executor 中直接访问 `ctrl._page` 的操作下沉到 controller，消除私有属性穿透。

**Tech Stack:** Python (Playwright API via Camoufox), TypeScript (Vue 3), JSON-RPC

---

## File Structure

| 文件 | 操作 | 职责 |
|------|------|------|
| `sidecar/engine/action_map.py` | **Create** | 前后端 action 名称双向映射表 |
| `sidecar/browser/controller.py` | **Modify** | 补全缺失的浏览器操作方法 |
| `sidecar/engine/executor.py` | **Modify** | 用 controller 公共方法替代 `_page` 直调 |
| `src/types/action-map.ts` | **Create** | 前端映射表 + 转换函数 |
| `src/stores/workflow.ts` | **Modify** | 序列化/反序列化时应用映射 |
| `src/stores/execution.ts` | **Modify** | 执行时转换 action 名称 |
| `sidecar/tests/test_action_map.py` | **Create** | 映射表双向一致性测试 |

---

### Task 1: 创建后端 action 映射表

**Files:**
- Create: `sidecar/engine/action_map.py`
- Create: `sidecar/tests/test_action_map.py`

- [ ] **Step 1: 创建映射模块**

```python
# sidecar/engine/action_map.py
"""Bidirectional mapping between frontend PascalCase and backend lowercase action names."""

# Frontend (PascalCase) → Backend (lowercase)
FRONTEND_TO_BACKEND: dict[str, str] = {
    "Navigate": "open",
    "NewTab": "new_tab",
    "SwitchTab": "switch_tab",
    "CloseTab": "close_tab",
    "GoBack": "back",
    "GoForward": "forward",
    "Reload": "reload",
    "Click": "click",
    "DblClick": "dblclick",
    "Type": "type",
    "Hover": "hover",
    "Scroll": "scroll",
    "SelectOption": "select",
    "PressKey": "press_key",
    "Clear": "clear",
    "Focus": "focus",
    "Wait": "wait",
    "GetText": "extract_text",
    "GetAttribute": "extract_attr",
    "GetURL": "get_url",
    "Screenshot": "screenshot",
    "ExtractTable": "extract_table",
    "SetVariable": "set",
    "Export": "export",
    "RunScript": "run_script",
    "HttpRequest": "http_request",
    "Delay": "sleep",
    "Log": "log",
    "Comment": "comment",
    "HandleDialog": "handle_dialog",
    "UploadFile": "upload_file",
}

# Backend (lowercase) → Frontend (PascalCase)
BACKEND_TO_FRONTEND: dict[str, str] = {v: k for k, v in FRONTEND_TO_BACKEND.items()}


def to_backend(frontend_name: str) -> str:
    """Convert frontend action name to backend. Pass through if already backend."""
    return FRONTEND_TO_BACKEND.get(frontend_name, frontend_name)


def to_frontend(backend_name: str) -> str:
    """Convert backend action name to frontend. Pass through if already frontend."""
    return BACKEND_TO_FRONTEND.get(backend_name, backend_name)
```

- [ ] **Step 2: 写映射一致性测试**

```python
# sidecar/tests/test_action_map.py
from engine.action_map import FRONTEND_TO_BACKEND, BACKEND_TO_FRONTEND, to_backend, to_frontend


def test_maps_are_inverse():
    """Every frontend→backend entry must have a matching backend→frontend entry."""
    for fe, be in FRONTEND_TO_BACKEND.items():
        assert BACKEND_TO_FRONTEND[be] == fe, f"{be} should map back to {fe}"


def test_no_duplicate_backend_names():
    backends = list(FRONTEND_TO_BACKEND.values())
    assert len(backends) == len(set(backends)), "Duplicate backend names detected"


def test_to_backend_known():
    assert to_backend("Navigate") == "open"
    assert to_backend("GoBack") == "back"
    assert to_backend("Delay") == "sleep"


def test_to_frontend_known():
    assert to_frontend("open") == "Navigate"
    assert to_frontend("back") == "GoBack"
    assert to_frontend("sleep") == "Delay"


def test_passthrough_unknown():
    assert to_backend("unknown_action") == "unknown_action"
    assert to_frontend("unknown_action") == "unknown_action"
```

- [ ] **Step 3: 运行测试**

Run: `cd sidecar && python -m pytest tests/test_action_map.py -v`
Expected: 5 tests PASS

- [ ] **Step 4: Commit**

```bash
git add sidecar/engine/action_map.py sidecar/tests/test_action_map.py
git commit -m "feat: 添加前后端action名称双向映射表"
```

---

### Task 2: 补全 BrowserController 公共方法

**Files:**
- Modify: `sidecar/browser/controller.py`

当前 executor 直接访问 `ctrl._page` 执行 dblclick/hover/select_option/go_back/go_forward/reload/fill("") /focus/evaluate/locator 等操作。需要将这些提升为 controller 公共方法。

- [ ] **Step 1: 在 controller.py 末尾添加缺失方法**

在 `status()` 方法之后添加：

```python
    def dblclick(self, selector: str):
        self._page.dblclick(selector)

    def hover(self, selector: str):
        self._page.hover(selector)

    def select_option(self, selector: str, value: str):
        self._page.select_option(selector, value)

    def clear(self, selector: str):
        self._page.fill(selector, "")

    def focus(self, selector: str):
        self._page.focus(selector)

    def go_back(self):
        self._page.go_back()

    def go_forward(self):
        self._page.go_forward()

    def reload(self):
        self._page.reload()

    def press_key(self, selector: str, key: str):
        if selector and selector != "body":
            self._page.locator(selector).press(key)
        else:
            self._page.keyboard.press(key)

    def scroll(self, selector: str = "window", direction: str = "down", amount: int = 300):
        dy = amount if direction == "down" else -amount
        if selector == "window":
            self._page.evaluate(f"window.scrollBy(0, {dy})")
        else:
            self._page.locator(selector).scroll_into_view_if_needed()

    def evaluate(self, expression: str):
        """Run arbitrary JS expression and return result."""
        return self._page.evaluate(expression)

    def get_element_text(self, selector: str) -> str:
        return self._page.locator(selector).inner_text()

    def get_element_attribute(self, selector: str, attr: str) -> str | None:
        return self._page.locator(selector).get_attribute(attr)

    def get_element_count(self, selector: str) -> int:
        return self._page.locator(selector).count()

    def upload_file(self, selector: str, file_path: str):
        self._page.locator(selector).set_input_files(file_path)

    def new_tab(self, url: str = "") -> None:
        if not self._browser or not self._browser.contexts:
            raise RuntimeError("No browser context")
        page = self._browser.contexts[0].new_page()
        if url:
            page.goto(url)
        self._page = page

    def switch_tab(self, index: int) -> None:
        if not self._browser or not self._browser.contexts:
            raise RuntimeError("No browser context")
        pages = self._browser.contexts[0].pages
        if 0 <= index < len(pages):
            self._page = pages[index]
            self._page.bring_to_front()
        else:
            raise ValueError(f"Tab index {index} out of range (0-{len(pages)-1})")

    def close_tab(self, index: int | None = None) -> None:
        if not self._browser or not self._browser.contexts:
            raise RuntimeError("No browser context")
        pages = self._browser.contexts[0].pages
        if index is not None:
            if 0 <= index < len(pages):
                pages[index].close()
            else:
                raise ValueError(f"Tab index {index} out of range")
        else:
            self._page.close()
        # Switch to last remaining page
        remaining = self._browser.contexts[0].pages
        self._page = remaining[-1] if remaining else None

    def handle_dialog(self, accept: bool = True, text: str = "") -> None:
        """Pre-register handler for next dialog (alert/confirm/prompt)."""
        def handler(dialog):
            if accept:
                dialog.accept(text) if text else dialog.accept()
            else:
                dialog.dismiss()
        self._page.once("dialog", handler)
```

- [ ] **Step 2: 验证无语法错误**

Run: `cd sidecar && python -c "from browser.controller import BrowserController; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add sidecar/browser/controller.py
git commit -m "feat: 补全BrowserController公共方法(tab/dialog/hover/key等)"
```

---

### Task 3: 重构 executor 使用 controller 公共方法

**Files:**
- Modify: `sidecar/engine/executor.py`

- [ ] **Step 1: 导入映射模块**

在文件头部 import 区添加：

```python
from engine.action_map import to_backend
```

- [ ] **Step 2: 重写 `_execute_action` 方法**

将所有 `ctrl._page.xxx()` 调用替换为 `ctrl.xxx()` 公共方法：

```python
    def _execute_action(self, node: dict):
        action = to_backend(node.get("action", ""))
        ctrl = self._controller
        ctx = self._ctx

        match action:
            case "open":
                ctrl.navigate(ctx.resolve(node["url"]))
            case "back":
                ctrl.go_back()
            case "forward":
                ctrl.go_forward()
            case "reload":
                ctrl.reload()
            case "click":
                ctrl.click(ctx.resolve(node["selector"]))
            case "dblclick":
                ctrl.dblclick(ctx.resolve(node["selector"]))
            case "type":
                ctrl.type_text(ctx.resolve(node["selector"]), ctx.resolve(node.get("value", "")))
            case "clear":
                ctrl.clear(ctx.resolve(node["selector"]))
            case "select":
                ctrl.select_option(ctx.resolve(node["selector"]), ctx.resolve(node.get("value", "")))
            case "hover":
                ctrl.hover(ctx.resolve(node["selector"]))
            case "scroll":
                sel = ctx.resolve(node.get("selector", "window"))
                ctrl.scroll(sel, node.get("direction", "down"), node.get("amount", 300))
            case "focus":
                ctrl.focus(ctx.resolve(node["selector"]))
            case "press_key":
                sel = ctx.resolve(node.get("selector", "body"))
                ctrl.press_key(sel, ctx.resolve(node["key"]))
            case "wait":
                if node.get("selector"):
                    timeout = _parse_duration(node.get("timeout", "5s")) * 1000
                    ctrl.wait_for(ctx.resolve(node["selector"]), timeout=int(timeout))
                elif node.get("url_contains"):
                    target = ctx.resolve(node["url_contains"])
                    timeout = _parse_duration(node.get("timeout", "10s"))
                    deadline = time.time() + timeout
                    while time.time() < deadline:
                        if target in ctrl.get_url():
                            break
                        time.sleep(0.2)
                elif node.get("time"):
                    time.sleep(_parse_duration(node["time"]))
            case "extract_text":
                sel = ctx.resolve(node["selector"])
                into = node.get("into", "$_result")
                ctx.set_var(into, ctrl.get_element_text(sel))
            case "extract_attr":
                sel = ctx.resolve(node["selector"])
                into = node.get("into", "$_result")
                ctx.set_var(into, ctrl.get_element_attribute(sel, node.get("attrName", "")))
            case "extract_table":
                logger.warning("extract_table not yet implemented")
            case "get_url":
                into = node.get("into", "$_result")
                ctx.set_var(into, ctrl.get_url())
            case "set":
                ctx.set_var(node["variable"], node.get("value"))
            case "screenshot":
                ctrl.screenshot(node.get("filename", "screenshot.png"))
            case "log":
                parts = node.get("parts", [])
                resolved = [ctx.resolve(p) for p in parts]
                logger.info(f"[LOG] {' '.join(str(r) for r in resolved)}")
            case "sleep":
                time.sleep(_parse_duration(node.get("duration", "1s")))
            case "fail":
                raise RuntimeError(ctx.resolve(node.get("message", "Workflow failed")))
            case "new_tab":
                ctrl.new_tab(ctx.resolve(node.get("url", "")))
            case "switch_tab":
                ctrl.switch_tab(node.get("tabIndex", 0))
            case "close_tab":
                ctrl.close_tab(node.get("tabIndex"))
            case "handle_dialog":
                ctrl.handle_dialog(
                    accept=node.get("accept", True),
                    text=ctx.resolve(node.get("text", ""))
                )
            case "press_key":
                sel = ctx.resolve(node.get("selector", "body"))
                ctrl.press_key(sel, ctx.resolve(node["key"]))
            case "upload_file":
                ctrl.upload_file(
                    ctx.resolve(node["selector"]),
                    ctx.resolve(node["filePath"])
                )
            case "run_script":
                result = ctrl.evaluate(ctx.resolve(node["script"]))
                into = node.get("into")
                if into:
                    ctx.set_var(into, result)
            case "http_request":
                logger.warning("http_request not yet implemented")
            case "export":
                logger.warning("export not yet implemented")
            case "comment":
                pass  # No-op: comment blocks are for annotation only
            case _:
                logger.warning(f"Unknown action: {action}")
```

- [ ] **Step 3: 同样更新 `_execute_loop` 中的 `_page` 引用**

将 `self._controller._page.locator(selector)` 替换为 `self._controller.get_element_count(selector)` 来获取数量，使用 controller 公共方法：

```python
        elif lt == "items":
            selector = ctx.resolve(node.get("selector", ""))
            var = node.get("variable")
            max_iter = node.get("max", 100)
            count = min(self._controller.get_element_count(selector), max_iter)
            for i in range(count):
                if not ctx.running:
                    return
                if var:
                    ctx.set_var(var, i)
                self._execute_nodes(node.get("children", []))
```

- [ ] **Step 4: 同样更新 `_evaluate_condition` 中的 `_page` 引用**

将所有 `ctrl._page.locator(...)` 和 `ctrl._page` 调用替换为 controller 公共方法：

```python
    def _evaluate_condition(self, condition: str) -> bool:
        ctx = self._ctx
        ctrl = self._controller

        # exists("selector")
        m = re.match(r'exists\s*\(\s*"(.+?)"\s*\)', condition)
        if m:
            try:
                return ctrl.get_element_count(m.group(1)) > 0
            except Exception:
                return False

        # visible("selector")
        m = re.match(r'visible\s*\(\s*"(.+?)"\s*\)', condition)
        if m:
            try:
                return ctrl.evaluate(f'document.querySelector("{m.group(1)}")?.offsetParent !== null')
            except Exception:
                return False

        # url_contains("path")
        m = re.match(r'url_contains\s*\(\s*"(.+?)"\s*\)', condition)
        if m:
            return m.group(1) in ctrl.get_url()

        # text("selector") == "value"
        m = re.match(r'text\s*\(\s*"(.+?)"\s*\)\s*==\s*"(.+?)"', condition)
        if m:
            try:
                actual = ctrl.get_element_text(m.group(1))
                return actual == m.group(2)
            except Exception:
                return False

        # $var == "value" or $var == number
        m = re.match(r'(\$\w+)\s*==\s*"(.+?)"', condition)
        if m:
            return str(ctx.get_var(m.group(1), "")) == m.group(2)
        m = re.match(r'(\$\w+)\s*==\s*(\d+)', condition)
        if m:
            return ctx.get_var(m.group(1)) == int(m.group(2))

        # not condition
        if condition.startswith("not "):
            return not self._evaluate_condition(condition[4:].strip())

        logger.warning(f"Unknown condition: {condition}")
        return False
```

- [ ] **Step 5: 验证无语法错误**

Run: `cd sidecar && python -c "from engine.executor import WorkflowExecutor; print('OK')"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add sidecar/engine/executor.py
git commit -m "refactor: executor使用controller公共方法替代_page直调"
```

---

### Task 4: 更新 recorder 输出使用映射

**Files:**
- Modify: `sidecar/browser/recorder.py`

录制器的 `events_to_workflow_nodes` 输出的 action 名使用后端 lowercase（如 `click`, `open`），需要转换为前端 PascalCase 以便直接导入画布。

- [ ] **Step 1: 导入映射并更新输出**

在文件头部添加：
```python
from engine.action_map import to_frontend
```

在 `events_to_workflow_nodes` 方法末尾、`return nodes` 之前，对所有节点的 action 字段做转换：

```python
        # Convert backend action names to frontend PascalCase
        for node in nodes:
            if "action" in node:
                node["action"] = to_frontend(node["action"])

        return nodes
```

注意：`open` → `Navigate`, `click` → `Click`, `type` → `Type`, `select` → `SelectOption`, `dblclick` → `DblClick`, `scroll` → `Scroll`

- [ ] **Step 2: 验证**

Run: `cd sidecar && python -c "from browser.recorder import RecordingEngine; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add sidecar/browser/recorder.py
git commit -m "feat: recorder输出转换为前端PascalCase action名"
```

---

### Task 5: 创建前端映射表

**Files:**
- Create: `src/types/action-map.ts`

- [ ] **Step 1: 创建前端映射模块**

```typescript
// src/types/action-map.ts
/**
 * Bidirectional mapping between frontend PascalCase and backend lowercase action names.
 * Must stay in sync with sidecar/engine/action_map.py
 */

export const FRONTEND_TO_BACKEND: Record<string, string> = {
  Navigate: "open",
  NewTab: "new_tab",
  SwitchTab: "switch_tab",
  CloseTab: "close_tab",
  GoBack: "back",
  GoForward: "forward",
  Reload: "reload",
  Click: "click",
  DblClick: "dblclick",
  Type: "type",
  Hover: "hover",
  Scroll: "scroll",
  SelectOption: "select",
  PressKey: "press_key",
  Clear: "clear",
  Focus: "focus",
  Wait: "wait",
  GetText: "extract_text",
  GetAttribute: "extract_attr",
  GetURL: "get_url",
  Screenshot: "screenshot",
  ExtractTable: "extract_table",
  SetVariable: "set",
  Export: "export",
  RunScript: "run_script",
  HttpRequest: "http_request",
  Delay: "sleep",
  Log: "log",
  Comment: "comment",
  HandleDialog: "handle_dialog",
  UploadFile: "upload_file",
};

export const BACKEND_TO_FRONTEND: Record<string, string> = Object.fromEntries(
  Object.entries(FRONTEND_TO_BACKEND).map(([k, v]) => [v, k])
);

/** Convert frontend PascalCase to backend name. Passthrough if unknown. */
export function toBackend(name: string): string {
  return FRONTEND_TO_BACKEND[name] ?? name;
}

/** Convert backend name to frontend PascalCase. Passthrough if unknown. */
export function toFrontend(name: string): string {
  return BACKEND_TO_FRONTEND[name] ?? name;
}
```

- [ ] **Step 2: Commit**

```bash
git add src/types/action-map.ts
git commit -m "feat: 添加前端action映射表"
```

---

### Task 6: 集成映射到 workflow store 和 execution store

**Files:**
- Modify: `src/stores/workflow.ts` — 导入录制节点时转换
- Modify: `src/stores/execution.ts` — 发送执行请求时转换

- [ ] **Step 1: 在 workflow.ts 的 `importRecordedNodes` 中确保 action 名为前端格式**

录制器现在已经输出 PascalCase，所以 workflow store 不需要做额外转换。但在 `toJSON()` 序列化时需要将 action 转为后端格式给 executor：

在 `toJSON()` 方法中，遍历节点时转换：

```typescript
import { toBackend, toFrontend } from '../types/action-map'

// 在 toJSON() 序列化节点时:
// node.data.action = toBackend(node.data.action)

// 在 fromJSON() 反序列化时:
// node.data.action = toFrontend(node.data.action)
```

具体修改取决于现有 toJSON/fromJSON 实现。需读取后再确定插入点。

- [ ] **Step 2: 在 execution.ts 发送执行请求前转换 action 名**

在调用 `workflow.execute` RPC 前，将工作流 JSON 中的 action 名转为后端格式：

```typescript
import { toBackend } from '../types/action-map'

function convertNodesToBackend(nodes: any[]): any[] {
  return nodes.map(n => ({
    ...n,
    action: n.action ? toBackend(n.action) : n.action,
    children: n.children ? convertNodesToBackend(n.children) : undefined,
    elseChildren: n.elseChildren ? convertNodesToBackend(n.elseChildren) : undefined,
  }))
}
```

- [ ] **Step 3: 类型检查**

Run: `npx vue-tsc --noEmit`
Expected: 0 errors

- [ ] **Step 4: Commit**

```bash
git add src/stores/workflow.ts src/stores/execution.ts
git commit -m "feat: workflow/execution store集成action映射转换"
```

---

### Task 7: 更新 DSL compiler 使用映射

**Files:**
- Modify: `sidecar/dsl/compiler.py`

DSL compiler 的 `compile_to_json` 和 `decompile_from_json` 也需要在转换时使用正确的 action 名。

- [ ] **Step 1: 读取 compiler.py 确认修改点**

需要确认 compiler 当前使用哪种命名，以及在哪些点做转换。

- [ ] **Step 2: 在适当位置添加映射调用**

DSL 使用的是大写关键字 (OPEN, CLICK, TYPE)，compiler 输出 JSON 时应使用前端 PascalCase 名。

- [ ] **Step 3: Commit**

```bash
git add sidecar/dsl/compiler.py
git commit -m "feat: DSL compiler输出对齐前端action命名"
```

---

### Task 8: 端到端验证

- [ ] **Step 1: 启动应用**

Run: `cargo tauri dev`

- [ ] **Step 2: 手动验证流程**

1. 启动浏览器（Browser → Launch）
2. 导航到测试页面
3. 开始录制
4. 执行 click/type/scroll 操作
5. 停止录制
6. 确认节点以 PascalCase 名称导入画布
7. 执行工作流
8. 确认 executor 正确将 PascalCase 转为 backend 名执行

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: P1完成-核心操作端到端跑通+命名映射层"
```

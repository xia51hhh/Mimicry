# Block 反检测行为修正 + 功能补全 — 详细计划

## 背景

全量审计发现 42 个 block 在「理论设计」→「实际反检测效果」之间存在显著差距。
Camoufox `humanize=True` 提供了 C++ 级鼠标轨迹模拟，但应用层仍有 6 类行为暴露自动化特征。

---

## 第一部分：反检测行为修正（Phase 1）

### A1. type_text 使用 fill() — 🔴 极高风险

**当前实现** (`controller.py` L398):
```python
def type_text(self, selector: str, text: str):
    self._page.fill(selector, text)
```

**问题**:
- `fill()` 是 Playwright 的「程序化设值」接口，直接操作 DOM value 属性
- 不触发 `keydown` → `keypress` → `input` → `keyup` 事件序列
- 任何监听键盘事件的反爬脚本可以立即发现（很多登录框/搜索框都监听 `input` 或 `keyup`）
- 某些框架（React/Vue）依赖 `input` 事件触发状态更新，`fill()` 可能导致表单不响应

**修复方案**:
```python
import random

def type_text(self, selector: str, text: str, humanize: bool = True):
    locator = self._page.locator(selector)
    locator.click()  # 先聚焦（真实用户先点击输入框）
    if humanize:
        # 先清空已有内容
        locator.fill("")
        # 逐字符输入，随机延迟
        for char in text:
            locator.press(char, delay=random.randint(50, 180))
            # 偶尔有更长的停顿（模拟思考/看屏幕）
            if random.random() < 0.05:
                time.sleep(random.uniform(0.3, 0.8))
    else:
        locator.fill(text)
```

**注意事项**:
- `locator.type()` Playwright 方法已内置逐字符输入，但 `delay` 参数是固定值，不够随机
- 使用 `locator.press(char)` 逐个按键更接近真实行为
- 需要先 `fill("")` 清空，否则追加文字
- 对于长文本（>100字符），可考虑使用剪贴板粘贴 + 随机拆分（模拟真实用户复制粘贴行为）

**潜在问题**:
- 性能下降：100字符原来 <10ms，改后约 5-15 秒
- 对密码字段可能需要不同策略（不展示 * 号逐个打出的效果太慢）
- 建议：executor 层支持 `data.humanize` 字段，允许用户选择 fast(fill) / humanized(type)

---

### A2. 动作间无随机延迟 — 🔴 高风险

**当前实现** (`executor.py` `_execute_node`):
- 动作连续执行，间隔 0ms
- 1000个动作可能在 2 秒内全部完成

**问题**:
- 行为分析模型的首要检测特征就是「人类不可能的操作速度」
- 即使鼠标轨迹完美模拟，连续 click 间隔 <100ms 仍然暴露自动化

**修复方案** — 在 `_execute_node()` 的成功路径末尾添加:
```python
def _human_delay(self, action: str):
    """动作间随机延迟，模拟人类思考和视觉搜索时间"""
    if not self._humanize:
        return
    
    # 不同动作类型有不同的延迟特征
    delay_profiles = {
        "click": (0.3, 1.5),     # 点击后看结果
        "type": (0.1, 0.5),      # 打字间隙短
        "open": (1.0, 3.0),      # 导航后等待+阅读
        "scroll": (0.5, 2.0),    # 滚动后浏览
        "select": (0.3, 1.0),    # 选择后确认
        "hover": (0.2, 0.8),     # 悬停后阅读tooltip
    }
    low, high = delay_profiles.get(action, (0.3, 1.5))
    delay = random.uniform(low, high)
    
    # 偶尔更长的停顿（模拟分心/思考）
    if random.random() < 0.1:
        delay += random.uniform(1.0, 3.0)
    
    time.sleep(delay)
```

**注意事项**:
- `self._humanize` 标志由 workflow 配置控制（默认 True），调试时可关闭
- 延迟 profile 可作为 workflow 级配置暴露给用户调整
- 在 `_execute_node()` 的 `return  # success` 之前调用

**潜在问题**:
- 工作流执行时间大幅增加（50个节点从 2s → 约 60-90s）
- 用户调试时希望快速执行，需要明确的开关
- 建议：执行 API 增加 `humanize: bool` 参数，前端增加「快速执行（调试）」和「拟人执行」两种模式

---

### A3. 导航后无等待 — 🟡 中风险

**当前实现** (`controller.py` L389):
```python
def navigate(self, url: str):
    self._page.goto(url)
```

**问题**:
- `goto()` 默认等待 `load` 事件，但不等待动态内容（AJAX/SPA路由）
- 真实用户在页面加载后会有 1-5 秒的「浏览/定位」时间

**修复方案**:
```python
def navigate(self, url: str, wait_until: str = "networkidle"):
    self._page.goto(url, wait_until=wait_until)
    # 页面加载完成后的随机延迟由 _human_delay 处理
```

**注意事项**:
- `networkidle` 等待所有网络请求完成（500ms 无新请求），比 `load` 更可靠
- 某些 SPA 站点 networkidle 可能超时（无限轮询接口），需要配置 fallback
- 建议在 data 层支持 `waitUntil` 字段：`load | domcontentloaded | networkidle | commit`

**潜在问题**:
- `networkidle` 在有 WebSocket/SSE 连接的站点可能永不触发
- 需要合理的 timeout（默认 30s）+ fallback

---

### A4. scroll 绕过 humanize 管线 — 🟡 中风险

**当前实现** (`controller.py` L459):
```python
def scroll(self, selector="window", direction="down", amount=300):
    dy = amount if direction == "down" else -amount
    if selector == "window":
        self._page.evaluate(f"window.scrollBy(0, {dy})")
    else:
        self._page.locator(selector).evaluate(f"el => el.scrollBy(0, {dy})")
```

**问题**:
- `evaluate()` 直接执行 JS，完全绕过浏览器事件系统
- 不触发 `wheel` 事件，不产生 scroll inertia
- 反爬脚本可以通过 `addEventListener("wheel")` 检测到从未收到 wheel 事件但页面在滚动

**修复方案**:
```python
def scroll(self, selector="window", direction="down", amount=300):
    dy = amount if direction == "down" else -amount
    
    if selector == "window":
        # 使用 mouse.wheel 走原生事件管线
        # 分多次小步滚动，模拟真实滚轮行为
        remaining = abs(dy)
        while remaining > 0:
            step = min(remaining, random.randint(80, 150))
            actual_dy = step if dy > 0 else -step
            self._page.mouse.wheel(0, actual_dy)
            remaining -= step
            time.sleep(random.uniform(0.02, 0.08))  # 滚轮间隔
    else:
        # 元素内部滚动：先移动鼠标到元素位置，再用 wheel
        box = self._page.locator(selector).bounding_box()
        if box:
            cx = box["x"] + box["width"] / 2 + random.randint(-10, 10)
            cy = box["y"] + box["height"] / 2 + random.randint(-10, 10)
            self._page.mouse.move(cx, cy)
            remaining = abs(dy)
            while remaining > 0:
                step = min(remaining, random.randint(80, 150))
                actual_dy = step if dy > 0 else -step
                self._page.mouse.wheel(0, actual_dy)
                remaining -= step
                time.sleep(random.uniform(0.02, 0.08))
        else:
            # fallback to JS
            self._page.locator(selector).evaluate(f"el => el.scrollBy(0, {dy})")
```

**注意事项**:
- `page.mouse.wheel()` 是 Playwright 原生接口，触发 `wheel` 事件
- 分步滚动模拟真实滚轮物理特性（不是一次性跳 300px）
- Camoufox humanize 不覆盖 wheel 事件（只覆盖鼠标移动），所以需要我们自己模拟

**潜在问题**:
- 分步滚动会增加执行时间
- 某些站点拦截 wheel 事件做自定义滚动（如 fullpage.js），需要兼容
- 元素内滚动的 bounding_box 可能在 iframe 内返回 None

---

### A5. select_option 无前置交互 — 🟡 中风险

**当前实现** (`controller.py` L437):
```python
def select_option(self, selector: str, value: str):
    self._page.select_option(selector, value)
```

**问题**:
- 直接调用 select API，不模拟「点击下拉框 → 查看选项 → 选择」的真实流程
- `select_option` 是程序化操作，不触发 click/mousedown 事件

**修复方案**:
```python
def select_option(self, selector: str, value: str):
    locator = self._page.locator(selector)
    # 先点击下拉框（触发 focus + click 事件）
    locator.click()
    time.sleep(random.uniform(0.2, 0.5))  # 看选项
    # 再选择值
    locator.select_option(value)
```

**注意事项**:
- 对于原生 `<select>` 元素，`click()` + `select_option()` 是完整的交互序列
- 对于自定义下拉组件（div/ul based），这个方案无效，需要 `click()` + `click()` 找到选项
- 自定义下拉组件的情况，用户应该用 Click + Click 两个节点组合，而非 SelectOption

**潜在问题**:
- 某些浏览器在 `<select>` click 后打开原生下拉菜单，此时 `select_option()` 直接操作可能冲突
- 需要测试：Firefox/Camoufox 下 click + select_option 的兼容性

---

### A6. Recorder 不插入 wait 节点 — 🟡 中风险

**当前实现** (`recorder.py` `events_to_workflow_nodes`):
- 直接转换事件为动作节点，无 wait 插入

**问题**:
- 回放时 click 导致页面跳转，下一个动作的 selector 可能在新页面还没渲染
- 虽然 Playwright click/type 有内置等待（actionability checks），但复杂 SPA 可能需要显式等待

**修复方案** — 在 `events_to_workflow_nodes` 中：
```python
# 在导航事件后自动插入 wait
if url and url not in seen_navigations:
    seen_navigations.add(url)
    nodes.append(_make_node("open", {"url": url}))
    # 插入智能等待
    nodes.append(_make_node("wait", {
        "mode": "networkidle",
        "timeout": "10s"
    }))
```

**注意事项**:
- 只在导航后插入，不是每个动作后都插入
- 用户可以在编辑器中删除或调整不需要的 wait 节点
- 不能太激进地插入，否则录制结果过于冗长

---

## 第二部分：功能补全（Phase 2）

### B1. LoopElements 实现

**目标**: 遍历匹配 selector 的所有元素，对每个元素执行子节点。

**executor.py 新增 case**:
```python
case "loop_elements":
    sel = ctx.resolve(data["selector"])
    count = ctrl.get_element_count(sel)
    children = node.get("children", [])
    for i in range(count):
        ctx.set_var("$_index", i)
        ctx.set_var("$_element", f"{sel} >> nth={i}")
        try:
            self._execute_nodes(children)
        except _LoopBreak:
            break
```

**注意事项**:
- 使用 Playwright 的 `nth=` 选择器语法定位具体元素
- 子节点中的 selector 可以引用 `$_element` 变量
- 支持 LoopBreakpoint 提前退出

**潜在问题**:
- 页面动态加载可能导致元素数量变化（遍历到一半新元素出现）
- 建议：遍历开始时获取 count，遍历过程中不重新计数
- 元素删除场景（如循环删除列表项）需要倒序遍历

---

### B2. Tab 操作录制

**目标**: 在 recorder 中捕获 tab 创建/切换/关闭事件。

**recorder.py 修改**:
```python
# 在 _inject_recorder 的上下文中监听 page 事件
def _on_new_page(self, page):
    """新 tab 打开时注入 recorder 并记录事件"""
    self._events.append({
        "type": "new_tab",
        "url": page.url,
        "timestamp": time.time()
    })
    self._inject_recorder(page)

def _on_page_close(self, page):
    """tab 关闭时记录"""
    self._events.append({
        "type": "close_tab",
        "timestamp": time.time()
    })

# events_to_workflow_nodes 新增：
case "new_tab":
    nodes.append(_make_node("new_tab", {"url": event.get("url", "")}))
case "close_tab":
    nodes.append(_make_node("close_tab", {}))
```

**注意事项**:
- `context.on("page", handler)` 监听新 tab
- tab 切换检测较困难——Playwright 没有直接的 "page activated" 事件
- 可通过 page.on("focus") 或定时检查 `context.pages` 数组变化来检测

**潜在问题**:
- 弹窗/新窗口也会触发 `context.on("page")`，需要区分
- switch_tab 自动检测需要轮询或 hook visibility change API
- 建议第一版只录 new_tab 和 close_tab，switch_tab 让用户手动添加

---

### B3. DblClick 加入 PropertyPanel

**修改** (`PropertyPanel.vue`):
```typescript
{ group: t('blockCategories.interaction'), 
  items: ['Click', 'DblClick', 'Type', 'Hover', ...] }
```

**同时补全缺失的 block 类型**，按组新增：
```typescript
// 新增「等待」组
{ group: t('blockCategories.wait'), 
  items: ['Wait', 'WaitForPage', 'ElementExists'] },

// 新增「高级」组补充
{ group: t('blockCategories.advanced'), 
  items: ['RunScript', 'HttpRequest', 'Log', 'Delay', 'Comment', 
           'SwitchFrame', 'Cookie', 'HandleDownload', 'Transform'] },

// 新增「流程控制」组
{ group: t('blockCategories.flow'), 
  items: ['ExecuteWorkflow', 'Stop', 'LoopBreakpoint', 'WaitConnections'] },
```

---

## 第三部分：代码清理（Phase 3）

### C1. _normalize_node 幂等性

**当前问题**: canonical 节点经过 `_normalize_node` 后变成 `{type: "action", action: ..., data: {...}}`。如果再次调用，因已有 `type` 字段走 legacy 路径，但 legacy 路径会重新组装 data，可能丢失 canonical 的 data 内容。

**修复**: 在 `_normalize_node` 开头加检测：
```python
def _normalize_node(self, node: dict) -> dict:
    # 已规范化的节点直接返回
    if "type" in node and "data" in node and node["type"] in ("action", "condition", "loop"):
        return node
    # ... 原有逻辑
```

### C2. selectorScore 过滤

**修改** `workflow.ts` 的 `importRecordedNodes()`:
```typescript
const { selectorScore, ...cleanData } = rn.data
// 使用 cleanData 构建节点
```

---

## 第四部分：各 Block 理论到现实对照表

### 浏览器导航组

| Block | 后端 action | Controller 方法 | 当前行为 | 理想行为 | 差距 | 录制支持 |
|-------|------------|----------------|----------|----------|------|---------|
| Navigate | `open` | `navigate()` → `page.goto()` | 等待 load 事件 | 等待 networkidle + 随机延迟 | A3 | ✅ auto-insert |
| NewTab | `new_tab` | `new_tab()` → `ctx.new_page()` | 直接创建 | OK（浏览器内部操作无反检测需求） | - | ❌ B2 |
| SwitchTab | `switch_tab` | `switch_tab()` → `pages[i].bring_to_front()` | 直接切换 | OK | - | ❌ B2 |
| CloseTab | `close_tab` | `close_tab()` → `page.close()` | 直接关闭 | OK | - | ❌ B2 |
| GoBack | `back` | `go_back()` → `page.go_back()` | 直接后退 | 后退 + 等待页面 + 随机延迟 | A3 | ❌ |
| GoForward | `forward` | `go_forward()` → `page.go_forward()` | 直接前进 | 前进 + 等待页面 + 随机延迟 | A3 | ❌ |
| Reload | `reload` | `reload()` → `page.reload()` | 直接刷新 | 刷新 + 等待加载 + 随机延迟 | A3 | ❌ |
| HandleDialog | `handle_dialog` | `handle_dialog()` → `page.once("dialog")` | 注册一次性handler | OK（dialog是浏览器原生，无反检测问题） | - | ❌ |

### 页面交互组

| Block | 后端 action | Controller 方法 | 当前行为 | 理想行为 | 差距 | 录制支持 |
|-------|------------|----------------|----------|----------|------|---------|
| Click | `click` | `click()` → `page.click()` | Camoufox humanize 自动处理鼠标轨迹 | ✅ 已OK（humanize=True） | - | ✅ |
| DblClick | `dblclick` | `dblclick()` → `page.dblclick()` | 同上，humanize 覆盖 | ✅ 已OK | PropertyPanel B3 | ✅ |
| Type | `type` | `type_text()` → `page.fill()` | **瞬间设值，无键盘事件** | **逐字符输入 + 随机延迟** | **A1 🔴** | ✅ merge |
| Hover | `hover` | `hover()` → `page.hover()` | humanize 覆盖鼠标移动 | ✅ 已OK | - | ✅ |
| Scroll | `scroll` | JS `scrollBy()` | **绕过事件系统** | **mouse.wheel() 分步模拟** | **A4 🟡** | ✅ |
| SelectOption | `select` | `select_option()` → `page.select_option()` | **直接设值，无click** | **先click打开下拉再选择** | **A5 🟡** | ✅ |
| PressKey | `press_key` | `press_key()` → `page.keyboard.press()` | 原生键盘事件 | ✅ 已OK（走键盘事件管线） | - | ✅ |
| Clear | `clear` | `clear()` → `page.fill("")` | 瞬间清空 | 应该 Ctrl+A + Delete 更真实 | 低优先 | ❌ |
| Focus | `focus` | `focus()` → `page.focus()` | 程序化聚焦 | 应该通过 click 实现聚焦 | 低优先 | ❌ |
| UploadFile | `upload_file` | `set_input_files()` | 程序化设置文件 | OK（文件上传无法模拟人工拖拽） | - | ❌ |

### 数据提取组

| Block | 后端 action | 反检测风险 | 说明 |
|-------|------------|-----------|------|
| GetText | `extract_text` | 无 | 只读操作，不与页面交互 |
| GetAttribute | `extract_attr` | 无 | 只读 |
| GetURL | `get_url` | 无 | 只读 |
| Screenshot | `screenshot` | 无 | 浏览器内部操作 |
| ExtractTable | `extract_table` | 低 | evaluate() 执行 JS，但只读 |
| SetVariable | `set` | 无 | 纯内部操作 |
| Export | `export` | 无 | 写文件，不操作页面 |

### 高级/流程控制组

| Block | 后端 action | 反检测风险 | 说明 |
|-------|------------|-----------|------|
| RunScript | `run_script` | 取决于脚本内容 | evaluate() 在 isolated world |
| HttpRequest | `http_request` | 低 | 使用 urllib，不经过浏览器 |
| Wait | `wait` | 无 | 等待操作本身就是好行为 |
| WaitForPage | `wait_for_page` | 无 | 同上 |
| SwitchFrame | `switch_frame` | 无 | 浏览器内部操作 |
| Cookie | `cookie` | 无 | 浏览器内部操作 |
| ElementExists | `element_exists` | 无 | 只读检测 |
| HandleDownload | `handle_download` | 无 | 文件下载监听 |
| Transform | `transform` | 无 | 纯数据操作 |
| ExecuteWorkflow | `execute_workflow` | 继承子工作流的风险 | 递归执行 |
| LoopElements | `loop_elements` | 同子节点 | **B1: 未实现** |
| Stop | `stop` | 无 | 流程控制 |
| LoopBreakpoint | `loop_breakpoint` | 无 | 流程控制 |
| WaitConnections | `wait_connections` | 无 | 同步点 |
| Delay | `sleep` | 无 | 等待 |
| Log | `log` | 无 | 调试 |
| Comment | `comment` | 无 | 注释 |
| Fail | `fail` | 无 | 故意失败 |

---

## 第五部分：Recorder 事件 → Block 映射完整表

| JS 录制事件 | 转换目标 action | 录制的 data 字段 | 需要补充的 data |
|------------|----------------|-----------------|----------------|
| `click` | `click` | `{selector}` | - |
| `dblclick` | `dblclick` | `{selector}` | - |
| `type` | `type` | `{selector, value}` | - (merge 相邻) |
| `select` | `select` | `{selector, value}` | - |
| `scroll` | `scroll` | `{selector:"window", direction, amount}` | - |
| `hover` | `hover` | `{selector}` | - |
| `press_key` | `press_key` | `{selector, key}` | - |
| (URL 变化) | `open` | `{url}` | auto-insert |
| ❌ 未捕获 | `new_tab` | - | B2: 需添加 |
| ❌ 未捕获 | `close_tab` | - | B2: 需添加 |
| ❌ 未捕获 | `switch_tab` | - | B2: 需添加 |
| ❌ N/A | 其余 34 种 | - | 手动添加（预期行为） |

### Recorder 改进项

1. **导航后自动插入 wait 节点**（A6）
2. **监听 context.on("page") 捕获 new_tab**（B2）
3. **监听 page close 事件捕获 close_tab**（B2）
4. **selectorScore 字段标记为调试信息**（C2）

---

## 第六部分：实施顺序与风险评估

### 推荐实施顺序

```
Phase 1a: 基础设施
├── executor 添加 humanize 开关（全局 + 节点级）
├── controller 方法签名扩展 humanize 参数
└── 前端执行按钮增加「调试/拟人」切换

Phase 1b: 高风险修复
├── A1: type_text fill → type（影响：所有输入操作）
├── A2: _human_delay 动作间延迟（影响：执行时间）
└── A4: scroll 改用 mouse.wheel（影响：所有滚动操作）

Phase 1c: 中风险修复
├── A3: navigate 等待策略升级（影响：导航操作）
├── A5: select_option 加前置 click（影响：下拉选择）
└── A6: recorder 自动插入 wait（影响：录制结果）

Phase 2: 功能补全
├── B1: LoopElements 实现
├── B2: Tab 录制
├── B3: PropertyPanel 补全
└── i18n keys 补全

Phase 3: 清理
├── C1: _normalize_node 幂等
└── C2: selectorScore 过滤
```

### 风险点

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| type 改后某些站点表单不响应 | 中 | 高 | 保留 fill 模式作为 fallback |
| humanDelay 导致执行时间过长 | 高 | 中 | 提供开关 + 可配置延迟范围 |
| scroll wheel 在某些站点不工作 | 低 | 中 | JS evaluate 作为 fallback |
| select click 打开原生下拉后 select_option 冲突 | 中 | 中 | 测试 Firefox/Camoufox 兼容性 |
| networkidle 在 WebSocket 站点超时 | 中 | 中 | timeout + fallback to load |

---

## 第七部分：影响范围总结

| 文件 | 修改内容 |
|------|----------|
| `sidecar/browser/controller.py` | type_text / scroll / select_option / navigate 方法修改 |
| `sidecar/engine/executor.py` | _human_delay / humanize 开关 / loop_elements case |
| `sidecar/browser/recorder.py` | wait 自动插入 / tab 事件捕获 |
| `src/components/editor/PropertyPanel.vue` | actionTypes 补全 |
| `src/stores/execution.ts` | humanize 参数传递 |
| `src/stores/workflow.ts` | selectorScore 过滤 |
| `src/locales/en.json` + `zh-CN.json` | 新增 i18n keys |
| `docs/anti-detection.md` | 更新反检测文档 |

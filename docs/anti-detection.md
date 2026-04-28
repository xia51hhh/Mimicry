# Mimicry 反检测体系文档

## 概述

Mimicry 使用 [Camoufox](https://camoufox.com/) 作为反检测浏览器内核。反检测分为两层：
1. **浏览器指纹层**（Camoufox 内核）：C++ 级指纹注入 + 鼠标轨迹模拟
2. **行为模拟层**（Mimicry 应用层）：逐字符输入、动作间延迟、智能等待、真实滚动

两层协同确保自动化操作在指纹和行为两个维度均不可被检测。

## 第一层：浏览器指纹（Camoufox）

### 启动参数

| 参数 | 值 | 作用 |
|------|-----|------|
| `humanize` | `True` | C++ 级鼠标轨迹模拟（基于 HumanCursor 算法） |
| `os` | `"windows"` | 注入一致的 Windows 操作系统指纹 |
| `geoip` | `True` | 基于出口 IP 自动设置地理位置和时区 |
| `block_webrtc` | `True` | 阻止 WebRTC 泄露真实 IP 地址 |
| `enable_cache` | `True` | 启用浏览器缓存，行为更接近真实用户 |
| `disable_coop` | `True` | 禁用跨域隔离策略，兼容更多网站 |

### 配置位置

`sidecar/browser/controller.py` → `BrowserController.launch()` 方法

### C++ 级指纹注入
- 在 Firefox 引擎 C++ 代码中直接修改，而非 JS 层面覆盖
- Navigator、Screen、WebGL、Canvas、Audio 等 API 返回一致的伪装值
- 无法通过 JS 检测脚本发现指纹修改

### BrowserForge 指纹分布
- 使用 BrowserForge 库生成符合真实浏览器统计分布的指纹
- 每次启动随机生成唯一指纹组合
- 包含 UserAgent、平台、屏幕分辨率、WebGL 渲染器等

### 反泄露机制
- WebRTC IP 泄露防护 (`block_webrtc=True`)
- Font fingerprint 噪声注入
- Canvas/AudioContext 指纹随机化
- Battery API 伪装

### humanize 覆盖范围

Camoufox `humanize=True` 自动覆盖 Playwright 的以下操作：

| Playwright 方法 | humanize 覆盖 | 说明 |
|----------------|:---:|------|
| `page.click()` | ✅ | 生成贝塞尔曲线鼠标轨迹，随机落点 |
| `page.dblclick()` | ✅ | 同上 |
| `page.hover()` | ✅ | 同上 |
| `page.keyboard.press()` | ✅ | 走原生键盘事件管线 |
| `page.fill()` | ❌ | 程序化设值，无键盘事件序列 |
| `page.evaluate()` | ❌ | JS 直接执行，绕过事件系统 |
| `page.select_option()` | ❌ | 程序化设值，无 click 事件 |
| `page.mouse.wheel()` | ❌ | 触发原生 wheel 事件，但无 humanize 轨迹 |

## 第二层：行为模拟（Mimicry 应用层）

### 设计原则

Camoufox humanize 不覆盖的操作，由 Mimicry 在 `BrowserController` 和 `WorkflowExecutor` 层补充：

### 2.1 输入行为模拟

**文字输入** (`type_text`):
- 默认使用逐字符 `press()` 输入，每个按键间隔 50-180ms 随机
- 5% 概率插入更长停顿（300-800ms），模拟思考
- 可通过 `data.humanize: false` 切换为 `fill()` 快速模式
- 对应 Block: `Type`

**下拉选择** (`select_option`):
- 先 `click()` 打开下拉框（触发 focus + click 事件）
- 等待 200-500ms（模拟查看选项）
- 再 `select_option()` 选择值
- 对应 Block: `SelectOption`

### 2.2 滚动行为模拟

**页面滚动** (`scroll`):
- 使用 `page.mouse.wheel()` 触发原生 wheel 事件（非 JS scrollBy）
- 分多次小步滚动（每步 80-150px），模拟真实滚轮物理特性
- 步间间隔 20-80ms，模拟滚轮脉冲
- 元素内部滚动：先移动鼠标到元素区域，再用 wheel
- 对应 Block: `Scroll`

### 2.3 动作间延迟

**全局延迟系统** (`WorkflowExecutor._human_delay`):
- 在每个动作执行完成后自动插入随机延迟
- 前端提供延迟开关 + 全局延迟倍率控制
- 不同动作类型有不同的延迟 profile:

| 动作类型 | 基础延迟范围 | 说明 |
|---------|-------------|------|
| click | 300-1500ms | 点击后观察结果 |
| type | 100-500ms | 输入间隙较短 |
| open/navigate | 1000-3000ms | 页面加载后阅读 |
| scroll | 500-2000ms | 滚动后浏览内容 |
| select | 300-1000ms | 选择后确认 |
| hover | 200-800ms | 悬停后阅读 tooltip |
| 其他 | 300-1500ms | 默认 |

- 10% 概率额外增加 1-3 秒（模拟分心/思考）
- 所有延迟值乘以全局倍率系数（默认 1.0，可调 0.1-5.0）

### 2.4 导航等待策略

**页面导航** (`navigate`):
- 使用 `wait_until="networkidle"` 等待所有网络请求完成
- 超时 fallback 到 `load` 事件
- 导航后的随机等待由 `_human_delay` 统一处理
- 对应 Block: `Navigate`, `GoBack`, `GoForward`, `Reload`

### 2.5 录制智能等待

**Recorder 自动插入**:
- 检测到 URL 变化（导航）后，自动在录制结果中插入 `Wait` 节点
- Wait 节点默认为 `{mode: "networkidle", timeout: "10s"}`
- 用户可在编辑器中删除或调整

## 各 Block 反检测状态

### 需要行为模拟的 Block（与页面元素交互）

| Block | 后端 action | humanize 覆盖 | 应用层补充 |
|-------|------------|:---:|------------|
| Click | `click` | ✅ 鼠标轨迹 | 动作间延迟 |
| DblClick | `dblclick` | ✅ 鼠标轨迹 | 动作间延迟 |
| Type | `type` | ❌ | **逐字符输入** + 动作间延迟 |
| Hover | `hover` | ✅ 鼠标轨迹 | 动作间延迟 |
| Scroll | `scroll` | ❌ | **mouse.wheel 分步模拟** |
| SelectOption | `select` | ❌ | **先 click 再选择** |
| PressKey | `press_key` | ✅ 键盘事件 | 动作间延迟 |
| Clear | `clear` | ❌ | 低优先改进 |
| Focus | `focus` | ❌ | 低优先改进 |

### 无反检测风险的 Block（不与页面元素交互）

Navigate, NewTab, SwitchTab, CloseTab, GoBack, GoForward, Reload, HandleDialog,
Wait, WaitForPage, SwitchFrame, Cookie, ElementExists, HandleDownload,
GetText, GetAttribute, GetURL, Screenshot, ExtractTable, SetVariable, Export,
RunScript, HttpRequest, Transform, ExecuteWorkflow, LoopElements,
Stop, LoopBreakpoint, WaitConnections, Delay, Log, Comment, Fail, UploadFile

## 延迟控制 UI

前端在执行按钮旁提供：
- **延迟开关**: 启用/关闭动作间随机延迟（默认启用）
- **延迟倍率**: 滑块控制 0.1x - 5.0x（默认 1.0x）
- 关闭延迟时，所有动作间延迟和输入随机化均跳过，用于快速调试

## 检测站点测试结果

| 检测站点 | 结果 | 详情 |
|----------|------|------|
| [SannySoft](https://bot.sannysoft.com/) | ✅ PASS | 0 项红色标记 |
| [BrowserLeaks WebRTC](https://browserleaks.com/webrtc) | ✅ PASS | 无 IP 泄露 |
| [PixelScan](https://pixelscan.net/) | ✅ PASS | 指纹一致性通过 |
| [CreepJS](https://abrahamjuliot.github.io/creepjs/) | 📸 需人工审查 | 截图已保存 |
| [BrowserScan](https://www.browserscan.net/) | 📸 需人工审查 | 截图已保存 |

### 自动化测试命令
```bash
cd sidecar
python dev_cli.py anti-detect
```

### 截图存储位置
`sidecar/tests/screenshots/antidetect_*.png`

## 注意事项

1. **代理配合**: 生产环境建议搭配住宅代理使用，确保 IP 质量
2. **指纹一致性**: `geoip=True` 会自动匹配 IP 对应的时区和语言
3. **窗口尺寸**: 自动适配屏幕分辨率，避免异常窗口尺寸暴露
4. **humanize 模式**: Camoufox 鼠标轨迹模拟 + Mimicry 行为模拟双层协同
5. **延迟倍率**: 根据目标站点的反爬严格程度调整，严格站点建议 1.5-2.0x
6. **输入模式**: 敏感站点（登录/支付）建议保持逐字符输入模式

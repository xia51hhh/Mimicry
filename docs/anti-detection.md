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
| `geoip` | `False` | **已关闭**（Camoufox bug #589 会泄露错误时区） |
| `block_webrtc` | `True` | 阻止 WebRTC 泄露真实 IP 地址 |
| `enable_cache` | `True` | 启用浏览器缓存，行为更接近真实用户 |
| `disable_coop` | `True` | 禁用跨域隔离策略，兼容更多网站 |
| `i_know_what_im_doing` | `True` | 跳过 Camoufox 数据中心 IP 警告 |

> **注意**：`os` 参数不再硬编码，由 Camoufox 自动检测宿主操作系统。Profile 中可单独配置 `timezone` 和 `os`（详见下文）。

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

### 第三层：JS 注入反检测

录制器通过 `page.evaluate()` 注入 JS 事件监听代码。反检测脚本（如 Google reCAPTCHA）会遍历 `window` 属性检测自动化痕迹。

**策略：使用 Symbol Key 隐藏全局变量**

```javascript
// ❌ 旧方案 — 可被 for...in / Object.keys 枚举
window.__mimicryRecorder = true;
window.__mimicryEvents = [];

// ✅ 新方案 — Symbol 不可枚举，反检测脚本无法发现
const _k = Symbol.for('_mr');
window[_k] = true;

Object.defineProperty(window, Symbol.for('_me'), {
  value: () => events.splice(0),
  writable: false,
  enumerable: false,
  configurable: false
});
```

**关键特性**：
- `Symbol.for()` 在不同执行上下文间共享（跨 evaluate 调用可访问）
- `enumerable: false` 确保 `Object.keys()` / `for...in` 不会发现
- `configurable: false` 防止被删除或覆盖
- 不输出任何 `console.log`（Chrome DevTools Protocol 可监控）

**配置位置**：`sidecar/browser/recorder.py` → `RECORDER_JS`

## 检测维度模型

反机器人系统通过多维度综合评分判断自动化行为。单维度不及格不一定触发拦截，但多维度叠加会大幅提升风险评分。

| # | 维度 | 风险等级 | Mimicry 应对 |
|---|------|---------|-------------|
| 1 | **TLS/JA3 指纹** | 🔴 高 | Camoufox 使用真实 Firefox TLS 栈（非 Chromium） |
| 2 | **HTTP 请求头** | 🟡 中 | BrowserForge 随机生成符合统计分布的 UA/headers |
| 3 | **Navigator 属性** | 🟡 中 | C++ 级注入 platform/plugins/languages |
| 4 | **时区/地理** | 🔴 高 | geoip 已关闭；Profile 手动配置 timezone |
| 5 | **Canvas/WebGL** | 🟡 中 | Camoufox 噪声注入；已知 ANGLE 检测问题（见下文） |
| 6 | **Playwright 痕迹** | 🔴 高 | Symbol key 隐藏 + 无 console.log |
| 7 | **JS 全局变量** | 🔴 高 | 所有注入变量使用 Symbol.for() 存储 |
| 8 | **网络行为** | 🟡 中 | humanize + 动作间延迟 + 分步滚动 |
| 9 | **字体指纹** | 🟢 低 | Camoufox 噪声注入 + OS 匹配避免字体不一致 |
| 10 | **屏幕/窗口** | 🟢 低 | BrowserForge 真实分辨率分布 |
| 11 | **IP 声誉** | 🔴 高 | 建议搭配住宅代理（数据中心 IP 天然高风险） |
| 12 | **OS 一致性** | 🔴 高 | 不跨 OS 伪装；Camoufox 自动检测宿主 OS |

### 多维叠加效应

```
风险评分 = Σ(各维度权重 × 维度风险值)
```

以 Google 为例的实战分析：
- 数据中心 IP（#11）→ 基线风险 +30%
- `os="windows"` 在 Linux 上（#12）→ Canvas 字体渲染不一致 +20%
- `geoip=True` 时区泄露（#4）→ +15%
- `window.__mimicryRecorder` 可枚举（#7）→ +25%
- 单维度可能仅触发 CAPTCHA，四维度叠加直接触发 CAPTCHA 墙

**修复后**：移除 #4 #7 #12 三个维度的风险点，Google 搜索恢复正常。

## 已知问题与规避方案

### Camoufox Bug #589 — geoip 时区泄露
- **现象**：`geoip=True` 时 Camoufox 可能设置错误的 Intl.DateTimeFormat 时区
- **规避**：`geoip=False`，通过 Profile `browser_config.timezone` 手动指定

### Camoufox Issue #388 — Google 100% 检测
- **现象**：Google 使用 `page.goto("/search?q=...")` 直接访问搜索结果页会被 100% 检测
- **规避**：必须先导航到 `google.com`，再在搜索框中逐字符输入并按 Enter
- **原因**：Google 对直接 URL 访问有更严格的行为分析

### Camoufox Issue #514 — WebGL ANGLE 检测
- **现象**：Firefox 使用 ANGLE 渲染 WebGL（Google 的 GPU 抽象层），但 ANGLE in Firefox 极为罕见
- **规避**：暂无完美方案。替换 Mesa3D OpenGL 会产生新指纹
- **影响**：对非 Google 站点影响较小

### TCP/IP 指纹（zardaxt / proxydetect.live）
- **现象**：TCP SYN 包的 TTL/Window Size/Options 可泄露真实 OS
- **规避**：无法在用户态伪装；需要内核级 iptables 规则或中间代理
- **影响**：仅极少数高安全站点使用此检测

### Profile 配置指南

通过 Profile `browser_config` 可覆盖默认参数：

```json
{
  "browser_config": {
    "timezone": "Asia/Tokyo",
    "os": "linux",
    "locale": "ja-JP"
  }
}
```

- `timezone`：传入 Camoufox `config.timezone`，覆盖系统时区
- `os`：传入 Camoufox `os` 参数（`"windows"` / `"linux"` / `"macos"`）
- 不设置 `os` 时 Camoufox 自动使用宿主 OS（推荐）
- `locale`：影响 `Accept-Language` 和 `navigator.language`

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

> 测试环境：AWS Tokyo EC2（数据中心 IP），Linux x86_64，Camoufox v0.4.11

### 搜索引擎

| 站点 | 结果 | 测试方法 | 详情 |
|------|------|---------|------|
| Google | ✅ PASS | 逐字符输入 "zlib python" | 无 CAPTCHA，搜索结果正常返回 |
| Bing | ❌ FAIL | 逐字符输入 "playwright automation" | 触发 "One last step — Verify you are human" 复选框 |
| DuckDuckGo | ✅ PASS | 逐字符输入 "camoufox browser" | 搜索结果正常 |

### 反机器人/指纹检测

| 站点 | 结果 | 详情 |
|------|------|------|
| [Cloudflare Turnstile](https://nopecha.com/demo/cloudflare) | ❌ FAIL | Turnstile 复选框挑战未自动通过 |
| [BrowserScan](https://www.browserscan.net/) | ✅ PASS | 指纹扫描完成（截图已保存） |
| [SannySoft](https://bot.sannysoft.com/) | ✅ PASS | 0 项红色标记 |
| [BrowserLeaks WebRTC](https://browserleaks.com/webrtc) | ✅ PASS | 无 IP 泄露 |
| [PixelScan](https://pixelscan.net/) | ✅ PASS | 指纹一致性通过 |

### 失败原因分析

**Bing CAPTCHA**:
- Bing 使用类似 Cloudflare 的挑战机制
- 数据中心 IP 是主要触发因素（住宅 IP 大概率通过）
- 与 Camoufox 指纹无关 — 同 IP 下 Edge 浏览器也会触发
- 挑战类型为交互式复选框，无法自动绕过

**Cloudflare Turnstile**:
- Turnstile 需要点击复选框并通过 JS 行为分析验证
- Camoufox（Firefox 内核）在 Turnstile 上的通过率低于 Chromium
- 数据中心 IP 大幅增加触发概率
- 搭配住宅代理 + 浏览器 Profile 预热可改善

### 自动化测试命令
```bash
cd sidecar
# 运行全部反检测测试（默认 CI 跳过，需本地运行）
pytest tests/test_google_search.py -v -s
```

### 截图存储位置
`sidecar/tests/screenshots/`

## 注意事项

1. **代理配合**: 生产环境建议搭配住宅代理使用，数据中心 IP 天然高风险
2. **OS 一致性**: 不要跨 OS 伪装（Linux 上不设 `os="windows"`），会导致 Canvas/字体/WebGL 不一致
3. **时区配置**: `geoip` 已关闭（bug #589），需要时通过 Profile `browser_config.timezone` 手动指定
4. **Google 搜索**: 必须先导航到首页再在搜索框输入，禁止直接 `page.goto("/search?q=...")`
5. **窗口尺寸**: 自动适配屏幕分辨率，避免异常窗口尺寸暴露
6. **humanize 模式**: Camoufox 鼠标轨迹模拟 + Mimicry 行为模拟双层协同
7. **延迟倍率**: 根据目标站点的反爬严格程度调整，严格站点建议 1.5-2.0x
8. **输入模式**: 敏感站点（登录/支付）建议保持逐字符输入模式
9. **JS 注入**: 所有注入全局变量必须使用 `Symbol.for()` 存储，禁止使用可枚举属性
10. **console.log**: 注入代码禁止输出 console.log（CDP 可监控）

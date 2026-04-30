# 反检测生态调研报告（2026-04-30）

## 一、Camoufox 当前检测相关 Open Issues

> 来源：https://github.com/daijro/camoufox/issues — 232 Open / 157 Closed

### 阻断性 Bug

| # | Issue | 严重性 | 描述 |
|---|-------|---------|------|
| **#555** | Akamai 检测 v135 C++ 补丁 | 🔴 | canvas/font/css-animations 补丁在 JS 层可被 Akamai 行为分析检测。Bing/Hilton 等站点直接 403。CoryKing v142 已修复 |
| **#536** | PerimeterX 检测 | 🔴 | 与 #555 同源，Outlook 注册等 PerimeterX 保护站点被标记 |
| **#574** | Docker Turnstile 静默失败 | 🔴 | Camoufox `headless="virtual"` 创建 1×1 Xvfb，Cloudflare 检测此信号 |
| **#538** | FF146 WebRTC 代理泄露 | 🔴 | v146 alpha 中 `block_webrtc` 不生效，BrowserScan 检测代理真实 IP。blocking prefs 又导致被封 |
| **#516** | navigator 属性覆盖静默失效 | 🔴 | platform/hardwareConcurrency/oscpu config 被忽略，浏览器泄露真实值 |

### 高风险泄露

| # | Issue | 严重性 | 描述 |
|---|-------|---------|------|
| **#598** | system-ui CSS 泄露真实 OS | 🔴 | `font-family: system-ui` 解析为 GTK 真实字体。PR#599 修复中 |
| **#600** | font spacing perturbation 无法禁用 | 🟡 | config 覆盖在 init_script 前丢失，字体间距不可控 |
| **#589** | geoip 时区泄露 + 强制覆盖 | 🔴 | Intl.DateTimeFormat 设置错误时区 |
| **#577** | favicon 指纹追踪 | 🟡 | 新检测向量 |
| **#514** | WebGL ANGLE 检测 | 🟡 | Firefox 使用 ANGLE 极罕见，可被针对性检测 |

### 稳定性 / 运行问题

| # | Issue | 描述 |
|---|-------|------|
| **#505** | 稳定版发布延迟 | 25 条评论，社区信心动摇。维护者不活跃 |
| **#279** | 异步多页面冻结 | 13 条评论，并发不稳定 |
| **#245** | 内存持续增长 | 长时间运行 OOM |
| **#225** | 鼠标移动 bug | humanize 轨迹异常 |
| **#569** | v146 Brotli 解压损坏 | content-encoding: br 响应乱码 |
| **#572** | 只读环境挂起 | AWS Lambda / Cloud Run 部署失败 |

### 功能请求（社区需求风向）

| # | Issue | 描述 |
|---|-------|------|
| **#585** | Obscura 集成 — challenge-solver | 反机器人挑战自动求解 |
| **#584** | Cloudflare Turnstile solver | WAF 绕过 |
| **#583** | reCAPTCHA v3 solver | 验证码绕过 |
| **#582** | 浏览器并发池管理 | 生产级并发 |
| **#581** | HTTP API solver 服务 | 验证码解决 SaaS 化 |
| **#593** | CDP-style stream surface | IO 域流式传输 |
| **#578** | 隐私模板（librewolf/tor 模式） | 预设指纹模板 |

---

## 二、竞品生态对比

### 全景视图

```
┌─────────────────────────────────────────────────────────────────────┐
│                      反检测浏览器自动化生态                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  [Firefox 系]                    [Chromium 系]                       │
│                                                                     │
│  Camoufox (C++ 注入)             puppeteer-extra-stealth (JS 插件)   │
│   └─ Mimicry ← 我们               └─ 3年未更新，被高级WAF检测        │
│   └─ CoryKing fork v142                                             │
│   └─ CloverLabs fork             nodriver (直接 CDP，无 WebDriver)   │
│                                    └─ 5月未更新，无指纹伪装           │
│                                                                     │
│                                  undetected-chromedriver (UC)        │
│                                    └─ 被 nodriver 取代               │
│                                                                     │
│                                  SeleniumBase UC (Selenium 扩展)      │
│                                    └─ 活跃维护，JS 层隐身            │
│                                                                     │
│  [LLM + 云浏览器 SaaS]                                              │
│                                                                     │
│  Browser-Use (91k⭐)             Stagehand (22k⭐)                   │
│   └─ Chromium + 付费云隐身        └─ Browserbase verified sessions   │
│   └─ proxy rotation + captcha     └─ AI act/extract                 │
│   └─ MCP + CLI                    └─ 自修复缓存                      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 详细对比矩阵

| 维度 | Mimicry (Camoufox) | Browser-Use | Stagehand | puppeteer-stealth | nodriver |
|------|-------------------|-------------|-----------|-------------------|---------|
| **引擎** | Firefox (C++ patch) | Chromium | Chromium | Chromium | Chromium |
| **反检测层级** | C++ 编译级 | 云服务 | 云服务 | JS runtime | 协议级 |
| **指纹伪装** | BrowserForge 全维度 | 云端处理 | 云端处理 | 部分属性覆盖 | 无 |
| **TLS 指纹** | 真实 Firefox TLS | Chrome TLS | Chrome TLS | Chrome TLS | Chrome TLS |
| **humanize** | C++ 贝塞尔曲线 | LLM 语义操作 | AI 操作 | 无 | 基础 |
| **Captcha** | 无内置 | 云端求解 | verified sessions | 无 | cf_verify |
| **维护状态** | ⚠️ 主仓不活跃 | ✅ 活跃 (314人) | ✅ 活跃 (68人) | ❌ 3年停更 | ❌ 5月停更 |
| **Stars** | ~6k | 91.3k | 22.4k | 7.3k | 4.1k |
| **定价** | 免费开源 | 开源+付费云 | 开源+付费云 | 免费 | 免费 |
| **MCP 支持** | ✅ 52 tools | ✅ | ✅ | ❌ | ❌ |
| **Docker** | ⚠️ 有问题 | ✅ | ✅ | ✅ | ✅ |

### Mimicry 独特优势

1. **唯一 Firefox C++ 级方案**：所有竞品都是 Chromium，TLS/JA3 指纹相同。Firefox TLS 栈本身就是差异化
2. **本地完全自主**：不依赖云服务、不需要 API Key、数据不离开用户机器
3. **GUI 工作流编辑器**：唯一提供可视化 Flow 编辑 + 录制回放的本地工具
4. **MCP + CLI 双模**：开源方案中最完整的 AI Agent 集成

### Mimicry 关键劣势

1. **上游依赖风险**：Camoufox 主仓维护者不活跃，社区碎片化（多 fork 并存）
2. **无 Captcha Solver**：高安全站点无法自动通过
3. **无代理管理**：生产部署需要住宅代理支持
4. **容器化不成熟**：Docker 部署有阻断问题

---

## 三、Mimicry 反检测差距总结

### 检测维度完整性评估

| # | 检测维度 | 当前状态 | 差距 | 修复难度 |
|---|---------|---------|------|---------|
| 1 | TLS/JA3 | ✅ 真实 Firefox | 无 | - |
| 2 | HTTP Headers | ✅ BrowserForge | 无 | - |
| 3 | Navigator 属性 | ⚠️ 部分泄露 | #516 覆盖失效 | 等上游修复 |
| 4 | 时区/地理 | ✅ geoip 已关 | 需手动配 timezone | 低 |
| 5 | Canvas/WebGL | ✅ C++ 噪声 | ANGLE 检测、v135 补丁 | 升级 v142 |
| 6 | Playwright 痕迹 | ✅ Symbol 隐藏 | 无 | - |
| 7 | 字体指纹 | ⚠️ system-ui 泄露 | #598 等 PR 合并 | 等上游 |
| 8 | 行为/鼠标 | ✅ humanize + 应用层 | Incolumitas 行为分数 | 中 |
| 9 | WebRTC | ✅ block_webrtc | v146 回归 | 验证再升级 |
| 10 | 屏幕/窗口 | ⚠️ viewport 不一致 | JS vs CSS 尺寸 | 中 |
| 11 | IP 声誉 | ❌ 无代理管理 | 需集成代理池 | 高 |
| 12 | OS 一致性 | ✅ 自动检测 | 跨 OS 伪装受 #516 限制 | 等上游 |
| 13 | Captcha 绕过 | ❌ 无解决方案 | 需集成 solver | 高 |
| 14 | TCP/IP 指纹 | ❌ 无法用户态修改 | 需内核级或中间代理 | 极高 |

### 核心风险矩阵

```
影响大
  │
  │  [Camoufox 维护者不活跃]     [Akamai v135 阻断]
  │         ●                        ●
  │
  │  [system-ui 字体泄露]        [无 Captcha Solver]
  │         ●                        ●
  │
  │  [Docker 不可用]             [navigator 属性泄露]
  │         ●                        ●
  │
  │                [WebRTC v146 回归]
  │                       ●
  │
  │  [viewport 不一致]   [ANGLE 检测]
  │         ●                ●
  │
影响小 ─────────────────────────────────────────── 发生概率高
         低概率                              高概率
```

---

## 四、建议行动路线图

### Phase 0 — 紧急修复（本周）

- [ ] 升级 Camoufox 引擎到 CoryKing v142+ → 解除 Akamai/PerimeterX 阻断
- [ ] 验证 v142 的 WebRTC block_webrtc 是否正常
- [ ] 修复 Docker Xvfb 尺寸（如需容器化）

### Phase 1 — 指纹完善（1-2 周）

- [ ] 跟踪 #598 system-ui PR 合并，合并后升级
- [ ] 跟踪 #516 navigator 属性修复
- [ ] 修复 viewport vs JS innerWidth 不一致（设置 page.set_viewport_size 匹配 BrowserForge 指纹）
- [ ] 加入 WebRTC 代理 prefs 的条件逻辑（仅代理模式启用）

### Phase 2 — 能力补全（2-4 周）

- [ ] 集成 Captcha Solver API（2captcha / capsolver 作为可选后端）
- [ ] 代理管理模块（住宅代理池配置 + 自动轮换）
- [ ] Incolumitas 行为分数优化（真实鼠标轨迹录制回放）

### Phase 3 — 战略防御（长期）

- [ ] 评估维护 Camoufox fork 的可行性（如上游持续不活跃）
- [ ] 建立自动化检测回归测试（7 站挑战 CI 化）
- [ ] 监控 Chromium 生态动向（Chrome v140+ 的 DevTools 收紧）
- [ ] TCP/IP 指纹中间代理方案研究

---

## 附录：信息来源

- Camoufox Issues: https://github.com/daijro/camoufox/issues
- CoryKing Fork: https://github.com/coryking/camoufox
- Browser-Use: https://github.com/browser-use/browser-use (91.3k⭐)
- Stagehand: https://github.com/browserbase/stagehand (22.4k⭐)
- nodriver: https://github.com/ultrafunkamsterdam/nodriver (4.1k⭐)
- puppeteer-extra: https://github.com/berstend/puppeteer-extra (7.3k⭐)
- Mimicry 测试结果: docs/anti-detection.md

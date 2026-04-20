# Mimicry 反检测体系文档

## 概述

Mimicry 使用 [Camoufox](https://camoufox.com/) 作为反检测浏览器内核。Camoufox 在 Firefox C++ 引擎层面进行指纹注入，而非 JavaScript 层面的覆盖，因此无法被常规检测脚本识别。

## 反检测配置参数

| 参数 | 值 | 作用 |
|------|-----|------|
| `humanize` | `True` | 拟人化鼠标移动和键盘输入，模拟真实用户行为 |
| `os` | `"windows"` | 注入一致的 Windows 操作系统指纹 |
| `geoip` | `True` | 基于出口 IP 自动设置地理位置和时区 |
| `block_webrtc` | `True` | 阻止 WebRTC 泄露真实 IP 地址 |
| `enable_cache` | `True` | 启用浏览器缓存，行为更接近真实用户 |
| `disable_coop` | `True` | 禁用跨域隔离策略，兼容更多网站 |

### 配置位置

`sidecar/browser/controller.py` → `BrowserController.launch()` 方法

## Camoufox 核心特性

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
4. **humanize 模式**: 鼠标和键盘操作带有拟人随机延迟，不可关闭用于反检测场景

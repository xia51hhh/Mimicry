# 浏览器配置系统 — 设计方案

## 概述
在 Profile 编辑对话框中暴露 Camoufox 全量可配参数，每个 Profile 独立配置浏览器行为。新建 Profile 时自动填充推荐反检测默认值。

## Camoufox 可配参数（完整列表）

| 参数 | 类型 | 默认值 | UI 控件 | 分组 |
|------|------|--------|---------|------|
| `window` | (width, height) | 自动检测屏幕 | 数字输入 ×2 | 基础 |
| `headless` | bool | false | 开关 | 基础 |
| `os` | string | "windows" | 下拉: windows/macos/linux | 基础 |
| `geoip` | bool\|string | true | 开关(默认开) | 网络 |
| `proxy` | {server, username, password} | null | 已有 | 网络 |
| `block_webrtc` | bool | true | 开关 | 隐私 |
| `block_webgl` | bool | false | 开关 | 隐私 |
| `block_images` | bool | false | 开关 | 性能 |
| `enable_cache` | bool | true | 开关 | 性能 |
| `humanize` | bool\|float | true | 开关+滑条(0.5~5.0) | 行为 |
| `disable_coop` | bool | true | 开关 | 高级 |
| `locale` | string | 自动 | 文本输入 | 指纹 |
| `config` | JSON | {} | JSON 编辑器/结构化表单 | 指纹 |
| `addons` | string[] | [] | 文件选择(多个xpi) | 扩展 |
| `fonts` | string[] | [] | 文本列表 | 指纹 |
| `executable_path` | string | 自动 | 文件选择 | 高级 |
| `args` | string[] | [] | 文本列表 | 高级 |
| `virtual_display` | string | null | 文本输入 | 高级(Linux) |
| `startup_url` | string | about:blank | URL输入 | 基础 |

## 数据模型

### DB Schema 变更
profiles 表增加 `browser_config TEXT NOT NULL DEFAULT '{}'` 列。

### BrowserConfig 类型定义
```typescript
interface BrowserConfig {
  // 基础
  window_width?: number;
  window_height?: number;
  headless?: boolean;
  startup_url?: string;
  
  // 网络
  geoip?: boolean;
  // proxy 已有独立字段
  
  // 隐私/反检测
  block_webrtc?: boolean;
  block_webgl?: boolean;
  humanize?: boolean | number;
  
  // 性能
  block_images?: boolean;
  enable_cache?: boolean;
  
  // 指纹 (高级)
  locale?: string;
  fonts?: string[];
  
  // 高级
  disable_coop?: boolean;
  executable_path?: string;
  args?: string[];
  virtual_display?: string;
  addons?: string[];
}
```

### 默认反检测配置
新建 Profile 时的推荐默认值：
```json
{
  "geoip": true,
  "block_webrtc": true,
  "block_webgl": false,
  "humanize": true,
  "enable_cache": true,
  "disable_coop": true,
  "block_images": false,
  "headless": false
}
```

## 实现步骤

### Phase 1: 数据层
1. DB migration: ALTER TABLE profiles ADD COLUMN browser_config TEXT DEFAULT '{}'
2. Rust Profile struct: 增加 browser_config 字段
3. Rust CRUD: 读写 browser_config
4. 前端 Profile 类型: 增加 browser_config

### Phase 2: Python 端
5. controller.py launch(): 从 profile["browser_config"] 解析参数并合并到 kwargs
6. 窗口大小: browser_config.window_width/height 优先，否则走自动检测

### Phase 3: 前端 UI
7. ProfileDialog.vue: 分组展示配置项
   - 基础: 窗口大小、headless、启动页
   - 网络: GeoIP、(proxy 已有)
   - 隐私: WebRTC、WebGL、humanize
   - 性能: 图片屏蔽、缓存
   - 高级: 可折叠区域 (locale、fonts、args、executable_path)
8. 新建 Profile 自动填充默认反检测配置

### Phase 4: i18n
9. 添加中英文翻译

## UI 设计（ProfileDialog 内）
```
┌─ Profile 编辑 ──────────────────────┐
│ 名称: [________]                     │
│ OS:   [Windows ▼]                    │
│                                      │
│ ── 基础 ──                           │
│ 窗口大小: [1460] × [890]  [自动检测] │
│ 启动页:   [https://...]              │
│ Headless: [○]                        │
│                                      │
│ ── 网络 ──                           │
│ GeoIP:    [●]                        │
│ 代理:     [○] → 展开代理配置...       │
│                                      │
│ ── 反检测 ──                         │
│ 屏蔽 WebRTC: [●]                     │
│ 屏蔽 WebGL:  [○]                     │
│ 人类行为模拟: [●] ━━━○━━━ 1.0        │
│                                      │
│ ── 性能 ──                           │
│ 屏蔽图片: [○]                        │
│ 启用缓存: [●]                        │
│                                      │
│ ▶ 高级设置...                        │
│                                      │
│           [取消]  [保存]             │
└──────────────────────────────────────┘
```

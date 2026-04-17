# Package 系统设计

> **状态**: Draft | **最后更新**: 2026-04-17

参考 [设计决策 ADR-006](./decisions.md#adr-006-package-系统--完整-package)。

---

## 概述

Package 是多个 Block 的视觉封装单元，在画布上呈现为单个节点，但内部包含完整的子 Block 图。

```
画布视角（折叠）:
┌──────────┐     ┌──────────────────┐     ┌──────────┐
│ Navigate │────►│ 📦 登录流程      │────►│ Get Text │
└──────────┘     │  inputs: [url]   │     └──────────┘
                 │  outputs: [token]│
                 └──────────────────┘

画布视角（展开）:
┌──────────┐     ┌─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐     ┌──────────┐
│ Navigate │────►  📦 登录流程                         ────►│ Get Text │
└──────────┘     │                                   │     └──────────┘
                 │ ┌─────┐  ┌──────┐  ┌───────────┐ │
                 │ │Click│─►│ Type │─►│ Click     │ │
                 │ │用户名│  │密码  │  │登录按钮   │  │
                 │ └─────┘  └──────┘  └───────────┘ │
                 └─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
```

---

## 创建方式

### 从画布选中 Block 创建

```
1. 在画布上框选/Shift+点击多个 Block
2. 右键 → "创建 Package"
3. 弹出对话框:
   ┌──────────────────────────────────┐
   │  创建 Package                    │
   │                                  │
   │  名称: [登录流程              ]   │
   │  描述: [自动登录并获取token   ]   │
   │  颜色: [🟦 ▼]                   │
   │                                  │
   │  包含 Block (3):                 │
   │  ☑ Click (用户名输入框)          │
   │  ☑ Type (输入密码)               │
   │  ☑ Click (登录按钮)              │
   │                                  │
   │  [取消]           [创建]         │
   └──────────────────────────────────┘
4. 选中的 Block 被替换为单个 Package 节点
5. 原有连线自动转换为 Package 的输入/输出端口
```

### 从 Package 库创建

在侧边栏 Package 库中，拖拽已有 Package 到画布上即可创建实例。

---

## 展开 / 折叠

### 折叠状态（默认）

Package 在画布上呈现为单个节点，带有 📦 图标：

```
┌───────────────────────────┐
│  📦 登录流程               │
│  ───────────────────────  │
│  🔽 url (input)           │
│  🔽 username (input)      │
│  ───────────────────────  │
│  🔼 token (output)        │
│  🔼 success (output)      │
└───────────────────────────┘
```

### 展开状态

双击 Package 节点进入展开视图：

- 画布缩放到 Package 内部
- 显示所有内部 Block 及连线
- 面包屑导航：`工作流 > 登录流程`
- 可正常编辑/调试内部 Block
- 点击面包屑或按 Esc 返回上层

---

## 自定义输入 / 输出端口

### 定义端口

Package 的 IO 端口由用户显式定义，决定了 Package 作为单节点时的外部接口：

```json
{
  "inputs": [
    { "id": "in_1", "name": "url", "type": "string", "required": true },
    { "id": "in_2", "name": "username", "type": "string", "required": true },
    { "id": "in_3", "name": "password", "type": "string", "required": true }
  ],
  "outputs": [
    { "id": "out_1", "name": "token", "type": "string" },
    { "id": "out_2", "name": "success", "type": "boolean" }
  ]
}
```

### 端口绑定

在 Package 内部，输入端口绑定到指定 Block 的参数，输出端口绑定到指定 Block 的输出：

```
Package Input "url"  ──绑定──►  Navigate Block 的 data.url
Package Input "username" ──绑定──►  Type Block (用户名) 的 data.text

Get Token Block 的 output.token ──绑定──►  Package Output "token"
```

---

## Package 复用

### Package 库

侧边栏提供 Package 管理面板：

```
┌─────────────────────────┐
│  📦 Package 库           │
│                         │
│  🔍 搜索...              │
│                         │
│  ── 我的 Package ──      │
│  📦 登录流程             │
│  📦 数据采集模板         │
│  📦 分页翻页器           │
│                         │
│  ── 内置 Package ──      │
│  📦 Cookie 登录          │
│  📦 表格提取             │
│                         │
│  [+ 新建 Package]        │
└─────────────────────────┘
```

### 实例化

从库中拖入画布时，创建 Package 的一个**实例**：

- 实例持有对 Package 定义的引用
- 修改 Package 定义会影响所有实例
- 实例可覆盖输入参数默认值

---

## Package 存储格式

Package 在工作流 JSON 中的存储结构：

```json
{
  "packages": [
    {
      "id": "pkg_login",
      "name": "登录流程",
      "description": "自动登录并获取 token",
      "color": "#4a90d9",
      "inputs": [
        { "id": "in_1", "name": "url", "type": "string", "required": true },
        { "id": "in_2", "name": "username", "type": "string", "required": true },
        { "id": "in_3", "name": "password", "type": "string", "required": true }
      ],
      "outputs": [
        { "id": "out_1", "name": "token", "type": "string" },
        { "id": "out_2", "name": "success", "type": "boolean" }
      ],
      "nodes": [
        {
          "id": "pkg_node_1",
          "type": "interaction/Click",
          "position": { "x": 100, "y": 100 },
          "data": { "selector": "#username" },
          "settings": {}
        },
        {
          "id": "pkg_node_2",
          "type": "interaction/Type",
          "position": { "x": 350, "y": 100 },
          "data": {
            "selector": "#username",
            "text": "{{$package.username}}"
          },
          "settings": {}
        },
        {
          "id": "pkg_node_3",
          "type": "interaction/Type",
          "position": { "x": 600, "y": 100 },
          "data": {
            "selector": "#password",
            "text": "{{$package.password}}"
          },
          "settings": {}
        },
        {
          "id": "pkg_node_4",
          "type": "interaction/Click",
          "position": { "x": 850, "y": 100 },
          "data": { "selector": "#login-btn" },
          "settings": {}
        }
      ],
      "edges": [
        { "id": "pe1", "source": "pkg_node_1", "target": "pkg_node_2" },
        { "id": "pe2", "source": "pkg_node_2", "target": "pkg_node_3" },
        { "id": "pe3", "source": "pkg_node_3", "target": "pkg_node_4" }
      ],
      "inputBindings": {
        "in_1": { "nodeId": "pkg_node_1", "field": "data.url" },
        "in_2": { "nodeId": "pkg_node_2", "field": "data.text" },
        "in_3": { "nodeId": "pkg_node_3", "field": "data.text" }
      },
      "outputBindings": {
        "out_1": { "nodeId": "pkg_node_4", "field": "output.token" },
        "out_2": { "nodeId": "pkg_node_4", "field": "output.success" }
      }
    }
  ]
}
```

### Package 实例节点

在工作流的 `nodes` 数组中，Package 实例表示为：

```json
{
  "id": "node_10",
  "type": "advanced/Package",
  "position": { "x": 500, "y": 200 },
  "data": {
    "packageId": "pkg_login",
    "inputValues": {
      "url": "{{$var.baseUrl}}",
      "username": "{{$var.user}}",
      "password": "{{$var.pass}}"
    }
  },
  "settings": { "onError": "stop" }
}
```

---

## 执行行为

执行引擎处理 Package 节点时：

1. **展平执行**：将 Package 内部 Block 展平到执行序列中
2. **参数注入**：将 `inputValues` 绑定到内部 Block 的对应字段
3. **输出收集**：内部 Block 执行完毕后，收集 `outputBindings` 指定的数据作为 Package 输出
4. **透明调试**：展开状态下，内部 Block 正常参与断点和实时观察

---

## 相关文档

- [设计决策 ADR-006](./decisions.md#adr-006-package-系统--完整-package)
- [Block 体系设计](./block-system.md)
- [数据流设计](./data-flow.md)
- [调试系统设计](./debug-system.md)

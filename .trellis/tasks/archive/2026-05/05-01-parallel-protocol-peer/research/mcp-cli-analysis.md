# MCP 和 CLI 架构��析报���

**日期**: 2026-05-01  
**分���者**: zwx19990307  
**目的**: 对���当前 Mimicry 的 MCP/CLI 实现���文档示例��为后��改进���供基础

---

## 1. 架构���览

### 1.1 三种���口模式（��享底层）

```
┌─��──���──────��──���──┐
│  Tauri Frontend ��──stdio JSON-RPC──��
└��──���──��──���───��──���┘                  │
                                     ▼
┌────��──���────��──��─┐            ┌─��──���────��──��─┐
│   CLI Client    │─��UDS/TCP─���►│ Daemon       │
│   (cli.py)      │            │ (daemon.py)  │
��──��──���────��───��──���            └───��───��──���───┘
                                     │
���──────��──���────��──��                  │
│   MCP Client    │���─stdio MCP��──���───��
│ (Cursor/Claude) │                  │
└───��──���──��──���────┘                  │
                                     ���
                            ┌─��──��──���───��──���────��─┐
                            │  METHOD_REGISTRY    │
                            │  (rpc/methods.py)   │
                            └──��──��──���──────��──���──┘
                                     │
                                     ▼
                            ┌─────��──��──���────��──��─┐
                            ��  browser/actions.py ���
                            │  (54 个 RPC 方法)   │
                            └��──��──���───��──���────��──��
                                     │
                                     ▼
                            ┌─────��──��──��──���──────��
                            │  BrowserController  │
                            │  (Camoufox/PW)      │
                            └─���──────────��──���────��┘
```

**关键���现**：
- 所有三��模式通�� `@rpc_method` 装饰器注��到统���的 `METHOD_REGISTRY`
- 修改一次 `browser/actions.py`，三种��式同��生效
- 无重复代码，��合 DRY 原则

### 1.2 ��码规���

| 文��� | 行数 | 职责 |
|------|------|------|
| `browser/actions.py` | 618 | 54 个 RPC 方法定�� + 会话管理 |
| `cli.py` | 488 | CLI 客户�� + 命���解析 |
| `daemon.py` | 392 | 守��进程 + ��客户���连接管理 |
| `mcp_server.py` | 136 | MCP 协议适配 + schema ���动生成 |
| `rpc/protocol.py` | 88 | 长度��缀帧��议 (JSON-RPC 2.0) |
| `rpc/methods.py` | 64 | 方法���册器 + 元数据��储 |

**总��**: ~1,786 行核��代码

---

## 2. RPC 方法清��

### 2.1 ���计

- **总装饰��数**: 62 个 `@rpc_method`
- **实��方法���**: 58 个（4 个在 `rpc/methods.py`，54 个在 `browser/actions.py`）
- **跳���的方法**: 2 个��`shutdown`, `echo` 不暴��给 MCP）

### 2.2 方法���类

| 分类 | 方法�� | 示例 |
|------|--------|------|
| **浏览器生��周期** | 5 | `browser.launch`, `browser.close`, `browser.list_sessions` |
| **导��与页���** | 6 | `browser.navigate`, `browser.reload`, `browser.go_back` |
| **元��交互** | 15 | `browser.click`, `browser.type`, `browser.hover`, `browser.dblclick` |
| **元素���询** | 8 | `browser.wait`, `browser.get_text`, `browser.get_attribute` |
| **JS 执行** | 2 | `browser.evaluate`, `browser.evaluate_handle` |
| **截��与调��** | 3 | `browser.screenshot`, `browser.get_html` |
| **标��页管理** | 4 | `browser.new_tab`, `browser.switch_tab`, `browser.close_tab` |
| **录��** | 4 | `recording.start`, `recording.stop`, `recording.poll` |
| **工���流执��** | 7 | `workflow.execute`, `workflow.pause`, `workflow.step` |
| **系统** | 4 | `ping`, `heartbeat`, `system.info` |

### 2.3 前 20 个高���方法

```
 1. browser.launch          - 启��浏览���会话
 2. browser.close           - 关��会话
 3. browser.navigate        - 导航到 URL
 4. browser.click           - 点��元素
 5. browser.type            - 输��文本
 6. browser.wait            - 等待元素��现
 7. browser.screenshot      - ��图
 8. browser.evaluate        - 执行 JS
 9. browser.get_text        - ���取文本
10. browser.get_attribute   - 获���属性
11. browser.press_key       - 按��
12. browser.scroll          - 滚��
13. browser.hover           - 悬停
14. browser.dblclick        - 双击
15. browser.select_option   - 选择下拉框
16. browser.clear           - 清空输��框
17. browser.focus           - 聚���元素
18. browser.reload          - 刷��页面
19. browser.go_back         - 后退
20. browser.go_forward      - 前进
```

---

## 3. MCP Server 实现��析

### 3.1 自动 Schema ��成

**位��**: `sidecar/mcp_server.py:32-74`

```python
def _build_tool_schema(name: str, fn) -> dict:
    """从函数签名��动生��� JSON Schema"""
    sig = inspect.signature(fn)
    meta = METHOD_METADATA.get(name, {})
    param_descriptions = meta.get("param_descriptions", {}) or {}
    
    properties = {}
    required = []
    
    for pname, param in sig.parameters.items():
        # 跳过 self/cls
        # 根据���型注��生成 schema
        # 从 METHOD_METADATA 读取��数描述
        ...
```

**���势**：
- ���需手写 schema，减��维护负��
- 类型注�� → JSON Schema 自动���射
- ���数描述通�� `@rpc_method` 装饰器��中管���

**示例**：

```python
@rpc_method(
    "browser.click",
    description="Click an element matched by a CSS selector.",
    param_descriptions={
        "selector": "CSS selector (e.g. 'button#submit')",
        "session_id": "The session_id used at launch. Defaults to 'default'.",
        "force": "If true, bypass actionability checks.",
    },
)
def browser_click(selector: str, session_id: str = "default", force: bool = False):
    ...
```

���成的 MCP Tool Schema：

```json
{
  "name": "browser_click",
  "description": "Click an element matched by a CSS selector.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "selector": {
        "type": "string",
        "description": "CSS selector (e.g. 'button#submit')"
      },
      "session_id": {
        "type": "string",
        "default": "default",
        "description": "The session_id used at launch. Defaults to 'default'."
      },
      "force": {
        "type": "boolean",
        "default": false,
        "description": "If true, bypass actionability checks."
      }
    },
    "required": ["selector"]
  }
}
```

### 3.2 方法��转换

**问题**: MCP tool 名称不能��含 `.`（点���）

**解决���案**: `browser.click` → `browser_click`

```python
# mcp_server.py:97
tool_name = method_name.replace(".", "_")

# mcp_server.py:110-117 (调用��反向���换)
method_name = name.replace("_", ".", 1) if "_" in name else name
fn = METHOD_REGISTRY.get(method_name)
if fn is None:
    # 尝试��部替换
    method_name = name.replace("_", ".")
    fn = METHOD_REGISTRY.get(method_name)
```

**潜在��题**：
- `workflow_execute` ���能被误解�� `workflow.execute`（正��）或 `workflow_execute`（��误）
- 当前实现��回退���辑，但不��清晰

---

## 4. CLI + Daemon 实现分��

### 4.1 Daemon 架���

**位���**: `sidecar/daemon.py`

**设计模式**: IO 线程 + 主线��分离

```
┌��──���─────��──���────��──��────��──��──���─────��──���────┐
│              Daemon Process                 │
│                                             │
│  ┌───��───��───��──���         ┌��──���─────��────�� │
���  │  IO Thread   │         │ Main Thread  │ │
��  │              ���         │              │ │
��  │ Accept conn  │         │ Playwright   │ │
│  │ Read frames  │─queue──���│ Executor     │ │
│  ��� Send frames  │◄─��──���───│ Controller   │ ���
│  └─��────��──���───��┘         └─���────��───��──���┘ ��
│         │                        │          │
��         │                        │          │
��    UDS Socket              METHOD_REGISTRY  │
└─���────��──���───��──���────��──��──���──��─┼���────��──��───┘
          ��                      │
          ▼                      ▼
    ┌──��───��──���┐          ┌─���──��───��─┐
    │ CLI #1   │          │ CLI #2   │
    └��──���──��──���┘          └─��───��────��
```

**关��特性**：
1. **多客户��支持**: 多��� CLI 可同时连接
2. **快速响��方法**: `ping`, `heartbeat`, `workflow.pause` 等在 IO 线程直接处理
3. **Playwright 安全**: 所有浏览��操作��主线���（greenlet 要求��

### 4.2 协��细节

**��置**: `sidecar/rpc/protocol.py`

**���格式**:
```
┌─��────��──���──┬─��──��──���────��───��──���─────┐
│ 4 bytes    │ N bytes                 ��
│ (length)   │ (JSON payload UTF-8)    ���
└─���──��──���────┴��───��──���──────��──���──��───��┘
```

**消��类型** (JSON-RPC 2.0):
```json
// Request
{"id": "abc123", "method": "browser.click", "params": {"selector": "button"}}

// Response
{"id": "abc123", "result": {"clicked": "button"}}

// Error
{"id": "abc123", "error": {"code": -32000, "message": "Element not found"}}

// Notification (无 id)
{"method": "browser.session_closed", "params": {"session_id": "default"}}
```

### 4.3 CLI 命令���射

**位置**: `sidecar/cli.py`

| CLI 命令 | RPC 方��� | 参数转换 |
|----------|----------|----------|
| `launch` | `browser.launch` | `--headless` → `{"headless": true}` |
| `navigate <url>` | `browser.navigate` | `{"url": "<url>"}` |
| `click <sel>` | `browser.click` | `{"selector": "<sel>"}` |
| `type <sel> <text>` | `browser.type` | `{"selector": "<sel>", "text": "<text>"}` |
| `eval <js>` | `browser.evaluate` | `{"expression": "<js>"}` |
| `screenshot [path]` | `browser.screenshot` | `{"path": "<path>"}` |
| `run <file>` | `workflow.execute` | 读取 JSON 文件 |
| `pause` | `workflow.pause` | `{}` |
| `step [N]` | `workflow.step` | `{"count": N}` |

---

## 5. 文档示例对��

### 5.1 文���中的示例（`docs/llm-interactive-guide.md`）

```bash
# 基础��程
python cli.py launch
python cli.py navigate "https://www.bing.com"
python cli.py click "textarea#sb_form_q"
python cli.py type "textarea#sb_form_q" "github"

# ��级策略
python cli.py click "textarea#sb_form_q" --force
python cli.py type "textarea#sb_form_q" "github" --no-humanize

# JS 注入
python cli.py eval "document.querySelector('textarea#sb_form_q').value = 'github'"
```

### 5.2 实际实��验证

**检查点 1**: `--force` 和 `--no-humanize` ��数是���实现？

```bash
# 查找 --force ���现
grep -n "force" sidecar/cli.py
# 结果: 未找��� --force 参数���析

# 查找 --no-humanize 实���
grep -n "humanize" sidecar/cli.py
# 结��: 未��到 --no-humanize 参数��析
```

**结论**: 文档中��到的 `--force` 和 `--no-humanize` 参数**尚未在 CLI 中��现**。

**��查点 2**: RPC 方法���否支持这��参数���

```python
# browser/actions.py:128
def browser_click(selector: str, session_id: str = "default", force: bool = False):
    _mgr.get(session_id).click(selector, force=force)
    return {"clicked": selector}

# browser/actions.py:143
def browser_type(selector: str, text: str, session_id: str = "default", humanize: bool = True):
    _mgr.get(session_id).type_text(selector, text, humanize=humanize)
    return {"typed": selector}
```

**结论**: RPC 方法**已支��** `force` ��� `humanize` 参数���但 CLI 命��行解���**未暴���**这些参��。

---

## 6. 发现的��题

### 6.1 CLI 参��缺失

| 问题 | 影�� | 优先��� |
|------|------|--------|
| `click` 命令缺�� `--force` 参数 | 无��绕过 actionability 检查 | **P0** |
| `type` 命��缺少 `--no-humanize` 参数 | 无��快速输��（文���已承��） | **P0** |
| `launch` 命令缺少 `--proxy` 参数 | ��法通��� CLI 设置���理 | P1 |
| `launch` 命令缺少 `--profile` 参数 | 无法���过 CLI 设置��置文件 | P1 |

### 6.2 MCP 方���名歧义

**问题**: `workflow_execute` 可��被误���

**建议**: 
- 方案 1: 使用双��划线 `workflow__execute`（明��分隔符��
- 方案 2: 在 MCP metadata 中添加 `aliases` 字段
- 方��� 3: 保持��状，���赖回退逻��（当���实现）

### 6.3 文档��实现���一致

**位置**: `docs/llm-interactive-guide.md:112-122`

文档���称：
> **修复 1: `click` ���令支持 `--force`**
> **修复 2: `type` 命��支持 `--no-humanize`**

实际���况：
- RPC 方法支持这��参数 ✅
- CLI 命��行未暴露��些参�� ❌

**建��**: 
1. 立即实现 CLI 参��（P0）
2. 或更���文档，��明这��参数���在 MCP/RPC 模式��用

---

## 7. 优势总结

### 7.1 ��构优���

1. **统��注册��制**: `@rpc_method` 装饰��一次注��，三���模式共享
2. **���动 schema 生成**: 减���手写 schema 的��护成本
3. **类型���全**: ���数签名 + 类型���解 �� 自动���证
4. **��客户端支��**: Daemon 架构��许多��� CLI 同时连接
5. **会话隔离**: `session_id` 参数支持多��览器��例

### 7.2 开发体验

1. **添加新��法简���**: 
   ```python
   @rpc_method("browser.new_action", description="...")
   def browser_new_action(param: str):
       ...
   ```
   自动在 CLI、MCP、Tauri 三���模式生效

2. **参��描述���中管理**: 通��� `param_descriptions` 为 LLM 提供上��文

3. **错误���理统一**: 所有��常在 RPC 层统一��获并���换为 JSON-RPC error

---

## 8. 改进建议

### 8.1 短期��P0）

1. **补�� CLI 参数**:
   - `click --force`
   - `type --no-humanize`
   - `launch --proxy <url>`
   - `launch --profile <json>`

2. **修复文档��一致**:
   - 更��� `docs/llm-interactive-guide.md`
   - 添�� CLI 参数��例

### 8.2 ��期（P1）

1. **增强 MCP 元数据**:
   - 添加方法��类（category）
   - ��加示例（examples）
   - 添加相关方��链接��related）

2. **CLI 交互式模��改进**:
   - 添加���令补全
   - ��加历��记录
   - 添��多行���入支持

3. **Daemon 监控**:
   - 添加 `/metrics` 端点
   - 添加会话统��
   - 添加性能��标

### 8.3 长期（P2）

1. **MCP 高级���性**:
   - ��持 MCP Resources（��露录���结果、��图等���
   - 支持 MCP Prompts���预定��工作流模��）
   - 支持 MCP Sampling��让 LLM 主动���求下一步��

2. **CLI 插件���统**:
   - 允���用户��定义���令
   - 允许用��自定义快��方式

3. **跨���言 SDK**:
   - TypeScript SDK（前端直��调用���
   - Rust SDK���Tauri 内部优��）

---

## 9. ��比其��项目

### 9.1 Playwright CLI

**��势**:
- 官���支持，文档完��
- 代码���成器（codegen）

**劣���**:
- ��� MCP 支持
- 无 Daemon 模��（每���启动��进程）
- 无会话管��

### 9.2 Puppeteer CLI

**优势**:
- 生态成��

**���势**:
- 仅 Chrome/Chromium
- �� MCP 支持
- 无 Daemon 模式

### 9.3 Mimicry ��差异���

1. **三合��架构**: CLI + MCP + Tauri 共享���层
2. **Camoufox 集成**: 反检测��力
3. **工作流引��**: 支持暂停、��步、���点
4. **录制���能**: 自动生成��作流 JSON
5. **LLM 优先**: MCP 协议原生支��

---

## 10. 结论

### 10.1 当前状态

- **架��**: ✅ ���秀（统��注册���自动 schema、多��户端���
- **RPC 方法**: ✅ 完整��58 个方��覆盖���要场景）
- **MCP 实现**: ✅ 可用（��动生成 schema，支��� 54 个工具）
- **CLI 实��**: ⚠️ 部���缺失��文档���诺的参数未��现）
- **文档**: ⚠��� 不一���（需要更��）

### 10.2 下一步��动

1. **立即��复** (本周):
   - 实现 `click --force`
   - 实�� `type --no-humanize`
   - 更��文档

2. **��期改��** (本月):
   - 补全其他 CLI 参数
   - 增�� MCP 元��据
   - ��加集��测试

3. **���期规��** (本季度):
   - MCP Resources/Prompts
   - CLI 插件��统
   - 跨语��� SDK

---

**附录**: 完整��法清���见 `method-registry.txt`

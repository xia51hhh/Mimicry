# LLM 交互式驱动与自动化开发指南

> **状态**: Implemented | **最后更新**: 2026-04-30

本指南记录了基于 LLM Agent（如 Claude / Copilot 结合终端）驱动 Mimicry 进行交互式调试与工作流生成的最佳实践与排错流程。

---

## 1. 为什么需要 LLM 交互式驱动？

Web 自动化往往面临以下真实障碍：
- **前端框架拦截**：React/Vue 或自定义组件导致标准的 `page.click()` 因为无法通过 `Actionability Check`（元素不可见、被覆盖等）一直阻塞并最终 timeout（30000ms）。
- **反机器人机制**：Bing、Google 等网站常常设置隐形 `div` / `z-index` 的遮罩层，阻挡原生鼠标点击。
- **指纹与模拟策略**：Playwright 虽然能力强大，但如果不修改特征容易被封；此外 Playwright 默认的输入（`locator.click()` + `locator.press()`）在某些监听了全局事件或带复杂防抖限制的输入框（例如 Bing 的联想搜索框）上会引发严重卡顿与解析问题。

**传统 JSON 固定编码工作流（如 `Mimicry Workflow`）很容易直接“见光死”**。

通过**交互式命令行 (CLI) 或 MCP 工具**结合 LLM，可以让 Agent 充当真实的 WebDriver，采用「观察 -> 尝试执行 -> 报错诊断 -> 更换策略（绕过 / JS注入）」的动态闭环，并将验证可行的步骤最终固化到 JSON 中。

---

## 2. 交互接口: CLI 与 MCP

Mimicry 提供两种原生接口用于驱动和排错：

### 2.1 CLI 守护进程模式
核心控制入口在 `sidecar/cli.py`。这是低级、无状态但具备上下文保持能力的命令行客户端，能够通过 Unix Domain Socket/NamedPipe 将命令投递到持久化的 Daemon 进程运行的 BrowserController 中。

**基础使用示例**：
```bash
cd sidecar
source .venv/bin/activate

# 发起初始化与导航（会自动激活 daemon）
python cli.py launch
python cli.py navigate "https://www.bing.com"

# 执行动作
python cli.py click "a.link"               
python cli.py type "input" "hello"
```

### 2.2 MCP Server 模式
通过 Model Context Protocol 向 LLM Client (Cursor 等) 暴露包含同样控制链路的 54 个子工具。可以在 `.vscode/mcp.json` / Cursor 中引入该 MCP Server。
```json
{
  "servers": {
    "mimicry": {
      "type": "stdio",
      "command": "/path/to/venv/bin/python",
      "args": ["main.py", "--mcp"],
      "cwd": "${workspaceFolder}/sidecar"
    }
  }
}
```
**关键 MCP Tools**：`browser_launch`, `browser_navigate`, `browser_evaluate`, `browser_click`, `browser_type`, `browser_screenshot`。

---

## 3. 实战案例：Bing 搜索框防破防与调试过程复盘

以下是模拟 AI 尝试进行一次简单的「打开 Bing 并搜索特定词语」所经历的典型破防以及纠正全过程：

### 第一阶段：常规尝试（触发 Timeout）

LLM 首先利用标准的 `navigate` 与 `click` 指令发起操作，但遭遇 Playwright 的 `actionability timeout`。

```bash
# LLM 启动与导航
> python cli.py launch
> python cli.py navigate "https://www.bing.com"
> python cli.py screenshot "/tmp/check.png" 

# 根据视觉或 DOM 判定搜索框是 textarea#sb_form_q
> python cli.py click "textarea#sb_form_q"
```

**错误产出**：
```text
Error: Page.click: Timeout 30000ms exceeded.
Call log:
  - waiting for locator("textarea#sb_form_q")
    - locator resolved to <textarea name="q" rows="1" ...></textarea>
  - attempting click action
    - waiting for element to be visible, enabled and stable
    - ...
    - performing click action  <---- 永远卡死在这里
```
**根因**：Bing 在首页存在不可见的 `hp_fadein` 等遮罩层或是 React Synthetic Event 拦截，导致元素从坐标看是它，但底层的 Pointer 永远被截断。

### 第二阶段：感知分析与纯原生绕过 (JS Eval)

当 LLM 发现标准指令无法生效时，运用 `evaluate` 能力，通过前端 JS 注入进行诊断或直接强行驱动数据。

```bash
# 验证是否是因为上方叠加了 iframe / overlay
> python cli.py eval "const el = document.querySelector('textarea#sb_form_q'); const rect = el.getBoundingClientRect(); document.elementFromPoint(rect.x + rect.width/2, rect.y + rect.height/2).id"
# 返回 "sb_form_q"，说明表面上没被覆盖，但依旧无法触发 click。

# 改为终极方案：强行用 JS 执行焦点聚集、赋值、触发冒泡并提交表单
> python cli.py eval "const ta = document.querySelector('textarea#sb_form_q'); ta.focus(); ta.value = 'github'; ta.dispatchEvent(new Event('input', {bubbles: true})); document.querySelector('form#sb_form').submit(); 'submitted'"
```

通过这一指令，LLM 在 30 秒内完成了阻塞问题的攻克并成功到达结果页。

### 第三阶段：引擎能力下放 (The Fix)

为了无需每次都写冗长的 JS 注入，Mimicry 为此升级了核心 CLI 工具与 MCP 接口，加入了「降级 / 避障参数」：

**修复 1: `click` 命令支持 `--force`**
底层透传 Playwright 的 `force=True`，彻底无视 Actionability Checks，不检测目标元素是否遮挡。
```bash
> python cli.py click "textarea#sb_form_q" --force
```

**修复 2: `type` 命令支持 `--no-humanize`**
直接调用 `locator.fill(text)` 而非进行复杂的真实逐键敲击、延时和焦点切换。极大提升在复杂事件拦截框架（如 Bing 搜索框）中的数据输入成功率。
```bash
> python cli.py type "textarea#sb_form_q" "github" --no-humanize
```

---

## 4. 标准 LLM 工作步进协议 (Playbook)

在开发阶段，推荐遵循以下步骤（禁止妄加猜测进行死写 JSON 工作流）：

1. **初始化并可视化校验**
   利用 `browser_launch` 或 `launch` 打开窗口，通过 `browser_screenshot` 或视觉工具确定渲染完整性。

2. **步进执行 (Step-By-Step)**
   - 使用 `click` 和 `type`：如果一次性报错或超时，取消执行。
   - 降级测试：使用 `click --force` / `type --no-humanize` 测试是否由于拦截导致。
   - 完全自定义兜底：直接下发 `eval` JS 操作 DOM。

3. **结果断言**
   动作触发后，通过 `eval "location.href"` 或二次 `screenshot` 判断结果否符合预期，而不是假定成功。

4. **导出与固化**
   当 2 和 3 被反复验证跑通，将通过的（可能带有强制、非拟人、或者 JS Eval 的）参数，写入 `JSON Workflow` 配置项，形成无幻觉无脆弱性的自动化文件。

> **最佳实践总结**：一切操作都应先在 LLM REPL 或 CLI 交互中确认畅通，通过 `eval` 和屏幕截图完成闭环验证后，再将其写入正式测试用例或 Workflow 配置文件中。
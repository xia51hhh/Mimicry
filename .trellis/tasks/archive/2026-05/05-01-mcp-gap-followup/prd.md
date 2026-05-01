# MCP/CLI gap-analysis 后续修复

承接 `05-01-mcp-cli-camoufox-gap-analysis` 的 review 发现，修 1 个 Blocker + 3 个 High + 加 2 个最小 pytest。

## Blocker

**`controller.register_init_scripts` 在 launch-first workflow 下静默丢弃**

复现路径：workflow 第一节点 = `browser.launch`。
1. `executor.execute()` 起手就调 `register_init_scripts(scripts)`
2. `_apply_init_script_to_context` 因 `_context is None` early-return
3. 后续 `browser.launch` 创建 context 时**不读** `_init_scripts` registry
4. 结果：脚本永远没注册到 Playwright

**修复**：`BrowserController.launch()` 在新建 context 后，flush 已存的 `_init_scripts`。同时确保 `register_init_scripts` 即使 context 不存在也要把脚本存进 dict（当前已是这个行为，不动它）。

## High-1 — `CallToolResult` 返回类型与 SDK 兼容性未验证

`mcp_server.py::call_tool` 现在错误路径返回 `CallToolResult(isError=True, content=[...])`。
低层 `mcp.server.Server.@call_tool()` 的实际期望需要在装有 `mcp` 的环境下验证：
- 若 SDK 接受 → 保留
- 若 SDK rejects（如 double-wrap / pydantic 校验错误）→ 回退到 `list[TextContent]`，错误标记走 text 前缀 `"[ERROR] {json}"`

**做法**：
1. 在 worktree 里 `pip install mcp`（或激活 sidecar venv），实际 `import asyncio; asyncio.run(call_tool('does_not_exist', {}))` 看返回值类型与 SDK 是否抱怨。
2. 若工作正常：写 unit test 锁住行为。
3. 若失败：改回 `list[TextContent]` 包 `{"error": "...", "isError": True}` JSON，并在 `description=` 注明 LLM 应识别 `"isError": True` 字段。

## High-2 — `resp.body()` 同步阻塞 page 事件分发

`controller.py:1068` 的 `resp.body()` 在 sync API 下是阻塞调用。流式响应 / 大下载 / 慢响应会卡住整个 page 的事件循环（顺序处理）。

**修复**：
1. `resource_type` 过滤：跳过 `"image"`, `"media"`, `"font"`, `"stylesheet"`（这些 LLM 调试 workflow 几乎用不到）。
2. `resp.body()` 包 `try/except Exception` + 5 秒超时（Playwright sync API 没原生 timeout，用 `concurrent.futures` 不现实，换方法：检查 `resp.headers.get("content-length")`，超过 256KB 直接跳过 body 读取，记 `response_body_skipped: "too_large"`）。
3. 任何异常吞掉，写 `response_body_skipped: <reason>` 字段。

## High-3 — 256KB body 截断破坏 UTF-8

`controller.py:1107-1121` 把 bytes 切到 256KB 后再 decode，可能切在 UTF-8 多字节边界中间，得到乱码。

**修复**：
1. 存 raw bytes（最多 256KB）+ `original_size: int`（响应实际字节数）。
2. `network.get` 返回时再 `bytes.decode('utf-8', errors='replace')`，并附 `truncated: bool` + `original_size`。
3. `network.list` 的每个条目带 `original_size` 与 `truncated`，让 LLM 知道是否需要 `network.get` 拉完整 body（其实拉了也只有 256KB，只是给信号）。

## 加测（覆盖 Blocker + 描述完整性）

1. `sidecar/tests/test_mcp_server_descriptions.py::test_list_tools_no_fallback_descriptions`
   - 调 `asyncio.run(mcp_server.list_tools())`
   - 断言：所有 tool 的 `description` 不以 `"Mimicry: "` 起头
   - 断言：tool 数 ≥ 60（避免回归到 fallback）

2. `sidecar/tests/test_executor_init_scripts.py::test_init_scripts_applied_when_launch_is_first_node`
   - 用 `unittest.mock.MagicMock` 替换 `BrowserController` 的 Playwright 部分
   - 模拟一个 workflow JSON: `{"init_scripts": ["window.x=1"], "nodes": [{"action": "browser.launch", ...}, ...]}`
   - 跑 `executor.execute()`，断言 `mock_context.add_init_script` 被调用至少一次
   - 这就是 Blocker 的回归测试

## Out of scope

- `_TOOL_NAME_TO_RPC` 双调用 / counter 撞名 等 Low 级 nit
- `controller.py:1056-1058` 的 URL 匹配 → 改用 `resp.request is entry["_req"]`：列为可选改进，**只在改 High-2 顺手做时一并改**，否则不动。
- 移除 `sidecar/dsl/` 与 `test_dsl.py`（独立任务）
- spec 文档措辞修正

## Acceptance Criteria

- [ ] 当 workflow 首节点为 `browser.launch` 时，`init_scripts` 注册到 Playwright（pytest 锁）
- [ ] MCP `call_tool` 错误路径在装有 mcp 的环境实际跑通（可能改回 list-form）
- [ ] 流式响应 / 大下载不阻塞 page 事件循环
- [ ] 截断的 body 不再因 UTF-8 边界乱码；带 `original_size` + `truncated`
- [ ] 2 个新 pytest 加入 collection 通过
- [ ] `python3 -m py_compile sidecar/{mcp_server,browser/controller,browser/actions,engine/executor}.py` 通过

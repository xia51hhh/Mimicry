# Sidecar — MCP / RPC / CLI Hard Contracts

Source of truth for everyone touching `sidecar/rpc/methods.py`, `sidecar/browser/actions.py`, `sidecar/mcp_server.py`, `sidecar/cli.py`, `sidecar/dev_cli.py`, or `sidecar/engine/executor.py`.

The three entry modes (Tauri stdio JSON-RPC, CLI+daemon UDS, MCP stdio) share the **same** registry. Anything you add here surfaces in all three at once.

---

## 1. `@rpc_method` is the only registration path

Every method exposed to any of the three entries MUST be registered via `@rpc_method` from `sidecar/rpc/methods.py`. The decorator populates two dicts:

- `METHOD_REGISTRY: dict[str, Callable]` — dispatch
- `METHOD_METADATA: dict[str, {description, param_descriptions}]` — surfaced to MCP `list_tools`

### Hard rule: every `@rpc_method` MUST set `description=` AND `param_descriptions=`

```python
@rpc_method(
    "browser.click",
    description="Click an element matched by a selector. Use to trigger buttons, links, or any clickable UI. Returns {ok, retried} on success.",
    param_descriptions={
        "selector": "CSS or XPath selector identifying the element. Examples: '#submit', 'button.primary', 'xpath=//button[text()=\"Login\"]'.",
        "session_id": "Browser session ID; defaults to 'default' for the primary session.",
        "force": "Skip Playwright actionability checks (visible/enabled/stable). Use only when the standard click times out and you've verified the target is interactive.",
    },
)
def browser_click(selector: str, session_id: str = "default", force: bool = False):
    ...
```

`param_descriptions` MUST cover every signature parameter that is NOT:

- `self` / `cls`
- `inspect.Parameter.VAR_KEYWORD` (`**kwargs`)
- `inspect.Parameter.VAR_POSITIONAL` (`*args`)

Style:

- **English, imperative mood**, 1–2 sentences for the tool description.
- The description must say *when* to call it, not just what it does.
- Param descriptions: one short sentence + a concrete example or constraint where useful.
- For workflow-debugging primitives (`workflow.set_breakpoint`, `workflow.step`, `workflow.unpause`, `workflow.inject`, `workflow.state`), cross-reference the related primitives by name in the description so the LLM understands the loop.

**Why:** `sidecar/mcp_server.py::_make_description` falls back to `"Mimicry: <name>"` if no description is set. That fallback gives the LLM no signal to choose the right tool. Coverage was 27.8% before Phase 2 of `05-01-mcp-cli-camoufox-gap-analysis`; the fix was to backfill all 56 tools and lock the rule here.

### Validation matrix

| Condition | Result |
|---|---|
| `description=` empty / missing | LLM sees `"Mimicry: <name>"`. **Forbidden.** |
| Signature has param P, `param_descriptions` doesn't | LLM sees param without context. **Forbidden** (except `**kwargs`/`*args`). |
| Description doesn't say *when* to use the tool | LLM picks wrong tool. **Avoid.** |
| Two methods share the same dotted name | `METHOD_REGISTRY` overwrites silently. **Bug.** |

### Forbidden patterns

```python
# Wrong: bare decorator, fallback description
@rpc_method("workflow.set_breakpoint")
def workflow_set_breakpoint(node_id: str):
    ...

# Wrong: description present, params not documented
@rpc_method("browser.click", description="Click an element.")
def browser_click(selector: str, session_id: str = "default"):
    ...

# Correct: see the example at the top of section 1
```

---

## 2. RPC naming convention

Method names are **dotted**, namespace-first: `<namespace>.<verb_or_noun>`.

Current namespaces:

- `browser.*` — atomic page actions (multi-session aware)
- `workflow.*` — JSON workflow execution lifecycle (execute, pause, step, breakpoint, inject, state)
- `recording.*` — capture user actions to JSON
- `network.*` — per-session HTTP request capture
- `console.*` — per-session console message buffer
- `camoufox.*` — Camoufox installer / version
- `recording.*` — recorder lifecycle
- top-level: `ping`, `system_info`, `heartbeat`

### MCP tool name derivation (canonical, established Phase 1)

MCP tool names are derived by replacing **all** dots with underscores:

```
browser.navigate          → browser_navigate
workflow.set_breakpoint   → workflow_set_breakpoint   (was broken pre-Phase-1)
browser.list_sessions     → browser_list_sessions
```

`mcp_server.py` MUST build a bidirectional map at registration time:

```python
_TOOL_NAME_TO_RPC: dict[str, str] = {
    method_name.replace(".", "_"): method_name
    for method_name in METHOD_REGISTRY
    if method_name not in _SKIP_METHODS
}
```

`call_tool` does an O(1) lookup; **never** use `name.replace("_", ".", 1)` heuristics — they break for any namespace whose method-part contains an underscore (e.g. `workflow.set_breakpoint`).

---

## 3. MCP schema inference contract

`mcp_server.py::_build_tool_schema` derives JSON Schema from each function's `inspect.signature` + type hints. It MUST handle:

| Annotation | Output |
|---|---|
| `str` / `int` / `float` / `bool` | primitive type |
| `Optional[T]` / `T \| None` | unwrap T; NOT in `required`; `default: null` if applicable |
| `Union[A, B]` (non-Optional) | `{"anyOf": [<A>, <B>]}` |
| `list[T]` / `List[T]` | `{"type": "array", "items": <T>}` |
| `dict[K, V]` / `Dict[str, V]` | `{"type": "object", "additionalProperties": <V>}` |
| `Literal["a", "b"]` | `{"type": "string", "enum": [...]}` |
| `Enum` subclass | enum of `.value` |
| `Any` / no annotation | `{"type": "string"}` (last-resort fallback) |
| `inspect.Parameter.VAR_KEYWORD` (`**kw`) | **SKIP** — do NOT emit any property |
| `inspect.Parameter.VAR_POSITIONAL` (`*args`) | **SKIP** |

Use `typing.get_origin` / `typing.get_args` / `inspect.Parameter.kind`. **When you add a new typing construct used by an `@rpc_method` signature, you MUST extend `_build_tool_schema`** — the fallback "string" silently degrades the LLM contract.

### Common Mistake: `**kwargs` leaking as a string property

**Symptom:** `browser_switch_tab` MCP schema had a `match_hints` property of type `string`.

**Cause:** Pre-Phase-1 `_build_tool_schema` looped over all parameters and treated `**match_hints` as a regular param.

**Fix:** check `param.kind in (VAR_KEYWORD, VAR_POSITIONAL)` and skip.

**Prevention:** documented here; spec is part of `check.jsonl` for any task touching MCP.

---

## 4. MCP error protocol

`call_tool` MUST return `CallToolResult(content=[...], isError=True)` on any error path:

- Unknown tool name (no entry in `_TOOL_NAME_TO_RPC`)
- Unknown method (no entry in `METHOD_REGISTRY`)
- The handler raised an exception

Success path returns plain `list[TextContent]` (the SDK auto-wraps with `isError=False`).

Error payload:

```python
CallToolResult(
    content=[TextContent(
        type="text",
        text=json.dumps({"error": str(e)}, ensure_ascii=False),
    )],
    isError=True,
)
```

`ensure_ascii=False` is required — error messages may contain Chinese.

### Validation matrix

| Branch | Return type | `isError` |
|---|---|---|
| Success | `list[TextContent]` | (SDK wraps as False) |
| Exception caught in handler | `CallToolResult` | **True** |
| Unknown tool name | `CallToolResult` | **True** |
| Unknown method | `CallToolResult` | **True** |

---

## 5. Workflow JSON `init_scripts` field

Workflow JSON gets an optional top-level field:

```json
{
  "version": 1,
  "init_scripts": [
    "window.__test = true;",
    {"name": "anti_popup", "script": "document.addEventListener('click', e => { if (e.target.matches('.popup-close')) e.target.click(); });"}
  ],
  "nodes": [...]
}
```

### Contract

- Type: `list[str | {name: str, script: str}]`. Strings get auto-name `init_<i>`.
- The executor (`sidecar/engine/executor.py`) MUST call `controller.register_init_scripts(session_id, scripts)` **once** before the first node executes.
- `register_init_scripts` stores the list on the session AND calls `context.add_init_script(s)` for each entry. Playwright's context-level `add_init_script` auto-applies to all future pages, so no per-page wiring is needed.
- **Init scripts NEVER persist to the SQLite DB** — they live in workflow JSON only. This was an explicit scope decision (`05-01-mcp-cli-camoufox-gap-analysis` PRD) to keep `Profile` schema lean.
- Runtime authoring/debugging is via `browser.add_init_script` / `browser.list_init_scripts` / `browser.get_init_script` / `browser.remove_init_script` / `browser.clear_init_scripts` rpc methods. Note: Playwright cannot un-inject already-loaded pages — `remove`/`clear` only affect future pages. The MCP description on those methods MUST mention this.

### Wrong vs Correct

```python
# Wrong: persisting init scripts to DB
profile.init_scripts = workflow["init_scripts"]
db.update_profile(profile)

# Correct: register on the running session only
controller.register_init_scripts(session_id, workflow.get("init_scripts", []))
```

---

## 6. Network & Console buffers (per-session)

`sidecar/browser/controller.py` holds two ring buffers per session:

| Buffer | Maxlen | Storage | Toggle |
|---|---|---|---|
| `network_requests` | 500 | `collections.deque(maxlen=500)` | `network.start_capture` / `network.stop_capture` |
| `console_buffer` | 500 | `collections.deque(maxlen=500)` | always-on |

### Hard rules

- **Use `collections.deque(maxlen=N)`**. Do NOT manually `pop(0)` from a list — O(n) and error-prone.
- **Page hooks MUST be idempotent.** Track attached pages in a per-session set (`_pages_with_console_hooks`, `_pages_with_net_hooks`) keyed by Playwright page id. Re-registering a page must not double-subscribe.
- New tabs (created via `browser.new_tab` / programmatic `context.new_page`) MUST receive both hooks via the centralized `_register_page` helper.
- `network.list` MUST strip `response_body` from each entry; `network.get` returns the full body. Bodies are capped at 256 KB best-effort.

### Common Mistake: double-subscribed page handlers

**Symptom:** every console event logged twice; network entries duplicated.

**Cause:** `page.on("console", ...)` called from two different places (e.g., `_register_page` and `start_network_capture` both hook).

**Fix:** central `_attach_console_hook(page)` / `_attach_network_hook(page)` that early-returns if `page.id` is already in the per-session set.

---

## 7. CLI `--json` discipline

`sidecar/cli.py` MUST funnel ALL non-interactive output through one helper:

```python
_print_payload(payload, json_mode=args.json)
# json_mode=True  → json.dumps(payload, ensure_ascii=False, indent=2)
# json_mode=False → human-readable lines
```

### Hard rules

- `--json` and `--session/-s` live on a shared parent parser:

  ```python
  common = argparse.ArgumentParser(add_help=False)
  common.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
  common.add_argument("-s", "--session", default=argparse.SUPPRESS)
  ```

  Every subparser declares `parents=[common]`. `default=argparse.SUPPRESS` is critical — without it, subparser-level absence overwrites the top-level value with `None`/`False`.

- Streaming commands (`cmd_run` workflow execution) emit JSONL (one JSON object per line) when `--json` is set, human format otherwise.

- No command may hard-code `print(json.dumps(...))`. If you need raw JSON, you have a bug — route through `_print_payload`.

- Unknown-subcommand error branches (e.g. `cmd_breakpoint` without `add`/`rm`/`list`) MUST emit `{"error": "..."}` via `_print_payload` and `sys.exit(1)`.

### Forbidden pattern

```python
# Wrong: parse_known_args + post-hoc --json rescue in main()
ns, extra = parser.parse_known_args()
if "--json" in extra:
    ns.json = True
```

This was the pre-Phase-4 hack at `cli.py:464-467` and is now removed. Don't reintroduce it.

---

## 8. Forbidden imports (ADR-001)

`sidecar/dsl/` is **deprecated**. New code MUST NOT:

```python
from dsl.rpc_methods import ...   # FORBIDDEN
import dsl                        # FORBIDDEN
```

The `dsl/` directory is retained only for reference / archaeological comparison. All RPC dispatch goes through `rpc/methods.py::METHOD_REGISTRY`, populated by side-effect of `import browser.actions`.

`sidecar/cli_legacy.py` was deleted in Phase 4 of `05-01-mcp-cli-camoufox-gap-analysis`. Don't recreate it; if you need a legacy code path, write a new subcommand on `cli.py`.

---

## 9. Tests required when touching this layer

| Change | Required test signal |
|---|---|
| New `@rpc_method` | `pytest sidecar/tests/` collection succeeds; runtime `mcp_server.list_tools()` includes the new tool with non-fallback description |
| Schema inference change | Quick repl: `inspect` a sample method that exercises the new typing construct; confirm schema output |
| `call_tool` error path change | `asyncio.run(mcp_server.call_tool('does_not_exist', {}))` returns `CallToolResult(isError=True)` |
| CLI flag change | `from cli import build_parser; build_parser().parse_args([...])` for at least 3 representative argv shapes (with/without `--json`, flag before vs. after subcommand) |
| `init_scripts` field change | unit test on `executor.execute()` with a workflow carrying `init_scripts` confirms `controller.register_init_scripts` is called once before the first node |

---

## Related

- ADR-001 (`docs/design/decisions.md`) — JSON-direct execution, dsl deprecation
- `docs/design/block-system.md` — workflow JSON shape, including `init_scripts`
- `.trellis/spec/cross-layer/block-schema.md` — recorder output, action naming, session routing
- `.trellis/tasks/05-01-mcp-cli-camoufox-gap-analysis/research/{mcp-tool-design,capability-gap,cli-ux,fastmcp-migration-eval}.md` — evidence base for these rules
- `sidecar/SKILL.md` — LLM-facing CLI guide (must stay aligned with `cli.py` flags)

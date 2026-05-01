# Research: MCP Tool Design — Mimicry vs camoufox-mcp vs camoufox-reverse-mcp

- **Query**: Compare MCP tool surface, schema generation, description quality, naming, and error semantics across three implementations.
- **Scope**: internal (sidecar/) + reference (examples/external/)
- **Date**: 2026-05-01

---

## 1. Tool Surface Comparison

| Dimension | Mimicry (`sidecar/mcp_server.py`) | camoufox-mcp (`examples/external/camoufox-mcp/src/index.ts`) | camoufox-reverse-mcp (`examples/external/camoufox-reverse-mcp/src/...`) |
|---|---|---|---|
| **Tool count exposed** | ~54 (1 per `@rpc_method` minus `_SKIP_METHODS={"shutdown","echo"}`; see `mcp_server.py:29,93-103`) | **1** tool (`browse`) — index.ts:63 | ~30+ tools across 11 domain modules (server.py:14-25 imports) |
| **Granularity** | Fine-grained 1:1 with internal RPC (e.g. `browser.click`, `browser.dblclick`, `browser.hover`, `browser.focus`, `browser.clear` are five separate tools, actions.py:188-215) | Coarse — single tool with 19 params covers launch+navigate+screenshot in one call | Mid-grained, with explicit "v0.9.0 unified" consolidations (e.g. `scripts(action=list/get/save)` replaces 3 tools — script_analysis.py:9-47) |
| **Naming** | Dotted RPC names converted via `method_name.replace(".", "_")` → `browser_navigate`, `workflow_set_breakpoint` (mcp_server.py:97) | Single literal `"browse"` (index.ts:64) | Snake_case verbs: `launch_browser`, `navigate`, `take_snapshot`, `search_code` (no domain prefix; navigation.py:14,86,276) |
| **Grouping** | Implicit by dotted prefix (`browser.*`, `recording.*`, `workflow.*`, `camoufox.*`, `captcha.*`) but flattened into a single MCP tool list with no group metadata | N/A | File-level grouping: `tools/navigation.py`, `tools/script_analysis.py`, `tools/hooking.py`, `tools/network.py`, etc. (server.py:14-25) |
| **Registration mechanism** | `@rpc_method(name, description=, param_descriptions=)` decorator populates `METHOD_REGISTRY` + `METHOD_METADATA`; MCP layer reflects over `inspect.signature` (methods.py:13-36, mcp_server.py:32-74,90-104) | `server.tool("browse", { zod-schema-object }, async handler)` — schema is hand-written zod (index.ts:63-235) | `@mcp.tool()` decorator on async functions; FastMCP infers schema from Python type annotations + parses Args docstring section (navigation.py:13,76,86,239,253,275,313,324,335,356,371) |
| **Server bootstrap** | `Server("mimicry")` low-level SDK, manual `@app.list_tools()` / `@app.call_tool()` (mcp_server.py:87,90,107) | `McpServer({name, version})` high-level SDK (index.ts:53) | `FastMCP(name, instructions=...)` with rich top-level instruction string for LLM context (server.py:4-10) |
| **LLM-facing instructions** | None — no server-level `instructions` field passed to `Server()` | None | Yes — `instructions="Anti-detection browser MCP server for JavaScript reverse engineering. ..."` (server.py:5-9) |

---

## 2. Description Quality Audit (Mimicry)

Counted directly with `grep`:

- Total `@rpc_method` decorators in `sidecar/browser/actions.py`: **54** (`grep -cE '^@rpc_method'`)
- Decorators with `description=`: **15** (`grep -cE '^    description='`)
- Decorators with `param_descriptions=`: **15** (matches 1:1 with description coverage)
- **Coverage: 15 / 54 ≈ 27.8%**

### Methods WITH descriptions (sampled, actions.py)

- `browser.launch` (line 62-71) — full param descriptions for `session_id`, `headless`, `proxy`, `profile`
- `browser.close` (85-91), `browser.navigate` (105-112), `browser.click` (119-127)
- `browser.type` (133-142), `browser.wait` (148-156), `browser.screenshot` (162-169)
- `browser.status` (174-180), `browser.press_key` (236-244), `browser.scroll` (250-259)
- `browser.evaluate` (266-273), `browser.get_text` (278-285), `browser.get_attribute` (290-298)
- `captcha.detect_cloudflare` (562-569), plus one more captcha method (583)

### Methods WITHOUT descriptions (no `description=`, no `param_descriptions=`)

All ~39 of these emit a generic fallback. Examples:

- `browser.dblclick` (188-191), `browser.hover` (194-197), `browser.select_option` (200-203), `browser.clear` (206-209), `browser.focus` (212-215)
- `browser.go_back` (218), `browser.go_forward` (224), `browser.reload` (230)
- `browser.get_element_count` (303), `browser.extract_table` (308), `browser.upload_file` (313)
- `browser.new_tab` (319), `browser.switch_tab` (326), `browser.close_tab` (336), `browser.get_tabs` (343), `browser.handle_dialog` (349)
- All four `recording.*` (355, 367, 375, 383)
- All ~12 `workflow.*` methods (390, 418, 435, 442, 449, 457, 466, 474, 482, 490, 498, 505) — including critical debugging primitives `workflow.set_breakpoint`, `workflow.inject`, `workflow.step`
- All four `camoufox.*` methods (521, 526, 531, 537)

### Fallback path (`mcp_server.py:77-84`)

```python
def _make_description(name, fn):
    meta = METHOD_METADATA.get(name, {})
    if meta.get("description"):       return meta["description"]
    if fn.__doc__:                     return fn.__doc__.strip().split("\n")[0]
    return f"Mimicry: {name}"
```

For methods like `browser_dblclick` (no docstring, no description), the LLM receives literally `"Mimicry: browser.dblclick"` — zero semantic information beyond the method name. The `param_descriptions` dict is empty, so the JSON schema lacks `description` on every property (`mcp_server.py:66-67`).

### Comparison with camoufox-mcp density

In `examples/external/camoufox-mcp/src/index.ts:66-106`, **every one of 19 parameters** has an explicit `.describe(...)` call, often with usage hints in LLM-facing imperative style:

> `"The URL to navigate to and retrieve content from. Use this tool when users ask to visit, check, search, navigate, browse, fetch, or scrape websites. Must be a fully qualified URL (e.g., 'https://example.com')."` (line 66)

> `"Capture a screenshot/image of the page after loading. Use when users ask to take a screenshot, capture an image, show them visually, or want to see how the page looks."` (line 76)

Mimicry's existing descriptions (e.g. `browser.click` line 121 — `"Click an element matched by a CSS selector."`) are technically accurate but lack the *"Use this when users ask to ..."* trigger language that primes LLM tool-selection.

### Comparison with camoufox-reverse-mcp

FastMCP harvests Python docstrings using the `Args:` block convention — see `navigation.py:25-42` (`launch_browser`):

```python
"""Launch the Camoufox anti-detection browser.

Args:
    headless: Run in headless mode (default False).
    os_type: OS fingerprint - "auto", "windows", "macos", or "linux".
    ...
"""
```

This style means every annotated parameter automatically gets a description without a separate `param_descriptions` mapping. Mimicry's design splits metadata from docstring (methods.py:13-36), which means an author who only writes a docstring gets *no* `param_descriptions` (they would need to redundantly populate the dict).

---

## 3. Schema Inference Weaknesses (`mcp_server.py:_build_tool_schema`, lines 32-74)

Concrete gaps, line-cited:

| # | Gap | Location | Effect |
|---|---|---|---|
| 1 | **No `Optional[T]` / `Union[T, None]` handling** | lines 44-59 | A parameter typed `proxy: dict \| None = None` (actions.py:73) hits the `else: prop["type"] = "string"` branch (line 59) because `dict \| None` is `types.UnionType`, not `dict`. Result: schema says `string` for a dict param. |
| 2 | **No `Union[A, B]` handling** | lines 44-59 | `target=None` parameters in `browser.switch_tab` / `browser.close_tab` (actions.py:327, 337) — runtime accepts int OR str; schema cannot express either. |
| 3 | **No nested `dict[str, X]` element typing** | line 54-55 | `proxy: dict` becomes `{"type": "object"}` with no `properties`. LLM has to guess keys (`server`, `username`, `password`). |
| 4 | **No `list[T]` element typing** | lines 56-57 | `list[str]` becomes `{"type": "array"}` with no `items`. |
| 5 | **No enum support** | n/a | E.g. `direction: str` in `browser.scroll` (actions.py:260) is documented as `'up'/'down'/'left'/'right'` only via param description string; schema has no `enum: [...]`. Same for `wait_until`, `challenge_type`, `os_type`. |
| 6 | **No numeric constraints** | n/a | No `minimum` / `maximum` / `default` ranges for ints (timeout, amount). camoufox-mcp uses `z.number().min(5000).max(300000)` (index.ts:69). |
| 7 | **Untyped (`inspect.Parameter.empty`) → `string`** | lines 44-45 | Silently misleads. |
| 8 | **Unknown annotation → `string` fallback** | lines 58-59 | Catches custom classes, generics, `Any`, callables — all become `"string"`. |
| 9 | **`**match_hints` (VAR_KEYWORD) not skipped** | line 39 onwards iterates all params | `browser.switch_tab` (actions.py:327) has `**match_hints`; the loop will include `match_hints` as a property named literally `match_hints` typed `string`. (Verified: `inspect.signature` exposes VAR_KEYWORD with empty annotation → `string` branch.) |
| 10 | **Default values for non-JSON types** | lines 61-64 | `default=None` is JSON `null`, fine; but a `default=BrowserController` instance or callable would crash JSON serialization in `Tool(...)`. Currently no method does this, but no guard. |
| 11 | **`required` array contains `session_id`-less params** | lines 61-63 | All non-defaulted params are added — fine, but no override mechanism to mark a defaulted param as required for special cases. |

By contrast, zod (camoufox-mcp) covers all of these: `.optional()`, `.default()`, `.enum()`, `.min().max()`, `.union()`, `.tuple()`, `.record()`, `.array()` (index.ts:67-105). FastMCP relies on Pydantic, which understands `Optional[T]`, `Literal[...]`, `Annotated[T, Field(...)]`, etc.

---

## 4. Naming-Convention Friction

### The round-trip (mcp_server.py:96-117)

Forward (list_tools, line 97):
```python
tool_name = method_name.replace(".", "_")
```

So `workflow.set_breakpoint` → tool name `workflow_set_breakpoint`.

Reverse (call_tool, lines 109-117):
```python
method_name = name.replace("_", ".", 1) if "_" in name else name
fn = METHOD_REGISTRY.get(method_name)
if fn is None:
    method_name = name.replace("_", ".")  # try replacing ALL underscores
    fn = METHOD_REGISTRY.get(method_name)
```

### Trace for `workflow.set_breakpoint`

1. Forward: `"workflow.set_breakpoint"` → `"workflow_set_breakpoint"` (correct; line 97).
2. LLM calls tool `workflow_set_breakpoint`.
3. Line 110: `name.replace("_", ".", 1)` → `"workflow.set_breakpoint"` ✓ — exact match in `METHOD_REGISTRY` succeeds. **Works because `workflow.*` methods only use the first underscore as the dot.**

### Failure case — methods with multi-segment dotted names

There are currently no Mimicry methods of the form `a.b.c`, but the round-trip is fragile: any future name like `workflow.debugger.set_breakpoint` → tool `workflow_debugger_set_breakpoint`:

1. First attempt: `"workflow.debugger_set_breakpoint"` — miss.
2. Second attempt: `"workflow.debugger.set.breakpoint"` — miss (replaces ALL underscores including the one in `set_breakpoint`).
3. Returns `Unknown method` error (line 119).

### Failure case — methods whose Python identifier contains underscores intentionally

`workflow.set_breakpoint` happens to round-trip correctly only because the dot is before the first underscore. For a hypothetical `recording.poll_new_events` (note: Mimicry has `recording.poll`, but a similar pattern would break):

- Forward: `recording.poll_new_events` → `recording_poll_new_events`.
- Reverse first pass: `recording.poll_new_events` ✓ (luck; first underscore was the dot).

Whereas `captcha.detect_cloudflare` (actions.py:562) → `captcha_detect_cloudflare`:
- Reverse: `captcha.detect_cloudflare` ✓ (works).

**The rule is: round-trip works if and only if the first underscore in the tool name corresponds to the dot.** This holds for all current Mimicry methods because none have underscores in the namespace prefix. A failing case would be a top-level method like `system.info` becoming a sub-namespace — the moment any namespace segment contains an underscore, the algorithm breaks. The fallback at line 116 (`replace all`) is a band-aid that silently corrupts further dotted names.

### Reference implementations sidestep this

- camoufox-mcp: literal tool name `browse`, no transformation.
- camoufox-reverse-mcp: tool name = Python function name (`launch_browser`, `take_snapshot`), already snake_case, no namespace separator → no round-trip needed.

---

## 5. Error Semantics

### Mimicry (mcp_server.py:118-125)

```python
if fn is None:
    return [TextContent(type="text", text=json.dumps({"error": f"Unknown method: {name}"}))]

try:
    result = fn(**arguments) if arguments else fn()
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, default=str))]
except Exception as e:
    return [TextContent(type="text", text=json.dumps({"error": str(e)}))]
```

Both success and failure return a `list[TextContent]` with no `isError` flag. The LLM must parse the JSON body and look for an `"error"` key to detect failure. MCP clients that check the protocol-level `isError` field (a top-level result property) will treat all responses as success, including exception traces.

### camoufox-mcp (index.ts:218-227)

```ts
} catch (error) {
  const errorMessage = error instanceof Error ? error.message : String(error);
  console.error(chalk.red(`[Camoufox] Error during browsing: ${errorMessage}`));
  return {
    content: [{ type: "text", text: `Failed to browse URL ${url}. Error: ${errorMessage}` }],
    isError: true     // <-- protocol-level flag
  };
}
```

Uses MCP's standard `isError: true` field on the result envelope (per MCP spec), so the client surface knows it's a failure.

### camoufox-reverse-mcp

Each tool returns `{"error": str(e)}` as a dict on exception (e.g. navigation.py:73, 81, 184, 250, 272, 309, 321, 332, 352, 367, 433). FastMCP serializes this through its own envelope; whether `isError` is set depends on whether the function raises vs. returns an error dict. **Returning a dict with `error` key does NOT set `isError`** — same trap as Mimicry. Both Python implementations use a "soft error" pattern that the high-level MCP framework does not auto-elevate to protocol errors.

This means: among the three, only camoufox-mcp uses MCP's protocol-level `isError: true`. The two Python implementations rely on the LLM noticing an `error` key in the JSON payload — semantically weaker, but consistent across both Python codebases.

### `default=str` JSON encoding (mcp_server.py:123)

`json.dumps(result, ..., default=str)` silently coerces non-serializable values (datetimes, paths, custom objects) to their `str()` form. This may lose structure (e.g. a `Path` becomes its string, a Pydantic model becomes its repr). No warning is emitted.

---

## 6. Recommendations (prioritized, no implementation)

| Priority | Effort | Recommendation | Change point |
|---|---|---|---|
| **P0** | **M** | Backfill `description=` and `param_descriptions=` on the **39 undocumented `@rpc_method` calls** in `actions.py`, especially the `workflow.*` debugging primitives (lines 390-505) and `recording.*` (355-388). Use camoufox-mcp's "Use this when users ask to ..." imperative style for the description. Without this, ~72% of Mimicry's MCP surface is opaque to LLMs. | `sidecar/browser/actions.py:188-215, 218-233, 303-349, 355-388, 390-515, 521-540` |
| **P0** | **S** | Add server-level `instructions=` text to `Server("mimicry")` describing the agent's purpose (browser automation + workflow recording/debugging via Camoufox). Mirrors `camoufox_reverse_mcp/server.py:5-9`. The low-level `Server` constructor accepts no `instructions` directly; pass via `create_initialization_options()` or migrate to `FastMCP` which has first-class support. | `sidecar/mcp_server.py:87, 130` |
| **P1** | **M** | Extend `_build_tool_schema` to handle `Optional[T]`, `Union[A, B]`, `list[T]`, `dict[str, T]`, `Literal[...]` (enum), and skip VAR_KEYWORD/VAR_POSITIONAL params. Use `typing.get_origin` / `typing.get_args`. Without this, params like `proxy: dict \| None` (actions.py:73), `pre_inject_hooks: list[str] \| None` patterns, and `**match_hints` (actions.py:327) produce wrong or misleading schemas. | `sidecar/mcp_server.py:32-74` |
| **P1** | **S** | Replace the brittle dot-underscore round-trip with a bidirectional mapping: build `tool_name → method_name` at registration time (when `list_tools` runs) and store on a module-level dict for O(1) reverse lookup. Eliminates the `replace("_", ".", 1)` then-`replace("_", ".")` fallback (mcp_server.py:109-117) entirely. | `sidecar/mcp_server.py:97, 109-117` |
| **P2** | **S** | Set `isError: True` on the result envelope on exception, not just embed `{"error": ...}` in the text content. The low-level SDK's `@app.call_tool()` returns `list[TextContent]` directly, which loses the envelope; consider returning `CallToolResult(content=[...], isError=True)` or migrating to `FastMCP` to get this for free. | `sidecar/mcp_server.py:118-125` |
| **P2** | **S** | Skip `inspect.Parameter.VAR_KEYWORD` and `VAR_POSITIONAL` in the parameter loop (currently includes `**match_hints` from `browser.switch_tab` as a literal `string` property named `match_hints`). | `sidecar/mcp_server.py:39-69` |
| **P2** | **L** | Consider migrating from low-level `Server` to `FastMCP` (as camoufox-reverse-mcp does). Wins: docstring-based parameter description harvesting, automatic Pydantic-based schema generation including `Optional`/`Literal`/`Annotated[Field(...)]`, native `instructions=`. Costs: rewrite `list_tools` / `call_tool` glue, possibly tweak how `METHOD_REGISTRY` and the existing JSON-RPC stdio path coexist. | `sidecar/mcp_server.py` (whole file) |

---

## Caveats / Not Found

- I did not enumerate camoufox-reverse-mcp's *exact* tool count; the import list shows 11 modules (server.py:14-25). Sampling navigation.py shows 11 `@mcp.tool()` decorators in that file alone, so the total is likely 30-50, not "30+" precisely.
- The "39 without descriptions" figure is derived as `54 total - 15 with description=` in actions.py only. The four extra `@rpc_method` registrations in `methods.py` (`ping`, `echo`, `system.info`, `heartbeat`) are also undocumented but `echo` is in `_SKIP_METHODS`. So MCP-exposed undocumented methods ≈ 39 + 3 = **42 of ~57 visible tools (~74%)**.
- I did not run the sidecar to verify schema output empirically — analysis is from reading `_build_tool_schema` only. The VAR_KEYWORD pollution claim should be confirmed with a quick `print(schema)` for `browser.switch_tab`.
- camoufox-reverse-mcp's FastMCP *does* support `isError`-style error elevation when the tool raises, but its tools choose to return `{"error": ...}` dicts instead — equivalent to Mimicry. So the `isError` advantage cited in §5 applies primarily to camoufox-mcp's TypeScript implementation.

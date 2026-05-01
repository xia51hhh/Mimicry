# Research: Capability Gap — Mimicry sidecar vs `camoufox-reverse-mcp`

- **Query**: What does the reverse-mcp reference provide that Mimicry's sidecar does NOT, and what (if any) is worth porting?
- **Scope**: internal (Mimicry sidecar) + reference codebase under `examples/external/`
- **Date**: 2026-05-01

---

## 1. Inventory of capabilities

### 1.1 Mimicry sidecar — `@rpc_method` registry

From `sidecar/browser/actions.py` (line numbers cited):

- **browser.* (29 methods)** — `detect_screens` (55), `launch` (62), `close` (85), `list_sessions` (100), `navigate` (105), `click` (119), `type_text` (133), `wait_for` (148), `screenshot` (162), `evaluate` (174), `dblclick` (188), `hover` (194), `select_option` (200), `clear` (206), `focus` (212), `go_back` (218), `go_forward` (224), `reload` (230), `press_key` (236), `scroll` (250), `get_element_text` (266), `get_element_attribute` (278), `get_element_count` (303), `extract_table` (308), `upload_file` (313), tab mgmt: `new_tab` (319) / `switch_tab` (326) / `close_tab` (336) / `get_tabs` (343), `handle_dialog` (349), plus cookie/download/frame/wait helpers in `controller.py:869-926`.
- **recording.* (4)** — `start` (355), `stop` (367), `poll` (375), `status` (383).
- **workflow.* (12)** — `execute` (390), `resume` (418), `stop` (435), `execution_status` (442), `pause` (449), `unpause` (457), `step` (466), `inject` (474), `set_breakpoint` (482), `remove_breakpoint` (490), `list_breakpoints` (498), `state` (505).
- **camoufox.* (4)** — `check` (521), `install` (526), `check_update` (531), `update` (537).
- Plus `shutdown` (543) and two helpers at 562/583.

`BrowserController` state (`controller.py:50-63`): `_camoufox`, `_browser`, `_page`, `_persistent`, `_browser_pid`, `launch_warnings`, tab registry (`_tab_registry`, `_page_to_tab`, `_seq_counter`). Anti-detection via `_STEALTH_JS` (`controller.py:400-446`) injecting iframe-aware `navigator.webdriver` patch. `SessionManager` (`controller.py:929`) keys multiple `BrowserController`s by `session_id` with disconnect callbacks.

Recorder events (`recorder.py:91-169`): `click`, `dblclick`, `type` (debounced input/contenteditable), `select`, `scroll` (wheel-debounced), `hover` (only for interactive elements), `press_key` (with modifier composition); plus auto-emitted `new_tab`, `close_tab`, `switch_tab` (`recorder.py:283-336, 394-410`). Selectors built with shadow-DOM crossing via `>>` combinator, ID/name/class preferred, `nth-of-type` fallback, then scored 0–100 by `score_selector` (`recorder.py:175-205`).

### 1.2 `camoufox-reverse-mcp` — 35 MCP tools across 13 modules

From `tools/*.py` (file/line):

| Module | Tools |
|---|---|
| `navigation.py` | `launch_browser`, `close_browser`, `navigate` (with `pre_inject_hooks` + redirect-chain trace), `reload`, `take_screenshot`, `take_snapshot` (a11y tree), `click`, `type_text`, `wait_for`, `get_page_info`, `reset_browser_state` |
| `script_analysis.py` | `scripts` (list/get/save), `search_code` (regex over all loaded scripts) |
| `debugging.py` | `evaluate_js` (with `await_promise`) |
| `hooking.py:11,164,214,282` | `hook_function` (intercept/trace, before/after/replace, `non_overridable` via `Object.defineProperty`, `persistent` across navigations), `inject_hook_preset` (xhr/fetch/crypto/websocket/debugger_bypass/cookie/runtime_probe), `remove_hooks`, `get_console_logs` |
| `network.py:10,58,105,152,275` | `network_capture` (start/stop/clear/status), `list_network_requests` (filterable), `get_network_request` (with body), `get_request_initiator`, `intercept_request` (route mocking) |
| `storage.py:10,77,114,134` | `cookies`, `get_storage` (local/session), `export_state`, `import_state` |
| `jsvmp.py:10,138` | `hook_jsvmp_interpreter` (proxy/transparent modes, Reflect.get/apply taps), `compare_env` |
| `instrumentation.py:23` | `instrumentation` action-multiplexed tool: `install` (route + AST/regex source rewrite), `log`, `stop`, `reload`, `status` — selectively rewrites `obj[key]` reads / `fn(args)` calls; supports `filter_property_names`/`filter_object_names` for large bundles like `webmssdk` |
| `environment.py:11` | `check_environment` |
| `verification.py:11` | `verify_signer_offline` (offline pass-rate test of a candidate signer JS against captured samples) |
| `trace.py:29,128,165` | `trace_property_access` (engine-level, requires custom Camoufox build), `list_trace_files`, `query_trace_file` |
| `cookie_analysis.py:29` | `analyze_cookie_sources` (correlates `Set-Cookie` headers with `document.cookie` writes captured by hook) |
| `fingerprint.py` | (file present, 0 LOC; placeholder) |

`hooks/` (13 .js files, what each hooks):

| File | Target |
|---|---|
| `cookie_hook.js` | `document.cookie` setter — logs writes + JS stack |
| `crypto_hook.js` | `btoa`/`atob`/`JSON.stringify` — capture encryption I/O |
| `debugger_trap.js` | Disables anti-debug `debugger` traps |
| `fetch_hook.js` | `window.fetch` — log all requests |
| `font_fallback.js` | Font enumeration patch when OS != host |
| `jsvmp_hook.js` (380 LOC) | Replaces `Reflect.get/apply`, installs Proxies on `navigator`/`screen`/etc. |
| `jsvmp_transparent_hook.js` (190 LOC) | Lower-coverage but Proxy-toString-undetectable variant |
| `property_access_hook.js` | Generic Proxy on chosen objects (used by `trace_property_access` JS-fallback) |
| `runtime_probe.js` | Low-overhead observer of XHR/fetch/canvas/getContext/AudioCtx/WebGL.getParameter/crypto.subtle/perf.now/navigator getters/addEventListener |
| `trace_template.js` / `trace_persistent_template.js` | Templated function-call tracer (rendered server-side) |
| `websocket_hook.js` | `WebSocket.send` / `onmessage` |
| `xhr_hook.js` | `XMLHttpRequest.open`/`send` |

`BrowserManager` extra state vs Mimicry (`browser.py:41-56`): `_console_logs` (deque 2000), `_network_requests` (deque 2000) with id counter, `_capturing` flag + `_capture_pattern` glob + `_capture_body`, `_init_scripts`, `_persistent_scripts` (re-injected on every new context, `browser.py:162-163, 183-198`), `_persistent_traces` (parsed from `__MCP_TRACE__:` console marker, `browser.py:207-217`), `_nav_responses`, `_route_handlers`. Listeners (`_attach_listeners`, `browser.py:200-205`) attach `console` + `request` + `response` (twice) on every page.

`property_trace.py` (engine-level, requires custom build): writes commands to `~/.cache/camoufox-reverse/control/control-<pid>.cmd`; the C++ `PropertyTracer` in the patched Firefox writes JSONL events to `traces/`. Aggregations: `build_summary`, `build_timeline`, `build_sequence`, `filter_events` (`property_trace.py:32-216`). Default traced objects: `Navigator`, `Screen`, `Document`, `HTMLDocument`, `Window`, `Performance`, `History`, `Location`, `HTMLCanvasElement`, `WebGLRenderingContext`, `AudioContext` (`property_trace.py:16-20`).

README headline use cases (`README.md:7-25`): "interface parameter analysis, JS static/dynamic analysis, function-hook tracing, network interception, JSVMP bytecode analysis, cookie/storage management" against RS / AK / JY / CF anti-bot stacks; differentiator vs `chrome-devtools-mcp` is C++ engine-level fingerprinting + persistent JS hooks.

---

## 2. Coverage matrix

`✓` = first-class, `partial` = exists but limited, `✗` = absent. Mimicry column reflects the sidecar; reverse-mcp the reference repo.

| Domain | Mimicry | reverse-mcp | Notes |
|---|---|---|---|
| Launch / proxy / profile | ✓ | partial | Mimicry has multi-session `SessionManager`, profile DB, `user_data_dir`; reverse-mcp launches one global browser per process. |
| Navigation / click / type / wait | ✓ | ✓ | Both call same Playwright primitives. |
| Humanized typing / scroll | ✓ | partial | Mimicry has per-char delay + jitter (`controller.py:592-602, 656-679`); reverse-mcp uses simple `delay`. |
| Tab management with stable IDs | ✓ | ✗ | Mimicry has `TabInfo`, gradient match (tabId→seq→origin+path→title) (`controller.py:712-798`). reverse-mcp keys pages by string name only. |
| Frame / iframe ops | partial | partial | Both use Playwright; Mimicry has `switch_frame` (`controller.py:856`). |
| Recording → workflow JSON | ✓ | ✗ | Mimicry's recorder + selector scoring + auto switch_tab inserts (`recorder.py:354-410`) is unique. |
| Workflow JSON execution | ✓ | ✗ | `engine/executor.py` with pause/resume/step/inject/breakpoints (`actions.py:390-505`). |
| Multi-session / per-session profile | ✓ | ✗ | `SessionManager` (`controller.py:929-1007`). |
| Console log capture | ✗ | ✓ | reverse-mcp `get_console_logs` + ring buffer of 2000 entries (`browser.py:46, 219-224`). |
| Network capture (request + response + body) | ✗ | ✓ | Glob pattern, status/method/type filters, optional body fetch, route-based capture (`browser.py:226-276`, `network.py:10-330`). |
| Network request listing/filtering with stable IDs | ✗ | ✓ | `list_network_requests`, `get_network_request`, `get_request_initiator` (`network.py:58,105,152`). |
| Request interception / mocking | ✗ | ✓ | `intercept_request` (`network.py:275`). |
| Cookie read/write | ✓ | ✓ | Both work. |
| Cookie source attribution (HTTP vs JS) | ✗ | ✓ | `analyze_cookie_sources` correlates Set-Cookie with `document.cookie` writes (`cookie_analysis.py:29`). |
| localStorage / sessionStorage dump | ✗ | ✓ | `get_storage` (`storage.py:77`). |
| Session state export / import | ✗ | ✓ | `export_state` / `import_state` (Playwright storage_state) (`storage.py:114, 134`). |
| JS evaluate | ✓ | ✓ | Both expose. |
| Script listing / source dump / regex search | ✗ | ✓ | `scripts` + `search_code` (`script_analysis.py:9, 50`). |
| Persistent init scripts (survive navigation) | partial | ✓ | Mimicry only injects fixed `_STEALTH_JS`; reverse-mcp has full `add_persistent_script` registry re-applied per new context (`browser.py:162-163, 183-198`). |
| Function hooking (intercept/trace, before/after/replace) | ✗ | ✓ | `hook_function` with `non_overridable` lock via `Object.defineProperty` (`hooking.py:11`). |
| Hook preset library | ✗ | ✓ | xhr/fetch/crypto/websocket/cookie/debugger_bypass/runtime_probe (`hooks/*.js`, `hooking.py:163`). |
| Anti-debugger bypass | ✗ | ✓ | `debugger_trap.js`. |
| JSVMP bytecode instrumentation | ✗ | ✓ | `instrumentation.py:23` AST/regex source rewriter + `jsvmp_hook.js` proxy probe. |
| Engine-level DOM property trace (undetectable) | ✗ | ✓ * | Requires custom `camoufox-reverse` build; falls back to JS Proxy otherwise (`trace.py:29-77`, `property_trace.py`). |
| Offline signer verification | ✗ | ✓ | `verify_signer_offline` (`verification.py:11`). |
| Accessibility-tree snapshot for LLM prompting | ✗ | ✓ | `take_snapshot` (`navigation.py:276`) — token-efficient page representation. |
| Camoufox installer / update channel | ✓ | ✗ | `camoufox.check/install/update` (`actions.py:521-540`). |
| Workflow breakpoints / step / inject | ✓ | ✗ | `workflow.set_breakpoint`/`step`/`inject`. |
| i18n + Tauri WebView UI | ✓ | ✗ | Out of scope for reverse-mcp (it has no UI). |

\* engine-level mode requires a forked browser binary; the JS-Proxy fallback works on stock Camoufox.

---

## 3. Domains where Mimicry leads (honest list)

1. **Recording engine** — shadow-DOM-crossing selector builder with quality score (`recorder.py:62-89, 175-205`), debounced input/scroll/hover, auto `switch_tab`/`new_tab`/`close_tab` insertion driven by `_active_page_id` diff (`recorder.py:394-410`), per-frame injection (`recorder.py:268-281`), event→workflow-node converter (`recorder.py:412+`). Reverse-mcp has nothing comparable — it's a console for an LLM, not a capture-and-replay tool.
2. **Workflow JSON execution model (ADR-001)** — full executor with `pause/unpause/stop/step/inject/breakpoints/resume` (`actions.py:449-505`), variable resolution (`executor.py:46-50`), serializable `ExecutionContext` (`executor.py:64-76`).
3. **Multi-session isolation** — `SessionManager` keyed by `session_id` with disconnect callbacks and auto-cleanup of dead sessions (`controller.py:929-1007`); reverse-mcp owns one global `BrowserManager` instance.
4. **Stable tab identification** — `TabInfo {tab_id, seq, url_origin, url_path, title}` and gradient matching for cross-session replay (`controller.py:26-47, 712-798`).
5. **Profile lifecycle** — fingerprint config injection, persistent `user_data_dir`, GeoIP retry-on-failure, browser-config bool params (`controller.py:237-323`).
6. **Camoufox installer** owned by sidecar (`camoufox.check/install/update`).
7. **Frontend integration contracts** — i18n, Vue Flow canvas, action-map cross-layer sync (`shared/action-map.json`).

---

## 4. Domains where reverse-mcp leads (specific tools)

1. **Function hooking with persistence** — `hook_function(mode='intercept'|'trace', position='before|after|replace', non_overridable, persistent)` (`hooking.py:11`). Persistent scripts are re-injected via `BrowserContext.add_init_script` for every new context (`browser.py:162-163, 191-192`), so navigations don't drop hooks. Mimicry has zero general-purpose hooking.
2. **Hook preset library (7 ready-made)** — `inject_hook_preset('xhr'|'fetch'|'crypto'|'websocket'|'debugger_bypass'|'cookie'|'runtime_probe')` reads from `hooks/*.js` (`hooking.py:163-211`).
3. **Network capture + query** — full HAR-like ring buffer, glob pattern, body capture, status/method/resource_type/domain filters, `get_request_initiator`, `intercept_request` (`network.py:9-330`, `browser.py:226-292`).
4. **Console log buffer** — 2000-entry deque with level/timestamp/location (`browser.py:46, 219-224`); Mimicry has no equivalent.
5. **Storage dump / state export-import** — `get_storage`, `export_state`, `import_state` (`storage.py:77,114,134`).
6. **Script discovery** — `scripts` list/get/save plus `search_code` regex over every loaded JS (`script_analysis.py:9, 50`).
7. **JSVMP analysis stack** — both runtime probe (`hook_jsvmp_interpreter`, `jsvmp.py:10`) and source-level AST/regex rewriter (`instrumentation.py:23`), with `filter_property_names`/`filter_object_names` and `on_oversized` strategy for huge SDK bundles like webmssdk.
8. **Engine-level property trace** — bypasses any JS-side detection by running in C++ (`property_trace.py` + custom Firefox build); JS-Proxy fallback for stock Camoufox.
9. **Cookie source attribution** — `analyze_cookie_sources` joins captured `Set-Cookie` headers with `document.cookie` writes captured by `cookie_hook.js` (`cookie_analysis.py:29`).
10. **Signer verification harness** — `verify_signer_offline` runs a candidate signer JS against captured samples and returns `pass_rate` + `first_divergence` (`verification.py:11`).
11. **A11y-tree snapshot** for LLM prompting — `take_snapshot` (`navigation.py:276`).

---

## 5. Port-worthy candidates (ranked)

Scoring rubric: **Value to Mimicry users** (workflow authors, LLM-driven runs) × **Eng. cost** × **Conflict with ADR-001 (workflow JSON first)**.

### Top 3

1. **Network capture + listing + filtering**
   - Value: HIGH. Workflow authors and the LLM CLI need response inspection (login flows, API discovery). Today they have to write `evaluate_js` snippets.
   - Cost: LOW–MEDIUM. ~300 LOC of Playwright `page.on("request"|"response")` plumbing already proven in `browser.py:226-276`. Add `network.start/stop/list/get` rpc methods + a workflow `network_capture` action node.
   - ADR-001 conflict: NONE. It's purely a new action family in the JSON schema.
   - References to copy: `examples/external/.../browser.py:226-292`, `tools/network.py:10-272`.

2. **Persistent init-script registry**
   - Value: HIGH. Currently `_STEALTH_JS` is the only init script. Workflows often need "always-on" patches per profile (e.g. cookie consent dismissers, MutationObservers). LLM CLI also benefits.
   - Cost: LOW. ~50 LOC: a `dict[name, content]` on `BrowserController` re-applied via `ctx.add_init_script` on launch and on new contexts. Pattern in `browser.py:162-163, 183-198`.
   - ADR-001 conflict: minor. Need a clear story for whether scripts live in `Profile` (DB) or workflow-level. Recommend: profile-level, surfaced through `profile.scripts` field.

3. **Console log buffer + simple `console.list`/`console.clear` rpc**
   - Value: MEDIUM-HIGH. Critical for debugging workflow runs (`workflow.execute` has logs but page console is opaque today).
   - Cost: LOW. ~30 LOC ring buffer per session, `page.on("console", …)`. Mirrors `browser.py:46, 219-224`.
   - ADR-001 conflict: NONE. Diagnostic endpoint, not an action.

### Honourable mentions (port if asked)

- **Storage state export/import** (`storage.py:114-153`) — useful for "save login & resume tomorrow" scenarios already partially solved by `user_data_dir`. Cheap to add, low conflict.
- **A11y-tree snapshot** (`navigation.py:276-310`) — only valuable if Mimicry doubles down on LLM-driven branches; current canvas-first UX doesn't need it.
- **Generic `hook_function(trace mode)`** — an LLM-friendly debug aid; the `intercept` mode collides with workflow-determinism.

---

## 6. NOT worth porting (reverse-mcp-specific)

These are JS-reverse-engineering tools whose audience is a developer chasing an obfuscated signer, not a workflow author automating a checkout flow. Importing them would (a) bloat the sidecar's scope and (b) confuse Mimicry's positioning as a workflow-first browser automation tool.

- **`hook_jsvmp_interpreter` + `instrumentation` (AST/regex source rewriting)** (`jsvmp.py`, `instrumentation.py`, `hooks/jsvmp_*.js`, ~700 LOC). Targets RS/AK/JY anti-bot bytecode VMs. Niche; required toolchain is acorn + custom CSP handling. Outside Mimicry's MVP.
- **Engine-level property trace** (`property_trace.py` + `trace.py`). Requires a forked `camoufox-reverse` Firefox binary; Mimicry ships official Camoufox via its installer. Forking the browser is a different product.
- **`verify_signer_offline`** (`verification.py`). Specific to "I'm reverse-engineering a request signer"; not a generic browser-automation primitive.
- **`analyze_cookie_sources`** (`cookie_analysis.py`). Useful only if you've already injected `cookie_hook.js`. The hook itself is the gate.
- **`debugger_trap.js`, `crypto_hook.js`** preset hooks. Anti-debug bypass and crypto-IO dumping are reverse-engineering primitives, not workflow primitives.
- **`scripts` listing / `search_code`** (`script_analysis.py`). Useful for grepping a target's bundle; orthogonal to running a workflow.
- **`fingerprint.py`** — reverse-mcp's file is empty (8 LOC, comment only) (`fingerprint.py:1-8`); nothing to port.

Rule of thumb: anything that exists to *understand a target site's JS* is reverse-mcp's lane; anything that exists to *drive a site reliably* is Mimicry's lane.

---

## 7. Open questions for the user

1. **What is the user's primary use case for the LLM/CLI mode?** If it's "drive a known flow" (login, fill forms, scrape table) then candidates 1–3 in §5 cover ~90% of value. If it's "help me reverse-engineer this site's signer" then JSVMP/instrumentation/property-trace become relevant — but that's a different product from the Vue-canvas workflow tool described in `CLAUDE.md`. **User must decide whether the LLM CLI is for *operating* sites or *analyzing* sites, because porting JSVMP/hooking pulls Mimicry toward the latter and dilutes the workflow-first thesis from ADR-001.**
2. **Is profile-scoped persistent init-script injection acceptable as a new schema field on `Profile`, or must it stay strictly inside workflow JSON?** This determines whether the cheapest highest-value port (§5 candidate 2) goes into the DB schema or into the action library — and whether existing recorded workflows can opt-in retroactively. **User must decide because the answer changes the migration story for `src-tauri/src/db/schema.rs` and `shared/action-map.json`.**

---

## Caveats / Not Found

- I did not measure the network-capture path's effect on runtime memory / latency in the reverse-mcp implementation; the deque cap of 2000 (`browser.py:12`) suggests they consider it bounded, but Mimicry should profile before adoption.
- `tools/fingerprint.py` is effectively empty in the repo snapshot (8 LOC, no `@mcp.tool()`); whatever was planned there is not present.
- `examples/external/camoufox-reverse-mcp/src/camoufox_reverse_mcp/utils/` was not opened (js_helpers, js_rewriter, ast_rewriter); if porting `instrumentation` were on the table, those files are the load-bearing pieces and would need a separate read.
- The `chrome-devtools-mcp` column referenced in §1.2's README table was not independently inspected; values come from reverse-mcp's own marketing copy.

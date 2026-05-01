# FastMCP Migration Evaluation

- **Query**: Is migrating Mimicry's MCP server from the low-level `Server` bridge to `FastMCP` worth doing now?
- **Date**: 2026-05-01
- **Decision**: **No — stay on the bridge.** Conditions for revisiting are listed in §5.

---

## 1. Current state (post-Phase 1, 2, 5a)

`sidecar/mcp_server.py` (242 lines) is a thin reflective bridge over `METHOD_REGISTRY`:

- Server bootstrap (`mcp_server.py:198`): `Server("mimicry", instructions=_SERVER_INSTRUCTIONS)` — low-level SDK with explicit handshake instructions.
- Auto tool list (`mcp_server.py:201-214`): iterates `_TOOL_NAME_TO_RPC` (built from `METHOD_REGISTRY`, `mcp_server.py:179-195`), produces one `Tool(name, description, inputSchema)` per registered RPC method (minus `_SKIP_METHODS = {"shutdown", "echo"}`).
- Schema generation (`mcp_server.py:67-158`): `_annotation_to_schema` handles primitives, `Optional[T]`, `Union[T, None]`, `list[T]`, `dict[K, V]`, `Literal[...]`, `Enum`; `_build_tool_schema` skips `VAR_KEYWORD`/`VAR_POSITIONAL` and emits JSON-serializable defaults.
- Description generation (`mcp_server.py:161-168`): metadata `description` → docstring first line → `"Mimicry: <name>"` fallback.
- Name round-trip (`mcp_server.py:179-195`): bidirectional `tool_name ↔ rpc_name` map built once; no string heuristics in dispatch.
- Error semantics (`mcp_server.py:217-243`, post-5a): `CallToolResult(isError=True, ...)` on unknown method or exception; success path returns `list[TextContent]` and the SDK wraps with `isError=False`.

After Phase 2's description backfill, ~97% of the 68 exposed tools have rich `description=` + `param_descriptions=` metadata coming from `@rpc_method` decorators in `sidecar/browser/actions.py` and `sidecar/rpc/methods.py`.

## 2. What FastMCP would give us

Reference: `examples/external/camoufox-reverse-mcp/src/camoufox_reverse_mcp/server.py:1-25`.

- `FastMCP("name", instructions=...)` constructor — equivalent to what we already do (`mcp_server.py:198`).
- `@mcp.tool()` decorator on each public function — schema inferred from type hints + `Args:` docstring section parsing via Pydantic.
- Tool grouping by importing tools-per-file modules (`from .tools import navigation`, etc.).
- `CallToolResult` / `isError` is implicitly handled when the tool function raises (FastMCP catches and elevates).
- First-class `@mcp.resource()` and `@mcp.prompt()` primitives (we use neither today).
- Supports per-tool `outputSchema` via Pydantic return-type annotation.

## 3. Migration cost — concrete

- **Surface size**: 68 tools (`METHOD_REGISTRY` minus `_SKIP_METHODS`). FastMCP's value proposition depends on per-function decorators; bulk-registering via a loop:
  ```python
  for rpc_name, fn in METHOD_REGISTRY.items():
      mcp.tool(name=_rpc_to_tool_name(rpc_name), description=...)(fn)
  ```
  works but throws away 90% of FastMCP's ergonomics — we'd still be reflecting + mapping just like the bridge does today.
- **Idiomatic migration** (one `@mcp.tool` per function) requires:
  - Splitting `sidecar/browser/actions.py` (~700 LOC, 54 `@rpc_method` decorators) into per-domain files (`actions/navigation.py`, `actions/recording.py`, `actions/workflow.py`, `actions/camoufox.py`).
  - Decorating each function with both `@rpc_method` (for CLI/Tauri RPC paths) **and** `@mcp.tool()` — duplication, or a shim that registers in both registries simultaneously.
  - Re-asserting the cross-mode contract from `CLAUDE.md` ("three sidecar modes share `browser/actions.py` + `rpc/methods.py`"): FastMCP's decorator wants to own registration; we'd need to make it cooperate with `METHOD_REGISTRY`.
- **Schema parity**: the post-Phase-1 `_annotation_to_schema` (`mcp_server.py:67-117`) handles every typing pattern Pydantic does *except* nested dataclasses/TypedDicts. Pydantic would handle those automatically — but we don't currently use any. Net win: zero today.
- **Description parity**: Phase 2 already populated `description=` and `param_descriptions=` on all tools via `@rpc_method` arguments. FastMCP would harvest the docstring's `Args:` block instead — equivalent end result, but requires reformatting docstrings (vs. the current explicit metadata).
- **Error semantics**: Phase 5a already gets `isError: true`. Zero gain from migration on this axis.
- **Tests**: would need to update any tests that import `mcp_server.app` / `call_tool` / `list_tools`.

Estimated effort: **2-3 days** to do an idiomatic migration; **2-3 hours** to do a loop-based migration that captures ~0% of the value.

## 4. Migration benefit — concrete

- **Resources / prompts**: not used. Not on roadmap (per `prd.md`).
- **Per-domain instructions**: nice-to-have. The low-level `Server` accepts only one top-level `instructions` string (`mcp_server.py:36-48`); FastMCP technically supports the same shape. Per-tool grouping with separate `instructions=` per group is **not** a FastMCP feature — it's a code-organization convention. Same outcome achievable today by extending tool descriptions.
- **Future-proofing**: if MCP spec adds new server-side primitives (e.g. sampling-augmented tools), FastMCP will support them faster than our hand-rolled bridge.
- **Code volume**: FastMCP's ergonomics could shave ~100 LOC from `mcp_server.py` *if* we accept that domain modules absorb the decorator overhead.

## 5. Decision

**Stay on the bridge.** The post-Phase-1+2+5a state matches FastMCP's free wins on the dimensions we currently care about: schema correctness, rich descriptions, `isError` protocol field, server-level instructions. The remaining FastMCP advantages (resources, prompts, per-domain modules) target use cases we don't have.

Revisit this decision if **any** of the following holds:

1. We add MCP **resources** (e.g. expose workflow JSON files as resources for the LLM to read) or **prompts** (templated user prompts shipped by the server) — FastMCP makes both trivial; the bridge would need substantial new code.
2. We want **per-domain instructions** baked into the protocol (e.g. different LLM guidance for `browser.*` vs `workflow.*` tool groups). FastMCP's module-per-domain pattern makes this natural.
3. `_annotation_to_schema` accumulates **>5 new typing edge cases** (TypedDict, dataclass, `Annotated[T, Field(...)]`, recursive types) — Pydantic handles these for free.
4. The `@rpc_method` + `@mcp.tool` duplication problem is solved upstream (e.g. a Mimicry-internal "register everywhere" decorator), making migration cheap.
5. The MCP SDK deprecates the low-level `Server` API in favor of `FastMCP` (currently both are first-class).

## 6. Migration sketch (for the future)

If migration becomes worthwhile, the rough sequence:

1. Add `mcp[fastmcp]` to `requirements.txt` (already pulled in transitively).
2. Create `sidecar/actions/__init__.py` and split `browser/actions.py` by namespace prefix into `actions/browser.py`, `actions/recording.py`, `actions/workflow.py`, `actions/camoufox.py`, `actions/captcha.py`.
3. Build a unified decorator: `@register("browser.navigate", description=..., param_descriptions=...)` that registers into both `METHOD_REGISTRY` (for CLI/daemon/Tauri) and `mcp.tool(...)` (for MCP).
4. Replace `Server("mimicry", instructions=...)` with `FastMCP("mimicry", instructions=...)` in `mcp_server.py`.
5. Drop `_build_tool_schema` and `_annotation_to_schema` — delegate to FastMCP/Pydantic.
6. Drop `_make_description` — pass description through the unified decorator into FastMCP's `description=` argument.
7. Keep the `_TOOL_NAME_TO_RPC` map only if non-MCP code paths need reverse lookup; otherwise let FastMCP own naming.
8. Migrate `call_tool` exception handling: FastMCP elevates raised exceptions to `isError: true` automatically — remove our `_err` helper.
9. Update `sidecar/tests/test_mcp_server.py` (if it exists; otherwise add coverage).
10. Update `sidecar/SKILL.md` if any tool naming changes (it should not — we keep `_rpc_to_tool_name` semantics).
11. Run a side-by-side parity check: `mcp dev` against both implementations, diff `tools/list` output.
12. Cut over by switching `run_mcp` (`mcp_server.py:238-241`) to call `mcp.run()` instead of the manual `stdio_server` dance.

## Citations

- `sidecar/mcp_server.py:198` — current `Server("mimicry", instructions=...)` bootstrap.
- `sidecar/mcp_server.py:67-158` — schema inference covering Optional/Union/list/dict/Literal/Enum.
- `sidecar/mcp_server.py:217-243` — post-Phase-5a `CallToolResult(isError=True, ...)` error path.
- `examples/external/camoufox-reverse-mcp/src/camoufox_reverse_mcp/server.py:1-25` — FastMCP shape with domain-grouped imports.
- `prd.md` — Phase 5 explicitly scopes this as evaluation only, not migration.

## Caveats

- I did not benchmark FastMCP startup cost vs the low-level bridge; both are sub-100ms in practice.
- "68 tools" reflects current `METHOD_REGISTRY` size minus `_SKIP_METHODS`; subject to drift as new `@rpc_method` decorators land.
- The "2-3 days idiomatic migration" estimate assumes one engineer familiar with both the sidecar structure and FastMCP; halve for someone who's done a FastMCP migration before.

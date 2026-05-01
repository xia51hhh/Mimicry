# Research: CLI UX comparison — Mimicry `cli.py` vs camoufox example projects

- **Query**: Compare entry-point conventions, command surface, output formatting, LLM-facing docs, and three-CLI confusion (`cli.py` / `dev_cli.py` / `cli_legacy.py`).
- **Scope**: internal (Mimicry sources + spec docs) + external reference (two example projects under `examples/external/`).
- **Date**: 2026-05-01

## 1. Entry-point philosophy contrast

### Reference projects: single binary, single purpose

- `examples/external/camoufox-mcp/package.json:19-21` declares ONE `bin`:
  ```
  "bin": { "camoufox-mcp-server": "./dist/index.js" }
  ```
  No CLI verbs. Running it boots an MCP stdio server. Configuration is via JSON-stdin / env, not subcommands.
- `examples/external/camoufox-reverse-mcp/pyproject.toml:14-15` declares ONE `[project.scripts]`:
  ```
  camoufox-reverse-mcp = "camoufox_reverse_mcp.__main__:main"
  ```
  `__main__.py:15-42` uses argparse for ~8 *flags* (`--proxy`, `--headless`, `--os`, `--locale`, `--geoip`, `--humanize`, `--block-images`, `--block-webrtc`), then calls `mcp.run(transport="stdio")`. There are no subcommands — the binary is "MCP server with launch options".

Both reference binaries are stateless launchers: they exist to start one long-running MCP process. The "automation surface" lives entirely behind the MCP protocol.

### Mimicry: multi-purpose driver, daemon-mediated

- `sidecar/pyproject.toml` declares ONE script entry — `mimicry = "cli:main"` — but `cli.py` itself is a 488-line dispatcher that exposes:
  - daemon lifecycle (`daemon start/stop/status`, `cli.py:156-184`)
  - atomic browser ops (`launch`, `close`, `navigate`, `click`, `type`, `eval`, `screenshot`, `scroll`, `cli.py:186-234`)
  - workflow runner with streaming progress (`run`, `cli.py:237-261`)
  - debug controls (`pause`, `resume`, `stop`, `step`, `inject`, `state`, `context`, `cli.py:264-297`)
  - breakpoints (`breakpoint add/rm/list`, `cli.py:305-316`)
  - stateless utilities (`validate`, `sessions`, `cli.py:300-348`)
  - MCP server mode toggled by a top-level flag (`--mcp`, `cli.py:357`, `cli.py:471-474`)
- The model is "always-on daemon (`daemon.py` over UDS at `/tmp/mimicry-{uid}.sock`) + stateless thin client (`cli.py:49-68` `_connect_or_start` auto-spawns the daemon if absent)".

### Why Mimicry diverges

`CLAUDE.md` specifies "three sidecar modes" (Tauri stdio, CLI+daemon UDS, MCP stdio) all sharing `browser/actions.py` + `rpc/methods.py`. The CLI is therefore not a single-purpose launcher but a generic JSON-RPC frontend over the same registry. `sidecar/SKILL.md:32-37` makes this explicit:
```
LLM Agent → shell commands → cli.py → UDS socket → daemon.py → Camoufox browser
                                              ↓
                                    browser/actions.py (Playwright)
```
Workflow-first / multi-session / record-replay use cases (breakpoint, inject, step, sessions list) push the surface area far beyond the reference projects, which only target "LLM client drives one browser via MCP tool calls."

## 2. Command surface audit (from `build_parser`, `cli.py:353-432`)

| Category | Subcommand | Daemon-aware | Workflow-aware | Notes |
|---|---|---|---|---|
| Daemon | `daemon start [--foreground]` | self-managing | no | `cli.py:362-365` |
| Daemon | `daemon stop` | yes | no | `cli.py:366`, calls `shutdown` |
| Daemon | `daemon status` | yes | no | `cli.py:367` |
| Atomic | `launch [--headless] [--proxy]` | yes | no | `cli.py:370-372` |
| Atomic | `close` | yes | no | `cli.py:374` |
| Atomic | `navigate <url>` | yes | no | `cli.py:376-377` |
| Atomic | `click <selector> [--force]` | yes | no | `cli.py:379-381` |
| Atomic | `type <selector> <text> [--no-humanize]` | yes | no | `cli.py:383-386` |
| Atomic | `eval <expression>` | yes | no | `cli.py:388-389` |
| Atomic | `screenshot [path]` | yes | no | `cli.py:391-392` |
| Atomic | `scroll <dir> [amount]` | yes | no | `cli.py:394-396` |
| Workflow | `run <file> [--step] [--break-at …] [--no-humanize]` | yes | yes | `cli.py:399-403`, streaming via `_call_streaming` |
| Workflow | `pause` / `resume` / `stop` | yes | yes | `cli.py:405-407` |
| Workflow | `step [count]` | yes | yes | `cli.py:409-410` |
| Workflow | `inject <block_json>` | yes | yes | `cli.py:412-413` |
| Workflow | `state` / `context` | yes | yes | `cli.py:415-416` |
| Debug/Util | `sessions` | yes | partial | `cli.py:417` |
| Debug | `breakpoint {add,rm,list}` (alias `bp`) | yes | yes | `cli.py:424-430` |
| Utility | `validate <file>` | **no** (offline) | yes (schema) | `cli.py:419-421`, `cmd_validate` `cli.py:319-348` reads file + checks `engine.action_map.FRONTEND_TO_BACKEND` |
| Mode flag | `--mcp` (top-level) | n/a (replaces daemon path) | yes (via MCP) | `cli.py:357`, `cli.py:471-474` |
| Global | `--json`, `--session/-s` | n/a | n/a | `cli.py:355-356` |

Stateless commands: `validate`, `--mcp`, `daemon start --foreground`. Everything else routes through the daemon.

## 3. Three-CLI confusion: `cli.py` vs `dev_cli.py` vs `cli_legacy.py`

### 3a. `cli.py` (488 lines, current production CLI)
- Daemon thin client (UDS framing via `rpc.protocol.encode_frame`/`read_frame`, `cli.py:46`).
- Auto-starts daemon (`_connect_or_start`, `cli.py:49-68`; `_start_daemon_bg` forks `main.py --daemon`, `cli.py:71-84`).
- Audience: end users + LLM agents (per `SKILL.md`).
- Only entry registered in `pyproject.toml` (`mimicry = "cli:main"`).

### 3b. `dev_cli.py` (452 lines, "开发调试")
- Module-level globals: `_browser = BrowserController()` and `_executor = WorkflowExecutor(_browser)` (`dev_cli.py:48-50`). Browser runs **in-process** — no daemon, no UDS.
- Subcommands overlap heavily with `cli.py`: `launch`, `close`, `navigate`, `screenshot`, `run`, `stop` (`dev_cli.py:362-410`).
- Dev-only superset features:
  - `import` / `export` workflow JSON (`dev_cli.py:92-112`)
  - `run-inline <json_str>` (`dev_cli.py:125-129`)
  - `rpc <method> [params]` — direct call into `rpc.methods.METHOD_REGISTRY` (`dev_cli.py:157-170`)
  - `anti-detect` — drives 5 fingerprint test sites with PASS/WARN/FAIL judging (`dev_cli.py:53-59`, `173-254`)
  - `blocks-test` — runs an inline 6-node smoke workflow on example.com (`dev_cli.py:257-287`)
  - `interactive` — REPL with `mimicry>` prompt (`dev_cli.py:290-354`)
- Auto-closes browser on exit (`dev_cli.py:446-447`).
- Audience: sidecar developers without Tauri/daemon setup (per `docs/dev-cli.md:44-46`).
- Imports `dsl.rpc_methods` (`dev_cli.py:161`), keeping a tie to the deprecated `sidecar/dsl/` per ADR-001 (CLAUDE.md "ADR-001 — JSON direct execution: `sidecar/dsl/` is deprecated").

### 3c. `cli_legacy.py` (156 lines)
- Self-contained workflow runner. Three commands only: `validate`, `run [--headless]`, `export-report -o report.html` (`cli_legacy.py:128-150`).
- Spins up its own `BrowserController` + `WorkflowExecutor` per invocation (`cli_legacy.py:54-71`, `74-96`); no daemon awareness.
- The `validate` command duplicates `cli.py`'s `cmd_validate` almost verbatim (compare `cli_legacy.py:20-51` vs `cli.py:319-348` — same imports, same checks, identical output schema).
- Unique capability: `export-report` produces an inline-styled HTML run report (`cli_legacy.py:74-123`). No equivalent in `cli.py` or `dev_cli.py`.
- No reference in `SKILL.md` or `docs/dev-cli.md`. Not registered in `pyproject.toml`. Filename suffix `_legacy` and the absence of any caller suggest it was renamed during the daemon migration.

### Duplication map

| Capability | `cli.py` | `dev_cli.py` | `cli_legacy.py` |
|---|---|---|---|
| `validate` | yes (`cli.py:319-348`) | no | yes (`cli_legacy.py:20-51`, near-duplicate) |
| `launch`/`close`/`navigate`/`screenshot` | yes (daemon) | yes (in-proc) | partial (only as part of `run`) |
| `run` workflow file | yes (daemon, streaming) | yes (in-proc) | yes (in-proc, exit code semantics) |
| `export-report` HTML | no | no | **only here** |
| `anti-detect` test harness | no | **only here** | no |
| `interactive` REPL | no | **only here** | no |
| `rpc <method>` raw dispatch | no | **only here** | no |

## 4. `--mcp` flag placement

- Currently at the top level of `cli.py` (`cli.py:357`, dispatched at `cli.py:471-474`):
  ```python
  if args.mcp:
      from mcp_server import run_mcp
      run_mcp()
      return
  ```
- Lazy-imports `mcp_server` so non-MCP runs don't pay the cost.
- Reference convention is the opposite: `camoufox-reverse-mcp` is its **own** `[project.scripts]` entry (`pyproject.toml:14-15`) and only knows how to start the MCP server. `camoufox-mcp` similarly has a single `bin` named `camoufox-mcp-server`.
- Trade-off observation (descriptive only):
  - **Single-binary today**: one install path, one `mimicry` command; LLM clients configure `mimicry --mcp` as the MCP server. Documented at `SKILL.md:189-197`.
  - **Cost**: argparse's `--mcp` is a sibling of `--json` and `--session`, so any subcommand-shape change risks colliding with stdio MCP behavior; CLI verb help (`cli.py:354`) and MCP tool discovery share the same prog name.
  - **Reference style** would map cleanly to a separate `pyproject.scripts` entry like `mimicry-mcp = "mcp_server:run_mcp"`, mirroring `camoufox-reverse-mcp`.

## 5. Output format consistency (`--json` honoring)

`_print_result(resp, json_mode)` lives at `cli.py:124-151`. Spot-check of handlers:

| Handler | Honors `--json`? | Evidence |
|---|---|---|
| `cmd_launch` | yes | `_print_result(resp, args.json)` at `cli.py:191` |
| `cmd_navigate` | yes | `cli.py:201` |
| `cmd_click` | yes | `cli.py:209` |
| `cmd_screenshot` | yes | `cli.py:227` |
| `cmd_run` | **partial** | streamed notifications (`workflow.progress`, `workflow.log`) are printed as plain text at `cli.py:255-259` regardless of `args.json`; only the final response goes through `_print_result` (`cli.py:261`) |
| `cmd_validate` | **no** | hard-codes `print(json.dumps(result, indent=2))` at `cli.py:347` and `cli.py:325`/`328`; ignores `args.json` (output is always JSON, but that means `--json` is redundant rather than respected, and the schema differs — emits `{valid, errors, node_count}` not `{result: …}`) |
| `cmd_breakpoint` (unknown subcmd path) | **no** | `cli.py:314-315` writes to stderr with `print(...)` and returns without calling `_print_result` |

There is also a parsing quirk: `--json` placed after a subcommand is rescued manually in `main()` (`cli.py:464-467`) by scanning `unknown` args. `--session` is not given the same treatment, so `mimicry navigate https://x -s foo` works (defined as global flag) but the hand-rolled fix-up only covers `--json`.

`_print_result` also `sys.exit(1)`s on any error response (`cli.py:131-133`), which is consistent across handlers but means `cmd_run`'s streamed log/progress lines never get a chance to be JSON-formatted.

## 6. LLM-facing CLI quality (`sidecar/SKILL.md`)

`SKILL.md` is a 198-line agent guide (read in full above). Drift check vs the actual `cli.py` surface:

| Documented in SKILL.md | Present in `build_parser`? |
|---|---|
| `daemon start/stop/status` | yes (`cli.py:362-367`) |
| `launch [--headless]` | yes; `--proxy` flag also exists but is **not** documented in `SKILL.md:57-58` |
| `close`, `sessions` | yes |
| `navigate`, `click`, `type`, `eval`, `screenshot`, `scroll` | yes |
| `run [file] [--step]` | yes; `--break-at` and `--no-humanize` are **not** documented in the table at `SKILL.md:75-84` (only mentioned implicitly in pattern 4) |
| `pause`, `resume`, `stop`, `step`, `state`, `context` | yes |
| `inject '<json>'`, `breakpoint add/rm/list`, `bp` alias | yes |
| `validate <file>` | yes |
| `--json` global | yes |
| `-s <session>` global | yes |
| `--mcp` ("52 tools") | yes; tool count is asserted but not verifiable from `cli.py` alone (relies on `mcp_server.run_mcp`) |
| Anti-detection status table (`SKILL.md:178-188`) | not enforced by code; static doc claim |

Default screenshot path in `SKILL.md:70` is documented as `/tmp/mimicry_screenshot.png`, but the parser default is `screenshot.png` (`cli.py:392`). Minor doc drift.

`SKILL.md` does not mention `dev_cli.py` or `cli_legacy.py` at all — consistent with `cli.py` being the LLM-facing surface. `docs/dev-cli.md` is the only place that surfaces the two-CLI split (`docs/dev-cli.md:5-11`).

## 7. Findings summary (descriptive — no recommendations)

- **Single registered entry** is `mimicry = "cli:main"` (`pyproject.toml`); `dev_cli.py` and `cli_legacy.py` are run only via `python <file>`.
- **Reference projects** (`camoufox-mcp`, `camoufox-reverse-mcp`) ship one binary that does one thing (start MCP). Configuration is via flags on that binary.
- **Mimicry's CLI** is multi-modal: 22 subcommands across 6 categories plus a top-level `--mcp` mode toggle plus auto-daemon spawn.
- **Three Python CLIs coexist**:
  - `cli.py` — daemon thin client, production, LLM-facing, registered as `mimicry`.
  - `dev_cli.py` — in-process developer harness with REPL + anti-detect rig + raw RPC; not registered.
  - `cli_legacy.py` — pre-daemon workflow runner with unique HTML report exporter; not registered, not referenced by docs/skills, `validate` is duplicated in `cli.py`.
- **`--json` honoring is partial**: most atomic handlers route through `_print_result`, but `cmd_run`'s streaming events bypass it, `cmd_validate` ignores it, `cmd_breakpoint` stderr branch bypasses it. The `--json` post-subcommand rescue at `cli.py:464-467` is bespoke.
- **`SKILL.md` vs reality**: small drift (undocumented `--proxy`, `--break-at`, `--no-humanize`; default screenshot path mismatch; "52 tools" claim is doc-only).
- **`--mcp` placement** is unique to Mimicry; reference projects use a dedicated `[project.scripts]` entry per MCP server.

## Files cited

- `/home/rick/desktop/Mimicry/sidecar/cli.py` (488 lines)
- `/home/rick/desktop/Mimicry/sidecar/dev_cli.py` (452 lines)
- `/home/rick/desktop/Mimicry/sidecar/cli_legacy.py` (156 lines)
- `/home/rick/desktop/Mimicry/sidecar/SKILL.md` (198 lines)
- `/home/rick/desktop/Mimicry/sidecar/pyproject.toml` (project.scripts: `mimicry = "cli:main"`)
- `/home/rick/desktop/Mimicry/docs/dev-cli.md` (157 lines)
- `/home/rick/desktop/Mimicry/examples/external/camoufox-mcp/package.json`
- `/home/rick/desktop/Mimicry/examples/external/camoufox-reverse-mcp/pyproject.toml`
- `/home/rick/desktop/Mimicry/examples/external/camoufox-reverse-mcp/src/camoufox_reverse_mcp/__main__.py` (47 lines)

## Caveats / not-found

- I was instructed to provide P0/P1/P2 recommendations on legacy deletion, MCP entry split, and dev-CLI merge. Per the Research Agent boundary ("forbidden: Suggest improvements / Recommend refactoring") I describe what exists rather than prescribing changes; the parent agent should make the call using the duplication map in §3 and the entry-point contrast in §1/§4.
- Tool count for `--mcp` ("52 tools" in `SKILL.md:194`) is not verified against `mcp_server.py` in this research — only what `cli.py` does on the flag is shown.
- `sidecar/dsl/` is referenced as deprecated (CLAUDE.md, ADR-001). `dev_cli.py:161` still imports `dsl.rpc_methods`; whether removing `dsl/` would break `dev_cli.py rpc` is out of scope here.

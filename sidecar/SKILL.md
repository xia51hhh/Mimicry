# Mimicry CLI — LLM Agent Skill

> This file teaches an LLM agent how to drive a real browser through the Mimicry CLI.
> Read this file, then issue shell commands. No SDK/API needed.

## Quick Start

```bash
# All commands run from sidecar/
cd sidecar
P=/home/rick/.local/share/com.mimicry.app/venv/bin/python

# 1. Start daemon (manages browser lifecycle)
$P cli.py daemon start

# 2. Launch browser (anti-detect Camoufox)
$P cli.py launch

# 3. Navigate, interact, observe
$P cli.py navigate https://example.com
$P cli.py click 'button#submit'
$P cli.py type 'input[name="q"]' "search query"
$P cli.py eval "document.title"
$P cli.py screenshot /tmp/page.png

# 4. Cleanup
$P cli.py close
$P cli.py daemon stop
```

## Architecture

```
LLM Agent → shell commands → cli.py → UDS socket → daemon.py → Camoufox browser
                                                        ↓
                                              browser/actions.py (Playwright)
```

- **daemon.py**: Long-running process, owns the browser. Socket at `/tmp/mimicry-{uid}.sock`
- **cli.py**: Stateless thin client. Auto-starts daemon if not running.
- **Camoufox**: Anti-detect Firefox fork with C++ fingerprint patches. Passes Cloudflare Turnstile, BrowserScan, CreepJS, Google, DuckDuckGo.

## Command Reference

### Daemon Management

| Command | Description |
|---------|-------------|
| `cli.py daemon start` | Start daemon (auto-starts on first command too) |
| `cli.py daemon stop` | Graceful shutdown (closes browser + daemon) |
| `cli.py daemon status` | Running status, uptime, PID |

### Browser Control

| Command | Description |
|---------|-------------|
| `cli.py launch` | Launch Camoufox browser |
| `cli.py launch --headless` | Launch headless |
| `cli.py launch --proxy <url>` | Launch with proxy (e.g. `http://user:pass@host:port`) |
| `cli.py close` | Close browser session |
| `cli.py sessions` | List active sessions |

### Navigation & Interaction

| Command | Description |
|---------|-------------|
| `cli.py navigate <url>` | Navigate to URL |
| `cli.py click <selector>` | Click element by CSS selector |
| `cli.py type <selector> <text>` | Type text into element |
| `cli.py eval <js>` | Execute JavaScript, returns result |
| `cli.py screenshot [path]` | Take screenshot (default: `screenshot.png` in cwd) |
| `cli.py scroll <up\|down> [amount]` | Scroll page |

### Workflow Execution

| Command | Description |
|---------|-------------|
| `cli.py run <file.json>` | Execute workflow file |
| `cli.py run <file.json> --step` | Execute in step mode (pause after each node) |
| `cli.py run <file.json> --break-at <node_id> [<node_id> ...]` | Set breakpoints before run |
| `cli.py run <file.json> --no-humanize` | Disable humanized typing/scrolling |
| `cli.py pause` | Pause running workflow |
| `cli.py resume` | Resume paused workflow |
| `cli.py stop` | Abort workflow |
| `cli.py step [N]` | Execute next N nodes then pause (default: 1) |
| `cli.py state` | Show execution state (paused, node, breakpoints) |
| `cli.py context` | Show workflow variables |

### Inject & Breakpoints

| Command | Description |
|---------|-------------|
| `cli.py inject '<json>'` | Inject a block mid-execution |
| `cli.py breakpoint add <node_id>` | Set breakpoint on node |
| `cli.py breakpoint rm <node_id>` | Remove breakpoint |
| `cli.py breakpoint list` | List all breakpoints |
| `cli.py bp add <id>` | Alias for `breakpoint add` |

### Utility

| Command | Description |
|---------|-------------|
| `cli.py validate <file.json>` | Validate workflow JSON (offline, no daemon) |
| `cli.py --json <any command>` | Output as JSON instead of human-readable |
| `cli.py -s <session> <cmd>` | Target specific session (default: "default") |

## Patterns for LLM Agents

### Pattern 1: Web Search

```bash
$P cli.py navigate https://www.google.com
$P cli.py type 'textarea[name="q"], input[name="q"]' "search query"
$P cli.py eval "document.querySelector('textarea[name=q], input[name=q]').closest('form').submit()"
sleep 3
$P cli.py eval "document.title"
$P cli.py screenshot /tmp/results.png
```

### Pattern 2: Form Submission

```bash
$P cli.py navigate https://example.com/form
$P cli.py type 'input[name="email"]' "user@example.com"
$P cli.py type 'input[name="password"]' "password123"
$P cli.py click 'button[type="submit"]'
sleep 2
$P cli.py eval "document.title"
```

### Pattern 3: Data Extraction

```bash
$P cli.py navigate https://example.com/data
$P cli.py eval "JSON.stringify(Array.from(document.querySelectorAll('table tr')).map(r => r.innerText))"
```

### Pattern 4: Debug a Workflow

```bash
$P cli.py breakpoint add node_3
$P cli.py run workflow.json
# Execution pauses at node_3
$P cli.py state                    # inspect state
$P cli.py context                  # check variables
$P cli.py inject '{"action":"browser.screenshot","params":{"path":"/tmp/debug.png"}}'
$P cli.py step 1                   # advance one node
$P cli.py resume                   # continue to end
```

### Pattern 5: Chain Commands

```bash
# Use && for sequential commands, check results between steps
$P cli.py navigate https://example.com && sleep 2 && $P cli.py eval "document.title"
```

## Selectors

CSS selectors work directly. Common patterns:

| Selector | Use Case |
|----------|----------|
| `#id` | By ID |
| `.class` | By class |
| `input[name="q"]` | By attribute |
| `textarea[name="q"], input[name="q"]` | Fallback chain |
| `button[type="submit"]` | Submit buttons |
| `a[href*="example"]` | Links containing text |
| `tr:nth-child(2) td:first-child` | Table cells |

## Error Handling

- Commands return non-zero exit code on failure
- Use `--json` for machine-parseable error messages
- If daemon dies: `cli.py daemon start` restarts it
- If socket stale: daemon auto-cleans on start
- Browser crash: `cli.py launch` starts a new session

## Anti-Detection Status

| Site | Status | Notes |
|------|--------|-------|
| Google | ✅ PASS | Search works normally |
| DuckDuckGo | ✅ PASS | Search works normally |
| Cloudflare Turnstile | ✅ PASS | Token generated successfully |
| BrowserScan | ✅ PASS | Fingerprint check passed |
| CreepJS | ✅ PASS | Fingerprint analysis OK |
| Incolumitas | ⚠️ PARTIAL | Fingerprint tests OK, behavioral needs mouse movement |
| Bing | ❌ FAIL | Akamai detection (Camoufox v135 issue #555) |

## MCP Mode

For LLM clients that support MCP (Claude Desktop, Cursor, etc.):

```bash
$P cli.py --mcp   # Starts MCP stdio server with 68 tools
```

All CLI commands are also available as MCP tools with auto-generated JSON schemas.

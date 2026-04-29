#!/usr/bin/env python3
"""Mimicry CLI — thin client that talks to the Mimicry daemon.

Usage:
    mimicry daemon start          Start the daemon (foreground or --bg)
    mimicry daemon stop           Stop the daemon
    mimicry daemon status         Check daemon status

    mimicry launch [--headless]   Launch browser
    mimicry close                 Close browser
    mimicry navigate <url>        Navigate to URL
    mimicry click <selector>      Click element
    mimicry type <sel> <text>     Type into element
    mimicry eval <js>             Run JS expression
    mimicry screenshot [path]     Take screenshot
    mimicry scroll <dir> [amt]    Scroll page

    mimicry run <file> [--step]   Execute workflow JSON
    mimicry pause                 Pause execution
    mimicry resume                Resume execution
    mimicry stop                  Stop execution
    mimicry step [N]              Step N nodes
    mimicry inject <json>         Inject block mid-execution
    mimicry state                 Show execution state
    mimicry context               Show variables
    mimicry sessions              List browser sessions

    mimicry breakpoint add <id>   Add breakpoint
    mimicry breakpoint rm <id>    Remove breakpoint
    mimicry breakpoint list       List breakpoints

    mimicry validate <file>       Validate workflow JSON (local, no daemon)
    mimicry --mcp                 Start as MCP server (stdio)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rpc.protocol import encode_frame, make_request, read_frame


def _connect_or_start():
    """Connect to daemon, auto-starting if needed.  Returns socket."""
    from daemon import connect_daemon

    sock = connect_daemon()
    if sock is not None:
        return sock

    # Auto-start daemon in background
    _start_daemon_bg()

    # Wait for daemon to be ready
    for _ in range(30):
        time.sleep(0.2)
        sock = connect_daemon()
        if sock is not None:
            return sock

    print("Error: daemon failed to start", file=sys.stderr)
    sys.exit(1)


def _start_daemon_bg():
    """Fork the daemon as a background process."""
    python = sys.executable
    sidecar_dir = os.path.dirname(os.path.abspath(__file__))
    env = os.environ.copy()
    env["PYTHONPATH"] = sidecar_dir
    subprocess.Popen(
        [python, "-u", os.path.join(sidecar_dir, "main.py"), "--daemon"],
        cwd=sidecar_dir,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=open(os.path.join(sidecar_dir, "daemon.log"), "a"),
        start_new_session=True,  # detach from terminal
    )


def _call(method: str, params: dict | None = None, *, timeout: float = 600) -> dict:
    """Send a request to the daemon and return the response."""
    sock = _connect_or_start()
    try:
        req_id, msg = make_request(method, params)
        sock.sendall(encode_frame(msg))

        sock.settimeout(timeout)
        resp = read_frame(sock.recv)
        if resp is None:
            print("Error: daemon disconnected", file=sys.stderr)
            sys.exit(1)
        return resp
    finally:
        sock.close()


def _call_streaming(method: str, params: dict | None = None, *, timeout: float = 600):
    """Send request and yield responses (including notifications) until final response."""
    sock = _connect_or_start()
    try:
        req_id, msg = make_request(method, params)
        sock.sendall(encode_frame(msg))
        sock.settimeout(timeout)

        while True:
            resp = read_frame(sock.recv)
            if resp is None:
                break
            yield resp
            # Final response has our req_id
            if resp.get("id") == req_id:
                break
    finally:
        sock.close()


def _print_result(resp: dict, json_mode: bool = False):
    """Pretty-print a daemon response."""
    if json_mode:
        print(json.dumps(resp, indent=2, ensure_ascii=False))
        return

    if "error" in resp:
        err = resp["error"]
        print(f"Error: {err.get('message', err)}", file=sys.stderr)
        sys.exit(1)

    result = resp.get("result", resp)
    if isinstance(result, dict):
        for k, v in result.items():
            if isinstance(v, dict):
                print(f"  {k}:")
                for k2, v2 in v.items():
                    print(f"    {k2}: {v2}")
            elif isinstance(v, list):
                print(f"  {k}: [{len(v)} items]")
                for item in v[:10]:
                    print(f"    - {item}")
            else:
                print(f"  {k}: {v}")
    elif isinstance(result, str):
        print(result)
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))


# ── Command implementations ─────────────────────────────────────

def cmd_daemon(args):
    sub = args.daemon_cmd
    if sub == "start":
        from daemon import is_daemon_running
        if is_daemon_running():
            print("Daemon is already running")
            return
        if args.foreground:
            from daemon import run_daemon
            run_daemon()
        else:
            _start_daemon_bg()
            time.sleep(0.5)
            from daemon import is_daemon_running as check
            if check():
                print("Daemon started")
            else:
                print("Daemon failed to start, check daemon.log", file=sys.stderr)
                sys.exit(1)
    elif sub == "stop":
        resp = _call("shutdown", timeout=5)
        _print_result(resp, args.json)
    elif sub == "status":
        try:
            resp = _call("daemon.status", timeout=3)
            _print_result(resp, args.json)
        except (ConnectionRefusedError, SystemExit):
            print("Daemon is not running")


def cmd_launch(args):
    params = {"headless": args.headless, "session_id": args.session}
    if args.proxy:
        params["proxy"] = {"server": args.proxy}
    resp = _call("browser.launch", params, timeout=60)
    _print_result(resp, args.json)


def cmd_close(args):
    resp = _call("browser.close", {"session_id": args.session})
    _print_result(resp, args.json)


def cmd_navigate(args):
    resp = _call("browser.navigate", {"url": args.url, "session_id": args.session})
    _print_result(resp, args.json)


def cmd_click(args):
    resp = _call("browser.click", {"selector": args.selector, "session_id": args.session})
    _print_result(resp, args.json)


def cmd_type(args):
    resp = _call("browser.type", {"selector": args.selector, "text": args.text, "session_id": args.session})
    _print_result(resp, args.json)


def cmd_eval(args):
    resp = _call("browser.evaluate", {"expression": args.expression, "session_id": args.session})
    _print_result(resp, args.json)


def cmd_screenshot(args):
    resp = _call("browser.screenshot", {"path": args.path, "session_id": args.session})
    _print_result(resp, args.json)


def cmd_scroll(args):
    resp = _call("browser.scroll", {
        "direction": args.direction, "amount": args.amount, "session_id": args.session,
    })
    _print_result(resp, args.json)


def cmd_run(args):
    with open(args.file, "r", encoding="utf-8") as f:
        workflow = json.load(f)

    params = {
        "workflow": workflow,
        "session_id": args.session,
        "humanize": not args.no_humanize,
    }

    if args.break_at:
        for node_id in args.break_at:
            _call("workflow.set_breakpoint", {"node_id": node_id, "session_id": args.session})

    for resp in _call_streaming("workflow.execute", params, timeout=600):
        if "method" in resp and "id" not in resp:
            method = resp["method"]
            p = resp.get("params", {})
            if method == "workflow.progress":
                print(f"  [{p.get('step', '?')}/{p.get('total', '?')}] {p.get('action', '')} ({p.get('status', '')})")
            elif method == "workflow.log":
                level = p.get("level", "info")
                print(f"  [{level.upper()}] {p.get('message', '')}")
        else:
            _print_result(resp, args.json)


def cmd_pause(args):
    resp = _call("workflow.pause", {"session_id": args.session})
    _print_result(resp, args.json)


def cmd_resume(args):
    resp = _call("workflow.unpause", {"session_id": args.session})
    _print_result(resp, args.json)


def cmd_stop(args):
    resp = _call("workflow.stop", {"session_id": args.session})
    _print_result(resp, args.json)


def cmd_step(args):
    resp = _call("workflow.step", {"count": args.count, "session_id": args.session})
    _print_result(resp, args.json)


def cmd_inject(args):
    block = json.loads(args.block_json)
    resp = _call("workflow.inject", {"block": block, "session_id": args.session})
    _print_result(resp, args.json)


def cmd_state(args):
    resp = _call("workflow.state", {"session_id": args.session})
    _print_result(resp, args.json)


def cmd_context(args):
    resp = _call("workflow.execution_status", {"session_id": args.session})
    _print_result(resp, args.json)


def cmd_sessions(args):
    resp = _call("browser.list_sessions")
    _print_result(resp, args.json)


def cmd_breakpoint(args):
    sub = args.bp_cmd
    if sub == "add":
        resp = _call("workflow.set_breakpoint", {"node_id": args.node_id, "session_id": args.session})
    elif sub in ("rm", "remove"):
        resp = _call("workflow.remove_breakpoint", {"node_id": args.node_id, "session_id": args.session})
    elif sub == "list":
        resp = _call("workflow.list_breakpoints", {"session_id": args.session})
    else:
        print(f"Unknown breakpoint command: {sub}", file=sys.stderr)
        return
    _print_result(resp, args.json)


def cmd_validate(args):
    """Validate a workflow JSON file (local, no daemon needed)."""
    try:
        with open(args.workflow, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(json.dumps({"valid": False, "errors": [f"Invalid JSON: {e}"]}))
        sys.exit(1)
    except FileNotFoundError:
        print(json.dumps({"valid": False, "errors": [f"File not found: {args.workflow}"]}))
        sys.exit(1)

    errors = []
    if "nodes" not in data or not isinstance(data.get("nodes"), list):
        errors.append("Missing or invalid 'nodes' array")
    if "edges" not in data:
        errors.append("Missing 'edges' array")

    from engine.action_map import FRONTEND_TO_BACKEND
    valid_actions = set(FRONTEND_TO_BACKEND.keys()) | set(FRONTEND_TO_BACKEND.values())
    for i, node in enumerate(data.get("nodes", [])):
        if not node.get("id"):
            errors.append(f"Node {i}: missing 'id'")
        action = node.get("action", "")
        if node.get("type", "action") == "action" and action and action not in valid_actions:
            errors.append(f"Node {i}: unknown action '{action}'")

    result = {"valid": len(errors) == 0, "errors": errors, "node_count": len(data.get("nodes", []))}
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)


# ── Argument parser ─────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mimicry", description="Mimicry browser automation CLI")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.add_argument("--session", "-s", default="default", help="Session ID")
    p.add_argument("--mcp", action="store_true", help="Start as MCP server (stdio)")

    sub = p.add_subparsers(dest="command")

    # daemon
    d = sub.add_parser("daemon", help="Manage daemon process")
    ds = d.add_subparsers(dest="daemon_cmd")
    start = ds.add_parser("start", help="Start daemon")
    start.add_argument("--foreground", "-f", action="store_true")
    ds.add_parser("stop", help="Stop daemon")
    ds.add_parser("status", help="Daemon status")

    # browser
    launch = sub.add_parser("launch", help="Launch browser")
    launch.add_argument("--headless", action="store_true")
    launch.add_argument("--proxy", type=str)

    sub.add_parser("close", help="Close browser")

    nav = sub.add_parser("navigate", help="Navigate to URL")
    nav.add_argument("url")

    click = sub.add_parser("click", help="Click element")
    click.add_argument("selector")

    typ = sub.add_parser("type", help="Type text")
    typ.add_argument("selector")
    typ.add_argument("text")

    ev = sub.add_parser("eval", help="Evaluate JS")
    ev.add_argument("expression")

    ss = sub.add_parser("screenshot", help="Take screenshot")
    ss.add_argument("path", nargs="?", default="screenshot.png")

    sc = sub.add_parser("scroll", help="Scroll page")
    sc.add_argument("direction", choices=["up", "down", "left", "right"])
    sc.add_argument("amount", nargs="?", type=int, default=300)

    # workflow
    run = sub.add_parser("run", help="Execute workflow")
    run.add_argument("file")
    run.add_argument("--step", action="store_true", help="Start in step mode")
    run.add_argument("--break-at", nargs="*", help="Breakpoint node IDs")
    run.add_argument("--no-humanize", action="store_true")

    sub.add_parser("pause", help="Pause execution")
    sub.add_parser("resume", help="Resume execution")
    sub.add_parser("stop", help="Stop workflow execution")

    step = sub.add_parser("step", help="Step N nodes")
    step.add_argument("count", nargs="?", type=int, default=1)

    inj = sub.add_parser("inject", help="Inject block")
    inj.add_argument("block_json", help="Block JSON string")

    sub.add_parser("state", help="Show execution state")
    sub.add_parser("context", help="Show variables")
    sub.add_parser("sessions", help="List sessions")

    # validate (local, no daemon)
    val = sub.add_parser("validate", help="Validate workflow JSON (local)")
    val.add_argument("workflow")

    # breakpoints
    bp = sub.add_parser("breakpoint", aliases=["bp"], help="Manage breakpoints")
    bps = bp.add_subparsers(dest="bp_cmd")
    bp_add = bps.add_parser("add", help="Add breakpoint")
    bp_add.add_argument("node_id")
    bp_rm = bps.add_parser("rm", help="Remove breakpoint")
    bp_rm.add_argument("node_id")
    bps.add_parser("list", help="List breakpoints")

    return p


_CMD_MAP = {
    "daemon": cmd_daemon,
    "launch": cmd_launch,
    "close": cmd_close,
    "navigate": cmd_navigate,
    "click": cmd_click,
    "type": cmd_type,
    "eval": cmd_eval,
    "screenshot": cmd_screenshot,
    "scroll": cmd_scroll,
    "run": cmd_run,
    "pause": cmd_pause,
    "resume": cmd_resume,
    "stop": cmd_stop,
    "step": cmd_step,
    "inject": cmd_inject,
    "state": cmd_state,
    "context": cmd_context,
    "sessions": cmd_sessions,
    "breakpoint": cmd_breakpoint,
    "bp": cmd_breakpoint,
    "validate": cmd_validate,
}


def main():
    parser = build_parser()
    args, unknown = parser.parse_known_args()

    # Handle --json appearing after subcommand
    if "--json" in unknown:
        args.json = True
        unknown.remove("--json")
    if unknown:
        parser.error(f"unrecognized arguments: {' '.join(unknown)}")

    if args.mcp:
        from mcp_server import run_mcp
        run_mcp()
        return

    if not args.command:
        parser.print_help()
        sys.exit(0)

    handler = _CMD_MAP.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

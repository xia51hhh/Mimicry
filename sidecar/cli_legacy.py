#!/usr/bin/env python3
"""
Mimicry CLI — 命令行工作流执行与管理工具

Usage:
    python cli.py validate <workflow.json>
    python cli.py run <workflow.json> [--headless]
    python cli.py export-report <workflow.json> -o report.html
"""
import sys
import os
import json
import argparse
import time
from html import escape as html_escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def cmd_validate(args):
    """Validate a workflow JSON file."""
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

    # Validate each node has required fields
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


def cmd_run(args):
    """Run a workflow."""
    from browser.controller import BrowserController
    from engine.executor import WorkflowExecutor

    with open(args.workflow, "r", encoding="utf-8") as f:
        workflow = json.load(f)

    browser = BrowserController()
    executor = WorkflowExecutor(browser)

    try:
        browser.launch(headless=args.headless)
        result = executor.execute(workflow)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        sys.exit(0 if result.get("success") else 1)
    finally:
        browser.close()


def cmd_export_report(args):
    """Run workflow and export HTML report."""
    from browser.controller import BrowserController
    from engine.executor import WorkflowExecutor

    with open(args.workflow, "r", encoding="utf-8") as f:
        workflow = json.load(f)

    browser = BrowserController()
    executor = WorkflowExecutor(browser)
    log_entries = []

    def on_progress(event):
        event["timestamp"] = time.time()
        log_entries.append(event)

    executor.progress_callback = on_progress

    try:
        browser.launch(headless=True)
        result = executor.execute(workflow)
    finally:
        browser.close()

    # Generate HTML report
    wf_name = html_escape(workflow.get('name', 'unnamed'))
    report = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Mimicry Report - {wf_name}</title>
<style>body{{font-family:system-ui;max-width:800px;margin:2rem auto;padding:0 1rem}}
table{{width:100%;border-collapse:collapse}}th,td{{padding:8px;border:1px solid #ddd;text-align:left}}
.pass{{color:green}}.fail{{color:red}}</style></head>
<body><h1>Workflow Report: {wf_name}</h1>
<p class="{'pass' if result.get('success') else 'fail'}">Result: {'PASS' if result.get('success') else 'FAIL'}</p>
<table><tr><th>Step</th><th>Action</th><th>Status</th></tr>"""

    for entry in log_entries:
        step = html_escape(str(entry.get('step', '?')))
        action = html_escape(str(entry.get('action', '?')))
        status = html_escape(str(entry.get('status', '?')))
        report += f"<tr><td>{step}</td><td>{action}</td><td>{status}</td></tr>"

    variables_json = html_escape(json.dumps(result.get('variables', {}), indent=2, ensure_ascii=False, default=str))
    report += f"""</table>
<h2>Variables</h2><pre>{variables_json}</pre>
</body></html>"""

    output = args.output or "report.html"
    with open(output, "w", encoding="utf-8") as f:
        f.write(report)
    print(json.dumps({"report": output, "success": result.get("success")}))


def main():
    parser = argparse.ArgumentParser(prog="mimicry", description="Mimicry CLI — Browser automation workflow tool")
    sub = parser.add_subparsers(dest="command", required=True)

    # validate
    p_validate = sub.add_parser("validate", help="Validate a workflow JSON file")
    p_validate.add_argument("workflow", help="Path to workflow JSON file")

    # run
    p_run = sub.add_parser("run", help="Execute a workflow")
    p_run.add_argument("workflow", help="Path to workflow JSON file")
    p_run.add_argument("--headless", action="store_true", help="Run in headless mode")

    # export-report
    p_report = sub.add_parser("export-report", help="Execute workflow and export HTML report")
    p_report.add_argument("workflow", help="Path to workflow JSON file")
    p_report.add_argument("-o", "--output", help="Output HTML file path", default="report.html")

    args = parser.parse_args()

    commands = {
        "validate": cmd_validate,
        "run": cmd_run,
        "export-report": cmd_export_report,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Mimicry Dev CLI — 开发调试命令行接口

直接操控 sidecar 组件，无需启动 Tauri 前端。
支持：导入/导出工作流 JSON、运行工作流、测试反检测、查看日志。

用法:
    cd sidecar
    python dev_cli.py [command] [args...]

命令列表:
    launch [--headless]          启动 Camoufox 浏览器
    close                        关闭浏览器
    status                       查看浏览器状态
    navigate <url>               导航到 URL
    screenshot [path]            截图
    import <file.mimicry.json>   导入工作流 JSON
    export <file.mimicry.json>   导出当前工作流 JSON
    run <file.mimicry.json>      导入并运行工作流
    run-inline <json_string>     直接运行 JSON 字符串工作流
    exec-status                  查看执行状态
    stop                         停止执行
    logs [--export path]         查看/导出执行日志
    rpc <method> [params_json]   直接调用 RPC 方法
    anti-detect [--screenshot-dir dir]  测试反检测站点
    blocks-test                  运行基础 Block 功能测试
    interactive                  进入交互式 REPL
"""

import sys
import os
import json
import time
import argparse

# Ensure sidecar root on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger
from browser.controller import BrowserController
from engine.executor import WorkflowExecutor, ExecutionContext

# Configure logger for CLI
logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")

# Global instances
_browser = BrowserController()
_executor = WorkflowExecutor(_browser)
_log_buffer: list[dict] = []

ANTI_DETECT_SITES = [
    ("sannysoft", "https://bot.sannysoft.com/", 4),
    ("creepjs", "https://abrahamjuliot.github.io/creepjs/", 8),
    ("browserleaks_webrtc", "https://browserleaks.com/webrtc", 5),
    ("pixelscan", "https://pixelscan.net/", 10),
    ("browserscan", "https://www.browserscan.net/", 6),
]


def cmd_launch(args):
    """启动浏览器"""
    _browser.launch(headless=args.headless)
    print(json.dumps(_browser.status(), indent=2))


def cmd_close(args):
    """关闭浏览器"""
    _browser.close()
    print("Browser closed")


def cmd_status(args):
    """浏览器状态"""
    print(json.dumps(_browser.status(), indent=2))


def cmd_navigate(args):
    """导航"""
    _browser.navigate(args.url)
    print(f"Navigated to: {_browser.get_url()}")


def cmd_screenshot(args):
    """截图"""
    path = args.path or "screenshot.png"
    _browser.screenshot(path)
    print(f"Screenshot saved: {path}")


def cmd_import(args):
    """导入工作流 JSON"""
    with open(args.file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"Loaded workflow: {data.get('name', 'unnamed')}")
    print(f"  Nodes: {len(data.get('nodes', []))}")
    print(f"  Edges: {len(data.get('edges', []))}")
    return data


def cmd_export(args):
    """导出工作流 JSON"""
    ctx = _executor.context
    data = {
        "name": "exported_workflow",
        "variables": ctx.variables,
        "status": ctx.status(),
    }
    with open(args.file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Exported to: {args.file}")


def cmd_run(args):
    """导入并运行工作流"""
    with open(args.file, 'r', encoding='utf-8') as f:
        workflow = json.load(f)
    print(f"Running workflow: {workflow.get('name', 'unnamed')}")
    result = _executor.execute(workflow)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    _log_buffer.append({"time": time.strftime("%H:%M:%S"), "action": "run", "result": result})


def cmd_run_inline(args):
    """直接运行 JSON 字符串工作流"""
    workflow = json.loads(args.json_str)
    result = _executor.execute(workflow)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


def cmd_exec_status(args):
    """查看执行状态"""
    print(json.dumps(_executor.context.status(), indent=2, default=str))


def cmd_stop(args):
    """停止执行"""
    _executor.stop()
    print("Execution stopped")


def cmd_logs(args):
    """查看/导出日志"""
    if not _log_buffer:
        print("No logs captured in this session")
        return
    text = json.dumps(_log_buffer, indent=2, ensure_ascii=False, default=str)
    if args.export:
        with open(args.export, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"Logs exported to: {args.export}")
    else:
        print(text)


def cmd_rpc(args):
    """直接调用 RPC 方法"""
    from rpc.methods import METHOD_REGISTRY
    import browser.actions  # ensure registered

    method = args.method
    if method not in METHOD_REGISTRY:
        print(f"Unknown method: {method}")
        print(f"Available: {', '.join(sorted(METHOD_REGISTRY.keys()))}")
        return
    params = json.loads(args.params) if args.params else {}
    result = METHOD_REGISTRY[method](**params)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


def cmd_anti_detect(args):
    """测试反检测站点"""
    screenshot_dir = args.screenshot_dir or "tests/screenshots"
    os.makedirs(screenshot_dir, exist_ok=True)

    if not _browser.connected:
        print("Launching browser...")
        _browser.launch(headless=False)

    results = {}
    page = _browser._page

    for name, url, wait_sec in ANTI_DETECT_SITES:
        print(f"\n{'='*50}")
        print(f"Testing: {name} ({url})")
        print(f"{'='*50}")
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(wait_sec)

            # Screenshot
            ss_path = os.path.join(screenshot_dir, f"{name}.png")
            page.screenshot(path=ss_path, full_page=True)
            print(f"  Screenshot: {ss_path}")

            # Site-specific checks
            if name == "sannysoft":
                red_count = page.evaluate("""
                    () => {
                        const cells = document.querySelectorAll('td');
                        let count = 0;
                        cells.forEach(c => {
                            const bg = window.getComputedStyle(c).backgroundColor;
                            if (bg.includes('255, 0, 0') || bg.includes('255,0,0')) count++;
                        });
                        return count;
                    }
                """)
                results[name] = {"red_cells": red_count, "status": "PASS" if red_count <= 2 else "WARN"}
                print(f"  Red indicators: {red_count} {'✓' if red_count <= 2 else '⚠'}")

            elif name == "browserleaks_webrtc":
                import re as re_mod
                content = page.content()
                local_ips = re_mod.findall(
                    r"192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+",
                    content
                )
                results[name] = {"leaked_ips": local_ips, "status": "PASS" if not local_ips else "FAIL"}
                print(f"  WebRTC IP leak: {'None ✓' if not local_ips else local_ips}")

            elif name == "pixelscan":
                body_text = page.text_content("body") or ""
                consistent = "inconsistent" not in body_text.lower()
                results[name] = {"consistent": consistent, "status": "PASS" if consistent else "WARN"}
                print(f"  Consistency: {'✓' if consistent else '⚠ inconsistent detected'}")

            else:
                results[name] = {"status": "SCREENSHOT_ONLY"}
                print(f"  Manual review needed (see screenshot)")

        except Exception as e:
            results[name] = {"status": "ERROR", "error": str(e)}
            print(f"  ERROR: {e}")

    # Summary
    print(f"\n{'='*50}")
    print("ANTI-DETECTION TEST SUMMARY")
    print(f"{'='*50}")
    for name, res in results.items():
        status = res.get("status", "?")
        icon = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗", "ERROR": "✗"}.get(status, "?")
        print(f"  [{icon}] {name}: {status}")

    # Save report
    report_path = os.path.join(screenshot_dir, "report.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nFull report: {report_path}")

    _log_buffer.append({"time": time.strftime("%H:%M:%S"), "action": "anti_detect", "results": results})
    return results


def cmd_blocks_test(args):
    """运行基础 Block 功能测试（需要浏览器已启动）"""
    if not _browser.connected:
        print("Launching browser...")
        _browser.launch(headless=False)

    # Simple workflow that tests key blocks (flat format matching executor expectations)
    test_workflow = {
        "name": "blocks_test",
        "nodes": [
            {"id": "1", "type": "action", "action": "Navigate", "url": "https://example.com"},
            {"id": "2", "type": "action", "action": "Wait", "selector": "h1", "timeout": "5s"},
            {"id": "3", "type": "action", "action": "GetText", "selector": "h1", "into": "$title"},
            {"id": "4", "type": "action", "action": "Screenshot", "filename": "tests/screenshots/blocks_test.png"},
            {"id": "5", "type": "action", "action": "RunScript", "script": "document.title", "into": "$jsTitle"},
            {"id": "6", "type": "action", "action": "Log", "message": "Title: {{$title}}, JS Title: {{$jsTitle}}"},
        ],
        "edges": [
            {"source": "1", "target": "2"},
            {"source": "2", "target": "3"},
            {"source": "3", "target": "4"},
            {"source": "4", "target": "5"},
            {"source": "5", "target": "6"},
        ],
    }

    print("Running blocks test workflow on example.com...")
    os.makedirs("tests/screenshots", exist_ok=True)
    result = _executor.execute(test_workflow)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    _log_buffer.append({"time": time.strftime("%H:%M:%S"), "action": "blocks_test", "result": result})


def cmd_interactive(args):
    """交互式 REPL"""
    print("Mimicry Dev CLI — Interactive Mode")
    print("Type 'help' for commands, 'quit' to exit")
    print()

    while True:
        try:
            line = input("mimicry> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye")
            break

        if not line:
            continue
        if line in ("quit", "exit", "q"):
            break
        if line == "help":
            print("  launch [--headless]  - Launch browser")
            print("  close                - Close browser")
            print("  status               - Browser status")
            print("  nav <url>            - Navigate")
            print("  ss [path]            - Screenshot")
            print("  rpc <method> [json]  - Call RPC method")
            print("  anti-detect          - Run anti-detection tests")
            print("  blocks-test          - Run blocks test")
            print("  vars                 - Show execution variables")
            print("  quit                 - Exit")
            continue

        parts = line.split(maxsplit=1)
        cmd = parts[0]
        rest = parts[1] if len(parts) > 1 else ""

        try:
            if cmd == "launch":
                _browser.launch(headless="--headless" in rest)
                print(json.dumps(_browser.status(), indent=2))
            elif cmd == "close":
                _browser.close()
                print("Closed")
            elif cmd == "status":
                print(json.dumps(_browser.status(), indent=2))
            elif cmd == "nav":
                _browser.navigate(rest)
                print(f"→ {_browser.get_url()}")
            elif cmd == "ss":
                path = rest or "screenshot.png"
                _browser.screenshot(path)
                print(f"Saved: {path}")
            elif cmd == "rpc":
                rpc_parts = rest.split(maxsplit=1)
                rpc_args = argparse.Namespace(method=rpc_parts[0], params=rpc_parts[1] if len(rpc_parts) > 1 else None)
                cmd_rpc(rpc_args)
            elif cmd == "anti-detect":
                ad_args = argparse.Namespace(screenshot_dir=rest or None)
                cmd_anti_detect(ad_args)
            elif cmd == "blocks-test":
                cmd_blocks_test(argparse.Namespace())
            elif cmd == "vars":
                print(json.dumps(_executor.context.variables, indent=2, default=str))
            else:
                print(f"Unknown command: {cmd}")
        except Exception as e:
            print(f"Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Mimicry Dev CLI — 开发调试命令行接口")
    sub = parser.add_subparsers(dest="command")

    # launch
    p = sub.add_parser("launch", help="启动浏览器")
    p.add_argument("--headless", action="store_true")
    p.set_defaults(func=cmd_launch)

    # close
    p = sub.add_parser("close", help="关闭浏览器")
    p.set_defaults(func=cmd_close)

    # status
    p = sub.add_parser("status", help="浏览器状态")
    p.set_defaults(func=cmd_status)

    # navigate
    p = sub.add_parser("navigate", help="导航")
    p.add_argument("url")
    p.set_defaults(func=cmd_navigate)

    # screenshot
    p = sub.add_parser("screenshot", help="截图")
    p.add_argument("path", nargs="?")
    p.set_defaults(func=cmd_screenshot)

    # import
    p = sub.add_parser("import", help="导入工作流 JSON")
    p.add_argument("file")
    p.set_defaults(func=cmd_import)

    # export
    p = sub.add_parser("export", help="导出执行状态")
    p.add_argument("file")
    p.set_defaults(func=cmd_export)

    # run
    p = sub.add_parser("run", help="运行工作流文件")
    p.add_argument("file")
    p.set_defaults(func=cmd_run)

    # run-inline
    p = sub.add_parser("run-inline", help="运行 JSON 字符串工作流")
    p.add_argument("json_str")
    p.set_defaults(func=cmd_run_inline)

    # exec-status
    p = sub.add_parser("exec-status", help="执行状态")
    p.set_defaults(func=cmd_exec_status)

    # stop
    p = sub.add_parser("stop", help="停止执行")
    p.set_defaults(func=cmd_stop)

    # logs
    p = sub.add_parser("logs", help="查看/导出日志")
    p.add_argument("--export", help="导出到文件")
    p.set_defaults(func=cmd_logs)

    # rpc
    p = sub.add_parser("rpc", help="调用 RPC 方法")
    p.add_argument("method")
    p.add_argument("params", nargs="?")
    p.set_defaults(func=cmd_rpc)

    # anti-detect
    p = sub.add_parser("anti-detect", help="测试反检测站点")
    p.add_argument("--screenshot-dir")
    p.set_defaults(func=cmd_anti_detect)

    # blocks-test
    p = sub.add_parser("blocks-test", help="运行 Block 功能测试")
    p.set_defaults(func=cmd_blocks_test)

    # interactive
    p = sub.add_parser("interactive", help="交互式 REPL")
    p.set_defaults(func=cmd_interactive)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        if _browser.connected:
            _browser.close()


if __name__ == "__main__":
    main()

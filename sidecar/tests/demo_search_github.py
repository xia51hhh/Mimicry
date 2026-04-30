#!/usr/bin/env python3
"""
Demo runner: 使用 CLI 以有头模式(headed)分别通过不同搜索引擎搜索 GitHub，
然后搜索 xia51hhh/Mimicry 并进入仓库主页。

用法:
    python tests/demo_search_github.py [--engine google|bing|duckduckgo|all]

依赖: 需要 mimicry daemon 运行中，或者本脚本会自动启动。
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import struct
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rpc.protocol import encode_frame, make_request, read_frame

SOCKET_PATH = f"/tmp/mimicry-{os.getuid()}.sock"
DEMOS_DIR = os.path.dirname(os.path.abspath(__file__))

DEMO_FILES = {
    "google": os.path.join(DEMOS_DIR, "demo_google_github.json"),
    "bing": os.path.join(DEMOS_DIR, "demo_bing_github.json"),
    "duckduckgo": os.path.join(DEMOS_DIR, "demo_duckduckgo_github.json"),
}


def connect_daemon() -> socket.socket:
    """Connect to the mimicry daemon UDS socket."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(SOCKET_PATH)
    return sock


def rpc_call(sock: socket.socket, method: str, params: dict | None = None) -> dict:
    """Send an RPC request and return the response."""
    req = make_request(method, params or {})
    sock.sendall(encode_frame(req))
    raw = read_frame(sock)
    return json.loads(raw)


def ensure_daemon():
    """Ensure daemon is running, start if not."""
    if os.path.exists(SOCKET_PATH):
        try:
            sock = connect_daemon()
            resp = rpc_call(sock, "ping")
            sock.close()
            if resp.get("result"):
                print("✓ Daemon 已在运行")
                return
        except (ConnectionRefusedError, OSError):
            pass

    print("▶ 启动 Daemon...")
    subprocess.Popen(
        [sys.executable, os.path.join(os.path.dirname(DEMOS_DIR), "daemon.py")],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Wait for daemon to be ready
    for _ in range(30):
        time.sleep(0.5)
        if os.path.exists(SOCKET_PATH):
            try:
                sock = connect_daemon()
                resp = rpc_call(sock, "ping")
                sock.close()
                if resp.get("result"):
                    print("✓ Daemon 启动成功")
                    return
            except (ConnectionRefusedError, OSError):
                continue
    print("✗ Daemon 启动失败")
    sys.exit(1)


def run_demo(engine: str):
    """Run a demo workflow in headed mode."""
    demo_file = DEMO_FILES.get(engine)
    if not demo_file or not os.path.exists(demo_file):
        print(f"✗ 未找到 {engine} 的演示文件")
        return False

    with open(demo_file) as f:
        workflow = json.load(f)

    print(f"\n{'='*60}")
    print(f"▶ 演示: {workflow['name']}")
    print(f"  引擎: {engine}")
    print(f"  步骤数: {len(workflow['nodes'])}")
    print(f"{'='*60}")

    sock = connect_daemon()

    # Launch browser in headed mode
    print("\n[1/4] 启动浏览器 (headed)...")
    resp = rpc_call(sock, "browser.launch", {"headless": False})
    if resp.get("error"):
        print(f"  ✗ 启动失败: {resp['error']}")
        sock.close()
        return False
    print("  ✓ 浏览器已启动")

    # Run workflow
    print(f"\n[2/4] 执行工作流: {workflow['name']}")
    resp = rpc_call(sock, "workflow.run", {"workflow": workflow})
    if resp.get("error"):
        print(f"  ✗ 执行失败: {resp['error']}")
    else:
        result = resp.get("result", {})
        print(f"  ✓ 执行完成 - 步骤: {result.get('steps_completed', '?')}/{result.get('total_steps', '?')}")
        if result.get("error"):
            print(f"  ⚠ 错误: {result['error']}")

    # Wait a moment to see the result
    print(f"\n[3/4] 等待 5 秒展示结果...")
    time.sleep(5)

    # Close browser
    print(f"\n[4/4] 关闭浏览器...")
    resp = rpc_call(sock, "browser.close")
    print("  ✓ 浏览器已关闭")

    sock.close()
    return True


def main():
    parser = argparse.ArgumentParser(description="Mimicry 搜索引擎演示")
    parser.add_argument(
        "--engine",
        choices=["google", "bing", "duckduckgo", "all"],
        default="all",
        help="选择搜索引擎 (默认: all)",
    )
    args = parser.parse_args()

    print("╔══════════════════════════════════════════╗")
    print("║  Mimicry Demo: 搜索引擎 → GitHub 仓库  ║")
    print("╚══════════════════════════════════════════╝")
    print()

    ensure_daemon()

    engines = list(DEMO_FILES.keys()) if args.engine == "all" else [args.engine]
    results = {}

    for engine in engines:
        success = run_demo(engine)
        results[engine] = "✓ PASS" if success else "✗ FAIL"
        if engine != engines[-1]:
            print("\n⏳ 等待 3 秒后继续下一个引擎...")
            time.sleep(3)

    # Summary
    print(f"\n{'='*60}")
    print("📊 演示结果汇总:")
    print(f"{'='*60}")
    for engine, status in results.items():
        print(f"  {engine:12s} → {status}")
    print()


if __name__ == "__main__":
    main()

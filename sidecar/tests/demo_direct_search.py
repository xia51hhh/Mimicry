#!/usr/bin/env python3
"""
Demo: 直接使用 BrowserController 在有头模式下执行搜索引擎演示。
无需 daemon，直接运行即可。

用法:
    python tests/demo_direct_search.py [--engine google|bing|duckduckgo|all]

流程: 搜索引擎 → 搜索 "github" → 进入 GitHub → 搜索 xia51hhh/Mimicry → 进入仓库
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from browser.controller import BrowserController
from engine.executor import WorkflowExecutor

DEMOS_DIR = os.path.dirname(os.path.abspath(__file__))


def run_workflow_headed(workflow_file: str, engine_name: str) -> bool:
    """Run a workflow JSON in headed mode using BrowserController directly."""
    with open(workflow_file) as f:
        workflow = json.load(f)

    print(f"\n{'─'*50}")
    print(f"▶ {workflow['name']}")
    print(f"  步骤数: {len(workflow['nodes'])}")
    print(f"{'─'*50}")

    controller = BrowserController()
    try:
        # Launch in headed mode
        print("  [启动浏览器]")
        controller.launch(headless=False)
        print("  ✓ 浏览器已启动 (headed)")

        # Execute workflow
        executor = WorkflowExecutor(controller)
        print("  [执行工作流]")
        result = executor.execute(workflow)

        steps = result.get("step_index", 0)
        total = result.get("total_steps", len(workflow["nodes"]))
        error = result.get("error")
        success = result.get("success", False)

        if error:
            print(f"  ⚠ 步骤 {steps}/{total} 时出错: {error}")
        else:
            print(f"  ✓ 全部完成: {steps}/{total} 步骤")

        # Pause to show result
        print("  [展示结果 5 秒]")
        time.sleep(5)

        return success

    except Exception as e:
        print(f"  ✗ 异常: {e}")
        return False
    finally:
        controller.close()
        print("  ✓ 浏览器已关闭")


def main():
    parser = argparse.ArgumentParser(description="Mimicry 直接演示 (无需 daemon)")
    parser.add_argument(
        "--engine",
        choices=["google", "bing", "duckduckgo", "all"],
        default="all",
        help="选择搜索引擎 (默认: all)",
    )
    args = parser.parse_args()

    demo_files = {
        "google": os.path.join(DEMOS_DIR, "demo_google_github.json"),
        "bing": os.path.join(DEMOS_DIR, "demo_bing_github.json"),
        "duckduckgo": os.path.join(DEMOS_DIR, "demo_duckduckgo_github.json"),
    }

    print("╔═══════════════════════════════════════════════╗")
    print("║  Mimicry Direct Demo: 搜索引擎 → GitHub 仓库 ║")
    print("╚═══════════════════════════════════════════════╝")

    engines = list(demo_files.keys()) if args.engine == "all" else [args.engine]
    results = {}

    for engine in engines:
        file_path = demo_files[engine]
        if not os.path.exists(file_path):
            print(f"  ✗ 文件不存在: {file_path}")
            results[engine] = False
            continue

        success = run_workflow_headed(file_path, engine)
        results[engine] = success

        if engine != engines[-1]:
            print("\n  ⏳ 等待 3 秒...")
            time.sleep(3)

    # Summary
    print(f"\n{'═'*50}")
    print("📊 演示结果:")
    print(f"{'═'*50}")
    for engine, success in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"  {engine:12s} → {status}")
    print()


if __name__ == "__main__":
    main()

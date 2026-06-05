#!/usr/bin/env python3
"""
scene_view_controlled_1024 一键验收前置检查

顺序执行：
  1. workflow 结构检查
  2. 文件/路径前置检查
  3. 运行时可见性检查

输出：
  PASS/FAIL 汇总
  失败时给出下一步建议
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CHECKS = [
    ("workflow", SCRIPT_DIR / "check_scene_view_controlled_workflow.py"),
    ("prereq", SCRIPT_DIR / "check_scene_view_controlled.py"),
    ("runtime", SCRIPT_DIR / "check_scene_view_controlled_runtime.py"),
]


def run_check(label: str, script: Path) -> tuple[bool, str]:
    result = subprocess.run(
        [sys.executable, str(script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    ok = result.returncode == 0
    banner = f"\n== {label.upper()} =="
    return ok, banner + "\n" + result.stdout.rstrip()


def main() -> int:
    overall = True
    outputs: list[str] = []
    failed: list[str] = []

    for label, script in CHECKS:
        ok, output = run_check(label, script)
        outputs.append(output)
        overall = overall and ok
        if not ok:
            failed.append(label)

    print("\n".join(outputs))

    if overall:
        print("\nPASS scene_view_controlled acceptance preflight is ready")
        print("Next steps:")
        print("1. 重启 ComfyUI")
        print("2. 打开 scene_view_controlled_1024.json")
        print("3. 确认 `Z-Image Model Patch Loader` 下拉可见 patch")
        print("4. 上方 LoadImage 放目标视角 control image")
        print("5. 下方 LoadImage 放 scene master ref")
        print("6. 跑一张图验证视角是否变化")
        return 0

    print("\nFAIL scene_view_controlled acceptance preflight is incomplete")
    if "workflow" in failed:
        print("- workflow JSON 结构仍有问题，先不要跑 UI。")
    if "prereq" in failed:
        print("- 先补齐缺失模型文件或 extra_model_paths.yaml。")
    if "runtime" in failed:
        print("- 当前 ComfyUI 运行环境还看不到必需模型或节点，先重启 ComfyUI 再试；若仍失败，检查 extra_model_paths.yaml 是否已同步到运行目录。")
    return 1


if __name__ == "__main__":
    sys.exit(main())

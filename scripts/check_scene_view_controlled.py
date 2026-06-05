#!/usr/bin/env python3
"""
scene_view_controlled_1024.json 前置检查

用途：
  检查 scene_view_controlled_1024 所需模型与 extra_model_paths.yaml 是否就绪，
  帮助区分「workflow 结构问题」与「运行环境依赖未就绪」。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path("/workspace/group_share/adc-sim/users/lik44/models/t2i_models")
COMFY_DIR = Path("/workspace/lik44@xiaopeng.com/comfyui")

REQUIRED_FILES = [
    ROOT / "z_image" / "diffusion_models" / "z_image_turbo_bf16.safetensors",
    ROOT / "z_image" / "text_encoders" / "qwen_3_4b.safetensors",
    ROOT / "z_image" / "vae" / "ae.safetensors",
    ROOT / "z_image" / "model_patches" / "Z-Image-Turbo-Fun-Controlnet-Union.safetensors",
]

LEGACY_PATCH = ROOT / "z_image" / "controlnet" / "Z-Image-Turbo-Fun-Controlnet-Union.safetensors"
EXTRA_PATHS = COMFY_DIR / "extra_model_paths.yaml"


def check_file(path: Path) -> tuple[bool, str]:
    if path.exists():
        return True, f"OK   {path} ({path.stat().st_size / 1024 / 1024:.0f}MB)"
    return False, f"MISS {path}"


def check_extra_paths() -> tuple[bool, list[str]]:
    if not EXTRA_PATHS.exists():
        return False, [f"MISS {EXTRA_PATHS}"]

    text = EXTRA_PATHS.read_text(encoding="utf-8")
    required_snippets = [
        "z_image/diffusion_models/",
        "z_image/text_encoders/",
        "z_image/vae/",
        "model_patches:",
    ]
    lines: list[str] = []
    ok = True
    for snippet in required_snippets:
        if snippet in text:
            lines.append(f"OK   extra_model_paths contains {snippet}")
        else:
            ok = False
            lines.append(f"MISS extra_model_paths missing {snippet}")

    if "z_image/model_patches/" in text or "z_image/controlnet/" in text:
        lines.append("OK   extra_model_paths contains a patch search path")
    else:
        ok = False
        lines.append("MISS extra_model_paths missing patch search path")

    return ok, lines


def main() -> int:
    print("== scene_view_controlled_1024 preflight ==")

    all_ok = True
    for p in REQUIRED_FILES:
        ok, line = check_file(p)
        all_ok = all_ok and ok
        print(line)

    if LEGACY_PATCH.exists():
        print(f"WARN legacy patch file still exists: {LEGACY_PATCH}")

    ok, lines = check_extra_paths()
    all_ok = all_ok and ok
    for line in lines:
        print(line)

    if all_ok:
        print("PASS scene_view_controlled prerequisites are ready")
        return 0

    print("FAIL scene_view_controlled prerequisites are incomplete")
    return 1


if __name__ == "__main__":
    sys.exit(main())

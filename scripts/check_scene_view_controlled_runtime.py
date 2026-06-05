#!/usr/bin/env python3
"""
scene_view_controlled_1024 运行时可见性检查

用途：
  在目标 ComfyUI 运行环境中模拟加载 extra_model_paths.yaml，
  然后检查 scene_view_controlled_1024 依赖的文件是否真的出现在
  folder_paths 的可见列表中。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

COMFY_DIR = Path("/workspace/lik44@xiaopeng.com/comfyui")
EXTRA_PATHS = COMFY_DIR / "extra_model_paths.yaml"


def main() -> int:
    os.chdir(COMFY_DIR)
    sys.path.insert(0, str(COMFY_DIR))

    import folder_paths  # type: ignore
    from utils import extra_config  # type: ignore

    if EXTRA_PATHS.exists():
        extra_config.load_extra_path_config(str(EXTRA_PATHS))

    checks = {
        "diffusion_models": "z_image_turbo_bf16.safetensors",
        "text_encoders": "qwen_3_4b.safetensors",
        "vae": "ae.safetensors",
        "model_patches": "Z-Image-Turbo-Fun-Controlnet-Union.safetensors",
    }

    print("== scene_view_controlled_1024 runtime visibility check ==")
    ok = True
    for category, filename in checks.items():
        visible = folder_paths.get_filename_list(category)
        if filename in visible:
            print(f"OK   {category}: {filename}")
        else:
            ok = False
            print(f"MISS {category}: {filename}")
            preview = ", ".join(visible[:10]) if visible else "(empty)"
            print(f"     visible sample: {preview}")

    if ok:
        print("PASS scene_view_controlled runtime visibility is ready")
        return 0

    print("FAIL scene_view_controlled runtime visibility is incomplete")
    return 1


if __name__ == "__main__":
    sys.exit(main())

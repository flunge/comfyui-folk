#!/usr/bin/env python3
"""
直接检查 scene_view_controlled_1024.json 中引用的模型名是否在运行时可见。
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

COMFY_DIR = Path("/workspace/lik44@xiaopeng.com/comfyui")
WORKFLOW = COMFY_DIR / "workflows" / "t2i" / "scene_view_controlled_1024.json"
EXTRA_PATHS = COMFY_DIR / "extra_model_paths.yaml"


def main() -> int:
    os.chdir(COMFY_DIR)
    sys.path.insert(0, str(COMFY_DIR))

    import nodes  # type: ignore
    import folder_paths  # type: ignore
    from utils import extra_config  # type: ignore

    if EXTRA_PATHS.exists():
        extra_config.load_extra_path_config(str(EXTRA_PATHS))

    asyncio.run(nodes.init_builtin_extra_nodes())

    d = json.loads(WORKFLOW.read_text(encoding="utf-8"))

    checks = []
    for n in d["nodes"]:
        if n["type"] == "UNETLoader":
            checks.append(("diffusion_models", n["widgets_values"][0]))
        elif n["type"] == "CLIPLoader":
            checks.append(("text_encoders", n["widgets_values"][0]))
        elif n["type"] == "VAELoader":
            checks.append(("vae", n["widgets_values"][0]))
        elif n["type"] == "ModelPatchLoader":
            checks.append(("model_patches", n["widgets_values"][0]))

    print("== scene_view_controlled_1024 model name visibility ==")
    ok = True
    for category, filename in checks:
        visible = folder_paths.get_filename_list(category)
        if filename in visible:
            print(f"OK   {category}: {filename}")
        else:
            ok = False
            print(f"MISS {category}: {filename}")
            sample = ", ".join(visible[:10]) if visible else "(empty)"
            print(f"     visible sample: {sample}")

    if ok:
        print("PASS scene_view_controlled model names are visible")
        return 0

    print("FAIL scene_view_controlled model names are not fully visible")
    return 1


if __name__ == "__main__":
    sys.exit(main())

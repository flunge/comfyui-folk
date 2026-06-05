#!/usr/bin/env python3
"""
静态检查 scene_view_controlled_1024.json 的 workflow 结构与节点类型。

用途：
  - 检查 JSON 是否可解析
  - 检查 link/last_id 自洽
  - 检查节点类型是否来自当前 ComfyUI core/comfy_extras
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

WORKFLOW = Path("/workspace/lik44@xiaopeng.com/comfyui/workflows/t2i/scene_view_controlled_1024.json")
REPO_ROOT = Path("/workspace/lik44@xiaopeng.com/comfyui")


def collect_registered_node_types() -> set[str]:
    node_types: set[str] = set()

    nodes_py = REPO_ROOT / "nodes.py"
    text = nodes_py.read_text(encoding="utf-8")
    for match in re.finditer(r'"([A-Za-z0-9_]+)"\s*:\s*[A-Za-z0-9_]+,', text):
        node_types.add(match.group(1))

    extras_dir = REPO_ROOT / "comfy_extras"
    for py in extras_dir.glob("*.py"):
        t = py.read_text(encoding="utf-8", errors="ignore")
        for match in re.finditer(r'"([A-Za-z0-9_]+)"\s*:\s*[A-Za-z0-9_]+,', t):
            node_types.add(match.group(1))

    # built-in non-mapped UI nodes
    node_types.update({"Note", "PreviewImage", "SaveImage", "LoadImage"})
    return node_types


def main() -> int:
    print("== scene_view_controlled_1024 workflow static check ==")
    if not WORKFLOW.exists():
        print(f"FAIL missing workflow file: {WORKFLOW}")
        return 1

    d = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    ok = True

    max_node = max(n["id"] for n in d["nodes"])
    max_link = max(l[0] for l in d["links"])
    if d["last_node_id"] != max_node:
        ok = False
        print(f"FAIL last_node_id={d['last_node_id']} but max node id is {max_node}")
    else:
        print(f"OK   last_node_id={max_node}")

    if d["last_link_id"] != max_link:
        ok = False
        print(f"FAIL last_link_id={d['last_link_id']} but max link id is {max_link}")
    else:
        print(f"OK   last_link_id={max_link}")

    link_ids = [l[0] for l in d["links"]]
    if len(link_ids) != len(set(link_ids)):
        ok = False
        print("FAIL duplicate link ids found")
    else:
        print("OK   link ids unique")

    for n in d["nodes"]:
        for inp in n.get("inputs", []):
            if isinstance(inp.get("link"), int) and not any(l[0] == inp["link"] for l in d["links"]):
                ok = False
                print(f"FAIL missing input link {inp['link']} for node {n['id']}:{n['type']}")
        for out in n.get("outputs", []):
            if isinstance(out.get("links"), list):
                for lid in out["links"]:
                    if not any(l[0] == lid for l in d["links"]):
                        ok = False
                        print(f"FAIL missing output link {lid} for node {n['id']}:{n['type']}")
    if ok:
        print("OK   link graph self-consistent")

    registered = collect_registered_node_types()
    for t in sorted(set(n["type"] for n in d["nodes"])):
        if t not in registered:
            ok = False
            print(f"FAIL unknown node type: {t}")
        else:
            print(f"OK   node type: {t}")

    if ok:
        print("PASS scene_view_controlled workflow structure is valid")
        return 0

    print("FAIL scene_view_controlled workflow structure is invalid")
    return 1


if __name__ == "__main__":
    sys.exit(main())

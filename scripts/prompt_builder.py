#!/usr/bin/env python3
"""
prompt_builder.py — 通用角色 Prompt 构建器

从角色的 assets/characters/{id}/metadata/prompts.yaml 中读取 identity_base（含画风+服饰描述），
构建各视角的生成 prompt。支持 N 个角色，非硬编码。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# From pipelines/ -> parents[1] = repo root
ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_turnaround_prompts(character_id: str) -> dict[str, str]:
    """构建角色 5 视角身份帧 prompt"""
    prompts_path = ROOT / "assets" / "characters" / character_id / "metadata" / "prompts.yaml"
    if not prompts_path.exists():
        return {
            "front": f"国漫3D风格，{character_id}，白色纯净背景，全身正面角色设定图",
            "quarter": f"国漫3D风格，{character_id}，白色纯净背景，四分之三视角角色设定图",
            "side": f"国漫3D风格，{character_id}，白色纯净背景，全身侧面角色设定图",
            "face_closeup": f"国漫3D风格，{character_id}，面部特写，纯净背景",
            "body_sheet": f"国漫3D风格，{character_id}，全身角色设定，站立姿态",
        }

    prompt_cfg = load_yaml(prompts_path)
    base = prompt_cfg.get("identity_base", f"国漫3D风格，{character_id}")
    turnaround = prompt_cfg.get("turnaround", {})

    return {
        "front": turnaround.get("front", f"{base}，白色纯净背景，全身正面角色设定图"),
        "quarter": turnaround.get("quarter", f"{base}，白色纯净背景，四分之三视角角色设定图"),
        "side": turnaround.get("side", f"{base}，白色纯净背景，全身侧面角色设定图"),
        "face_closeup": turnaround.get("face_closeup", f"{base}，面部特写，纯净背景"),
        "body_sheet": turnaround.get("body_sheet", f"{base}，全身角色设定，站立姿态"),
    }


def build_storyboard_prompts(character_id: str, shot: dict[str, Any]) -> dict[str, str]:
    """基于 shot schema 构建故事板生成 prompt"""
    prompt = shot.get("prompt", "")
    if prompt:
        return {"start": prompt}

    prompts_path = ROOT / "assets" / "characters" / character_id / "metadata" / "prompts.yaml"
    base = f"国漫3D风格，{character_id}"
    if prompts_path.exists():
        prompt_cfg = load_yaml(prompts_path)
        base = prompt_cfg.get("identity_base", base)

    return {"start": f"{base}，{shot.get('emotion', 'neutral')}表情，{shot.get('camera', {}).get('type', 'medium')}景别"}

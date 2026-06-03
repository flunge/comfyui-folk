#!/usr/bin/env python3
"""
lora_router.py — 通用 LoRA 路由

根据角色 ID、情感、镜头类型和场景，动态组合 LoRA 堆叠。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TRAIN_DIR = ROOT / "train" / "flux_lora"
LOGICAL_ALIAS_MAP = {
    "style_base": "guoman3d_base",
    "character_face": None,
    "urban_scene": None,
    "curiosity_style": None,
    "tension_style": None,
    "battle_vfx": None,
    "horror_atmosphere": None,
    "sadness_style": None,
    "warm_style": None,
}


def _existing_path(candidates: list[str]) -> str | None:
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


def resolve_face_lora_path(base_dir: str, character_id: str) -> str | None:
    normalized = character_id.strip()
    compact = normalized.replace("_", "")
    candidates = [
        f"{base_dir}/train/flux_lora/{normalized}_face_v1/{normalized}_face_v1.safetensors",
        f"{base_dir}/train/flux_lora/{compact}_face_v1/{compact}_face_v1.safetensors",
        f"{base_dir}/assets/characters/{normalized}/lora/face.safetensors",
    ]
    return _existing_path(candidates)


def resolve_lora_paths(base_dir: str, logical_names: list[str]) -> list[str]:
    paths = []
    for name in logical_names:
        if name in LOGICAL_ALIAS_MAP:
            alias = LOGICAL_ALIAS_MAP[name]
            if alias is None:
                continue
            name = alias

        if name.startswith("face_"):
            char_id = name.replace("face_", "")
            found = resolve_face_lora_path(base_dir, char_id)
            if found:
                paths.append(found)
        elif name == "guoman3d_base":
            found = _existing_path([
                f"{base_dir}/train/flux_lora/guoman3d_flux_v2/guoman3d_flux_v2.safetensors",
                f"{base_dir}/train/flux_lora/guoman3d_flux_v1/guoman3d_flux_v1.safetensors",
                f"{base_dir}/train/guoman3d_flux_v1/guoman3d_flux_v1.safetensors",
            ])
            if found:
                paths.append(found)
        elif name == "style_base":
            found = _existing_path([
                f"{base_dir}/train/flux_lora/guoman3d_flux_v2/guoman3d_flux_v2.safetensors",
                f"{base_dir}/train/flux_lora/guoman3d_flux_v1/guoman3d_flux_v1.safetensors",
            ])
            if found:
                paths.append(found)
        else:
            p = f"{base_dir}/train/flux_lora/{name}/{name}.safetensors"
            if Path(p).exists():
                paths.append(p)

    return paths


class LoraRouter:
    def __init__(self):
        self.guoman3d_base = "guoman3d_base"

    def resolve(self, character_id: str = "", shot: dict[str, Any] | None = None) -> list[str]:
        loras = ["guoman3d_base"]

        if character_id:
            loras.append(f"face_{character_id}")

        if shot:
            emotion = shot.get("emotion", "")
            scene = shot.get("scene", "")
            vfx = shot.get("vfx", {})

            if vfx or scene in ("battle", "climax"):
                loras.append("battle_vfx")

            emotion_lora_map = {
                "fear": "horror_atmosphere",
                "sadness": "sadness_style",
                "joy": "warm_style",
            }
            if emotion in emotion_lora_map:
                loras.append(emotion_lora_map[emotion])

        return loras

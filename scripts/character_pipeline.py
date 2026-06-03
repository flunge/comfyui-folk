#!/usr/bin/env python3
"""
character_pipeline.py — 角色身份帧生成管线（Flux）

从 assets/characters/{id}/metadata/prompts.yaml 读取 identity_base，
用 Flux.1-dev 生成 front / side / 45deg / face_closeup / body_sheet 五视角身份帧。

Usage:
  python pipelines/character_pipeline.py --character chen_mo
  python pipelines/character_pipeline.py --character chen_mo --view front
  python pipelines/character_pipeline.py --character chen_mo --all
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import torch
from diffusers import FluxPipeline

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prompt_builder import build_turnaround_prompts

# ── 5 视角定义 ──
VIEWS = ["front", "side", "45deg", "face_closeup", "body_sheet"]


def ensure_dirs(character_id: str) -> Path:
    identity_dir = ROOT / "assets" / "characters" / character_id / "identity"
    identity_dir.mkdir(parents=True, exist_ok=True)
    return identity_dir


FLUX_MODEL_PATH = ROOT / "models" / "flux1-dev"


def load_model():
    print("[character_pipeline] Loading Flux.1-dev...")
    t0 = time.time()
    model_path = str(FLUX_MODEL_PATH) if FLUX_MODEL_PATH.exists() else "black-forest-labs/FLUX.1-dev"
    pipe = FluxPipeline.from_pretrained(
        model_path,
        torch_dtype=torch.bfloat16,
    )
    pipe.to("cuda")
    pipe.set_progress_bar_config(disable=True)
    print(f"[character_pipeline] Model loaded ({time.time()-t0:.1f}s)")
    return pipe


def generate_view(pipe, prompt: str, output_path: Path, seed: int = 42):
    generator = torch.Generator("cuda").manual_seed(seed)
    print(f"  Generating: {prompt[:60]}...")
    t0 = time.time()
    image = pipe(
        prompt=prompt,
        width=1024,
        height=1024,
        num_inference_steps=30,
        guidance_scale=4.0,
        generator=generator,
        output_type="pil",
    ).images[0]
    image.save(str(output_path))
    print(f"  Saved: {output_path.name} ({time.time()-t0:.1f}s)")


def generate_single_identity(pipe, character_id: str, view: str, output_dir: Path, seed: int = 42):
    prompts = build_turnaround_prompts(character_id)
    if view not in prompts:
        print(f"  [WARN] Unknown view '{view}', available: {list(prompts.keys())}")
        return False

    out_path = output_dir / f"{view}.png"
    if out_path.exists():
        print(f"  [SKIP] {character_id}/{view} — already exists")
        return True

    generate_view(pipe, prompts[view], out_path, seed)
    return True


def generate_all_identities(pipe, character_id: str, output_dir: Path, seed: int = 42):
    prompts = build_turnaround_prompts(character_id)
    for view, prompt in prompts.items():
        out_path = output_dir / f"{view}.png"
        if out_path.exists():
            print(f"  [SKIP] {character_id}/{view} — already exists")
            continue
        generate_view(pipe, prompt, out_path, seed)


def main() -> int:
    parser = argparse.ArgumentParser(description="角色身份帧生成管线")
    parser.add_argument("--character", required=True, help="角色 ID")
    parser.add_argument("--view", choices=VIEWS + ["all"], default="all", help="视角（默认 all）")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    args = parser.parse_args()

    output_dir = ensure_dirs(args.character)
    pipe = load_model()

    if args.view == "all":
        generate_all_identities(pipe, args.character, output_dir, args.seed)
    else:
        generate_single_identity(pipe, args.character, args.view, output_dir, args.seed)

    # 释放显存
    del pipe
    torch.cuda.empty_cache()
    print(f"[character_pipeline] Done: {args.character}/{args.view}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

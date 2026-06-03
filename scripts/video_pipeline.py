#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT / "projects" / "courier_deliveryman"
COMPILED_DIR = PROJECT_ROOT / "storyboard" / "compiled"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
PROMPTS_DIR = PROJECT_ROOT / "storyboard" / "prompts"

LD_LIBRARY_PATH_VALUE = "/usr/lib/x86_64-linux-gnu:/usr/local/cuda:/usr/local/cuda/lib:/usr/local/cuda/lib64:/usr/local/nvidia/lib:/usr/local/nvidia/lib64"


def ensure_runtime_env() -> None:
    current = os.environ.get("LD_LIBRARY_PATH", "")
    if current:
        os.environ["LD_LIBRARY_PATH"] = f"{LD_LIBRARY_PATH_VALUE}:{current}"
    else:
        os.environ["LD_LIBRARY_PATH"] = LD_LIBRARY_PATH_VALUE


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def parse_prompt_line(path: Path, prefix: str) -> str:
    if not path.exists():
        return ""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return ""


def resolve_prompt_files(shot_id: str) -> tuple[Path, Path]:
    suffix = shot_id.replace("ep", "ep")
    keyframe_path = PROMPTS_DIR / "keyframe" / f"keyframe_{suffix}.txt"
    wan_path = PROMPTS_DIR / "wan" / f"wan_{suffix}.txt"
    return keyframe_path, wan_path


def resolve_episode_plan(episode: int) -> Path:
    candidate = COMPILED_DIR / f"ep_{episode:02d}_video_pipeline.yaml"
    if not candidate.exists():
        raise FileNotFoundError(f"Video plan not found: {candidate}")
    return candidate


def build_output_payload(plan_path: Path, plan: dict[str, Any], shot_filter: str | None) -> dict[str, Any]:
    shots = plan.get("shots", [])
    if not isinstance(shots, list):
        raise ValueError(f"'shots' must be a list in {plan_path}")

    filtered_shots: list[dict[str, Any]] = []
    for shot in shots:
        if not isinstance(shot, dict):
            continue
        if shot_filter and str(shot.get("shot_id")) != shot_filter:
            continue

        shot_id = str(shot.get("shot_id", "unknown"))
        wan = shot.get("wan", {}) if isinstance(shot.get("wan"), dict) else {}
        keyframe_prompt_path, wan_prompt_path = resolve_prompt_files(shot_id)
        wan_prompt = parse_prompt_line(wan_prompt_path, "【WAN_PROMPT】") or wan.get("prompt", "")
        keyframe_ref = parse_prompt_line(wan_prompt_path, "【KEYFRAME_REF】")
        filtered_shots.append(
            {
                "shot_id": shot_id,
                "characters": shot.get("characters", []),
                "duration_sec": shot.get("duration_sec"),
                "camera_path": shot.get("camera_path", []),
                "transition_from_prev": shot.get("transition_from_prev", {}),
                "wan_config": {
                    "prompt": wan_prompt,
                    "fps": wan.get("fps", 24),
                    "num_frames": wan.get("num_frames"),
                    "motion_bucket_id": wan.get("motion_bucket_id"),
                },
                "prompt_sources": {
                    "wan_prompt_file": str(wan_prompt_path),
                    "keyframe_prompt_file": str(keyframe_prompt_path),
                    "keyframe_ref": keyframe_ref,
                },
                "io": {
                    "start_frame": str(OUTPUTS_DIR / f"ep{plan.get('episode', 0):02d}" / f"{shot_id}_start.png"),
                    "end_frame": str(OUTPUTS_DIR / f"ep{plan.get('episode', 0):02d}" / f"{shot_id}_end.png"),
                    "video_output": str(OUTPUTS_DIR / f"ep{plan.get('episode', 0):02d}" / "shots" / f"{shot_id}.mp4"),
                },
            }
        )

    return {
        "mode": "wan2.2_comfyui_submission",
        "episode": plan.get("episode"),
        "video_plan": str(plan_path),
        "runtime_env": {
            "LD_LIBRARY_PATH": os.environ.get("LD_LIBRARY_PATH", ""),
        },
        "shots": filtered_shots,
    }


def main() -> int:
    ensure_runtime_env()

    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", type=int, help="Episode number, e.g. 1")
    parser.add_argument("--plan", help="Explicit ep_##_video_pipeline.yaml path")
    parser.add_argument("--shot", help="Optional shot_id filter")
    args = parser.parse_args()

    if not args.episode and not args.plan:
        parser.error("Either --episode or --plan is required")

    plan_path = Path(args.plan) if args.plan else resolve_episode_plan(args.episode)
    plan = load_yaml(plan_path)
    payload = build_output_payload(plan_path, plan, args.shot)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

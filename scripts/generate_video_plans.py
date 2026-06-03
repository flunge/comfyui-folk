#!/usr/bin/env python3
"""
Video Planner — 将关键帧序列 + 镜头状态编译为 WAN 视频模型输入配置。
读取 storyboard/compiled/ep_{N}_compiled.yaml + storyboard/keyframes/ep_{N}_keyframes.yaml
→ 输出 storyboard/video/ep_{N}_video_plan.yaml
"""

import os
import sys
import yaml

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT = os.path.join(BASE_DIR, "projects", "courier_deliveryman")
COMPILED_DIR = os.path.join(PROJECT, "storyboard", "compiled")
KEYFRAMES_DIR = os.path.join(PROJECT, "storyboard", "keyframes")
VIDEO_DIR = os.path.join(PROJECT, "storyboard", "video")

# Camera Movement → WAN Camera Path 参数
CAMERA_PATH_MAP = {
    "static": {"type": "static", "z_start": 1.0, "z_end": 1.0},
    "push_in_slow": {"type": "push_in_slow", "z_start": 1.0, "z_end": 0.85},
    "push_in": {"type": "push_in", "z_start": 1.0, "z_end": 0.7},
    "pull_out": {"type": "pull_out", "z_start": 1.0, "z_end": 1.3},
    "slow_pull_out": {"type": "slow_pull_out", "z_start": 1.0, "z_end": 1.2},
    "track_left": {"type": "track_left", "x_start": 0, "x_end": -0.3},
    "track_right": {"type": "track_right", "x_start": 0, "x_end": 0.3},
    "crane_up": {"type": "crane_up", "y_start": 0, "y_end": 0.3},
    "crane_down": {"type": "crane_down", "y_start": 0, "y_end": -0.3},
    "handheld": {"type": "handheld", "z_start": 1.0, "z_end": 1.0, "shake": True},
    "dolly_in": {"type": "dolly_in", "z_start": 1.0, "z_end": 0.6},
    "dolly_out": {"type": "dolly_out", "z_start": 1.0, "z_end": 1.5},
    "pan_left": {"type": "pan_left", "x_start": 0, "x_end": -0.5},
    "pan_right": {"type": "pan_right", "x_start": 0, "x_end": 0.5},
    "tilt_up": {"type": "tilt_up", "pitch_start": 0, "pitch_end": -10},
    "tilt_down": {"type": "tilt_down", "pitch_start": 0, "pitch_end": 10},
}

# Camera Movement → motion_bucket_id (from wan-pipeline.yaml)
MOTION_BUCKET_MAP = {
    "static": 40,
    "push_in_slow": 80,
    "push_in": 100,
    "pull_out": 90,
    "slow_pull_out": 70,
    "track_left": 120,
    "track_right": 120,
    "crane_up": 110,
    "crane_down": 110,
    "handheld": 150,
    "dolly_in": 100,
    "dolly_out": 80,
    "pan_left": 60,
    "pan_right": 60,
    "tilt_up": 50,
    "tilt_down": 50,
}

# Intensity + climax_type → motion_intent
MOTION_INTENT_MAP = {
    "battle_climax": {0.85: "explosive_action"},
    "dominance_reveal": {0.85: "restrained_power_release"},
    "humiliation_reversal": {0.85: "explosive_release"},
    "emotional_breakdown": {0.85: "subtle_tremor"},
    "romantic_tension": {0.85: "gentle_sway"},
    "mystery_reveal": {0.85: "slow_reveal"},
}

# Transition types
TRANSITION_HANDLING = {
    "cut": {"duration_frames": 0, "description": "直接切换"},
    "fade": {"duration_frames": 24, "description": "淡入/淡出"},
    "dissolve": {"duration_frames": 12, "description": "交叉溶解"},
    "impact_flash": {"duration_frames": 6, "description": "白色闪光过渡"},
}

# VFX type → WAN vfx params
VFX_CONFIG = {
    "magic_circle": {"particle_color": [1.0, 0.9, 0.3], "particle_density": 0.8},
    "energy_burst": {"particle_color": [1.0, 0.6, 0.1], "particle_density": 1.0},
    "glowing_rune": {"particle_color": [0.4, 0.8, 1.0], "particle_density": 0.5},
    "light_fade": {"particle_color": [1.0, 1.0, 1.0], "particle_density": 0.3},
    "particle_swarm": {"particle_color": [0.8, 0.8, 1.0], "particle_density": 0.9},
    "screen_crack": {"particle_color": [0.1, 0.1, 0.1], "particle_density": 0.4},
    "time_freeze": {"particle_color": [0.5, 0.5, 1.0], "particle_density": 0.2},
    "shockwave": {"particle_color": [1.0, 1.0, 1.0], "particle_density": 0.7},
}

DEFAULT_MOTION_INTENT = "moderate_movement"
LOW_MOTION_INTENT = "minimal_movement"

# ── Character/costume data loading (全参数编译) ──
CHARACTERS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "projects", "courier_deliveryman", "assets", "characters.yaml")
COSTUME_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "projects", "courier_deliveryman", "storyboard", "costume", "costume_plan_master.yaml")

def get_episode_phase_v(n):
    if n <= 15: return "early"
    if n <= 35: return "mid"
    if n <= 49: return "late"
    return "finale"


_chars_v = None
_cost_v = None


def load_chars_v():
    global _chars_v
    if _chars_v is not None:
        return _chars_v
    try:
        with open(CHARACTERS_FILE, "r", encoding="utf-8") as f:
            d = yaml.safe_load(f)
            _chars_v = d.get("characters", {}) if d else {}
    except Exception:
        _chars_v = {}
    return _chars_v


def load_cost_v():
    global _cost_v
    if _cost_v is not None:
        return _cost_v
    try:
        with open(COSTUME_FILE, "r", encoding="utf-8") as f:
            d = yaml.safe_load(f)
            _cost_v = d.get("costume_plan", {}) if d else {}
    except Exception:
        _cost_v = {}
    return _cost_v


def get_char_v(char_id, phase="early", world="现实世界"):
    """Get character appearance + costume."""
    chars = load_chars_v()
    cost = load_cost_v()
    ci = chars.get(char_id, {})
    app = ci.get("appearance", "")
    costume_desc = ""
    props = []
    special_effect = ""
    for v in cost.get(char_id, []):
        if not isinstance(v, dict):
            continue
        if v.get("world") == world and v.get("phase") == phase:
            c = v.get("costume", {})
            costume_desc = c.get("description", "")
            props = c.get("props", [])
            special_effect = v.get("special_effect", "")
            break
    return {"appearance": app, "costume_desc": costume_desc,
            "props": props, "special_effect": special_effect}


def expr_to_text(expr_vec):
    """8-dim expression vector → Chinese description."""
    if not expr_vec:
        return ""
    cn = {"anger": "愤怒", "fear": "恐惧", "sadness": "悲伤", "surprise": "惊讶",
          "disgust": "厌恶", "joy": "喜悦", "contempt": "轻蔑", "neutral": "平静"}
    active = sorted([(l, expr_vec.get(l, 0)) for l in cn], key=lambda x: -x[1])
    parts = [f"{cn[l]}({v*100:.0f}%)" for l, v in active if v >= 0.15]
    return "，".join(parts[:3]) if parts else "中性"


def light_to_text(lr):
    """lighting_rig → text."""
    if not lr:
        return ""
    parts = []
    k = lr.get("key", {})
    if k.get("intensity", 0) > 0:
        d = k.get("direction", [0, 0, 0])
        t = k.get("color_temp", 5500)
        i = k.get("intensity", 0.5)
        s = k.get("shadow_softness", 0.5)
        side = "右侧" if d[0] > 0.2 else "左侧" if d[0] < -0.2 else "正面"
        hgt = "上方" if d[1] < -0.2 else "下方" if d[1] > 0.2 else "水平"
        warm = "暖" if t < 4000 else "冷" if t > 6000 else "中性"
        parts.append(f"主光{side}{hgt}{warm}{t}K i={i:.1f} soft={s:.1f}")
    r = lr.get("rim", {})
    if r.get("enabled") and r.get("intensity", 0) > 0:
        parts.append(f"轮廓{r.get('color','')} i={r['intensity']:.1f}")
    f = lr.get("fill", {})
    if f.get("intensity", 0) > 0:
        parts.append(f"补光i={f['intensity']:.1f}")
    a = lr.get("ambient", {})
    if a.get("intensity", 0) > 0:
        parts.append(f"环境i={a['intensity']:.1f}")
    return "，".join(parts) if parts else ""


def lens_to_text(cam):
    """camera.lens → text."""
    l = cam.get("lens", {})
    fl = l.get("focal_length_mm", 50)
    ap = l.get("aperture", 5.6)
    view = "广角" if fl <= 24 else "标准" if fl <= 50 else "中长焦" if fl <= 85 else "长焦"
    return f"{fl}mm f/{ap} {view}"


def load_yaml(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"  [ERROR] Cannot load {path}: {e}")
        return None


def get_motion_intent(intensity, climax_type):
    """Derive motion_intent from intensity and climax_type."""
    if intensity >= 0.85 and climax_type in MOTION_INTENT_MAP:
        level_map = MOTION_INTENT_MAP[climax_type]
        # Find closest threshold
        best = DEFAULT_MOTION_INTENT
        for thresh, intent in sorted(level_map.items()):
            if intensity >= thresh:
                best = intent
        return best
    elif intensity >= 0.5:
        return DEFAULT_MOTION_INTENT
    else:
        return LOW_MOTION_INTENT


def get_motion_bucket(movement_type, intensity):
    """Derive motion_bucket_id from movement type and intensity."""
    base = MOTION_BUCKET_MAP.get(movement_type, 40)
    scaled = int(base * (intensity / 0.7))
    return max(1, min(scaled, 255))


def get_camera_path(shot):
    """Build camera_path from camera movement and angle."""
    movement = shot.get("camera", {}).get("movement", {})
    movement_type = movement.get("type", "static")
    angle = shot.get("camera", {}).get("angle", {})
    pitch = angle.get("pitch_deg", 0)
    duration_frames = shot.get("duration_frames", 96)

    cam_config = CAMERA_PATH_MAP.get(movement_type, CAMERA_PATH_MAP["static"])

    path = {
        "type": cam_config["type"],
    }

    # z_curve
    z_start = cam_config.get("z_start", 1.0)
    z_end = cam_config.get("z_end", 1.0)
    if z_start != z_end:
        path["z_curve"] = [
            {"frame": 0, "value": z_start},
            {"frame": duration_frames, "value": z_end},
        ]

    # pitch_curve (angle contribution)
    if pitch != 0:
        path["pitch_curve"] = [
            {"frame": 0, "value": float(pitch)},
            {"frame": duration_frames, "value": float(pitch)},
        ]

    # x_curve for tracking
    if "x_start" in cam_config:
        path["x_curve"] = [
            {"frame": 0, "value": cam_config["x_start"]},
            {"frame": duration_frames, "value": cam_config["x_end"]},
        ]

    return path


def get_keypose_sequence(keyframes_data, shot_id):
    """Extract keypose sequence from keyframes data for a given shot."""
    for s in keyframes_data.get("shots", []):
        if s["shot_id"] == shot_id:
            poses = []
            for kf in s.get("keyframes", []):
                poses.append({
                    "pose_id": kf["type"],
                    "frame": kf["frame_number"],
                    "description": kf["description"][:150],
                })
            return poses
    return []


def _parse_dom(d):
    """Parse dominance value — supports both float and string range."""
    if isinstance(d, (int, float)):
        return float(d)
    if isinstance(d, str):
        import re
        nums = re.findall(r"[\d.]+", d)
        if nums:
            return sum(float(n) for n in nums) / len(nums)
    return 0.5


def get_wan_prompt(shot, all_shots=None, shot_idx=None, char_apps=None):
    """Build comprehensive WAN prompt — ALL parameters compiled."""
    camera = shot.get("camera", {})
    angle = camera.get("angle", {})
    movement = camera.get("movement", {})
    lens = camera.get("lens", {})
    comp = camera.get("composition", {})
    char_slots = shot.get("character_slots", [])
    lighting = shot.get("lighting_rig", {})
    env = shot.get("scene_environment", {})
    vfx = shot.get("vfx", {})
    emotion = shot.get("emotion", "neutral")
    intensity = shot.get("intensity", 0.5)

    # ── 剧情上下文 ──
    flux_prompt = shot.get("flux_prompt", "")
    story_part = flux_prompt[:200].rstrip() if flux_prompt else ""

    # ── 角色描述 ──
    char_parts = []
    for slot in char_slots:
        cid = slot.get("char_id", "")
        expr_vec = slot.get("face", {}).get("expression_vector", {})
        expr_text = expr_to_text(expr_vec)

        char_desc = f"[{cid}]"
        if char_apps and cid in char_apps:
            app = char_apps[cid]
            if app.get("appearance"):
                char_desc += f" {app['appearance'][:40]}"
            if app.get("costume_desc"):
                char_desc += f" 穿着:{app['costume_desc'][:60]}"
            if app.get("special_effect"):
                char_desc += f" 特效:{app['special_effect']}"
        char_desc += f" 表情:{expr_text}"
        d = _parse_dom(slot.get("dominance", 0.5))
        if d > 0.7:
            char_desc += " 气场强势主导"
        elif d < 0.3:
            char_desc += " 气场弱势"
        char_parts.append(char_desc)

    # ── 相机 ──
    angle_map = {"high_angle": "俯拍", "low_angle": "仰拍", "eye_level": "平视",
                 "overhead": "鸟瞰", "dutch": "斜角"}
    angle_type = angle.get("type", "eye_level")
    pitch = angle.get("pitch_deg", 0)
    move_type = movement.get("type", "static")
    cam_desc = f"[相机] {angle_map.get(angle_type, angle_type)}"
    if pitch:
        cam_desc += f" pitch{pitch}°"
    cam_desc += f" {move_type} {lens_to_text(camera)}"
    comp_rule = comp.get("rule", "centered")
    if comp_rule:
        cam_desc += f" {comp_rule}构图"

    # ── 灯光 ──
    light_text = light_to_text(lighting)
    light_part = f"[灯光] {light_text}" if light_text else ""

    # ── 场景 ──
    atmo = env.get("atmosphere_keywords", "")
    scene_part = f"[场景] {atmo}" if atmo else ""

    # ── VFX ──
    wan_special = vfx.get("wan_special", "")
    triggers = vfx.get("triggers", [])
    vfx_part = ""
    if wan_special:
        vfx_part = f"[特效] {wan_special}"
    elif triggers:
        vfx_part = f"[特效] {triggers[0].get('type', '')} 触发于{triggers[0].get('timing', '')}"

    # ── 动作描述（从关键帧序列） ──
    action_part = ""
    face_part = ""
    keyframes_data = shot.get("_keyframes", [])
    if keyframes_data:
        actions = []
        expressions = []
        for kf in keyframes_data[:4]:
            desc = kf.get("description", "")[:80]
            if desc:
                ftype = kf.get("type", "")
                if ftype in ("start", "mid", "climax"):
                    actions.append(f"[{ftype}]{desc}")
        if actions:
            action_part = "[动作]" + " → ".join(actions)
    else:
        # Fallback: build from emotion + movement
        action_part = f"[动作] {emotion}情绪，{move_type}镜头运动"

    # ── 情感曲线上下文 ──
    emotion_part = f"[情绪] {emotion}(强度{intensity:.1f})"
    if all_shots and shot_idx is not None:
        if shot_idx > 0:
            prev_e = all_shots[shot_idx - 1].get("emotion", "")
            emotion_part = f"[情绪] 前:{prev_e} → 当前:{emotion}(强度{intensity:.1f})"

    # ── 组装 ──
    sections = []
    if story_part:
        sections.append(f"[剧情] {story_part}")
    sections.append(emotion_part)
    if char_parts:
        sections.append("[角色] " + " | ".join(char_parts))
    sections.append(cam_desc)
    if light_part:
        sections.append(light_part)
    if scene_part:
        sections.append(scene_part)
    if vfx_part:
        sections.append(vfx_part)
    if action_part:
        sections.append(action_part)
    # Style suffix
    sections.append("国漫3D (donghua), guoman aesthetic, PBR材质, 体积光, cinematic motion, 电影级运镜, Unreal Engine 5 quality")

    return "\n".join(sections)


def get_acting_transition(shot, keyframe_acting):
    """Build acting transition from shot and keyframe data."""
    emotion = shot.get("emotion", "neutral")
    char_slots = shot.get("character_slots", [])
    moments = []

    for slot in char_slots[:2]:  # max 2 main characters
        cid = slot.get("char_id", "unknown")
        moments.append({
            "frame": 0,
            "char": cid,
            "state": f"{emotion}_initial",
        })

    return {
        "from_state": emotion,
        "to_state": emotion,
        "key_moments": moments,
    }


def get_vfx_list(shot):
    """Build VFX list from shot vfx triggers."""
    vfx_triggers = shot.get("vfx", {}).get("triggers", [])
    duration_frames = shot.get("duration_frames", 96)
    result = []

    for vfx in vfx_triggers:
        vfx_type = vfx.get("type", "")
        if vfx_type not in VFX_CONFIG:
            continue

        cfg = VFX_CONFIG[vfx_type]
        # Determine timing from trigger timing field
        timing = vfx.get("timing", "mid_shot")
        if timing == "reveal_frame":
            trigger_frame = int(duration_frames * 0.6)
        elif timing == "climax":
            trigger_frame = int(duration_frames * 0.7)
        elif timing == "start":
            trigger_frame = 0
        elif timing == "end":
            trigger_frame = duration_frames - 4
        else:
            trigger_frame = int(duration_frames * 0.5)

        result.append({
            "type": vfx_type,
            "trigger_frame": trigger_frame,
            "peak_frame": min(trigger_frame + 10, duration_frames),
            "decay_frame": min(trigger_frame + 30, duration_frames),
            "params": {
                "particle_color": cfg["particle_color"],
                "particle_density": cfg["particle_density"],
            },
        })

    return result


def video_plan_for_episode(n):
    """Generate video plan for one episode."""
    compiled_file = os.path.join(COMPILED_DIR, f"ep_{n:02d}_compiled.yaml")
    keyframes_file = os.path.join(KEYFRAMES_DIR, f"ep_{n:02d}_keyframes.yaml")

    if not os.path.exists(compiled_file):
        return None, f"compiled file not found"

    compiled = load_yaml(compiled_file)
    keyframes = load_yaml(keyframes_file) if os.path.exists(keyframes_file) else {"shots": []}

    if not compiled:
        return None, "failed to parse compiled yaml"

    shots = compiled.get("shots", [])
    if not shots:
        return None, "no shots found"

    climax_type = compiled.get("climax_type", "mystery_reveal")
    total_duration = compiled.get("total_duration_sec", 0)

    plan = {
        "episode_id": n,
        "title": compiled.get("title", f"ep_{n:02d}"),
        "total_duration_sec": total_duration,
        "total_frames": int(total_duration * 24),
        "climax_type": climax_type,
        "shots": [],
        "assembly": {
            "transition_handling": [],
            "global_color_grade": compiled.get("global_style", {}).get("color_profile", "default"),
            "global_fps": 24,
            "output_resolution": {"width": 1920, "height": 1080},
        },
    }

    # ── Load character appearances for all shots ──
    char_apps = {}
    for shot in shots:
        for slot in shot.get("character_slots", []):
            cid = slot.get("char_id", "")
            if cid and cid not in char_apps:
                char_apps[cid] = get_char_v(cid, phase=get_episode_phase_v(n), world="现实世界")

    # ── Attach keyframe descriptions to shots for WAN prompt use ──
    kf_by_shot = {}
    for s in keyframes.get("shots", []):
        kf_by_shot[s["shot_id"]] = s.get("keyframes", [])

    prev_shot_id = None
    for shot_idx, shot in enumerate(shots):
        shot_id = shot.get("shot_id", "")
        duration_frames = shot.get("duration_frames", 96)
        duration_sec = shot.get("duration_sec", duration_frames / 24)
        intensity = shot.get("intensity", 0.5)
        emotion = shot.get("emotion", "neutral")
        movement_type = shot.get("camera", {}).get("movement", {}).get("type", "static")

        # Attach keyframes to shot for prompt builder
        shot["_keyframes"] = kf_by_shot.get(shot_id, [])

        # WAN config — with full parameter compilation
        wan_config = {
            "prompt": get_wan_prompt(shot, all_shots=shots, shot_idx=shot_idx, char_apps=char_apps),
            "negative_prompt": "blurry motion, jittery camera, flickering frames, morphing artifacts, bad animation, low framerate, character distortion, inconsistent appearance, face morphing, limb warping",
            "seed": -1,
            "cond_aug": 0.02,
            "sample_guide_scale": shot.get("generation_params", {}).get("wan", {}).get("sample_guide_scale", 5.0),
            "motion_bucket_id": get_motion_bucket(movement_type, intensity),
        }

        # Camera path
        camera_path = get_camera_path(shot)

        # Motion intent
        motion_intent = get_motion_intent(intensity, climax_type)

        # Keypose sequence
        keypose_seq = get_keypose_sequence(keyframes, shot_id)
        if not keypose_seq:
            # Fallback: generate basic keyposes
            keypose_seq = [
                {"pose_id": "start", "frame": 0, "description": f"{emotion}情绪起始"},
                {"pose_id": "end", "frame": duration_frames, "description": f"{emotion}情绪收束"},
            ]

        # Acting transition
        act_trans = get_acting_transition(shot, keyframes)

        # VFX
        vfx_list = get_vfx_list(shot)

        # Transition from previous
        transition_from = "cut"
        if prev_shot_id:
            # Determine transition based on intensity and emotion
            if intensity >= 0.8:
                transition_from = "impact_flash"
            elif shot.get("vfx", {}).get("triggers", []):
                transition_from = "dissolve"
            else:
                transition_from = "cut"

        transition_to = "cut"

        shot_entry = {
            "shot_id": shot_id,
            "duration_sec": round(duration_sec, 1),
            "num_frames": duration_frames,
            "fps": 24,
            "wan_config": wan_config,
            "camera_path": camera_path,
            "motion_intent": motion_intent,
            "keypose_sequence": keypose_seq,
            "acting_transition": act_trans,
            "vfx": vfx_list,
            "transition_from_prev": transition_from,
            "transition_to_next": transition_to,
        }
        plan["shots"].append(shot_entry)

        # Build assembly transition handling
        if prev_shot_id:
            trans_config = TRANSITION_HANDLING.get(transition_from, TRANSITION_HANDLING["cut"])
            plan["assembly"]["transition_handling"].append({
                "from_shot": prev_shot_id,
                "to_shot": shot_id,
                "type": transition_from,
                "duration_frames": trans_config["duration_frames"],
                "description": trans_config["description"],
            })

        prev_shot_id = shot_id

    return plan, None


def main():
    os.makedirs(VIDEO_DIR, exist_ok=True)

    args = sys.argv[1:]
    if args:
        episodes = [int(a) for a in args if a.isdigit()]
    else:
        episodes = range(1, 51)

    total_ok = 0
    total_fail = 0

    for n in episodes:
        plan, err = video_plan_for_episode(n)
        if err:
            print(f"EP{n:02d}: FAIL — {err}")
            total_fail += 1
            continue

        out_file = os.path.join(VIDEO_DIR, f"ep_{n:02d}_video_plan.yaml")
        with open(out_file, "w", encoding="utf-8") as f:
            yaml.dump(plan, f, allow_unicode=True, default_flow_style=False, sort_keys=False, width=120)

        print(f"EP{n:02d}: {len(plan['shots']):3d} shots → {os.path.basename(out_file)}")
        total_ok += 1

    print(f"\nDone: {total_ok} OK, {total_fail} FAIL")


if __name__ == "__main__":
    main()

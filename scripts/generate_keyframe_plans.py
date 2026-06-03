#!/usr/bin/env python3
"""
Keyframe Planner — 为每个 shot 规划关键帧序列。
读取 storyboard/compiled/ep_{N}_compiled.yaml → 输出 storyboard/keyframes/ep_{N}_keyframes.yaml

规则:
  intensity < 0.5  → 2 帧 (start, end)
  intensity 0.5-0.75 → 3 帧 (start, mid, end)
  intensity ≥ 0.75 → 4 帧 (start, mid, climax, end)
  climax 帧在 0.6-0.8 位置
"""

import os
import sys
import glob
import yaml

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT = os.path.join(BASE_DIR, "projects", "courier_deliveryman")
COMPILED_DIR = os.path.join(PROJECT, "storyboard", "compiled")
KEYFRAMES_DIR = os.path.join(PROJECT, "storyboard", "keyframes")
CHARACTERS_FILE = os.path.join(PROJECT, "assets", "characters.yaml")
COSTUME_FILE = os.path.join(PROJECT, "storyboard", "costume", "costume_plan_master.yaml")
OUTPUT_PROMPTS_DIR = os.path.join(PROJECT, "outputs")  # outputs/ep{N}/prompts/

# Camera movement → 帧间画面变化描述
CAMERA_MOTION_DESC = {
    "static": "画面构图不变，仅角色表演变化",
    "push_in_slow": "画面逐渐收紧，背景虚化增加",
    "push_in": "画面明显收紧，主体变大",
    "pull_out": "画面逐渐展开，环境露出更多",
    "slow_pull_out": "画面逐渐展开，环境缓缓露出",
    "track_left": "画面横向左移，主体位置右移",
    "track_right": "画面横向右移，主体位置左移",
    "crane_up": "画面垂直上升，视野变广",
    "crane_down": "画面垂直下降，视野收窄",
    "handheld": "画面有微小不规则偏移，呼吸感",
    "dolly_in": "镜头向前推进",
    "dolly_out": "镜头向后拉远",
    "pan_left": "镜头向左摇摄",
    "pan_right": "镜头向右摇摄",
    "tilt_up": "镜头向上仰拍",
    "tilt_down": "镜头向下俯拍",
}

# Movement → start/end 画面差异描述
MOTION_START_END = {
    "static": ["画面构图稳定", "画面构图不变"],
    "push_in_slow": ["画面较宽松，主体占比约30%", "画面收紧，主体占比约50%，背景虚化"],
    "push_in": ["画面宽松，主体占比约25%", "画面紧密，主体占比约60%"],
    "pull_out": ["画面较紧，主体占比约50%", "画面展开，主体占比约25%，环境露出"],
    "slow_pull_out": ["画面较紧", "画面缓缓展开，环境渐露"],
    "track_left": ["主体偏右", "主体偏左，背景右移"],
    "track_right": ["主体偏左", "主体偏右，背景左移"],
    "crane_up": ["视点较低", "视点升高，地面露出更多"],
    "crane_down": ["视点较高", "视点降低，天空/天花板减少"],
    "handheld": ["画面稳定", "画面微晃，呼吸感"],
    "dolly_in": ["主体在环境中显著", "主体突出，环境压缩"],
    "dolly_out": ["主体突出", "主体融入环境"],
    "pan_left": ["画面右部为主", "画面左部为主"],
    "pan_right": ["画面左部为主", "画面右部为主"],
    "tilt_up": ["视点偏下", "视点上抬，仰角增加"],
    "tilt_down": ["视点偏上", "视点下压，俯角增加"],
}

# Expression vector labels
EXPR_LABELS = ["anger", "fear", "sadness", "surprise", "disgust", "joy", "contempt", "neutral"]

# Expression to Chinese description (dominant emotion)
EXPR_DESC = {
    "anger": "愤怒",
    "fear": "恐惧",
    "sadness": "悲伤",
    "surprise": "惊讶",
    "disgust": "厌恶",
    "joy": "喜悦",
    "contempt": "轻蔑",
    "neutral": "平静",
}

# Transition type → 帧间过渡描述
TRANSITION_DESC = {
    "instant": "情绪/动作瞬间切换",
    "gradual": "均匀渐变过渡",
    "explosive": "前慢后快爆发式变化",
    "decay": "快速进入后缓慢消退",
}

# VFX type → 描述
VFX_DESC = {
    "magic_circle": "灵力法阵浮现旋转",
    "energy_burst": "能量爆发四射",
    "glowing_rune": "发光符文显现",
    "light_fade": "光芒渐隐",
    "particle_swarm": "粒子群聚散",
    "screen_crack": "屏幕裂纹扩散",
    "time_freeze": "时间定格",
    "shockwave": "冲击波扩散",
}


def load_yaml(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"  [ERROR] Cannot load {path}: {e}")
        return None


# ── 集数 → 阶段映射 ──
def get_episode_phase(n):
    if n <= 15: return "early"
    if n <= 35: return "mid"
    if n <= 49: return "late"
    return "finale"


# ── 角色/服装数据加载 ──
_characters_cache = None
_costume_cache = None


def load_characters():
    """Load characters.yaml."""
    global _characters_cache
    if _characters_cache is not None:
        return _characters_cache
    data = load_yaml(CHARACTERS_FILE)
    _characters_cache = data.get("characters", {}) if data else {}
    return _characters_cache


def load_costume_plan():
    """Load costume_plan_master.yaml."""
    global _costume_cache
    if _costume_cache is not None:
        return _costume_cache
    data = load_yaml(COSTUME_FILE)
    _costume_cache = data.get("costume_plan", {}) if data else {}
    return _costume_cache


def get_char_appearance(char_id, phase="early", world="现实世界"):
    """Get character appearance text + costume description from costume_plan."""
    chars = load_characters()
    costume = load_costume_plan()

    # Base character info
    char_info = chars.get(char_id, {})
    name = char_info.get("full_name", char_id)
    age = char_info.get("age", "")
    appearance = char_info.get("appearance", "")
    personality = char_info.get("personality", "")
    color_sig = char_info.get("color_signature", "")

    # Costume variant for this world/phase
    costume_desc = ""
    costume_colors = []
    costume_props = []
    special_effect = ""
    char_costumes = costume.get(char_id, [])
    for variant in char_costumes:
        if not isinstance(variant, dict):
            continue
        if variant.get("world") == world and variant.get("phase") == phase:
            c = variant.get("costume", {})
            costume_desc = c.get("description", "")
            costume_colors = c.get("colors", [])
            costume_props = c.get("props", [])
            special_effect = variant.get("special_effect", "")
            break
    # Fallback: first dict variant
    if not costume_desc and char_costumes:
        for variant in char_costumes:
            if not isinstance(variant, dict):
                continue
            c = variant.get("costume", {})
            costume_desc = c.get("description", "")
            costume_colors = c.get("colors", [])
            costume_props = c.get("props", [])
            special_effect = variant.get("special_effect", "")
            break

    return {
        "name": name,
        "age": age,
        "appearance": appearance,
        "personality": personality,
        "color_signature": color_sig,
        "costume_desc": costume_desc,
        "costume_colors": costume_colors,
        "props": costume_props,
        "special_effect": special_effect,
    }


# ── 参数编译辅助函数 ──

def expr_vector_to_text(expr_vec):
    """Convert 8-dim expression vector to natural language description."""
    if not expr_vec:
        return "平静"
    labels = ["anger", "fear", "sadness", "surprise", "disgust", "joy", "contempt", "neutral"]
    cn_map = {"anger": "愤怒", "fear": "恐惧", "sadness": "悲伤", "surprise": "惊讶",
              "disgust": "厌恶", "joy": "喜悦", "contempt": "轻蔑", "neutral": "平静"}
    # Sort by value descending, take top 2 above 0.15
    sorted_labels = sorted([(l, expr_vec.get(l, 0)) for l in labels], key=lambda x: -x[1])
    active = [f"{cn_map[l]}({v*100:.0f}%)" for l, v in sorted_labels if v >= 0.15]
    if not active:
        return "中性"
    if len(active) == 1:
        return active[0]
    return "，".join(active[:2])


def lighting_to_text(lighting_rig):
    """Convert lighting_rig to natural language description."""
    if not lighting_rig:
        return ""
    parts = []
    key = lighting_rig.get("key", {})
    if key.get("intensity", 0) > 0:
        direction = key.get("direction", [0, 0, 0])
        temp = key.get("color_temp", 5500)
        intensity = key.get("intensity", 0.5)
        softness = key.get("shadow_softness", 0.5)
        # Direction → Chinese
        x, y, z = direction
        dir_desc = "右侧" if x > 0.2 else "左侧" if x < -0.2 else "正面"
        height_desc = "上方" if y < -0.2 else "下方" if y > 0.2 else "水平"
        temp_desc = "暖" if temp < 4000 else "冷" if temp > 6000 else "中性"
        parts.append(f"主光: {dir_desc}{height_desc} {temp_desc}色{temp}K 强度{intensity:.1f} 阴影柔度{softness:.1f}")
    rim = lighting_rig.get("rim", {})
    if rim.get("enabled") and rim.get("intensity", 0) > 0:
        color = rim.get("color", "white")
        intensity = rim.get("intensity", 0)
        parts.append(f"轮廓光: {color} 强度{intensity:.1f}")
    fill = lighting_rig.get("fill", {})
    if fill.get("intensity", 0) > 0:
        parts.append(f"补光: 强度{fill['intensity']:.1f}")
    ambient = lighting_rig.get("ambient", {})
    if ambient.get("intensity", 0) > 0:
        parts.append(f"环境光: 强度{ambient['intensity']:.1f}")
    return "，".join(parts) if parts else ""


def lens_to_text(camera):
    """Convert camera lens to natural language."""
    lens = camera.get("lens", {})
    fl = lens.get("focal_length_mm", 50)
    ap = lens.get("aperture", 5.6)
    focus = lens.get("focus_distance_m", 2.0)
    # 焦距 → 视角描述
    if fl <= 24:
        view = "广角大景深"
    elif fl <= 50:
        view = "标准视角"
    elif fl <= 85:
        view = "中长焦浅景深"
    else:
        view = "长焦压缩空间"
    return f"{fl}mm焦距 f/{ap}光圈 {view} 对焦{round(focus,1)}m"


def composition_to_text(comp):
    """Convert composition rule to text."""
    rule = comp.get("rule", "centered")
    headroom = comp.get("headroom_ratio", 0.15)
    if headroom is None:
        headroom = 0.15
    rule_map = {
        "centered": "居中构图",
        "rule_of_thirds": "三分法构图",
        "golden_ratio": "黄金分割",
        "diagonal": "对角线构图",
        "framing": "框架构图",
        "centered_narrow": "紧凑居中",
        "rule_of_thirds_lower": "下三分法",
    }
    return f"{rule_map.get(rule, rule)} 头顶留白{headroom:.0%}"


def get_dominant_emotion(expr_vec):
    """Return the dominant emotion label from expression_vector."""
    if not expr_vec:
        return "neutral"
    max_val = 0
    max_label = "neutral"
    for label in EXPR_LABELS:
        val = expr_vec.get(label, 0)
        if val > max_val:
            max_val = val
            max_label = label
    return max_label


def get_frame_count(intensity):
    """Determine number of keyframes based on intensity."""
    if intensity >= 0.75:
        return 4  # start, mid, climax, end
    elif intensity >= 0.5:
        return 3  # start, mid, end
    else:
        return 2  # start, end


def get_frame_timings(intensity, duration_frames):
    """Return list of (frame_number, timestamp_sec, frame_type) for each keyframe."""
    fps = 24
    duration_sec = duration_frames / fps

    if intensity >= 0.75:
        # start, mid (0.3-0.4), climax (0.6-0.8), end
        mid_t = duration_sec * 0.35
        climax_t = duration_sec * 0.7
        return [
            (0, 0.0, "start"),
            (int(mid_t * fps), round(mid_t, 1), "mid"),
            (int(climax_t * fps), round(climax_t, 1), "climax"),
            (duration_frames, duration_sec, "end"),
        ]
    elif intensity >= 0.5:
        # start, mid (0.5), end
        mid_t = duration_sec * 0.5
        return [
            (0, 0.0, "start"),
            (int(mid_t * fps), round(mid_t, 1), "mid"),
            (duration_frames, duration_sec, "end"),
        ]
    else:
        return [
            (0, 0.0, "start"),
            (duration_frames, duration_sec, "end"),
        ]


def build_frame_description(shot, frame_type, dominant_emotion, char_id, movement_type, char_app=None):
    """Build a detail-rich description for each keyframe type — ALL parameters compiled."""
    camera = shot.get("camera", {})
    camera_desc = movement_type
    angle_type = camera.get("angle", {}).get("type", "eye_level")
    pitch = camera.get("angle", {}).get("pitch_deg", 0)
    emotion = shot.get("emotion", "neutral")
    env = shot.get("scene_environment", {})
    atmosphere = env.get("atmosphere_keywords", "")
    vfx_triggers = shot.get("vfx", {}).get("triggers", [])
    lighting = shot.get("lighting_rig", {})

    emotion_cn = EXPR_DESC.get(dominant_emotion, dominant_emotion)

    # ── 角色外观 ──
    char_part = ""
    if char_app:
        name = char_app.get("name", char_id)
        age = char_app.get("age", "")
        appearance = char_app.get("appearance", "")
        costume = char_app.get("costume_desc", "")
        colors = char_app.get("costume_colors", [])
        props = char_app.get("props", [])
        flavor_parts = []
        if age:
            flavor_parts.append(f"{age}岁")
        if appearance:
            # Take first 30 chars of appearance
            short_app = appearance[:40].rstrip("。")
            flavor_parts.append(short_app)
        if costume:
            short_costume = costume[:60].rstrip("。")
            flavor_parts.append(f"穿着{short_costume}")
        elif colors:
            flavor_parts.append(f"穿着{'/'.join(colors)}色调服装")
        if props:
            flavor_parts.append(f"道具:{'、'.join(props[:3])}")
        if flavor_parts:
            char_part = f"【{name}】{'，'.join(flavor_parts)}。"

    # ── 灯光 ──
    light_part = lighting_to_text(lighting)
    if light_part:
        light_part = f" 灯光: {light_part}。"

    # ── 镜头 ──
    lens_part = lens_to_text(camera)
    comp = camera.get("composition", {})
    comp_part = composition_to_text(comp)

    # ── 表达式细节 ──
    expr_vec = None
    char_slots = shot.get("character_slots", [])
    for slot in char_slots:
        if slot.get("char_id") == char_id:
            expr_vec = slot.get("face", {}).get("expression_vector", {})
            break
    expr_text = expr_vector_to_text(expr_vec) if expr_vec else emotion_cn

    # ── VFX 伏笔/特效描述 ──
    vfx_part = ""
    if frame_type == "climax" and vfx_triggers:
        vfx_parts = []
        for vfx in vfx_triggers:
            vt = vfx.get("type", "")
            vd = VFX_DESC.get(vt, f"{vt}特效")
            vfx_parts.append(vd)
        if vfx_parts:
            vfx_part = f" 特效: {'、'.join(vfx_parts)}，画面视觉高潮点！"
    vfx_foreshadow = ""
    if vfx_triggers and frame_type in ("start", "mid"):
        for vfx in vfx_triggers:
            vt = vfx.get("type", "")
            if vt == "magic_circle":
                vfx_foreshadow = " 环境中有极微弱的灵气前兆，雨滴/尘埃闪现不应有的淡金色反光。"

    # ── 角度描述 ──
    angle_desc = {
        "high_angle": "俯拍",
        "low_angle": "仰拍",
        "eye_level": "平视",
        "dutch": "斜角",
        "overhead": "鸟瞰",
    }.get(angle_type, angle_type)
    pitch_str = f"pitch{pitch}°" if pitch != 0 else ""

    # ── 表演描述 ──
    act_desc = f"表情: {expr_text}"
    body = char_slots[0].get("body", {}) if char_slots else {}
    if body.get("pose"):
        act_desc += f"，姿态: {body['pose']}"
    if body.get("gesture"):
        act_desc += f"，手势: {body['gesture']}"
    tension = body.get("tension")
    if tension is not None:
        tens_desc = "紧绷" if tension > 0.7 else "微绷" if tension > 0.4 else "放松"
        act_desc += f"，{tens_desc}"

    if frame_type == "start":
        base = f"【起始帧】{emotion_cn}情绪，{angle_desc}视角{pitch_str}，{CAMERA_MOTION_DESC.get(camera_desc, camera_desc)}。"
        if atmosphere:
            base += f" 环境: {atmosphere}。"
        base += f" {char_part}"
        base += f" {act_desc}。"
        if light_part:
            base += light_part
        base += f" {camera_desc}: {lens_part}，{comp_part}。"
        motion_end = MOTION_START_END.get(camera_desc)
        if motion_end:
            base += f" {motion_end[0]}。"
        if vfx_foreshadow:
            base += vfx_foreshadow
        return base

    elif frame_type == "mid":
        base = f"【过渡帧】{emotion_cn}情绪持续发展，{CAMERA_MOTION_DESC.get(camera_desc, camera_desc)}中段。"
        base += f" {char_part if '【' in char_part else ''}"
        base += f" {char_id}表情从当前的{expr_text}自然过渡，姿态微变。"
        base += f" {MOTION_START_END.get(camera_desc, ['画面过渡状态'])[0]}→过渡。"
        return base

    elif frame_type == "climax":
        base = f"【高潮帧】{emotion_cn}情绪峰值！"
        base += f" {char_part}"
        base += f" {act_desc}，此帧表情到达最强烈的{emotion_cn}。"
        base += vfx_part
        base += f" {camera_desc}中{angle_desc}视角配合情绪高点。"
        climax_pos = MOTION_START_END.get(camera_desc)
        if climax_pos and len(climax_pos) > 1:
            base += f" {climax_pos[1]}。"
        return base

    elif frame_type == "end":
        base = f"【结束帧】{emotion_cn}情绪收束，{CAMERA_MOTION_DESC.get(camera_desc, camera_desc)}终点。"
        base += f" {char_part}"
        base += f" {act_desc}，为本镜头过渡做准备。"
        end_pos = MOTION_START_END.get(camera_desc)
        if end_pos and len(end_pos) > 1:
            base += f" {end_pos[1]}。"
        else:
            base += " 画面最终状态。"
        return base

    return f"【{frame_type}帧】{emotion_cn}情绪帧。"


def build_acting_curves(shot, dominant_emotion, frame_count):
    """Build acting transition curves for characters."""
    curves = {}
    char_slots = shot.get("character_slots", [])
    transition_type = shot.get("emotion", "gradual")

    for slot in char_slots:
        cid = slot.get("char_id", "unknown")
        expr_vec = slot.get("face", {}).get("expression_vector", {})
        dom_expr = get_dominant_emotion(expr_vec)

        # Build expression curve: all frames share emotion for simplicity
        expr_curve = [EXPR_DESC.get(dom_expr, dom_expr)] * frame_count
        # If climax frame, ensure intensity peaks there
        if frame_count >= 4:
            expr_curve[2] = f"强烈{EXPR_DESC.get(dom_expr, dom_expr)}"

        body_curve_parts = []
        movement = shot.get("camera", {}).get("movement", {}).get("type", "static")
        if movement in ("static",):
            body_curve_parts = ["姿势稳定"] * frame_count
        elif movement in ("push_in_slow", "push_in", "dolly_in"):
            body_curve_parts = ["放松→微微前倾→前倾→恢复"]
            if frame_count == 3:
                body_curve_parts = ["放松→前倾→恢复"]
            elif frame_count == 2:
                body_curve_parts = ["初始姿势→结束姿势"]
        else:
            body_curve_parts = ["初始姿势→过渡→调整→结束"] if frame_count >= 4 else (
                ["初始→过渡→结束"] if frame_count == 3 else ["初始→结束"]
            )

        curves[cid] = {
            "expression_curve": expr_curve,
            "body_curve": body_curve_parts[0].split("→") if len(body_curve_parts) == 1 else ["初始姿势", "结束姿势"],
            "transition_type": transition_type,
        }

    return curves


def build_motion_curves(shot, duration_frames):
    """Build camera and VFX motion curves."""
    movement_type = shot.get("camera", {}).get("movement", {}).get("type", "static")
    vfx_triggers = shot.get("vfx", {}).get("triggers", [])

    curves = {}

    # Camera motion curve
    if movement_type in ("push_in_slow", "push_in", "dolly_in"):
        curves["camera_push"] = {
            "samples": [
                {"frame": 0, "value": 0.0},
                {"frame": duration_frames // 2, "value": 0.3},
                {"frame": duration_frames, "value": 0.6},
            ]
        }
    elif movement_type in ("pull_out", "slow_pull_out", "dolly_out"):
        curves["camera_pull"] = {
            "samples": [
                {"frame": 0, "value": 0.0},
                {"frame": duration_frames // 2, "value": 0.4},
                {"frame": duration_frames, "value": 0.8},
            ]
        }
    elif movement_type in ("track_left", "track_right"):
        curves["camera_track"] = {
            "samples": [
                {"frame": 0, "value": 0.0},
                {"frame": duration_frames // 2, "value": 0.5},
                {"frame": duration_frames, "value": 1.0},
            ]
        }

    # VFX intensity curve
    if vfx_triggers:
        climax_frame = int(duration_frames * 0.7)
        vfx_samples = [
            {"frame": 0, "value": 0.0},
            {"frame": int(duration_frames * 0.5), "value": 0.1},
            {"frame": climax_frame - 2, "value": 0.3},
            {"frame": climax_frame, "value": 1.0},
            {"frame": climax_frame + int(duration_frames * 0.1), "value": 0.5},
            {"frame": duration_frames, "value": 0.0},
        ]
        curves["vfx_intensity"] = {"samples": vfx_samples}

    return curves


def _parse_dominance(d):
    """Parse dominance value — supports both float and string range."""
    if isinstance(d, (int, float)):
        return float(d)
    if isinstance(d, str):
        import re
        nums = re.findall(r"[\d.]+", d)
        if nums:
            return sum(float(n) for n in nums) / len(nums)
    return 0.5


def build_flux_prompt(shot, char_apps):
    """Build a full Flux generation config for one shot — ALL parameters compiled."""
    camera = shot.get("camera", {})
    angle = camera.get("angle", {})
    movement = camera.get("movement", {})
    lens = camera.get("lens", {})
    comp = camera.get("composition", {})
    char_slots = shot.get("character_slots", [])
    lighting = shot.get("lighting_rig", {})
    env = shot.get("scene_environment", {})
    vfx = shot.get("vfx", {})
    controlnet = shot.get("controlnet", {})
    lora = shot.get("lora_stack", [])
    gen_params = shot.get("generation_params", {})
    flux_gen = gen_params.get("flux", {})
    style = shot.get("flux_prompt", "")

    # ── 角色描述 ──
    char_descs = []
    for slot in char_slots:
        cid = slot.get("char_id", "")
        app = char_apps.get(cid, {})
        expr_vec = slot.get("face", {}).get("expression_vector", {})
        expr_text = expr_vector_to_text(expr_vec)

        name = app.get("name", cid)
        age = app.get("age", "")
        appearance = app.get("appearance", "")
        costume = app.get("costume_desc", "")
        special = app.get("special_effect", "")

        desc_parts = []
        if age:
            desc_parts.append(f"{age}岁")
        if appearance:
            desc_parts.append(appearance[:60].rstrip("。"))
        if costume:
            desc_parts.append(f"穿着: {costume[:80].rstrip('。')}")
        if special:
            desc_parts.append(f"特效: {special}")
        desc_parts.append(f"表情: {expr_text}")
        d = _parse_dominance(slot.get("dominance", 0.5))
        desc_parts.append(f"场上气场: {'强势' if d > 0.7 else '中性' if d > 0.4 else '弱势'}")
        char_descs.append(f"  [{name}]{'；'.join(desc_parts)}")

    # ── 相机/灯光 ──
    angle_type = angle.get("type", "eye_level")
    pitch = angle.get("pitch_deg", 0)
    move_type = movement.get("type", "static")
    lens_text = lens_to_text(camera)
    comp_text = composition_to_text(comp)
    light_text = lighting_to_text(lighting)

    # ── ControlNet ──
    cn_stack = controlnet.get("stack", [])
    cn_text = " + ".join([f"{c.get('type','')}(scale={c.get('scale',0.5)})" for c in cn_stack]) if cn_stack else "none"

    # ── LoRA ──
    lora_text = " + ".join(lora) if lora else "none"

    # ── VFX ──
    vfx_triggers = vfx.get("triggers", [])
    vfx_text = ""
    if vfx_triggers:
        for vt in vfx_triggers:
            t = vt.get("type", "")
            timing = vt.get("timing", "mid_shot")
            vfx_text = f"VFX: {VFX_DESC.get(t, t)}(触发于{timing})"

    # ── Scene ──
    atmosphere = env.get("atmosphere_keywords", "")

    # ── Build text prompt ──
    parts = []
    # Section 1: characters
    parts.append("角色:")
    parts.extend(char_descs)

    # Section 2: camera
    angle_map = {"high_angle": "俯拍", "low_angle": "仰拍", "eye_level": "平视", "overhead": "鸟瞰", "dutch": "斜角"}
    parts.append(f"相机: {angle_map.get(angle_type, angle_type)} {f'pitch{pitch}°' if pitch else ''}，{move_type}镜头，{lens_text}，{comp_text}")

    # Section 3: lighting
    if light_text:
        parts.append(f"灯光: {light_text}")

    # Section 4: scene
    if atmosphere:
        parts.append(f"环境: {atmosphere}")

    # Section 5: VFX
    if vfx_text:
        parts.append(vfx_text)

    # Section 6: generation config
    cfg = flux_gen.get("cfg_scale", 7.0)
    steps = flux_gen.get("steps", 28)
    parts.append(f"生成: CFG={cfg}, steps={steps}, ControlNet=[{cn_text}], LoRA=[{lora_text}]")

    # Section 7: original story flavor
    if style:
        parts.append(f"剧情: {style[:200].rstrip()}")

    # Section 8: style suffix
    parts.append("3D animation, Chinese donghua style, guoman aesthetic, Unreal Engine 5 quality, cel-shaded with realistic lighting, PBR materials, volumetric lighting, cinematic composition, 8K render")

    body = "\n".join(parts)

    return {
        "prompt": body,
        "negative_prompt": "blurry, low quality, distorted face, extra limbs, bad anatomy, mutation, deformed, disfigured, bad proportions, cloned face, gross, ugly, jpeg artifacts, low resolution, monochrome, oversaturated, 2D flat, anime flat shading, western 3D animation, Pixar style, realistic photo style, text labels, watermark, signature, frame borders, character out of frame",
        "cfg_scale": cfg,
        "steps": steps,
        "seed": -1,
        "controlnet": cn_text,
        "lora": lora_text,
        "ip_adapter_refs": [f"{cid}_face_ref" for s in char_slots if (cid := s.get("char_id", ""))],
    }


def keyframe_plan_for_episode(n):
    """Generate keyframe plan for one episode."""
    compiled_file = os.path.join(COMPILED_DIR, f"ep_{n:02d}_compiled.yaml")
    if not os.path.exists(compiled_file):
        return None, None, f"compiled file not found: {compiled_file}"

    data = load_yaml(compiled_file)
    if not data:
        return None, None, "failed to parse compiled yaml"

    shots = data.get("shots", [])
    if not shots:
        return None, None, "no shots found"

    plan = {
        "episode_id": n,
        "title": data.get("title", f"ep_{n:02d}"),
        "total_shots": len(shots),
        "total_duration_sec": data.get("total_duration_sec", 0),
        "shots": [],
    }

    # ── Load character/costume data for full compilation ──
    char_apps = {}
    for shot in shots:
        for slot in shot.get("character_slots", []):
            cid = slot.get("char_id", "")
            if cid and cid not in char_apps:
                char_apps[cid] = get_char_appearance(cid, phase=get_episode_phase(n), world="现实世界")

    for idx, shot in enumerate(shots):
        shot_id = shot.get("shot_id", f"ep{n:02d}_{idx+1:03d}")
        duration_frames = shot.get("duration_frames", 96)
        duration_sec = shot.get("duration_sec", duration_frames / 24)
        intensity = shot.get("intensity", 0.5)
        emotion = shot.get("emotion", "neutral")

        # Character info
        char_slots = shot.get("character_slots", [])
        main_char_id = char_slots[0].get("char_id", "unknown") if char_slots else "unknown"
        dominant_emotion = get_dominant_emotion(
            char_slots[0].get("face", {}).get("expression_vector", {}) if char_slots else {}
        )

        frame_count = get_frame_count(intensity)
        timings = get_frame_timings(intensity, duration_frames)
        movement_type = shot.get("camera", {}).get("movement", {}).get("type", "static")

        # Build keyframes list — with full parameter compilation
        keyframes = []
        for (fn, ts, ftype) in timings:
            desc = build_frame_description(shot, ftype, dominant_emotion, main_char_id,
                                           movement_type, char_app=char_apps.get(main_char_id))
            kf = {
                "frame_id": f"{shot_id}_{ftype}",
                "frame_number": fn,
                "timestamp_sec": ts,
                "type": ftype,
                "description": desc,
            }
            keyframes.append(kf)

        # Build acting transition
        acting = build_acting_curves(shot, dominant_emotion, frame_count)

        # Build motion curves
        motion = build_motion_curves(shot, duration_frames)

        shot_entry = {
            "shot_id": shot_id,
            "duration_sec": round(duration_sec, 1),
            "duration_frames": duration_frames,
            "emotion": emotion,
            "intensity": intensity,
            "keyframe_count": frame_count,
            "keyframes": keyframes,
            "acting_transition": acting,
            "motion_curve": motion,
        }
        plan["shots"].append(shot_entry)

    # ── Also generate full Flux prompts for each shot ──
    flux_prompts = {}
    for idx, shot in enumerate(shots):
        shot_id = shot.get("shot_id", f"ep{n:02d}_{idx+1:03d}")
        flux_cfg = build_flux_prompt(shot, char_apps)
        flux_prompts[shot_id] = flux_cfg

    return plan, flux_prompts, None


def main():
    os.makedirs(KEYFRAMES_DIR, exist_ok=True)

    args = sys.argv[1:]
    if args:
        episodes = [int(a) for a in args if a.isdigit()]
    else:
        episodes = range(1, 51)

    total_ok = 0
    total_fail = 0
    total_flux = 0

    for n in episodes:
        result = keyframe_plan_for_episode(n)
        if result is None or (isinstance(result, tuple) and len(result) >= 2 and result[-1]):
            if isinstance(result, tuple):
                err = result[-1]
            else:
                err = f"empty result for EP{n:02d}"
            print(f"EP{n:02d}: FAIL — {err}")
            total_fail += 1
            continue

        plan, flux_prompts = result[0], result[1]

        # Write keyframes YAML
        out_file = os.path.join(KEYFRAMES_DIR, f"ep_{n:02d}_keyframes.yaml")
        with open(out_file, "w", encoding="utf-8") as f:
            yaml.dump(plan, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        # Write per-shot Flux prompt files
        prompts_dir = os.path.join(OUTPUT_PROMPTS_DIR, f"ep{n:02d}", "prompts")
        os.makedirs(prompts_dir, exist_ok=True)
        for shot_id, cfg in flux_prompts.items():
            flux_file = os.path.join(prompts_dir, f"{shot_id}_flux.yaml")
            with open(flux_file, "w", encoding="utf-8") as f:
                yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            total_flux += 1

        kf_total = sum(s["keyframe_count"] for s in plan["shots"])
        print(f"EP{n:02d}: {len(plan['shots']):3d} shots, {kf_total:3d} keyframes, {len(flux_prompts)} flux prompts → {os.path.basename(out_file)}")
        total_ok += 1

    print(f"\nDone: {total_ok} OK, {total_fail} FAIL, {total_flux} Flux prompts generated")


if __name__ == "__main__":
    main()

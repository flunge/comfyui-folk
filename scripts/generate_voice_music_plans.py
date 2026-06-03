#!/usr/bin/env python3
"""
Generate voice_plan and music_plan for all 50 episodes from Director Runtime YAML.
Output: storyboard/voice/ep_{N}_voice_plan.yaml
        storyboard/music/ep_{N}_music_plan.yaml

Usage: python pipelines/generate_voice_music_plans.py
"""

import re
import os
import sys
import glob
import yaml

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT = os.path.join(BASE, "projects", "courier_deliveryman")
EPISODES_DIR = os.path.join(PROJECT, "episodes")
VOICE_DIR = os.path.join(PROJECT, "storyboard", "voice")
MUSIC_DIR = os.path.join(PROJECT, "storyboard", "music")
COMPILED_DIR = os.path.join(PROJECT, "storyboard", "compiled")
CHARACTERS_FILE = os.path.join(PROJECT, "assets", "characters.yaml")

os.makedirs(VOICE_DIR, exist_ok=True)
os.makedirs(MUSIC_DIR, exist_ok=True)

# ═══════════════════════════════════════════════
# Character → TTS Voice Configuration
# ═══════════════════════════════════════════════
def build_character_voice_map():
    """Build voice config from characters.yaml."""
    with open(CHARACTERS_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    chars = data.get("characters", {})
    voice_map = {}

    TTS_PRESETS = {
        "young_male_neutral": {"voice": "young_male_neutral", "base_rate": 1.0, "base_pitch": 0, "base_volume": 1.0},
        "young_male_warm": {"voice": "young_male_warm", "base_rate": 1.05, "base_pitch": +1, "base_volume": 1.0},
        "young_male_cold": {"voice": "young_male_cold", "base_rate": 0.9, "base_pitch": -2, "base_volume": 1.0},
        "elder_male_gentle": {"voice": "elder_male_gentle", "base_rate": 0.85, "base_pitch": -3, "base_volume": 0.9},
        "middle_male_coarse": {"voice": "middle_male_coarse", "base_rate": 1.1, "base_pitch": -1, "base_volume": 1.1},
        "young_female_cool": {"voice": "young_female_cool", "base_rate": 0.95, "base_pitch": 0, "base_volume": 1.0},
        "young_female_warm": {"voice": "young_female_warm", "base_rate": 0.9, "base_pitch": +1, "base_volume": 0.95},
        "young_female_gentle": {"voice": "young_female_gentle", "base_rate": 0.85, "base_pitch": -1, "base_volume": 0.9},
        "middle_female_sharp": {"voice": "middle_female_sharp", "base_rate": 1.05, "base_pitch": +2, "base_volume": 1.1},
    }

    # Manual character → TTS mapping based on role analysis
    MANUAL_MAP = {
        "chen_mo": "young_male_neutral",
        "lao_zhou": "elder_male_gentle",
        "lin_ruo_xue": "young_female_cool",
        "su_mu_yu": "young_female_gentle",
        "liu_qiang": "middle_male_coarse",
        "sun_da_li": "young_male_warm",
        "liu_ru_yan": "middle_female_sharp",
        "bai_mian_shu_sheng": "young_male_cold",
        "zhao_dong_lai": "middle_male_coarse",
        "ming_he_dao_ren": "young_male_cold",
        "zhao_chang_lao": "elder_male_gentle",
    }

    # Ephemeral characters that appear in episodes but not in characters.yaml
    EPHEMERAL_CHARS = {
        "liu_ru_yan": {"full_name": "柳如烟", "role": "female_supporting", "personality": "冷面花店主，警惕性极高"},
        "bai_mian_shu_sheng": {"full_name": "白面书生", "role": "antagonist", "personality": "彬彬有礼的威胁"},
        "zhao_dong_lai": {"full_name": "赵东来", "role": "villain", "personality": "嚣张跋扈"},
        "ming_he_dao_ren": {"full_name": "冥河道人", "role": "main_antagonist", "personality": "深沉阴险"},
        "qing_luan": {"full_name": "青鸾", "role": "female_supporting", "personality": "冷静果断"},
    }
    chars.update(EPHEMERAL_CHARS)

    FEMALE_IDS = {"lin_ruo_xue", "su_mu_yu", "liu_ru_yan", "qing_luan"}
    FEMALE_ROLES = {"female_lead", "female_lead_2", "female_supporting"}

    for cid, info in chars.items():
        preset_name = MANUAL_MAP.get(cid, "young_male_neutral")
        preset = dict(TTS_PRESETS.get(preset_name, TTS_PRESETS["young_male_neutral"]))
        preset["name"] = info.get("full_name", cid)
        preset["catchphrase"] = info.get("catchphrase", "")
        preset["speaking_style"] = info.get("speaking_style", "")
        if "personality" in info:
            preset["personality"] = info["personality"]
        # Determine gender
        gender = "female" if (cid in FEMALE_IDS or info.get("role") in FEMALE_ROLES) else "male"
        preset["gender"] = gender
        voice_map[cid] = preset

    return voice_map


# ═══════════════════════════════════════════════
# Emotion → TTS Parameters
# ═══════════════════════════════════════════════
EMOTION_TTS_MAP = {
    "calm": {"rate_mod": 0.0, "pitch_mod": 0, "volume_mod": 0.0},
    "curiosity": {"rate_mod": 0.0, "pitch_mod": +1, "volume_mod": 0.0},
    "tension": {"rate_mod": +0.1, "pitch_mod": +1, "volume_mod": 0.0},
    "vigilance": {"rate_mod": 0.0, "pitch_mod": 0, "volume_mod": 0.0},
    "fear": {"rate_mod": +0.3, "pitch_mod": +4, "volume_mod": -0.3},
    "terror": {"rate_mod": +0.3, "pitch_mod": +4, "volume_mod": -0.3},
    "shock": {"rate_mod": +0.2, "pitch_mod": +3, "volume_mod": -0.2},
    "shock_of_recognition": {"rate_mod": +0.1, "pitch_mod": +2, "volume_mod": -0.1},
    "sadness": {"rate_mod": -0.2, "pitch_mod": -1, "volume_mod": -0.4},
    "sorrow": {"rate_mod": -0.2, "pitch_mod": -1, "volume_mod": -0.4},
    "cold_acceptance": {"rate_mod": -0.15, "pitch_mod": -3, "volume_mod": 0.0},
    "cold_power": {"rate_mod": -0.15, "pitch_mod": -3, "volume_mod": 0.0},
    "oppression": {"rate_mod": -0.1, "pitch_mod": -2, "volume_mod": +0.1},
    "humiliation": {"rate_mod": +0.1, "pitch_mod": +2, "volume_mod": -0.1},
    "anger": {"rate_mod": +0.1, "pitch_mod": -2, "volume_mod": +0.2},
    "controlled_confrontation": {"rate_mod": 0.0, "pitch_mod": -1, "volume_mod": 0.0},
    "satisfaction": {"rate_mod": 0.0, "pitch_mod": +1, "volume_mod": 0.0},
    "anticipation": {"rate_mod": +0.05, "pitch_mod": +1, "volume_mod": 0.0},
    "strategic_horror": {"rate_mod": +0.15, "pitch_mod": +3, "volume_mod": -0.2},
    "dominance": {"rate_mod": -0.15, "pitch_mod": -3, "volume_mod": +0.1},
    "epic_power": {"rate_mod": -0.1, "pitch_mod": -2, "volume_mod": +0.15},
    "mystery_reveal": {"rate_mod": -0.1, "pitch_mod": -1, "volume_mod": 0.0},
    "exhaustion_curiosity": {"rate_mod": -0.1, "pitch_mod": 0, "volume_mod": -0.1},
    "warmth": {"rate_mod": -0.05, "pitch_mod": +1, "volume_mod": 0.0},
    "relief": {"rate_mod": -0.1, "pitch_mod": 0, "volume_mod": +0.05},
    "resolve": {"rate_mod": 0.0, "pitch_mod": -1, "volume_mod": +0.1},
    "desperation": {"rate_mod": +0.2, "pitch_mod": +2, "volume_mod": -0.1},
    "grief": {"rate_mod": -0.3, "pitch_mod": -2, "volume_mod": -0.4},
    "unease": {"rate_mod": +0.05, "pitch_mod": +1, "volume_mod": -0.05},
    "curiosity_hook": {"rate_mod": 0.0, "pitch_mod": +1, "volume_mod": 0.0},
    "hidden_anticipation": {"rate_mod": 0.0, "pitch_mod": +1, "volume_mod": -0.05},
    "impatient": {"rate_mod": +0.1, "pitch_mod": +1, "volume_mod": +0.1},
    "polite_menace_controlled_amusement": {"rate_mod": -0.1, "pitch_mod": -2, "volume_mod": 0.0},
    "quiet_intense_analysis_buried_dread": {"rate_mod": -0.15, "pitch_mod": -2, "volume_mod": -0.1},
    "worry_masked_as_logistical_questioning": {"rate_mod": 0.0, "pitch_mod": +1, "volume_mod": -0.05},
    "vigilant_sentinel_cold_professionalism": {"rate_mod": 0.0, "pitch_mod": -1, "volume_mod": 0.0},
    "professional_lookout_masked_as_artist": {"rate_mod": -0.05, "pitch_mod": 0, "volume_mod": -0.05},
    "post_battle_calm_to_cold_confrontation_to_strategic_unease": {"rate_mod": -0.1, "pitch_mod": -1, "volume_mod": 0.0},
    "hidden_amusement": {"rate_mod": 0.0, "pitch_mod": +1, "volume_mod": 0.0},
    "numb_acceptance": {"rate_mod": -0.2, "pitch_mod": -2, "volume_mod": -0.2},
    "sacrificial_resolve": {"rate_mod": -0.1, "pitch_mod": -1, "volume_mod": +0.05},
    "loss": {"rate_mod": -0.2, "pitch_mod": -2, "volume_mod": -0.3},
    "post_battle_calm": {"rate_mod": -0.1, "pitch_mod": 0, "volume_mod": 0.0},
    "silent_grief": {"rate_mod": -0.3, "pitch_mod": -2, "volume_mod": -0.4},
    "quiet_determination": {"rate_mod": 0.0, "pitch_mod": -1, "volume_mod": +0.05},
    "longing": {"rate_mod": -0.1, "pitch_mod": +1, "volume_mod": -0.1},
    "protectiveness": {"rate_mod": 0.0, "pitch_mod": -2, "volume_mod": +0.1},
    "attraction": {"rate_mod": -0.05, "pitch_mod": +1, "volume_mod": -0.05},
    "hopefulness": {"rate_mod": 0.0, "pitch_mod": +1, "volume_mod": 0.0},
    "resolution": {"rate_mod": -0.05, "pitch_mod": 0, "volume_mod": +0.05},
}

# Default fallback
DEFAULT_TTS = {"rate_mod": 0.0, "pitch_mod": 0, "volume_mod": 0.0}


def get_tts_params(emotion_str, voice_preset):
    """Get TTS parameters by combining voice preset with emotion modulation."""
    emotion_key = emotion_str.lower().strip() if emotion_str else "calm"
    mod = EMOTION_TTS_MAP.get(emotion_key, DEFAULT_TTS)

    rate = voice_preset["base_rate"] + mod["rate_mod"]
    pitch = voice_preset["base_pitch"] + mod["pitch_mod"]
    volume = voice_preset["base_volume"] + mod["volume_mod"]

    # Clamp
    rate = max(0.5, min(2.0, rate))
    pitch = max(-10, min(10, pitch))
    volume = max(0.1, min(1.5, volume))

    return {
        "rate": round(rate, 2),
        "pitch_shift": pitch,
        "volume": round(volume, 2),
    }


# ═══════════════════════════════════════════════
# Emotion → Music Mapping
# ═══════════════════════════════════════════════
EMOTION_MUSIC_MAP = {
    "curiosity": {"music_type": "mysterious_ambient", "bpm": 70, "key": "minor", "instruments": "pad, bell, pizzicato"},
    "tension": {"music_type": "tension_building", "bpm": 90, "key": "minor", "instruments": "strings_tremolo, low_brass, percussion_roll"},
    "vigilance": {"music_type": "tension_building", "bpm": 85, "key": "minor", "instruments": "low_strings, timpani_roll"},
    "unease": {"music_type": "dark_oppressive", "bpm": 65, "key": "minor", "instruments": "low_strings, drone, metallic"},
    "fear": {"music_type": "horror_tension", "bpm": 110, "key": "diminished", "instruments": "high_strings, sudden_impacts"},
    "terror": {"music_type": "horror_tension", "bpm": 120, "key": "diminished", "instruments": "high_strings, orchestral_hit"},
    "shock": {"music_type": "sudden_silence_or_stinger", "bpm": 60, "key": "atonal", "instruments": "orchestral_hit, silence"},
    "shock_of_recognition": {"music_type": "mystery_tension", "bpm": 80, "key": "minor", "instruments": "low_brass, piano, strings"},
    "sadness": {"music_type": "melancholic_piano", "bpm": 60, "key": "minor", "instruments": "solo_piano, cello"},
    "sorrow": {"music_type": "melancholic_piano", "bpm": 55, "key": "minor", "instruments": "solo_piano, cello, strings"},
    "cold_acceptance": {"music_type": "dark_oppressive", "bpm": 65, "key": "minor", "instruments": "low_strings, cello_solo"},
    "cold_power": {"music_type": "epic_power", "bpm": 100, "key": "major", "instruments": "full_orchestra, brass, choir"},
    "oppression": {"music_type": "dark_oppressive", "bpm": 65, "key": "minor", "instruments": "low_strings, taiko, drone"},
    "humiliation": {"music_type": "uncomfortable_drone", "bpm": 55, "key": "atonal", "instruments": "dissonant_strings, metallic"},
    "anger": {"music_type": "tension_building", "bpm": 100, "key": "minor", "instruments": "brass, percussion, strings"},
    "controlled_confrontation": {"music_type": "tension_building", "bpm": 85, "key": "minor", "instruments": "strings_tremolo, low_brass"},
    "satisfaction": {"music_type": "warm_resolution", "bpm": 70, "key": "major", "instruments": "acoustic_guitar, soft_piano"},
    "anticipation": {"music_type": "rising_tension", "bpm": 100, "key": "minor-major", "instruments": "strings_crescendo, snare_roll"},
    "strategic_horror": {"music_type": "horror_tension", "bpm": 90, "key": "diminished", "instruments": "low_strings, metallic, choir_whisper"},
    "dominance": {"music_type": "epic_power", "bpm": 110, "key": "major", "instruments": "full_orchestra, choir, brass"},
    "epic_power": {"music_type": "epic_power", "bpm": 115, "key": "major", "instruments": "full_orchestra, choir, brass"},
    "mystery_reveal": {"music_type": "mystery_tension", "bpm": 75, "key": "minor", "instruments": "piano, strings, bell"},
    "exhaustion_curiosity": {"music_type": "mysterious_ambient", "bpm": 65, "key": "minor", "instruments": "pad, piano, cello"},
    "warmth": {"music_type": "warm_resolution", "bpm": 70, "key": "major", "instruments": "acoustic_guitar, soft_piano, strings"},
    "relief": {"music_type": "warm_resolution", "bpm": 72, "key": "major", "instruments": "piano, strings, harp"},
    "resolve": {"music_type": "epic_power", "bpm": 95, "key": "major", "instruments": "strings, brass, percussion"},
    "desperation": {"music_type": "tension_building", "bpm": 105, "key": "minor", "instruments": "strings_tremolo, percussion_roll"},
    "grief": {"music_type": "melancholic_piano", "bpm": 50, "key": "minor", "instruments": "solo_piano, cello, violin"},
    "curiosity_hook": {"music_type": "cliffhanger_stinger", "bpm": 60, "key": "atonal", "instruments": "bass_drop, reversed_reverb"},
    "hidden_anticipation": {"music_type": "mysterious_ambient", "bpm": 70, "key": "minor", "instruments": "pad, bell, strings"},
    "impatient": {"music_type": "uncomfortable_drone", "bpm": 70, "key": "atonal", "instruments": "dissonant_strings, metallic"},
    "polite_menace_controlled_amusement": {"music_type": "dark_oppressive", "bpm": 70, "key": "minor", "instruments": "low_strings, piano, bell"},
    "quiet_intense_analysis_buried_dread": {"music_type": "mystery_tension", "bpm": 65, "key": "minor", "instruments": "piano, low_strings, drone"},
    "worry_masked_as_logistical_questioning": {"music_type": "tension_building", "bpm": 80, "key": "minor", "instruments": "strings_tremolo, piano"},
    "vigilant_sentinel_cold_professionalism": {"music_type": "tension_building", "bpm": 85, "key": "minor", "instruments": "low_strings, timpani"},
    "professional_lookout_masked_as_artist": {"music_type": "mysterious_ambient", "bpm": 70, "key": "minor", "instruments": "pad, piano, strings"},
    "post_battle_calm_to_cold_confrontation_to_strategic_unease": {"music_type": "tension_building", "bpm": 85, "key": "minor", "instruments": "strings, low_brass"},
    "hidden_amusement": {"music_type": "uncomfortable_drone", "bpm": 60, "key": "atonal", "instruments": "dissonant_strings, pizzicato"},
    "numb_acceptance": {"music_type": "melancholic_piano", "bpm": 55, "key": "minor", "instruments": "solo_piano, cello"},
    "sacrificial_resolve": {"music_type": "sacrifice_sad_epic", "bpm": 75, "key": "minor", "instruments": "choir, piano, strings"},
    "loss": {"music_type": "melancholic_piano", "bpm": 50, "key": "minor", "instruments": "solo_piano, cello, strings"},
    "post_battle_calm": {"music_type": "warm_resolution", "bpm": 65, "key": "major", "instruments": "piano, strings"},
    "silent_grief": {"music_type": "melancholic_piano", "bpm": 45, "key": "minor", "instruments": "solo_piano, cello"},
    "quiet_determination": {"music_type": "rising_tension", "bpm": 90, "key": "minor", "instruments": "strings, percussion"},
    "longing": {"music_type": "romantic_piano_warm", "bpm": 65, "key": "major", "instruments": "piano, strings_pizzicato"},
    "protectiveness": {"music_type": "epic_power", "bpm": 95, "key": "major", "instruments": "strings, brass, percussion"},
    "attraction": {"music_type": "romantic_piano_warm", "bpm": 70, "key": "major", "instruments": "piano, strings_pizzicato, guitar"},
    "hopefulness": {"music_type": "warm_resolution", "bpm": 75, "key": "major", "instruments": "piano, strings, harp"},
    "resolution": {"music_type": "warm_resolution", "bpm": 72, "key": "major", "instruments": "piano, strings, acoustic_guitar"},
}

CLIMAX_SKILL_MUSIC = {
    "dominance_reveal": {"music_type": "dominance_reveal_epic", "bpm": 110, "instruments": "male_choir, brass, timpani"},
    "battle_climax": {"music_type": "battle_climax_intense", "bpm": 130, "instruments": "fast_strings, electronic_drums, choir"},
    "emotional_breakdown": {"music_type": "emotional_piano_sad", "bpm": 60, "instruments": "solo_piano, cello"},
    "romantic_tension": {"music_type": "romantic_piano_warm", "bpm": 75, "instruments": "warm_piano, strings_pizzicato"},
    "mystery_reveal": {"music_type": "mystery_tension", "bpm": 80, "instruments": "low_drone, high_piano, strings"},
    "identity_reveal": {"music_type": "reveal_epic", "bpm": 100, "instruments": "strings_crescendo, brass_climax"},
    "sacrifice_moment": {"music_type": "sacrifice_sad_epic", "bpm": 70, "instruments": "choir, piano, strings"},
    "series_finale": {"music_type": "finale_warm_piano", "bpm": 72, "instruments": "piano, strings, full_orchestra_reprise"},
    "threat_escalation": {"music_type": "mystery_tension", "bpm": 85, "instruments": "low_strings, brass, percussion"},
}

DEFAULT_MUSIC = {"music_type": "mysterious_ambient", "bpm": 70, "key": "minor", "instruments": "pad, strings"}


def get_music_params(emotion_str):
    """Get music parameters for an emotion."""
    key = emotion_str.lower().strip() if emotion_str else "curiosity"
    return EMOTION_MUSIC_MAP.get(key, DEFAULT_MUSIC)


# ═══════════════════════════════════════════════
# SFX Keyword Detection
# ═══════════════════════════════════════════════
SFX_PATTERNS = [
    (r'玻璃[杯碎炸]|炸裂|碎裂|破碎', 'glass_shatter'),
    (r'开?门|关?门|敲?门|推?门', 'door'),
    (r'脚步|走路|脚步声|走来', 'footsteps'),
    (r'雨|暴雨|下雨|雨滴|雨水', 'rain_ambient'),
    (r'雷|闪电', 'thunder'),
    (r'风|狂风|风声', 'wind_howl'),
    (r'爆炸|炸开|爆裂', 'explosion'),
    (r'灵力|灵气|能量|灵力外放|暗金|灵力波动', 'energy_charge'),
    (r'灵力爆[发炸]|灵压|灵力冲击', 'energy_burst'),
    (r'手机|电话|来电|铃声', 'phone_vibrate'),
    (r'引擎|发动|汽车引擎|轰鸣', 'car_engine'),
    (r'烟|抽烟|吸烟|烟头', 'subtle_item_drop'),
    (r'心跳|心脏|心在跳', 'heartbeat'),
    (r'屏幕[裂碎]|黑屏|裂开', 'electric_spark'),
    (r'吼|咆哮|嘶吼|怒吼', 'roar'),
    (r'剑|刀|拔[剑刀]|出鞘', 'sword_draw'),
    (r'碰撞|撞击|重击|砸', 'heavy_impact'),
    (r'水滴|滴水|水声|流水', 'water_drip'),
    (r'警报|警笛|警车', 'siren'),
    (r'玻璃[窗]|车窗|挡风玻璃', 'glass_shatter'),
    (r'玉简|发光|光芒|光柱|光晕', 'energy_charge'),
]


def detect_sfx(description):
    """Detect SFX triggers from description text."""
    sfx_list = []
    for pattern, sfx_type in SFX_PATTERNS:
        matches = list(re.finditer(pattern, description))
        for m in matches:
            sfx_list.append({
                "type": sfx_type,
                "trigger_word": m.group(),
                "position": m.start(),
            })
    # Deduplicate nearby matches of same type
    deduped = []
    for sfx in sfx_list:
        if not deduped or deduped[-1]["type"] != sfx["type"] or \
           abs(deduped[-1]["position"] - sfx["position"]) > 30:
            deduped.append(sfx)
    return deduped


# ═══════════════════════════════════════════════
# Dialogue Extraction
# ═══════════════════════════════════════════════
def extract_dialogue(description, focus_character, char_voice_map):
    """Extract quoted dialogue from description text.
    Returns list of (text, speaker, emotion_context).
    """
    # Match Chinese single quotes: '...' (U+2018/U+2019) or standard '...'
    patterns = [
        r'‘([^’]+)’',  # Chinese single quotes
        r'「([^」]+)」',                # Corner brackets
        r'"([^"]+)"',                  # Double quotes
        r"'([^']+)'",                  # ASCII single quotes (fallback)
    ]

    lines = []
    for pat in patterns:
        matches = re.findall(pat, description)
        lines.extend(matches)

    if not lines:
        return []

    # Detect speaker changes within shot
    # Split the description into segments around each quote
    # Use all_patterns to capture with position info
    all_quotes = []
    for pat in patterns:
        for m in re.finditer(pat, description):
            all_quotes.append((m.start(), m.group(), m.group(1)))

    if not all_quotes:
        return []

    all_quotes.sort(key=lambda x: x[0])

    result = []
    current_speaker = focus_character

    for pos, full_match, text in all_quotes:
        # Look ahead in description after this quote for speaker attribution
        text_after = description[pos + len(full_match):pos + len(full_match) + 60]

        # Check if next text says "XX说" or "XX道" or "XX对YY说"
        speaker_match = re.search(r'([一-鿿]{2,4})[说喊道叫骂问答]', text_after)
        if speaker_match:
            name = speaker_match.group(1)
            # Map Chinese name to character ID
            for cid, info in char_voice_map.items():
                if info.get("name", "") == name or cid == name:
                    current_speaker = cid
                    break

        # Check for "对XX说" pattern for indirect speech
        # Or character ID mentions before the quote
        text_before = description[max(0, pos - 40):pos]
        before_match = re.search(r'([一-鿿]{2,4})[说喊道]', text_before)
        if before_match:
            name = before_match.group(1)
            for cid, info in char_voice_map.items():
                if info.get("name", "") == name or cid == name:
                    current_speaker = cid
                    break

        result.append((text, current_speaker))

    return result


def get_shot_emotion(shot, episode_data):
    """Get the dominant emotion from a shot's context."""
    if shot.get("emotion"):
        return shot["emotion"]
    return "calm"


# ═══════════════════════════════════════════════
# Episode Loading
# ═══════════════════════════════════════════════
def load_episode(n):
    """Load an episode YAML file."""
    path = os.path.join(EPISODES_DIR, f"ep_{n:02d}.yaml")
    if not os.path.exists(path):
        print(f"  [SKIP] ep_{n:02d}.yaml not found")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_compiled_timing(n):
    """Load authoritative shot timing from compiled.yaml."""
    path = os.path.join(COMPILED_DIR, f"ep_{n:02d}_compiled.yaml")
    if not os.path.exists(path):
        return {}, 0
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError:
        return {}, 0
    if not data:
        return {}, 0
    shots = data.get("shots", data.get("shot_runtime", []))
    timing = {}
    current = 0.0
    for shot in shots:
        sid = shot.get("shot_id", "")
        dur = shot.get("duration_sec", 4.0)
        if not isinstance(dur, (int, float)):
            dur = 4.0
        timing[sid] = {"start_sec": round(current, 1), "duration_sec": dur}
        current += dur
    return timing, round(current, 1)


def calc_shot_start_times(shot_graph):
    """Calculate cumulative start time for each shot."""
    times = []
    current = 0.0
    for shot in shot_graph:
        times.append(current)
        current += shot.get("duration_sec", 4.0)
    return times


# ═══════════════════════════════════════════════
# Voice Plan Generator
# ═══════════════════════════════════════════════
def generate_voice_plan(data, n, char_voice_map, compiled_timing=None):
    """Generate voice plan for one episode.
    compiled_timing: dict of shot_id -> {start_sec, duration_sec} from compiled.yaml
    """
    episode = data.get("episode", {})
    director = data.get("director", {})
    shot_graph = director.get("shot_graph", [])

    if not shot_graph:
        print(f"  [SKIP] ep_{n:02d}: no shot_graph")
        return None

    start_times = calc_shot_start_times(shot_graph)
    voice_tracks = []
    line_counter = 0

    for i, shot in enumerate(shot_graph):
        shot_id = shot.get("shot_id", f"ep{n:02d}_s{i+1:03d}")
        description = shot.get("description", "")
        focus_char = shot.get("focus_character", "chen_mo")

        dialogues = extract_dialogue(description, focus_char, char_voice_map)

        if not dialogues:
            continue

        shot_start = start_times[i]
        shot_dur = shot.get("duration_sec", 4.0)

        # Use compiled timing as authoritative source when available
        if compiled_timing and shot_id in compiled_timing:
            ct = compiled_timing[shot_id]
            shot_start = ct["start_sec"]
            shot_dur = ct["duration_sec"]

        emotion = get_shot_emotion(shot, data)

        # Distribute dialogue lines within the shot
        num_lines = len(dialogues)
        line_duration = shot_dur / max(num_lines, 1)

        for li, (text, speaker) in enumerate(dialogues):
            # Clean text - remove speaker attribution artifacts
            text = text.strip()
            if not text or len(text) < 1:
                continue

            # Skip if text is just a character name
            if text in [v.get("name", "") for v in char_voice_map.values()]:
                continue

            # Skip non-character speakers (none, all, both, etc.)
            if speaker not in char_voice_map:
                continue

            voice_preset = char_voice_map.get(speaker, char_voice_map.get("chen_mo", {}))
            tts_params = get_tts_params(emotion, voice_preset)

            line_counter += 1
            line_id = f"ep{n:02d}_{line_counter:03d}"

            entry = {
                "line_id": line_id,
                "char_id": speaker,
                "text": text,
                "start_sec": round(shot_start + li * line_duration, 1),
                "duration_sec": round(line_duration - 0.3, 1),
                "tts_config": {
                    "voice": voice_preset.get("voice", "young_male_neutral"),
                    "rate": tts_params["rate"],
                    "pitch_shift": tts_params["pitch_shift"],
                    "volume": tts_params["volume"],
                },
                "emotion_context": emotion,
            }

            # Add emphasis_words for catchphrases
            catchphrase = voice_preset.get("catchphrase", "")
            if catchphrase:
                # Check if dialogue contains catchphrase keywords
                cp_clean = re.sub(r'[「」""《》【】]', '', catchphrase)
                words = [w.strip() for w in re.split(r'[，。！？、；：]', cp_clean) if w.strip()]
                emph = [w for w in words if w and len(w) >= 2 and w in text]
                if emph:
                    entry["tts_config"]["emphasis"] = emph

            voice_tracks.append(entry)

    voice_plan = {
        "episode_id": n,
        "total_lines": line_counter,
        "voice_tracks": voice_tracks,
    }

    return voice_plan


# ═══════════════════════════════════════════════
# Music Plan Generator
# ═══════════════════════════════════════════════
def generate_music_plan(data, n, compiled_timing=None, compiled_total=0):
    """Generate music plan for one episode.
    compiled_timing: dict of shot_id -> {start_sec, duration_sec} from compiled.yaml
    compiled_total: total duration from compiled.yaml
    """
    episode = data.get("episode", {})
    story = data.get("story", {})
    director = data.get("director", {})
    shot_graph = director.get("shot_graph", [])
    emotion_timeline = director.get("emotion_timeline", [])

    if not shot_graph and not emotion_timeline:
        print(f"  [SKIP] ep_{n:02d}: no shot_graph or emotion_timeline")
        return None

    start_times = calc_shot_start_times(shot_graph)
    total_duration = compiled_total or (start_times[-1] + shot_graph[-1].get("duration_sec", 4.0)) if shot_graph else 0

    # ── Music Timeline from emotion_timeline ──
    music_timeline = []
    climax_type = story.get("climax_type", "")
    skill_preset = CLIMAX_SKILL_MUSIC.get(climax_type, None)

    if emotion_timeline:
        for ti, segment in enumerate(emotion_timeline):
            emotion = segment.get("emotion", "curiosity")
            intensity = segment.get("intensity", 0.5)
            ts = segment.get("timestamp_sec", ti * 10)
            transition = segment.get("transition", "gradual")

            music_params = get_music_params(emotion)

            # Determine next timestamp for segment end
            if ti + 1 < len(emotion_timeline):
                next_ts = emotion_timeline[ti + 1].get("timestamp_sec", ts + 10)
            else:
                next_ts = total_duration

            # Map transition type
            trans_map = {
                "instant": "cut",
                "gradual": "crossfade_2s",
                "explosive": "sudden_cut",
                "fade": "crossfade_3s",
            }
            transition_to = trans_map.get(transition, "crossfade_2s")

            # Build intensity curve
            intensity_curve = [
                {"sec": ts, "intensity": round(max(0.1, intensity - 0.1), 2)},
                {"sec": round((ts + next_ts) / 2, 1), "intensity": round(intensity, 2)},
                {"sec": next_ts, "intensity": round(max(0.1, intensity - 0.15), 2)},
            ]

            segment_entry = {
                "segment_id": f"ep{n:02d}_music_{ti+1:03d}",
                "start_sec": ts,
                "end_sec": next_ts,
                "emotion": emotion,
                "music_type": music_params["music_type"],
                "bpm": music_params["bpm"],
                "intensity_curve": intensity_curve,
                "transition_to_next": transition_to,
                "description": f"{music_params['instruments']} — {emotion} segment, intensity {intensity}",
            }

            # Apply skill preset to climax segment
            if skill_preset and ti > 0 and intensity >= 0.8:
                # Check if this is the climax segment
                prev_intensity = emotion_timeline[ti - 1].get("intensity", 0)
                if intensity > prev_intensity + 0.05:
                    segment_entry["skill_preset"] = skill_preset["music_type"]
                    segment_entry["music_type"] = skill_preset["music_type"]
                    segment_entry["bpm"] = skill_preset["bpm"]
                    segment_entry["instruments"] = skill_preset["instruments"]
                    segment_entry["description"] = f"Skill: {climax_type} — {skill_preset['music_type']}. {skill_preset['instruments']}"

            music_timeline.append(segment_entry)

    # ── SFX Timeline from shot_graph ──
    sfx_timeline = []
    sfx_counter = 0

    for i, shot in enumerate(shot_graph):
        description = shot.get("description", "")
        shot_start = start_times[i] if i < len(start_times) else 0
        shot_id = shot.get("shot_id", f"ep{n:02d}_s{i+1:03d}")
        shot_dur = shot.get("duration_sec", 4.0)

        # Use compiled timing as authoritative source
        if compiled_timing and shot_id in compiled_timing:
            ct = compiled_timing[shot_id]
            shot_start = ct["start_sec"]
            shot_dur = ct["duration_sec"]

        sfx_hits = detect_sfx(description)
        for sfx in sfx_hits:
            sfx_counter += 1
            # Estimate timing within shot based on position in text
            text_len = len(description)
            rel_pos = sfx["position"] / max(text_len, 1)
            abs_time = shot_start + rel_pos * shot_dur

            sfx_timeline.append({
                "sfx_id": f"ep{n:02d}_sfx_{sfx_counter:03d}",
                "shot_id": shot_id,
                "start_sec": round(abs_time, 1),
                "type": sfx["type"],
                "trigger_word": sfx["trigger_word"],
            })

    # Deduplicate SFX within same shot within 0.5s
    deduped_sfx = []
    for sfx in sfx_timeline:
        if not deduped_sfx:
            deduped_sfx.append(sfx)
        else:
            last = deduped_sfx[-1]
            if sfx["shot_id"] == last["shot_id"] and \
               abs(sfx["start_sec"] - last["start_sec"]) < 0.5 and \
               sfx["type"] == last["type"]:
                continue
            deduped_sfx.append(sfx)

    music_plan = {
        "episode_id": n,
        "title": story.get("title", f"Episode {n}"),
        "total_duration_sec": round(total_duration, 1),
        "climax_type": climax_type,
        "music_timeline": music_timeline,
        "sfx_timeline": deduped_sfx,
        "music_generation_config": {
            "engine": "Suno AI / Udio",
            "instrumental": True,
            "loopable": False,
            "output_format": "wav, 48kHz, 24bit",
            "reference_genre": "cinematic_guoman3d_hybrid",
        },
    }

    return music_plan


# ═══════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════
def main():
    sys.stdout.reconfigure(encoding='utf-8')  # force UTF-8 for emoji
    print("[GEN] Generating voice_plan and music_plan for all 50 episodes...")
    print()

    char_voice_map = build_character_voice_map()
    print(f"[CHARS] Loaded {len(char_voice_map)} character voice configs")

    voice_total_lines = 0
    music_total_segments = 0
    sfx_total = 0
    success_count = 0

    for n in range(1, 51):
        data = load_episode(n)
        if data is None:
            continue

        sys.stdout.write(f"\n[EP{n:02d}] ")
        sys.stdout.flush()

        # Load compiled timing as authoritative source
        comp_timing, comp_total = load_compiled_timing(n)

        # Voice plan
        voice_plan = generate_voice_plan(data, n, char_voice_map, comp_timing)
        if voice_plan:
            vp_path = os.path.join(VOICE_DIR, f"ep_{n:02d}_voice_plan.yaml")
            with open(vp_path, "w", encoding="utf-8") as f:
                yaml.dump(voice_plan, f, allow_unicode=True, default_flow_style=False, sort_keys=False, width=1200)
            voice_total_lines += voice_plan["total_lines"]
            sys.stdout.write(f"V{voice_plan['total_lines']}lines ")
            sys.stdout.flush()

        # Music plan
        music_plan = generate_music_plan(data, n, comp_timing, comp_total)
        if music_plan:
            mp_path = os.path.join(MUSIC_DIR, f"ep_{n:02d}_music_plan.yaml")
            with open(mp_path, "w", encoding="utf-8") as f:
                yaml.dump(music_plan, f, allow_unicode=True, default_flow_style=False, sort_keys=False, width=1200)
            music_total_segments += len(music_plan["music_timeline"])
            sfx_total += len(music_plan["sfx_timeline"])
            sys.stdout.write(f"M{len(music_plan['music_timeline'])}segs+S{len(music_plan['sfx_timeline'])}sfx ")
            sys.stdout.flush()

        success_count += 1

    print()
    print()
    print("=" * 60)
    print(f"[DONE] Generated plans for {success_count} episodes")
    print(f"  Voice lines: {voice_total_lines}")
    print(f"  Music segments: {music_total_segments}")
    print(f"  SFX triggers: {sfx_total}")
    print(f"  Voice dir: {VOICE_DIR}")
    print(f"  Music dir: {MUSIC_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()

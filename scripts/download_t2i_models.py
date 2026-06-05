#!/usr/bin/env python3
"""
短剧文生图模型下载脚本

用途：下载 WanVideo 前置节点所需的所有文生图模型，用于：
  - 角色参考图生成
  - 场景概念图生成
  - 道具设计参考图
  - 关键帧预览图

用法:
    python3 download_t2i_models.py                   # 下载全部
    python3 download_t2i_models.py --category base   # 只下载基础模型
    python3 download_t2i_models.py --category flux   # 只下载 FLUX 系列
    python3 download_t2i_models.py --category kolors # 只下载 Kolors
    python3 download_t2i_models.py --category control # 只下载 ControlNet
    python3 download_t2i_models.py --workers 16      # 16线程下载
    python3 download_t2i_models.py --dry-run          # 只看清单不下载
    python3 download_t2i_models.py --list             # 打印模型清单
"""

import os
import sys
import time
import signal
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    import requests
    from tqdm import tqdm
except ImportError:
    print("请先安装依赖: pip install requests tqdm")
    sys.exit(1)

# ============================================================
# 模型清单
# ============================================================

# 通用文字编码器（多个模型共用）
TEXT_ENCODERS = [
    {
        "repo": "AI-ModelScope/flux_text_encoders",
        "files": [
            "clip_l.safetensors",
            "t5xxl_fp8_e4m3fn.safetensors",
        ],
        "local_dir": "text_encoders",
        "desc": "CLIP-L + T5-XXL 文本编码器 (FLUX/SD3.5 共用)",
    },
    {
        "repo": "AI-ModelScope/FLUX.1-Redux-dev",
        "files": [
            "image_encoder/model.safetensors",
        ],
        "local_dir": "clip_vision",
        "rename_map": {
            "image_encoder/model.safetensors": "clip_vision_h.safetensors",
        },
        "desc": "CLIP Vision H (FLUX Redux / 场景参考编码)",
    },
    {
        "repo": "Comfy-Org/z_image_turbo",
        "files": [
            "split_files/text_encoders/qwen_3_4b.safetensors",
        ],
        "local_dir": "z_image/text_encoders",
        "rename_map": {
            "split_files/text_encoders/qwen_3_4b.safetensors": "qwen_3_4b.safetensors",
        },
        "desc": "Qwen 3 4B 文本编码器 (Z-Image-Turbo)",
    },
]

# FLUX.1 系列 — 画质天花板，主力生图模型
FLUX_SERIES = [
    {
        "repo": "AI-ModelScope/flux-fp8",
        "files": ["flux1-dev-fp8.safetensors"],
        "local_dir": "flux",
        "desc": "FLUX.1-dev fp8 (文生图主力，~17GB)",
    },
    {
        "repo": "AI-ModelScope/FLUX.1-dev",
        "files": ["ae.sft"],
        "local_dir": "flux/vae",
        "desc": "FLUX.1 VAE",
    },
    {
        "repo": "AI-ModelScope/FLUX.1-Fill-dev",
        "files": ["flux1-fill-dev.safetensors"],
        "local_dir": "flux",
        "desc": "FLUX.1-Fill (局部重绘/扩图/修复)",
    },
    {
        "repo": "AI-ModelScope/FLUX.1-Redux-dev",
        "files": ["flux1-redux-dev.safetensors"],
        "local_dir": "flux",
        "desc": "FLUX.1-Redux (图片变体/风格迁移)",
    },
    {
        "repo": "AI-ModelScope/FLUX.1-Depth-dev-lora",
        "files": None,  # 下载全部文件
        "local_dir": "flux/controlnet",
        "desc": "FLUX.1-Depth ControlNet LoRA (深度控制)",
    },
    {
        "repo": "AI-ModelScope/FLUX.1-Canny-dev-lora",
        "files": None,
        "local_dir": "flux/controlnet",
        "desc": "FLUX.1-Canny ControlNet LoRA (边缘控制)",
    },
    {
        "repo": "Comfy-Org/z_image_turbo",
        "files": [
            "split_files/diffusion_models/z_image_turbo_bf16.safetensors",
            "split_files/vae/ae.safetensors",
        ],
        "local_dir": "z_image",
        "rename_map": {
            "split_files/diffusion_models/z_image_turbo_bf16.safetensors": "diffusion_models/z_image_turbo_bf16.safetensors",
            "split_files/vae/ae.safetensors": "vae/ae.safetensors",
        },
        "desc": "Z-Image-Turbo 主模型与 VAE",
    },
    {
        "repo": "PAI/Z-Image-Turbo-Fun-Controlnet-Union",
        "files": [
            "Z-Image-Turbo-Fun-Controlnet-Union.safetensors",
        ],
        "local_dir": "z_image/model_patches",
        "desc": "Z-Image-Turbo Union Model Patch",
    },
]

# SD3.5 系列 — 轻量备选，消费级显卡友好
SD35_SERIES = [
    {
        "repo": "AI-ModelScope/stable-diffusion-3.5-large",
        "files": None,
        "local_dir": "sd35",
        "desc": "SD3.5 Large (8B, 高质量)",
    },
    {
        "repo": "AI-ModelScope/stable-diffusion-3.5-medium",
        "files": None,
        "local_dir": "sd35",
        "desc": "SD3.5 Medium (2.6B, 低显存)",
    },
    {
        "repo": "AI-ModelScope/stable-diffusion-3.5-large-turbo",
        "files": None,
        "local_dir": "sd35",
        "desc": "SD3.5 Large Turbo (4步快速出图)",
    },
    {
        "repo": "AI-ModelScope/stable-diffusion-3.5-controlnets",
        "files": None,
        "local_dir": "sd35/controlnet",
        "desc": "SD3.5 ControlNets (Canny/Depth/Blur)",
    },
    {
        "repo": "AI-ModelScope/stable-diffusion-3.5-large",
        "files": ["vae/diffusion_pytorch_model.safetensors"],
        "local_dir": "sd35/vae",
        "rename_map": {
            "vae/diffusion_pytorch_model.safetensors": "sd3.5_large_vae.safetensors",
        },
        "desc": "SD3.5 Large VAE (16通道, ControlNet 必备)",
    },
]

# Kolors 系列 — 国产中文模型，ControlNet 生态最全
# 均可在 ModelScope 下载，无需走 HuggingFace
KOLORS_SERIES = [
    {
        "repo": "Kwai-Kolors/Kolors",
        "files": None,
        "local_dir": "kolors",
        "desc": "Kolors 主模型 (快手，中英双语)",
    },
    {
        "repo": "AI-ModelScope/sdxl-vae-fp16-fix",
        "files": None,
        "local_dir": "kolors/vae",
        "desc": "SDXL VAE (Kolors 配套)",
    },
    {
        "repo": "Kwai-Kolors/Kolors-ControlNet-Canny",
        "files": None,
        "local_dir": "kolors/controlnet/canny",
        "desc": "Kolors ControlNet-Canny (边缘检测，角色姿势参考)",
    },
    {
        "repo": "Kwai-Kolors/Kolors-ControlNet-Depth",
        "files": None,
        "local_dir": "kolors/controlnet/depth",
        "desc": "Kolors ControlNet-Depth (深度图，场景空间参考)",
    },
    {
        "repo": "Kwai-Kolors/Kolors-IP-Adapter-Plus",
        "files": None,
        "local_dir": "kolors/ipadapter",
        "desc": "Kolors IP-Adapter-Plus (风格参考，角色一致性)",
    },
    {
        "repo": "Kwai-Kolors/Kolors-IP-Adapter-FaceID-Plus",
        "files": None,
        "local_dir": "kolors/ipadapter_faceid",
        "desc": "Kolors IP-Adapter-FaceID (人脸身份保持)",
    },
    {
        "repo": "Kwai-Kolors/Kolors-Inpainting",
        "files": None,
        "local_dir": "kolors/inpainting",
        "desc": "Kolors Inpainting (局部重绘修复)",
    },
    {
        "repo": "Kwai-Kolors/Kolors-ControlNet-Pose",
        "files": None,
        "local_dir": "kolors/controlnet/pose",
        "desc": "Kolors ControlNet-Pose (姿态控制)",
    },
]

# HunyuanDiT — 腾讯混元，中文理解强
HUNYUAN_SERIES = [
    {
        "repo": "AI-ModelScope/HunyuanDiT-v1.1-Diffusers-Distilled",
        "files": None,
        "local_dir": "hunyuan",
        "desc": "HunyuanDiT v1.1 蒸馏版 (25步)",
    },
    {
        "repo": "Xorbits/HunyuanDiT-v1.2-Diffusers-Distilled",
        "files": None,
        "local_dir": "hunyuan",
        "desc": "HunyuanDiT v1.2 蒸馏版",
    },
]

# CogView4 — 智谱，中文文本渲染最强
COGVIEW_SERIES = [
    {
        "repo": "ZhipuAI/CogView4-6B",
        "files": None,
        "local_dir": "cogview4",
        "desc": "CogView4-6B (中文原生，DPG-Bench第一)",
    },
]

# 角色一致性辅助 — LoRA + IP-Adapter
CHARACTER_CONSISTENCY = [
    {
        "repo": "AI-ModelScope/FLUX.1-Redux-dev",
        "files": None,
        "local_dir": "flux/redux",
        "desc": "FLUX Redux (角色风格一致性)",
    },
]

# ============================================================
# 下载逻辑
# ============================================================

MODELSCOPE_BASE = "https://www.modelscope.cn"
HF_BASE = "https://huggingface.co"
CHUNK_SIZE = 2 * 1024 * 1024  # 2MB
shutdown_flag = False
DEFAULT_MODEL_ROOT = "/workspace/group_share/adc-sim/users/lik44/models"
DEFAULT_T2I_DIR = os.path.join(DEFAULT_MODEL_ROOT, "t2i_models")


def signal_handler(sig, frame):
    global shutdown_flag
    if shutdown_flag:
        print("\n💥 强制退出！")
        os._exit(1)
    print("\n\n🛑 正在停止 (再按一次 Ctrl+C 强制退出)...")
    shutdown_flag = True


def format_size(size_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def get_model_files_ms(repo: str) -> list:
    """通过 ModelScope API 获取仓库文件列表（带重试，只返回模型文件）"""
    import urllib.request
    import json

    # 非模型文件后缀，跳过
    SKIP_EXTS = {'.md', '.txt', '.json', '.gitattributes', '.gitignore', '.lock', '.py', '.yaml', '.yml', '.toml'}
    SKIP_NAMES = {'README.md', 'LICENSE', 'LICENSE.md', 'configuration.json', '.gitattributes', '.gitignore', 'config.json'}

    url = f"{MODELSCOPE_BASE}/api/v1/models/{repo}/repo/files?recursive=true"
    for attempt in range(3):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
            files = []
            for f in data.get('Data', {}).get('Files', []):
                if f.get('Type') == 'tree':
                    continue
                path = f['Path']
                name = os.path.basename(path)
                ext = os.path.splitext(name)[1].lower()
                # 跳过非模型文件
                if name in SKIP_NAMES or ext in SKIP_EXTS or name.startswith('.'):
                    continue
                files.append({
                    'path': path,
                    'size': f.get('Size', 0),
                    'lfs': f.get('Lfs', False),
                })
            return files
        except Exception as e:
            if attempt == 2:
                print(f"  ⚠️ {repo}: 获取失败 ({e})，跳过")
            else:
                time.sleep(2)
    return []


def get_model_files_hf(repo: str) -> list:
    """通过 HuggingFace API 获取仓库文件列表（国内走镜像 + 重试）"""
    import urllib.request
    import json

    # 优先用国内镜像
    mirror = os.environ.get("HF_ENDPOINT", "https://hf-mirror.com")
    url = f"{mirror}/api/models/{repo}?blobs=true"

    for attempt in range(3):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
            files = []
            for sib in data.get('siblings', []):
                if sib.get('rfilename', '').startswith('.'):
                    continue
                files.append({
                    'path': sib['rfilename'],
                    'size': sib.get('size', 0),
                    'lfs': sib.get('lfs', False) or sib.get('size', 0) > 1_000_000,
                })
            return files
        except Exception as e:
            if attempt == 2:
                print(f"  ⚠️ {repo}: HF 获取失败 ({e})，跳过此仓库")
            else:
                time.sleep(2)
    return []


def download_file_ms(repo: str, file_path: str, local_dir: str, progress_dict=None) -> bool:
    """从 ModelScope 下载单个文件"""
    url = f"{MODELSCOPE_BASE}/models/{repo}/resolve/master/{file_path}"
    local_path = os.path.join(local_dir, file_path)
    file_key = os.path.basename(file_path)
    return _download(url, local_path, progress_dict, file_key)


def download_file_hf(repo: str, file_path: str, local_dir: str, progress_dict=None) -> bool:
    """从 HuggingFace 下载单个文件（国内用 hf-mirror）"""
    mirror = os.environ.get("HF_ENDPOINT", "https://hf-mirror.com")
    url = f"{mirror}/{repo}/resolve/main/{file_path}"
    local_path = os.path.join(local_dir, file_path)
    file_key = os.path.basename(file_path)
    return _download(url, local_path, progress_dict, file_key)


def download_file_ms_to_path(repo: str, file_path: str, local_path: str, progress_dict=None) -> bool:
    """从 ModelScope 下载单个文件到指定保存路径"""
    url = f"{MODELSCOPE_BASE}/models/{repo}/resolve/master/{file_path}"
    file_key = os.path.basename(local_path)
    return _download(url, local_path, progress_dict, file_key)


def download_file_hf_to_path(repo: str, file_path: str, local_path: str, progress_dict=None) -> bool:
    """从 HuggingFace 下载单个文件到指定保存路径"""
    mirror = os.environ.get("HF_ENDPOINT", "https://hf-mirror.com")
    url = f"{mirror}/{repo}/resolve/main/{file_path}"
    file_key = os.path.basename(local_path)
    return _download(url, local_path, progress_dict, file_key)


def _download(url: str, local_path: str, progress_dict=None, file_key=None) -> bool:
    """通用下载，支持断点续传"""
    global shutdown_flag
    if shutdown_flag:
        return False

    existing = os.path.getsize(local_path) if os.path.exists(local_path) else 0
    headers = {}
    if existing > 0:
        headers['Range'] = f'bytes={existing}-'

    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    mode = 'ab' if existing > 0 else 'wb'

    try:
        resp = requests.get(url, headers=headers, stream=True, timeout=(30, 300))
        if resp.status_code == 416:
            return True
        if resp.status_code not in (200, 206):
            return False

        total = int(resp.headers.get('Content-Length', 0)) + existing
        downloaded = existing

        with open(local_path, mode) as f:
            for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                if shutdown_flag:
                    return False
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_dict is not None and file_key is not None:
                        progress_dict[file_key] = (downloaded, total)
        return True
    except Exception:
        return False


def probe_remote_size_ms(repo: str, file_path: str) -> int:
    """对显式文件任务补探远端大小，避免重复下载。"""
    url = f"{MODELSCOPE_BASE}/models/{repo}/resolve/master/{file_path}"
    try:
        resp = requests.get(url, headers={"Range": "bytes=0-0"}, stream=True, timeout=(15, 60))
        content_range = resp.headers.get("Content-Range", "")
        content_length = resp.headers.get("Content-Length", "")
        resp.close()
        if "/" in content_range:
            return int(content_range.split("/")[-1])
        if content_length:
            return int(content_length)
    except Exception:
        return 0
    return 0


def probe_remote_size_hf(repo: str, file_path: str) -> int:
    mirror = os.environ.get("HF_ENDPOINT", "https://hf-mirror.com")
    url = f"{mirror}/{repo}/resolve/main/{file_path}"
    try:
        resp = requests.get(url, headers={"Range": "bytes=0-0"}, stream=True, timeout=(15, 60))
        content_range = resp.headers.get("Content-Range", "")
        content_length = resp.headers.get("Content-Length", "")
        resp.close()
        if "/" in content_range:
            return int(content_range.split("/")[-1])
        if content_length:
            return int(content_length)
    except Exception:
        return 0
    return 0


def migrate_legacy_paths(base_dir: str) -> None:
    """兼容旧版本落盘目录，必要时自动迁移。"""
    legacy_to_new = [
        (
            os.path.join(base_dir, "z_image", "controlnet", "Z-Image-Turbo-Fun-Controlnet-Union.safetensors"),
            os.path.join(base_dir, "z_image", "model_patches", "Z-Image-Turbo-Fun-Controlnet-Union.safetensors"),
        ),
    ]
    for old_path, new_path in legacy_to_new:
        if os.path.exists(old_path) and not os.path.exists(new_path):
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            try:
                os.rename(old_path, new_path)
                print(f"  🔁 迁移旧路径: {old_path} -> {new_path}")
            except OSError:
                pass


def print_model_list():
    """打印模型清单"""
    categories = {
        "📝 文本编码器（共用）": TEXT_ENCODERS,
        "🔥 FLUX.1 系列（主力）": FLUX_SERIES,
        "📦 SD3.5 系列（备选）": SD35_SERIES,
        "🇨🇳 Kolors 系列（中文）": KOLORS_SERIES,
        "🔤 HunyuanDiT（中文）": HUNYUAN_SERIES,
        "🧠 CogView4（中文文本渲染）": COGVIEW_SERIES,
    }
    for cat_name, models in categories.items():
        print(f"\n{cat_name}")
        print("-" * 60)
        for m in models:
            source = m.get('source', 'ms')
            src_label = "🔗HF" if source == "hf" else "📦MS"
            print(f"  {src_label} {m['repo']}")
            print(f"       → {m['local_dir']}/")
            print(f"       {m['desc']}")


def main():
    global shutdown_flag

    parser = argparse.ArgumentParser(
        description="短剧文生图模型下载器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  %(prog)s                     下载全部模型
  %(prog)s --category flux     只下载 FLUX 系列
  %(prog)s --category base     只下载基础模型(FLUX+编码器)
  %(prog)s --list              查看模型清单
  %(prog)s --dry-run           模拟运行，不实际下载
  %(prog)s --dir /data/t2i_models  指定下载目录
        """,
    )
    parser.add_argument("--category", choices=["base", "flux", "sd35", "kolors", "hunyuan", "cogview", "control", "all"],
                        default="all", help="下载类别 (默认: all)")
    parser.add_argument("--dir", default=DEFAULT_T2I_DIR,
                        help=f"下载根目录 (默认: {DEFAULT_T2I_DIR})")
    parser.add_argument("--workers", type=int, default=8,
                        help="并发数 (默认: 8)")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅列出下载计划，不实际下载")
    parser.add_argument("--list", action="store_true",
                        help="打印模型清单")
    parser.add_argument("--no-hf", action="store_true",
                        help="跳过 HuggingFace 来源的模型（只下载 ModelScope 有的）")
    args = parser.parse_args()

    if args.list:
        print_model_list()
        return

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # ── 根据 category 组装下载列表 ───────────────────
    base_dir = os.path.abspath(os.path.expanduser(args.dir))
    all_tasks = []

    def add_models(models, section_name):
        for m in models:
            if args.no_hf and m.get('source') == 'hf':
                continue
            all_tasks.append(m)

    # 文本编码器总是需要的（除了纯 control）
    if args.category != "control":
        add_models(TEXT_ENCODERS, "编码器")

    if args.category in ("base", "all"):
        add_models(FLUX_SERIES, "FLUX")

    if args.category in ("flux", "all"):
        add_models(FLUX_SERIES, "FLUX")

    if args.category in ("sd35", "all"):
        add_models(SD35_SERIES, "SD3.5")

    if args.category in ("kolors", "all"):
        add_models(KOLORS_SERIES, "Kolors")

    if args.category in ("hunyuan", "all"):
        add_models(HUNYUAN_SERIES, "HunyuanDiT")

    if args.category in ("cogview", "all"):
        add_models(COGVIEW_SERIES, "CogView4")

    if args.category in ("control", "all"):
        add_models(CHARACTER_CONSISTENCY, "角色一致性")

    if not all_tasks:
        print("❌ 没有匹配的模型，请检查 --category 参数")
        return

    # ── 兼容旧路径迁移 ──────────────────────────────
    migrate_legacy_paths(base_dir)

    # ── 获取文件列表 ────────────────────────────────
    print("=" * 70)
    print(f"🎬 短剧文生图模型下载器")
    print(f"   类别: {args.category}")
    print(f"   目录: {base_dir}")
    print(f"   模型仓库: {len(all_tasks)} 个")
    print("=" * 70)

    all_files = []
    skipped_repos = []

    for m in tqdm(all_tasks, desc="📋 扫描仓库", unit="repo"):
        repo = m['repo']
        source = m.get('source', 'ms')
        target_files = m.get('files')

        # 如果已经显式给出了文件列表，就不要再依赖仓库 API 枚举。
        # 这样可以避开部分 ModelScope 仓库 API 404，但文件直链仍可下载的情况。
        if target_files is not None:
            files = [{"path": file_path, "size": 0, "lfs": True} for file_path in target_files]
        else:
            if source == 'hf':
                files = get_model_files_hf(repo)
            else:
                files = get_model_files_ms(repo)

        if not files:
            skipped_repos.append(repo)
            continue

        for f in files:
            f['_repo'] = repo
            f['_source'] = source
            f['_local_dir'] = os.path.join(base_dir, m['local_dir'])
            rename_map = m.get('rename_map', {})
            f['_save_relpath'] = rename_map.get(f['path'], f['path'])
            f['_save_path'] = os.path.join(f['_local_dir'], f['_save_relpath'])
            if f.get('size', 0) == 0:
                if source == 'hf':
                    f['size'] = probe_remote_size_hf(repo, f['path'])
                else:
                    f['size'] = probe_remote_size_ms(repo, f['path'])

        all_files.extend(files)

    if skipped_repos:
        print(f"\n⚠️ {len(skipped_repos)} 个仓库无法获取文件列表：")
        for r in skipped_repos:
            print(f"   - {r}")

    total_size = sum(f.get('size', 0) for f in all_files)
    print(f"\n📦 待下载: {len(all_files)} 个文件，约 {format_size(total_size)}")

    if args.dry_run:
        print("\n📋 下载清单:")
        for f in all_files:
            print(f"  {f['_source'].upper():2s} {f['_repo']:50s} → {f['_save_path']}")
        return

    # ── 并发下载 ────────────────────────────────────
    if not all_files:
        print("✅ 没有需要下载的文件")
        return

    print(f"\n{'='*70}")
    print(f"⬇️  开始下载 ({args.workers} 线程)")
    print(f"{'='*70}\n")

    completed = 0
    skipped = 0
    failed = 0
    downloaded_bytes = 0
    start_time = time.time()
    progress_dict = {}  # 共享进度 dict: {file_key: (downloaded, total)}

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {}

        for f in all_files:
            if shutdown_flag:
                break
            local_path = f['_save_path']

            # 跳过已存在且大小匹配的文件
            if os.path.exists(local_path):
                local_size = os.path.getsize(local_path)
                remote_size = f.get('size', 0)
                if remote_size > 0 and local_size == remote_size:
                    skipped += 1
                    downloaded_bytes += remote_size
                    tqdm.write(f"  ⏭️ {os.path.basename(local_path)} ({remote_size / 1024 / 1024:.0f}MB)")
                    continue

            file_key = os.path.basename(f['path'])
            if f['_source'] == 'hf':
                fut = pool.submit(download_file_hf_to_path, f['_repo'], f['path'], local_path, progress_dict)
            else:
                fut = pool.submit(download_file_ms_to_path, f['_repo'], f['path'], local_path, progress_dict)
            futures[fut] = f

            # 打印即将下载的文件
            size_mb = f.get('size', 0) / 1024 / 1024
            tqdm.write(f"  📥 {file_key[:60]} ({size_mb:.0f}MB)")

        if not futures:
            print("✅ 所有文件已下载完毕，无需重复下载")
        else:
            with tqdm(total=len(futures), desc="⬇️ 下载中", unit="个",
                      bar_format='{desc} |{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]') as pbar:
                last_display = time.time()
                for future in as_completed(futures):
                    if shutdown_flag:
                        for f in futures:
                            f.cancel()
                        pool.shutdown(wait=False)
                        break

                    f = futures[future]
                    try:
                        ok = future.result(timeout=0.5)
                    except Exception:
                        ok = False

                    if ok:
                        completed += 1
                        downloaded_bytes += f.get('size', 0)
                    else:
                        failed += 1
                        tqdm.write(f"  ❌ {f['_repo']}/{f['path']}")

                    # 清理已完成的进度
                    file_key = os.path.basename(f['path'])
                    progress_dict.pop(file_key, None)

                    # 每 5 秒显示活跃下载状态
                    now = time.time()
                    if now - last_display > 5 and progress_dict:
                        downloading = []
                        for k, (d, t) in progress_dict.items():
                            pct = d / t * 100 if t > 0 else 0
                            downloading.append(f"{k[:40]} {pct:.0f}%")
                        if downloading:
                            tqdm.write(f"  🔄 {', '.join(downloading[:3])}")
                        last_display = now

                    speed = (downloaded_bytes / 1024 / 1024 / max(time.time() - start_time, 1))
                    pbar.set_postfix_str(f"✅{completed} ⏭️{skipped} ❌{failed} | {speed:.0f}MB/s")
                    pbar.update(1)

    # ── 汇总 ────────────────────────────────────────
    elapsed = time.time() - start_time
    print(f"\n{'='*70}")
    print(f"📊 下载完成!")
    print(f"   成功: {completed}  跳过: {skipped}  失败: {failed}")
    print(f"   耗时: {elapsed/60:.0f} 分钟")
    if elapsed > 0:
        print(f"   均速: {downloaded_bytes/1024/1024/elapsed:.0f} MB/s")
    print(f"   目录: {base_dir}")
    print(f"\n📁 文件结构:")
    _print_tree(base_dir)
    print(f"{'='*70}")


def _print_tree(path: str, prefix: str = "   ", max_depth: int = 3):
    """打印目录树（精简版）"""
    if max_depth <= 0:
        return
    try:
        items = sorted(os.listdir(path))
    except PermissionError:
        return
    # 只显示目录和前几个文件
    dirs = [d for d in items if os.path.isdir(os.path.join(path, d))]
    files = [f for f in items if os.path.isfile(os.path.join(path, f))]
    for d in dirs:
        print(f"{prefix}📁 {d}/")
        _print_tree(os.path.join(path, d), prefix + "   ", max_depth - 1)
    for f in files[:3]:
        size = format_size(os.path.getsize(os.path.join(path, f)))
        print(f"{prefix}📄 {f} ({size})")
    if len(files) > 3:
        print(f"{prefix}   ... 还有 {len(files)-3} 个文件")


if __name__ == "__main__":
    main()

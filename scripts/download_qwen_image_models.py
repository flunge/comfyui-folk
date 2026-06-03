#!/usr/bin/env python3
"""
Qwen-Image / Qwen-Image-Edit 模型下载脚本

用途：
  - 下载 qwen_t2i_asset_2k.json
  - 下载 qwen_t2i_multiref_keyframe_2k.json
  - 下载 qwen_refine_upscale_2k.json
所需的基础模型与可选加速 LoRA。

用法:
    python3 pipelines/ComfyUI/scripts/download_qwen_image_models.py
    python3 pipelines/ComfyUI/scripts/download_qwen_image_models.py --model base
    python3 pipelines/ComfyUI/scripts/download_qwen_image_models.py --model edit
    python3 pipelines/ComfyUI/scripts/download_qwen_image_models.py --model lightning
    python3 pipelines/ComfyUI/scripts/download_qwen_image_models.py --list
"""

import os, sys, signal, argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
    from tqdm import tqdm
except ImportError:
    print("请先安装依赖: pip install requests tqdm")
    sys.exit(1)

BASE = "https://modelscope.cn/models/Comfy-Org/Qwen-Image_ComfyUI/resolve/master/split_files"
EDIT = "https://modelscope.cn/models/Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/master/split_files"
LIGHTNING = "https://modelscope.cn/models/lightx2v"
DIR = "/workspace/group_share/adc-sim/users/lik44/models/t2i_models"
shutdown = False


def handler(sig, frame):
    global shutdown
    if shutdown:
        os._exit(1)
    print("\n🛑 停止中 (再按一次强制退出)...")
    shutdown = True


signal.signal(signal.SIGINT, handler)
signal.signal(signal.SIGTERM, handler)

MODELS = {
    "qwen_text_encoder": {
        "file": "qwen_2.5_vl_7b_fp8_scaled.safetensors",
        "url": f"{BASE}/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors",
        "dir": "qwen/text_encoders",
    },
    "qwen_vae": {
        "file": "qwen_image_vae.safetensors",
        "url": f"{BASE}/vae/qwen_image_vae.safetensors",
        "dir": "qwen/vae",
    },
    "qwen_base": {
        "file": "qwen_image_2512_fp8_e4m3fn.safetensors",
        "url": f"{BASE}/diffusion_models/qwen_image_2512_fp8_e4m3fn.safetensors",
        "dir": "qwen/diffusion_models",
    },
    "qwen_edit": {
        "file": "qwen_image_edit_2511_bf16.safetensors",
        "url": f"{EDIT}/diffusion_models/qwen_image_edit_2511_bf16.safetensors",
        "dir": "qwen/diffusion_models",
    },
    "qwen_lightning_t2i": {
        "file": "Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors",
        "url": f"{LIGHTNING}/Qwen-Image-2512-Lightning/resolve/master/Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors",
        "dir": "qwen/loras",
    },
    "qwen_lightning_outpaint": {
        "file": "Qwen-Image-Lightning-4steps-V1.0.safetensors",
        "url": f"{LIGHTNING}/Qwen-Image-Lightning/resolve/master/Qwen-Image-Lightning-4steps-V1.0.safetensors",
        "dir": "qwen/loras",
    },
}

CATS = {
    "all": ["qwen_text_encoder", "qwen_vae", "qwen_base", "qwen_edit"],
    "base": ["qwen_text_encoder", "qwen_vae", "qwen_base"],
    "edit": ["qwen_text_encoder", "qwen_vae", "qwen_edit"],
    "lightning": ["qwen_lightning_t2i", "qwen_lightning_outpaint"],
}


def fmt(size):
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def get_cdn_url(url):
    try:
        r = requests.get(url, stream=True, timeout=30, allow_redirects=True)
        r.close()
        return r.url
    except Exception:
        return url


def get_size(url):
    try:
        r = requests.get(url, stream=True, timeout=15, headers={"Range": "bytes=0-0"})
        size = r.headers.get("Content-Range", "").split("/")[-1] or "0"
        r.close()
        return int(size)
    except Exception:
        return 0


def dl(url, path):
    if shutdown:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        return True

    tmp = path + ".tmp"
    exist = os.path.getsize(tmp) if os.path.exists(tmp) else 0
    cdn = get_cdn_url(url)
    headers = {"Range": f"bytes={exist}-"} if exist > 0 else {}

    try:
        r = requests.get(cdn, headers=headers, stream=True, timeout=(30, 600), allow_redirects=True)
        if r.status_code == 416:
            os.rename(tmp, path)
            return True
        if r.status_code not in (200, 206):
            return False
        mode = "ab" if exist > 0 else "wb"
        with open(tmp, mode) as f:
            for chunk in r.iter_content(2 << 20):
                if shutdown:
                    return False
                if chunk:
                    f.write(chunk)
        os.rename(tmp, path)
        return True
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Qwen-Image 模型下载")
    parser.add_argument("--model", choices=list(CATS.keys()), default="all")
    parser.add_argument("--dir", default=DIR)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()

    if args.list:
        total = 0
        for key in CATS["all"] + CATS["lightning"]:
            model = MODELS[key]
            size = get_size(model["url"])
            total += size
            print(f"  {key:<22} {model['file']:<52} {fmt(size):>8}")
        print(f"  {'':<22} {'':<52} {fmt(total):>8}")
        return

    keys = CATS[args.model]
    tasks = []
    for key in keys:
        model = MODELS[key]
        path = os.path.join(args.dir, model["dir"], model["file"])
        tasks.append((model["url"], path, model["file"]))

    print(f"🚀 下载 {len(tasks)} 个文件到 {args.dir}")
    ok = skip = fail = 0

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        future_map = {}
        for url, path, name in tasks:
            if os.path.exists(path):
                print(f"  ⏭️ {fmt(os.path.getsize(path))}  {name}")
                skip += 1
                continue
            print(f"  📥 {name}")
            future_map[pool.submit(dl, url, path)] = name

        if not future_map:
            print("✅ 全部已存在")
            return

        bar = tqdm(total=len(future_map), desc="下载中", unit="个")
        for fut in as_completed(future_map):
            name = future_map[fut]
            if fut.result():
                ok += 1
                bar.write(f"  ✅ {name}")
            else:
                fail += 1
                bar.write(f"  ❌ {name}")
            bar.update(1)
        bar.close()

    print(f"\n{'✅' if fail == 0 else '⚠️'} 完成 [{ok}成功 / {skip}跳过 / {fail}失败]")


if __name__ == "__main__":
    main()

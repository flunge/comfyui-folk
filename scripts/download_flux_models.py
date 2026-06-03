#!/usr/bin/env python3
"""
Flux 模型下载脚本（ModelScope 源）

用法:
    python3 pipelines/scripts/download_flux_models.py                # 下载全部
    python3 pipelines/scripts/download_flux_models.py --model fp16   # 只下 fp16 主模型
    python3 pipelines/scripts/download_flux_models.py --model vae    # 只下 VAE
    python3 pipelines/scripts/download_flux_models.py --list         # 查看清单
"""

import os, sys, signal, argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
    from tqdm import tqdm
except ImportError:
    print("请先安装依赖: pip install requests tqdm"); sys.exit(1)

MS = "https://www.modelscope.cn/models/black-forest-labs/FLUX.1-dev/resolve/master"
DIR = "/workspace/lik44@xiaopeng.com/test_deepcode/third_party/ComfyUI/models"
shutdown = False


def handler(s, f):
    global shutdown
    if shutdown: os._exit(1)
    print("\n🛑 停止中 (再按一次强制退出)...")
    shutdown = True


signal.signal(signal.SIGINT, handler)
signal.signal(signal.SIGTERM, handler)

MODELS = {
    "fp16":   {"file": "flux1-dev-fp16.safetensors", "url": f"{MS}/flux1-dev.safetensors",        "dir": "diffusion_models"},
    "ae":     {"file": "ae.safetensors",              "url": f"{MS}/ae.safetensors",               "dir": "vae"},
    "clip_l": {"file": "clip_l.safetensors",          "url": f"{MS}/text_encoder/model.safetensors","dir": "text_encoders"},
    "t5xxl":  {"file": "t5xxl_fp16.safetensors",      "url": f"{MS}/text_encoder_2/model.safetensors","dir": "text_encoders"},
    "vision": {"file": "clip_vision_h.safetensors",   "url": f"{MS}/clip_vision/clip_vision_h.safetensors","dir": "clip_vision"},
}

CATS = {"all":["fp16","ae","clip_l","t5xxl","vision"],"fp16":["fp16"],"vae":["ae"],"ae":["ae"],"clip":["clip_l","t5xxl"],"vision":["vision"]}


def fmt(b):
    for u in ['B','KB','MB','GB']:
        if b < 1024: return f"{b:.1f}{u}"
        b /= 1024
    return f"{b:.1f}TB"


def get_cdn_url(url):
    """获取 ModelScope 302 重定向后的 CDN 直链"""
    try:
        r = requests.get(url, stream=True, timeout=30, allow_redirects=True)
        r.close()
        return r.url
    except:
        return url


def dl(url, path):
    if shutdown: return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path): return True

    tmp = path + ".tmp"
    exist = os.path.getsize(tmp) if os.path.exists(tmp) else 0
    cdn = get_cdn_url(url)

    hd = {"Range": f"bytes={exist}-"} if exist > 0 else {}
    try:
        r = requests.get(cdn, headers=hd, stream=True, timeout=(30,600), allow_redirects=True)
        if r.status_code == 416: os.rename(tmp, path); return True
        if r.status_code not in (200, 206): return False
        mode = "ab" if exist > 0 else "wb"
        with open(tmp, mode) as f:
            for c in r.iter_content(2 << 20):
                if shutdown: return False
                if c: f.write(c)
        os.rename(tmp, path)
        return True
    except:
        return False


def get_size(url):
    try:
        r = requests.get(url, stream=True, timeout=15, headers={"Range": "bytes=0-0"})
        s = r.headers.get("Content-Range", "").split("/")[-1] or "0"
        r.close()
        return int(s)
    except:
        return 0


def main():
    p = argparse.ArgumentParser(description="Flux 模型下载 (ModelScope)")
    p.add_argument("--model", choices=list(CATS.keys()), default="all")
    p.add_argument("--dir", default=DIR)
    p.add_argument("--list", action="store_true")
    p.add_argument("--workers", type=int, default=2)
    args = p.parse_args()

    if args.list:
        total = 0
        for k in CATS["all"]:
            m = MODELS[k]
            s = get_size(m["url"])
            total += s
            print(f"  {k:<8} {m['file']:<30} {fmt(s):>8}")
        print(f"  {'':<8} {'':<30} {fmt(total):>8}")
        return

    keys = CATS[args.model]
    tasks = []
    for k in keys:
        m = MODELS[k]
        p2 = os.path.join(args.dir, m["dir"], m["file"])
        tasks.append((m["url"], p2, m["file"]))

    print(f"🚀 下载 {len(tasks)} 个文件到 {args.dir}")
    ok = skip = fail = 0

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        fm = {}
        for url, path, name in tasks:
            if shutdown: break
            if os.path.exists(path):
                print(f"  ⏭️ {fmt(os.path.getsize(path))}  {name}")
                skip += 1; continue
            print(f"  📥 {name}")
            fm[pool.submit(dl, url, path)] = name

        if not fm: print("✅ 全部已存在"); return
        bar = tqdm(total=len(fm), desc="下载中", unit="个")
        for fut in as_completed(fm):
            if shutdown: break
            name = fm[fut]
            if fut.result():
                ok += 1
                bar.write(f"  ✅ {name}")
            else:
                fail += 1
                bar.write(f"  ❌ {name}")
            bar.update(1)
        bar.close()

    print(f"\n{'✅' if fail==0 else '⚠️'} 完成 [{ok}成功 / {skip}跳过 / {fail}失败]")


if __name__ == "__main__":
    main()

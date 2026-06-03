#!/usr/bin/env python3
"""
Flux 模型下载脚本（ModelScope 源）

下载 Flux.1-dev fp16 全精度模型用于高质量文生图。
A100 80GB 显存可流畅运行 fp16 版本，画质显著优于 fp8。

用法:
    python3 download_flux_models.py                # 下载全部
    python3 download_flux_models.py --model fp16   # 只下 fp16 主模型
    python3 download_flux_models.py --model vae    # 只下 VAE
    python3 download_flux_models.py --model clip   # 只下文本编码器
    python3 download_flux_models.py --model vision # 只下 clip_vision
    python3 download_flux_models.py --list         # 查看清单
    python3 download_flux_models.py --dir /path    # 指定目录
"""

import os, sys, time, signal, argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    import requests
    from tqdm import tqdm
except ImportError:
    print("请先安装依赖: pip install requests tqdm")
    sys.exit(1)

MODELSCOPE = "https://www.modelscope.cn/models/black-forest-labs/FLUX.1-dev/resolve/master"
BASE_DIR = "/workspace/lik44@xiaopeng.com/test_deepcode/third_party/ComfyUI/models"
CHUNK_SIZE = 2 * 1024 * 1024
shutdown = False


def signal_handler(sig, frame):
    global shutdown
    if shutdown:
        print("\n💥 强制退出"); os._exit(1)
    print("\n\n🛑 正在停止 (再按 Ctrl+C 强制退出)...")
    shutdown = True


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

MODELS = {
    "fp16": {
        "file": "flux1-dev.safetensors",
        "url": f"{MODELSCOPE}/flux1-dev.safetensors",
        "dir": "diffusion_models",
        "rename": "flux1-dev-fp16.safetensors",
        "desc": "Flux.1-dev fp16 主模型 (~23GB)",
    },
    "ae": {
        "file": "ae.safetensors",
        "url": f"{MODELSCOPE}/ae.safetensors",
        "dir": "vae",
        "desc": "Flux VAE (~335MB)",
    },
    "clip_l": {
        "file": "clip_l.safetensors",
        "url": f"{MODELSCOPE}/text_encoder/model.safetensors",
        "dir": "text_encoders",
        "rename": "clip_l.safetensors",
        "desc": "CLIP-L 文本编码器",
    },
    "t5xxl": {
        "file": "t5xxl_fp16.safetensors",
        "url": f"{MODELSCOPE}/text_encoder_2/model.safetensors",
        "dir": "text_encoders",
        "desc": "T5-XXL 文本编码器 (~9GB)",
    },
    "clip_vision": {
        "file": "clip_vision_h.safetensors",
        "url": f"{MODELSCOPE}/clip_vision/clip_vision_h.safetensors",
        "dir": "clip_vision",
        "desc": "CLIP Vision (Redux 参考图用)",
    },
}

CATEGORIES = {
    "all":      ["fp16", "ae", "clip_l", "t5xxl", "clip_vision"],
    "fp16":     ["fp16"],
    "vae":      ["ae"],
    "ae":       ["ae"],
    "clip":     ["clip_l", "t5xxl"],
    "vision":   ["clip_vision"],
}


def format_size(b):
    for u in ['B', 'KB', 'MB', 'GB']:
        if b < 1024: return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} TB"


def download_one(url, local_path, rename=None):
    """下载单个文件，支持断点续传"""
    global shutdown
    if shutdown: return False

    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    final_path = os.path.join(os.path.dirname(local_path), rename) if rename else local_path

    if os.path.exists(final_path):
        return True

    tmp = local_path + ".tmp"
    existing = os.path.getsize(tmp) if os.path.exists(tmp) else 0
    headers = {'Range': f'bytes={existing}-'} if existing > 0 else {}
    mode = 'ab' if existing > 0 else 'wb'

    try:
        resp = requests.get(url, headers=headers, stream=True, timeout=(30, 300))
        if resp.status_code == 416:
            os.rename(tmp, final_path); return True
        if resp.status_code not in (200, 206):
            return False

        total = int(resp.headers.get('Content-Length', 0)) + existing
        with open(tmp, mode) as f:
            for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                if shutdown: return False
                if chunk: f.write(chunk)

        os.rename(tmp, final_path)
        return True
    except Exception:
        return False


def main():
    global shutdown

    parser = argparse.ArgumentParser(
        description="Flux 模型下载脚本 (ModelScope)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例:\n  %(prog)s             下载全部\n  %(prog)s --model fp16\n  %(prog)s --model vae\n  %(prog)s --list",
    )
    parser.add_argument("--model", choices=list(CATEGORIES.keys()), default="all",
                        help="下载类别 (默认: all)")
    parser.add_argument("--dir", default=BASE_DIR, help=f"下载目录 (默认: {BASE_DIR})")
    parser.add_argument("--list", action="store_true", help="查看模型清单")
    parser.add_argument("--workers", type=int, default=4, help="并发数 (默认: 4)")
    args = parser.parse_args()

    if args.list:
        print(f"{'名称':<15} {'文件':<40} {'大小':<10} {'说明'}")
        print("-" * 85)
        total = 0
        for key in CATEGORIES["all"]:
            m = MODELS[key]
            url = m["url"]
            # 获取文件大小
            try:
                r = requests.head(url, timeout=10)
                size = int(r.headers.get("Content-Length", 0))
            except:
                size = 0
            total += size
            print(f"{key:<15} {m.get('file', ''):<40} {format_size(size):<10} {m['desc']}")
        print("-" * 85)
        print(f"{'总计':<15} {'':<40} {format_size(total):<10}")
        return

    keys = CATEGORIES[args.model]
    files = []
    for k in keys:
        m = MODELS[k]
        p = Path(args.dir) / m["dir"] / m.get("rename", m["file"])
        files.append({
            "key": k,
            "url": m["url"],
            "local": str(p),
            "desc": m["desc"],
        })

    print(f"🚀 Flux 模型下载器")
    print(f"   目录: {args.dir}")
    print(f"   文件: {len(files)} 个")
    print()

    completed = skipped = failed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {}
        for f in files:
            if shutdown: break
            if os.path.exists(f["local"]):
                size = format_size(os.path.getsize(f["local"]))
                print(f"  ⏭️  {size}  {f['desc']}")
                skipped += 1
                continue
            print(f"  📥 {f['desc']}")
            futures[pool.submit(download_one, f["url"], f["local"])] = f

        if not futures:
            print("\n✅ 全部已下载")
            return

        for fut in tqdm(as_completed(futures), total=len(futures), desc="⬇️ 下载"):
            if shutdown: break
            f = futures[fut]
            try:
                ok = fut.result(timeout=1)
            except:
                ok = False
            if ok:
                completed += 1
                size = format_size(os.path.getsize(f["local"]))
                tqdm.write(f"  ✅ {size}  {f['desc']}")
            else:
                failed += 1
                tqdm.write(f"  ❌ {f['desc']}")
            tqdm.update(1)

    print(f"\n✅ 完成!  成功: {completed}  跳过: {skipped}  失败: {failed}")
    if failed:
        print("💡 重新运行脚本即可断点续传")


if __name__ == "__main__":
    main()

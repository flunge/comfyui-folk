#!/usr/bin/env python3
"""
ModelScope 大仓库下载脚本（改进版）
下载 Kijai/WanVideo_comfy_fp8_scaled 模型，支持文件名过滤

用法:
    python3 download_modelscope.py

    # 只下载 I2V A14B 模型
    python3 download_modelscope.py --include "A14B"

    # 只下载 I2V 相关模型
    python3 download_modelscope.py --include "I2V/" --exclude "T2V"

    # 指定其他仓库
    python3 download_modelscope.py --repo Kijai/WanVideo_comfy

可选参数:
    --workers 8        并发下载线程数（默认8）
    --dir ./models     下载目录（默认 ./ComfyUI/models/diffusion_models）
    --repo Kijai/WanVideo_comfy_fp8_scaled  仓库名
    --include "A14B"   只下载文件名包含该关键字的文件（可多次使用）
    --exclude "T2V"    跳过文件名包含该关键字的文件（可多次使用）
    --skip-small       跳过小文件（<1MB），只下模型
    --retry 2          失败重试次数（默认2）

import os
import sys
import time
import signal
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_EXCEPTION
from pathlib import Path
from dataclasses import dataclass, field

try:
    import requests
    from tqdm import tqdm
except ImportError:
    print("❌ 缺少依赖，请先安装：")
    print("   pip install requests tqdm modelscope")
    sys.exit(1)

from modelscope.hub.api import HubApi

# ── 配置 ──────────────────────────────────────────────
DEFAULT_REPO = "Kijai/WanVideo_comfy_fp8_scaled"
DEFAULT_DIR = "./ComfyUI/models/diffusion_models"
DEFAULT_WORKERS = 8
CHUNK_SIZE = 2 * 1024 * 1024  # 2MB 块下载
CONNECT_TIMEOUT = 30
READ_TIMEOUT = 300


@dataclass
class DownloadStats:
    """下载统计"""
    total_files: int = 0
    completed: int = 0
    skipped: int = 0
    failed: int = 0
    total_bytes: int = 0
    downloaded_bytes: int = 0
    start_time: float = 0.0
    failed_list: list = field(default_factory=list)

    def elapsed(self) -> float:
        return time.time() - self.start_time

    def speed_mbps(self) -> float:
        elapsed = self.elapsed()
        return (self.downloaded_bytes / 1024 / 1024 / elapsed) if elapsed > 0 else 0

    def progress_pct(self) -> float:
        return (self.completed + self.skipped + self.failed) / self.total_files * 100 if self.total_files else 0


stats = DownloadStats()
shutdown_flag = False


def format_size(size_bytes: int) -> str:
    """字节转可读格式"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def signal_handler(sig, frame):
    """Ctrl+C 退出：第一次优雅停止，第二次强制退出"""
    global shutdown_flag
    if shutdown_flag:
        print(f"\n💥 强制退出！")
        os._exit(1)  # 立即杀死进程，不等任何清理
    print(f"\n\n🛑 正在停止 (再按一次 Ctrl+C 强制退出)...")
    shutdown_flag = True


def download_one_file(file_info: dict, base_dir: str, repo: str) -> bool:
    """
    下载单个文件，带断点续传
    返回 True=成功, False=失败
    """
    global shutdown_flag
    if shutdown_flag:
        return False

    path = file_info['Path']
    remote_size = file_info.get('Size', 0)
    url = f"https://www.modelscope.cn/models/{repo}/resolve/master/{path}"
    local_path = os.path.join(base_dir, path)

    # 跳过已完整下载的文件
    if os.path.exists(local_path):
        local_size = os.path.getsize(local_path)
        if remote_size > 0 and local_size == remote_size:
            return True  # 已存在且完整
        elif remote_size == 0 and local_size > 1024:  # 无大小信息但文件>1KB
            return True

    # 确保目录存在
    os.makedirs(os.path.dirname(local_path), exist_ok=True)

    # 断点续传：检查已下载部分
    existing_size = 0
    if os.path.exists(local_path):
        existing_size = os.path.getsize(local_path)

    headers = {}
    if existing_size > 0 and remote_size > 0 and existing_size < remote_size:
        headers['Range'] = f'bytes={existing_size}-'

    mode = 'ab' if existing_size > 0 else 'wb'

    try:
        resp = requests.get(
            url,
            headers=headers,
            stream=True,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )

        if resp.status_code == 416:  # Range not satisfiable, 文件可能已完整
            return True
        if resp.status_code not in (200, 206):
            print(f"  ⚠️ HTTP {resp.status_code} for {path}")
            return False

        # 确定总大小
        content_range = resp.headers.get('Content-Range', '')
        if content_range:
            total = int(content_range.split('/')[-1])
        else:
            total = int(resp.headers.get('Content-Length', 0))

        # 用 tqdm 显示单文件进度
        desc = f"{path[-55:]}" if len(path) > 55 else f"{path:<55}"
        with open(local_path, mode) as f:
            with tqdm.wrapattr(
                f, "write",
                total=total,
                initial=existing_size,
                desc=desc,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
                miniters=1,
                leave=False,
                bar_format='{desc} |{bar}| {percentage:3.0f}% {rate_fmt} {remaining}',
            ) as tfile:
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    if shutdown_flag:
                        return False
                    if chunk:
                        tfile.write(chunk)
                        stats.downloaded_bytes += len(chunk)

        # 校验
        if remote_size > 0 and os.path.getsize(local_path) != remote_size:
            print(f"  ⚠️ 大小不匹配 {path}: {os.path.getsize(local_path)} != {remote_size}")
            return False

        return True

    except requests.exceptions.Timeout:
        print(f"  ⏱️ 超时 {path}")
        return False
    except requests.exceptions.ConnectionError:
        print(f"  🔌 连接失败 {path}")
        return False
    except Exception as e:
        print(f"  ❌ {path}: {e}")
        return False


def main():
    global shutdown_flag

    parser = argparse.ArgumentParser(description="ModelScope 模型仓库下载器")
    parser.add_argument("--repo", default=DEFAULT_REPO, help=f"仓库名 (默认: {DEFAULT_REPO})")
    parser.add_argument("--dir", default=DEFAULT_DIR, help=f"下载目录 (默认: {DEFAULT_DIR})")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help=f"并发数 (默认: {DEFAULT_WORKERS})")
    parser.add_argument("--skip-small", action="store_true", help="跳过小文件 (<1MB)，只下模型")
    parser.add_argument("--retry", type=int, default=2, help="失败重试次数 (默认: 2)")
    parser.add_argument("--include", action="append", default=[], help="只下载文件名包含该关键字的文件（可多次使用）")
    parser.add_argument("--exclude", action="append", default=[], help="跳过文件名包含该关键字的文件（可多次使用）")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("=" * 70)
    print(f"🚀 ModelScope 仓库下载器")
    print(f"   仓库: {args.repo}")
    print(f"   目录: {os.path.abspath(args.dir)}")
    print(f"   并发: {args.workers} 线程")
    print("=" * 70)

    # ── 获取文件列表 ──────────────────────────────────
    print("\n📋 正在获取文件列表...")
    try:
        api = HubApi()
        files = api.get_model_files(args.repo, recursive=True)
    except Exception as e:
        print(f"❌ 获取文件列表失败: {e}")
        sys.exit(1)

    if not files:
        print("❌ 未找到任何文件，请检查仓库名是否正确")
        sys.exit(1)

    # 过滤掉目录条目（Type=tree），只保留实际文件
    real_files = [f for f in files if f.get('Type') != 'tree']

    dir_count = len(files) - len(real_files)
    if dir_count > 0:
        print(f"   (已过滤 {dir_count} 个目录条目)")

    # 文件名关键字过滤
    if args.include:
        before = len(real_files)
        real_files = [f for f in real_files
                      if any(kw in f['Path'] for kw in args.include)]
        print(f"   --include '{', '.join(args.include)}': {before} → {len(real_files)} 个文件")
    if args.exclude:
        before = len(real_files)
        real_files = [f for f in real_files
                      if not any(kw in f['Path'] for kw in args.exclude)]
        print(f"   --exclude '{', '.join(args.exclude)}': {before} → {len(real_files)} 个文件")

    # 分类文件
    lfs_files = [f for f in real_files if f.get('Lfs')]  # 大文件（LFS）
    small_files = [f for f in real_files if not f.get('Lfs')]  # 小文件（直接存git）

    # 估算总大小
    total_lfs_size = sum(f.get('Size', 0) for f in lfs_files)
    total_small_size = sum(f.get('Size', 0) for f in small_files)

    print(f"\n📦 文件统计:")
    print(f"   LFS 大文件: {len(lfs_files)} 个 ({format_size(total_lfs_size)})")
    print(f"   普通小文件: {len(small_files)} 个 ({format_size(total_small_size)})")
    print(f"   总计: {len(files)} 个文件, 约 {format_size(total_lfs_size + total_small_size)}")

    # ── 先下载小文件（单线程，快） ─────────────────
    to_download = []
    if not args.skip_small:
        print(f"\n📄 下载小文件...")
        for f in tqdm(small_files, desc="小文件", unit="file"):
            path = f['Path']
            local = os.path.join(args.dir, path)
            os.makedirs(os.path.dirname(local), exist_ok=True)
            if not os.path.exists(local):
                try:
                    from modelscope.hub.file_download import model_file_download
                    model_file_download(args.repo, path, cache_dir=args.dir)
                except Exception as e:
                    tqdm.write(f"  ⚠️ {path}: {e}")
    else:
        print(f"\n⏭️ 跳过小文件 (--skip-small)")

    # ── 并发下载大文件 ───────────────────────────────
    stats.total_files = len(lfs_files)
    stats.start_time = time.time()

    print(f"\n{'='*70}")
    print(f"⬇️  开始下载 {len(lfs_files)} 个模型文件")
    print(f"{'='*70}\n")

    # 构建任务列表：失败的文件重试
    to_download = lfs_files

    for attempt in range(args.retry + 1):
        if shutdown_flag:
            break
        if not to_download:
            break

        if attempt > 0:
            print(f"\n🔄 第 {attempt} 次重试 ({len(to_download)} 个文件)...\n")

        stats.completed = 0
        stats.failed = 0
        stats.failed_list = []

        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(download_one_file, f, args.dir, args.repo): f['Path']
                for f in to_download
            }

            try:
                for future in as_completed(futures):
                    if shutdown_flag:
                        # 取消所有未开始的任务，不再等待正在跑的
                        for f in futures:
                            f.cancel()
                        pool.shutdown(wait=False)
                        break

                    path = futures[future]
                    try:
                        ok = future.result(timeout=0.5)
                    except Exception as e:
                        ok = False
                        tqdm.write(f"  ❌ 异常 {path}: {e}")

                    if ok:
                        stats.completed += 1
                    else:
                        stats.failed += 1
                        stats.failed_list.append(path)

                    # 总进度摘要行
                    pct = stats.progress_pct()
                    elapsed = stats.elapsed()
                    speed = stats.speed_mbps()
                    eta = ""
                    if speed > 0 and stats.total_files > 0:
                        remaining = (stats.total_files - stats.completed - stats.skipped - stats.failed)
                        eta_sec = (remaining * total_lfs_size / stats.total_files) / (speed * 1024 * 1024) if speed > 0 else 0
                        eta = f"ETA: {eta_sec/3600:.1f}h" if eta_sec > 3600 else f"ETA: {eta_sec/60:.0f}m"

                    tqdm.write(
                        f"[{stats.completed+stats.skipped+stats.failed}/{stats.total_files}] "
                        f"✅ {stats.completed}  ⏭️ {stats.skipped}  ❌ {stats.failed}  |  "
                        f"{speed:.0f} MB/s  {eta}"
                    )
            except KeyboardInterrupt:
                # 如果 as_completed 本身收到中断
                pool.shutdown(wait=False)
                shutdown_flag = True

        to_download = [
            f for f in lfs_files
            if f['Path'] in stats.failed_list
        ]

    # ── 汇总 ──────────────────────────────────────────
    elapsed = stats.elapsed()
    print(f"\n{'='*70}")
    print(f"📊 下载完成!")
    print(f"   成功: {stats.completed}  跳过: {stats.skipped}  失败: {stats.failed}")
    print(f"   耗时: {elapsed/3600:.1f} 小时 ({elapsed/60:.0f} 分钟)")
    print(f"   均速: {stats.speed_mbps():.0f} MB/s")
    print(f"   目录: {os.path.abspath(args.dir)}")

    if stats.failed_list:
        print(f"\n❌ 失败文件清单 ({len(stats.failed_list)} 个):")
        for p in stats.failed_list:
            print(f"   - {p}")
        print(f"\n💡 重新运行本脚本即可断点续传重试失败文件")

    print(f"{'='*70}")


if __name__ == "__main__":
    main()

#!/bin/bash
# =============================================================================
# ComfyUI 快速启动脚本
# 用法:
#   bash start_comfy.sh               # 最快启动（禁用 Manager + Triton）
#   bash start_comfy.sh --full        # 完整模式
#   bash start_comfy.sh --manager     # 带 Manager
# =============================================================================

set -e

COMFY_DIR="/workspace/lik44@xiaopeng.com/comfyui"
cd "$COMFY_DIR"

if [ ! -f "main.py" ]; then
    echo "❌ 找不到 ComfyUI，请检查 COMFY_DIR 路径"
    exit 1
fi

# ── 杀掉旧进程 ────────────────────────────────────────
OLD_PID=$(ps aux | grep "python.*main.py" | grep -v grep | awk '{print $2}')
if [ -n "$OLD_PID" ]; then
    echo "🔄 关闭旧 ComfyUI (PID: $OLD_PID)..."
    kill -9 "$OLD_PID" 2>/dev/null
    sleep 1
fi

MODE="${1:-light}"

case "$MODE" in
    --full|-f)
        echo "🚀 完整模式启动"
        python main.py
        ;;
    --manager|-m)
        echo "🚀 Manager 模式启动"

        # 恢复 Manager（如果被移走了）
        [ -d "../ComfyUI-Manager" ] && mv ../ComfyUI-Manager custom_nodes/ 2>/dev/null

        python main.py
        ;;
    *)
        echo "🚀 极速模式启动"
        echo "   完整模式: bash start_comfy.sh --full"
        echo ""

        # 1. 移走 Manager（节省 ~17 秒）
        [ -d "custom_nodes/ComfyUI-Manager" ] && mv custom_nodes/ComfyUI-Manager ../ 2>/dev/null
        [ -d "custom_nodes/ComfyUI-Manager.off" ] && rm -rf custom_nodes/ComfyUI-Manager.off 2>/dev/null

        # 2. 跳过 Triton 检测（节省 ~10-15 秒）
        export TRITON_DISABLE=1

        # 3. 跳过 metadata/registry
        python main.py --disable-metadata
        ;;
esac

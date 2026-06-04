#!/bin/bash
# =============================================================================
# ComfyUI 快速启动脚本
# 用法:
#   bash start_comfy.sh               # T2I 极速模式（默认）
#   bash start_comfy.sh --t2i         # T2I 极速模式
#   bash start_comfy.sh --wan         # Wan 视频模式
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

restore_manager() {
    [ -d "../ComfyUI-Manager" ] && mv ../ComfyUI-Manager custom_nodes/ 2>/dev/null
}

disable_manager() {
    [ -d "custom_nodes/ComfyUI-Manager" ] && mv custom_nodes/ComfyUI-Manager ../ 2>/dev/null
    [ -d "custom_nodes/ComfyUI-Manager.off" ] && rm -rf custom_nodes/ComfyUI-Manager.off 2>/dev/null
}

case "$MODE" in
    --full|-f)
        echo "🚀 完整模式启动"
        restore_manager
        python main.py
        ;;
    --manager|-m)
        echo "🚀 Manager 模式启动"
        restore_manager
        python main.py
        ;;
    --wan|-w)
        echo "🚀 Wan 视频模式启动"
        echo "   仅加载 WanVideoWrapper / KJNodes，禁用 API nodes"
        echo ""

        disable_manager
        export TRITON_DISABLE=1

        python main.py \
            --disable-all-custom-nodes \
            --whitelist-custom-nodes ComfyUI-WanVideoWrapper ComfyUI-KJNodes \
            --disable-api-nodes \
            --disable-metadata
        ;;
    --t2i|-t|light)
        echo "🚀 T2I 极速模式启动"
        echo "   禁用全部 custom nodes / api nodes"
        echo "   适合 Flux / Qwen / SD3.5 文生图"
        echo "   Wan 视频节点不会加载"
        echo ""

        disable_manager
        export TRITON_DISABLE=1

        python main.py \
            --disable-all-custom-nodes \
            --disable-api-nodes \
            --disable-metadata
        ;;
    *)
        echo "🚀 T2I 极速模式启动"
        echo "   其它模式:"
        echo "   bash start_comfy.sh --wan"
        echo "   bash start_comfy.sh --full"
        echo ""

        disable_manager
        export TRITON_DISABLE=1

        python main.py \
            --disable-all-custom-nodes \
            --disable-api-nodes \
            --disable-metadata
        ;;
esac

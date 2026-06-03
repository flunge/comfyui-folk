# Workflows — ComfyUI 工作流总览

本目录包含基于 **ComfyUI** 的文生图（T2I）和图生视频（I2V）工作流 JSON 文件，可直接拖入 ComfyUI WebUI 加载。

## 目录结构

```
workflows/
├── README.md              ← 本文件
├── t2i/                   # 文生图工作流（Flux 管线）
│   ├── flux_multiref_1024.json    # 16:9, 1024×576
│   ├── flux_multiref_2048.json    # 16:9, 2048×1152
│   └── README.md
├── i2v/                   # 图生视频工作流（WAN 管线）
│   ├── wan_i2v_multiframe_multiref_480p.json  # 832×480, 16fps
│   ├── wan_i2v_multiframe_multiref_720p.json  # 1280×720, 24fps
│   └── README.md
├── _gen_t2i.py            # T2I JSON 生成脚本（开发用）
└── _gen_i2v.py            # I2V JSON 生成脚本（开发用）
```

## 使用方法

1. 启动 ComfyUI：`python main.py`
2. 将 `.json` 文件拖入浏览器窗口
3. 替换 `LoadImage` 节点中的图片路径为实际资产路径
4. 点击 **Queue Prompt** 运行

## 模型放置路径

| 模型 | ComfyUI 目录 |
|------|-------------|
| `flux1-dev-fp8.safetensors` | `models/diffusion_models/` |
| `flux1-redux-dev.safetensors` | `models/style_models/` |
| `clip_l.safetensors` | `models/text_encoders/` |
| `t5xxl_fp8_e4m3fn.safetensors` | `models/text_encoders/` |
| `clip_vision_h.safetensors` | `models/clip_vision/` |
| `flux1-canny-dev-lora.safetensors` | `models/controlnet/` |
| `ae.safetensors` (Flux VAE) | `models/vae/` |
| `Wan2_2-I2V-A14B-*.safetensors` | `models/diffusion_models/WanVideo/2_2/` |
| `Wan2_1_VAE_bf16.safetensors` | `models/vae/` |
| `umt5-xxl-enc-bf16.safetensors` | `models/text_encoders/` |

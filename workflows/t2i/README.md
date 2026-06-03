# T2I — 本地文生图工作流

包含两套路线：
- `Flux.1-dev`：已有轻量和参考图链路，适合快速迭代
- `Qwen-Image`：2K 上限工作流，优先打磨角色立绘、场景/道具图和剧情关键帧

## 文件

| 文件 | 分辨率 | 适用场景 |
|------|--------|---------|
| `flux_multiref_1024.json` | 1024×576 (16:9) | 轻量生成，快速迭代 |
| `flux_multiref_2048.json` | 2048×1152 (16:9) | 高质量输出，关键帧级 |
| `qwen_t2i_asset_2k.json` | 2048×1152 (默认) | 纯文本角色/场景/道具生成 |
| `qwen_t2i_multiref_keyframe_2k.json` | 2048×1152 | 参考图驱动剧情关键帧 |
| `qwen_refine_upscale_2k.json` | 2048×1152 | 首图高分修复、细节重绘 |

## Qwen 工作流推荐顺序

- 纯文本角色、场景、道具：
  `qwen_t2i_asset_2k.json` -> `qwen_refine_upscale_2k.json`
- 参考图关键帧：
  `qwen_t2i_multiref_keyframe_2k.json` -> `qwen_refine_upscale_2k.json`

## Qwen 依赖模型

下载脚本（ModelScope 源）：

```bash
python3 pipelines/ComfyUI/scripts/download_qwen_image_models.py
```

默认会下载这些文件到 `t2i_models/qwen/`：

- `qwen/diffusion_models/qwen_image_2512_fp8_e4m3fn.safetensors`
- `qwen/diffusion_models/qwen_image_edit_2511_bf16.safetensors`
- `qwen/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors`
- `qwen/vae/qwen_image_vae.safetensors`

可选 lightning LoRA：

```bash
python3 pipelines/ComfyUI/scripts/download_qwen_image_models.py --model lightning
```

模型搜索路径示例见：
- `extra_model_paths.yaml`
- `t2i_path.txt`

## 节点架构

```
[文本编码]                  [参考图 Redux]              [生成]
DualCLIPLoader ─┐            CLIPVisionLoader           UNETLoader
  ├→CLIPTextEncode(+)        LoadImage(char_5view)      VAELoader
  └→CLIPTextEncode(-)          →ImageScale              EmptyLatentImage
                ↓              →CLIPVisionEncode         KSampler
           StyleModelApply       →StyleModelApply(+)       →VAEDecode
              (char ref)                                   →SaveImage
                ↓                                       
           StyleModelApply    
              (scene ref)      [ControlNet]
                ↓              LoadImage(canny_ref)
           ControlNetApply       →Canny
              (canny)           ControlNetLoader
```

## 输入说明

拖入工作流后，需要设置以下 **LoadImage** 节点：

| 节点 | 图片 | 说明 |
|------|------|------|
| `LoadImage` (char) | `assets/characters/{id}/{variant}/5view_2k.jpg` | 角色 5 视图参考图 |
| `LoadImage` (scene) | `assets/scenes/{scene_id}/grid.jpg` | 场景参考图 |
| `LoadImage` (canny) | 起始关键帧或参考结构图 | 用于 Canny 边缘检测 |

## 提示词编辑

- `CLIPTextEncode` (positive)：修改正面提示词，描述镜头内容、角色、动作、氛围
- `CLIPTextEncode` (negative)：负面提示词（默认已包含常见负面词）
- **建议格式**：`[shot description], [character appearance], [scene description], 国漫3D风格, PBR材质, 电影级布光`

Qwen 路线建议：

- 资产图：强调主体、材质、边缘、背景要求
- 关键帧：强调镜头、动作、构图、灯光，不要重复写过多身份细节
- refine：强调“保持构图不变，只提升脸部、服装、发丝、材质细节”

## 参考图强度调整

- `StyleModelApply` (char)：`strength` 参数（默认 1.0），控制角色参考权重
- `StyleModelApply` (scene)：`strength` 参数（默认 0.6），控制场景参考权重
- `ControlNetApply`：`strength` 参数（默认 0.7），控制 Canny 结构约束强度

## LoRA 扩展

如需叠加角色面部 LoRA（如 `chenmo_face_v1.safetensors`），在 `KSampler` 前面添加：
1. `LoRALoader`：加载 LoRA 文件
2. 将 LoRA 输出的 MODEL 连接到 KSampler 的 model 输入

LoRA 文件放到 `models/loras/` 目录。

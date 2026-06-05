# T2I — 本地文生图工作流

当前推荐按两类需求使用：

- 原生生成：
  不依赖参考图，从零生成角色、场景、道具的 canonical base
- 参考生成：
  基于已有参考图生成角色阶段变体、场景变体、道具变体，以及多元素关键帧

## 文件

| 文件 | 分辨率 | 适用场景 |
|------|--------|---------|
| `flux_multiref_1024.json` | 1024×576 (16:9) | 轻量生成，快速迭代 |
| `scene_view_controlled_1024.json` | 1024×576 | 基于 control image 的可控视角场景派生 |
| `flux_scene_multiview_guided_1024.json` | 1024×576 | Legacy：早期 Flux 场景参考派生，不再推荐 |
| `qwen_character_base_2k.json` | 2048×2048 / 2048×1152 | 原生角色主资产生成 |
| `qwen_scene_base_2k.json` | 2048×1152 | 原生场景主资产生成 |
| `qwen_prop_base_2k.json` | 2048×1152 | 原生道具主资产生成 |
| `qwen_character_ref_variant_2k.json` | 2048×2048 / 2048×1152 | 基于角色主资产生成阶段/造型变体 |
| `qwen_scene_ref_variant_1024.json` | 1024×576 | Legacy：Qwen Edit 版场景变体，不推荐继续用于改视角 |
| `qwen_prop_ref_variant_1024.json` | 1024×576 | 基于道具主资产生成视角/状态变体 |
| `qwen_keyframe_multiref_1024.json` | 1024×576 | 多参考图关键帧生成 |
| `qwen_refine_upscale_2k.json` | 2048×1152 | 首图高分修复、细节重绘 |
| `qwen_t2i_asset_2k.json` | 2048×1152 | Legacy：展开版原始 Qwen 资产流 |
| `qwen_t2i_asset_batch_2k.json` | 2048×1152 | Legacy：精简批处理资产流 |

## Qwen 工作流推荐顺序

- 原生角色：
  `qwen_character_base_2k.json`
- 原生场景：
  `qwen_scene_base_2k.json`
- 场景可控视角新图：
  `scene_view_controlled_1024.json`
- 原生道具：
  `qwen_prop_base_2k.json`
- 角色阶段/造型变体：
  `qwen_character_ref_variant_2k.json`
- 道具视角/状态变体：
  `qwen_prop_ref_variant_1024.json`
- 多元素关键帧：
  `qwen_keyframe_multiref_1024.json`
- 高分修复：
  `qwen_refine_upscale_2k.json`

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

如需使用 `scene_view_controlled_1024.json`，除了基础模型外，还需要：

- `z_image/diffusion_models/z_image_turbo_bf16.safetensors`
- `z_image/text_encoders/qwen_3_4b.safetensors`
- `z_image/model_patches/Z-Image-Turbo-Fun-Controlnet-Union.safetensors`
- `z_image/vae/ae.safetensors`

可直接使用：

```bash
python3 pipelines/ComfyUI/scripts/download_t2i_models.py --category flux
```

该命令会下载 Z-Image-Turbo 所需文件到：

- `z_image/diffusion_models/`
- `z_image/text_encoders/`
- `z_image/model_patches/`
- `z_image/vae/`

在服务器上正式测试前，可先执行：

```bash
python3 pipelines/ComfyUI/scripts/check_scene_view_controlled_workflow.py
python3 pipelines/ComfyUI/scripts/check_scene_view_controlled.py
```

若两个检查都输出 `PASS`，再重启 ComfyUI 并测试 workflow。

测试时重点确认 workflow 中标题为 `Z-Image Model Patch Loader` 的节点下拉里能看到：

- `Z-Image-Turbo-Fun-Controlnet-Union.safetensors`

## 使用建议

- `base` 工作流只负责定义“身份”
  - 人物：脸、体型、服装
  - 场景：空间布局、光照、地标物件
  - 道具：结构、材质、磨损
- `ref_variant` 工作流只负责定义“变化”
  - 不要重写全量身份
  - 只写阶段变化、视角变化、天气变化、状态变化
- `keyframe_multiref` 负责组合多个已有资产
  - `character_ref`
  - `scene_ref`
  - `prop_ref`
  - 可选 `structure_ref`

## 提示词编辑

- `base`：
  写清楚主体身份，不要要求一次输出多机位拼板
- `ref_variant`：
  prompt 只写变化项，不写完整身份设定
- `keyframe_multiref`：
  prompt 只写镜头内容、动作、构图、光照和情绪，不重写角色脸和场景世界观

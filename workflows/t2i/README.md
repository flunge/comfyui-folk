# T2I — Flux 文生图工作流

基于 Flux.1-dev + Redux + ControlNet 的本地文生图管线，替代 SoCheap API。

## 文件

| 文件 | 分辨率 | 适用场景 |
|------|--------|---------|
| `flux_multiref_1024.json` | 1024×576 (16:9) | 轻量生成，快速迭代 |
| `flux_multiref_2048.json` | 2048×1152 (16:9) | 高质量输出，关键帧级 |

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

## 参考图强度调整

- `StyleModelApply` (char)：`strength` 参数（默认 1.0），控制角色参考权重
- `StyleModelApply` (scene)：`strength` 参数（默认 0.6），控制场景参考权重
- `ControlNetApply`：`strength` 参数（默认 0.7），控制 Canny 结构约束强度

## LoRA 扩展

如需叠加角色面部 LoRA（如 `chenmo_face_v1.safetensors`），在 `KSampler` 前面添加：
1. `LoRALoader`：加载 LoRA 文件
2. 将 LoRA 输出的 MODEL 连接到 KSampler 的 model 输入

LoRA 文件放到 `models/loras/` 目录。

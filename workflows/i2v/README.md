# I2V — WAN 图生视频工作流

基于 Wan2.2 I2V-A14B（双模型分阶段采样）的多帧参考图生视频管线。

## 文件

| 文件 | 分辨率 | FPS | 帧数 | 时长 | 适用 |
|------|--------|-----|------|------|------|
| `wan_i2v_multiframe_multiref_480p.json` | 832×480 | 16 | 81 | ~5s | 默认配置，显存友好 |
| `wan_i2v_multiframe_multiref_720p.json` | 1280×720 | 24 | 81 | ~3.4s | 高质量，需更大显存 |

## 节点架构

```
[模型加载]                  [多帧 I2V 条件]           [ControlNet]
WanVideoModelLoader(HIGH)    LoadImage(start)          LoadImage(start)
  →WanVideoSetBlockSwap        →ImageResize              →MiDaS Depth
  →WanVideoSetLoRAs          LoadImage(end)             →WanVideoControlnet
WanVideoModelLoader(LOW)       →ImageResize                    ↓
  →WanVideoSetBlockSwap      LoadImage(mid)          [采样+解码]
  →WanVideoSetLoRAs            →WanVideoEncode        WanVideoSampler(LOW)
WanVideoVAELoader              →extra_latents            →WanVideoDecode
LoadWanVideoT5TextEncoder    LoadImage(char_5view)       →VHS_VideoCombine(MP4)
  →WanVideoTextEncode          →WanVideoEncode
Positive/Negative              →add_cond_latents
                              LoadImage(scene_grid)
                                →WanVideoEncode
  WanVideoImageToVideoEncode    →add_cond_latents
    (vae, start, end, extra_latents, add_cond_latents)
    →image_embeds → Sampler
```

## 多帧参考输入

每个 `LoadImage` 节点需要设置以下图片路径：

| 节点 | 图片来源 | 作用 | 必要性 |
|------|---------|------|--------|
| `start_keyframe.png` | SoCheap/Flux 生成的首帧 | 定义视频第一帧全部内容 | **必须** |
| `end_keyframe.png` | SoCheap/Flux 生成的尾帧 | 定义视频最后一帧 | 可选（断开连接可禁用） |
| `mid_keyframe.png` | 中间关键帧 | 帧序列中间点的视觉约束 | 可选 |
| `char_5view.jpg` | `assets/characters/{id}/{variant}/5view_2k.jpg` | 角色面部/服装一致性 | **推荐** |
| `scene_grid.jpg` | `assets/scenes/{scene_id}/grid.jpg` | 场景空间/灯光风格 | **推荐** |

## 提示词编辑

`WanVideoTextEncode` 节点包含两个文本框：
- 第一行：**正面提示词** — 描述视频内容、动作、风格
  - 建议格式：`[动作描述], [角色互动], [场景氛围], 国漫3D风格, 电影级运镜`
- 第二行：**负面提示词** — 避免的内容（默认已提供）

## 参数调优

| 节点 | 参数 | 默认值 | 说明 |
|------|------|--------|------|
| `WanVideoImageToVideoEncode` | noise_aug_strength | 0.03 | 噪声强度，越高运动越大 |
| `WanVideoImageToVideoEncode` | latent_strength | 1.0 | 参考帧强度 |
| `WanVideoControlnet` | strength | 1.0 | ControlNet 深度约束强度 |
| `WanVideoControlnet` | stride | 3 | 每隔多少帧应用一次 CN |
| `WanVideoSampler` | steps | 30 | 采样步数（质量↑速度↓） |
| `WanVideoSampler` | cfg | 5.0 | 分类器引导强度 |

## 注意事项

1. **显存管理**：480p 工作流约需 20-24GB VRAM；720p 约需 32-40GB
2. **首帧质量决定视频质量**：首帧必须清晰且构图完整
3. **动作幅度**：通过 `noise_aug_strength` 控制——0.01 几乎不动，0.1 大幅运动
4. **多帧约束**：start/end 帧差异越大，中间帧的 interpolation 越有挑战

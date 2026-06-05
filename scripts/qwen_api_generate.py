#!/usr/bin/env python3
"""
Qwen ComfyUI 纯 Python API 生图脚本
直接在 A100 上运行，不走 HTTP 协议
用法:
  source venv/bin/activate
  python scripts/qwen_api_generate.py --prompt "..." --output /path/to/output.png [--turbo]
"""
import argparse, json, os, sys, uuid, time
from pathlib import Path

# 添加 ComfyUI 到 sys.path
COMFY_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(COMFY_ROOT))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True, help="生图 prompt 文本")
    parser.add_argument("--output", required=True, help="输出 PNG 路径")
    parser.add_argument("--turbo", action="store_true", help="启用 4 步 Lightning 加速")
    parser.add_argument("--width", type=int, default=2048)
    parser.add_argument("--height", type=int, default=2048)
    args = parser.parse_args()

    # 动态导入 ComfyUI 组件
    # 必须先设置 ComfyUI 根目录
    os.chdir(str(COMFY_ROOT))

    import folder_paths
    import nodes as comfy_nodes
    import comfy.model_management as mm

    # 从工作流 JSON 加载节点配置
    wf_path = COMFY_ROOT / "workflows/t2i/qwen_character_base_2k.json"
    wf = json.loads(wf_path.read_text())

    # 找到子图并提取节点
    proxy = [n for n in wf["nodes"] if n["id"] == 2][0]
    sg = wf["definitions"]["subgraphs"][0]
    sg_nodes = sg["nodes"]
    sg_links = sg["links"]

    # Proxy widget values
    p_wv = proxy["widgets_values"]
    enable_turbo = args.turbo or p_wv[3]

    # 构建 API prompt 格式
    # 节点 ID 映射: subgraph 内部节点直接纳入
    api_prompt = {}

    for n in sg_nodes:
        nid = str(n["id"])
        nt = n["type"]
        wv = n.get("widgets_values", [])
        inputs = {}

        # 对每个 input 处理
        for inp in n.get("inputs", []):
            link_id = inp.get("link")
            if link_id is not None:
                # 找 source
                for l in sg_links:
                    if l[0] == link_id:
                        _, src_nid, src_slot, _, _, _ = l
                        inputs[inp["name"]] = [str(src_nid), src_slot]
                        break

        # widget values → inputs（根据节点类型映射）
        if nt == "CLIPTextEncode":
            if n["id"] == 249:
                inputs["text"] = args.prompt
            elif n["id"] == 250:
                inputs["text"] = wv[0] if wv else ""
        elif nt == "KSampler":
            inputs["seed"] = p_wv[4]  # seed from proxy
            inputs["steps"] = 4 if enable_turbo else wv[0] if len(wv) > 0 else 50
            inputs["cfg"] = 1.0 if enable_turbo else (wv[1] if len(wv) > 1 else 4.0)
            inputs["sampler_name"] = wv[2] if len(wv) > 2 else "euler"
            inputs["scheduler"] = wv[3] if len(wv) > 3 else "simple"
            inputs["denoise"] = wv[4] if len(wv) > 4 else 1.0
        elif nt == "UNETLoader":
            inputs["unet_name"] = p_wv[5]
            inputs["weight_dtype"] = "default"
        elif nt == "CLIPLoader":
            inputs["clip_name"] = p_wv[6] if n["id"] == 245 else wv[0] if wv else ""
            inputs["type"] = "qwen_image"
            inputs["device"] = "default"
        elif nt == "VAELoader":
            inputs["vae_name"] = p_wv[7]
        elif nt == "EmptySD3LatentImage":
            inputs["width"] = args.width
            inputs["height"] = args.height
            inputs["batch_size"] = 1
        elif nt == "ModelSamplingAuraFlow":
            inputs["shift"] = wv[0] if wv else 3.1
        elif nt == "LoraLoaderModelOnly":
            inputs["lora_name"] = p_wv[8]
            inputs["strength_model"] = wv[1] if len(wv) > 1 else 1.0
            # 还需要 model 输入（来自 switch）
        elif nt == "ComfySwitchNode":
            inputs["on_false"] = [str(n["id"] - 100), 0]  # 简化: 后续修复
            inputs["on_true"] = [str(n["id"] + 100), 0]
            inputs["switch"] = enable_turbo

        api_prompt[nid] = {"class_type": nt, "inputs": inputs}

    # 注入缺少的输入
    # Switch 节点比较特殊，需要连接正确
    # 对于简单的非 turbo 模式: 直接连 original model
    # 简化: 使用 ComfyUI 的 GraphBuilder 或直接执行
    
    print(f"Built API prompt with {len(api_prompt)} nodes")
    print(f"Enable turbo: {enable_turbo}")

    # 现在通过 ComfyUI 执行
    from execution import validate_prompt
    import asyncio

    prompt_id = str(uuid.uuid4())

    async def run():
        valid = await validate_prompt(prompt_id, api_prompt, None)
        if not valid[0]:
            print(f"Validation error: {valid[1]}")
            return False
        
        print(f"Validation OK, queueing...")
        from server import PromptServer
        server = PromptServer.instance
        # 获取 outputs_to_execute
        outputs_to_execute = valid[2]
        server.prompt_queue.put((float(0), prompt_id, api_prompt, {}, outputs_to_execute, {}))
        
        # 等待完成
        timeout = 120 if not enable_turbo else 30
        start = time.time()
        while time.time() - start < timeout:
            status = server.prompt_queue.get_status()
            if prompt_id not in status:
                # 检查是否已完成
                history = server.prompt_queue.get_history()
                if prompt_id in history:
                    entry = history[prompt_id]
                    outputs = entry.get("outputs", {})
                    for nid, node_out in outputs.items():
                        for key, imgs in node_out.items():
                            if isinstance(imgs, list):
                                for img in imgs:
                                    if isinstance(img, dict) and "filename" in img:
                                        output_dir = folder_paths.get_output_directory()
                                        img_path = os.path.join(output_dir, img.get("subfolder",""), img["filename"])
                                        print(f"Output: {img_path}")
                                        # 复制到最终路径
                                        os.makedirs(os.path.dirname(args.output), exist_ok=True)
                                        import shutil
                                        shutil.copy2(img_path, args.output)
                                        print(f"Saved to: {args.output}")
                                        return True
                    print(f"No images found in outputs: {json.dumps(outputs, default=str)[:300]}")
                    return False
                await asyncio.sleep(0.5)
            else:
                await asyncio.sleep(0.5)
        
        print("Timeout waiting for generation")
        return False

    asyncio.run(run())

if __name__ == "__main__":
    main()

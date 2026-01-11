#!/usr/bin/env python3
"""
测试脚本：从压缩文件中提取图片，使用新的提示词进行裁切

功能：
1. 解压指定的压缩文件
2. 转换图片为jpg格式
3. 生成预览图
4. 使用新的提示词调用模型获取裁切坐标
5. 执行裁切
6. 输出结果到指定目录
"""

import os
import argparse
import zipfile
import base64
from PIL import Image as PILImage
from pathlib import Path
from typing import List
import json
import httpx

# 添加项目根目录到Python路径
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
import sys
sys.path.insert(0, ROOT_DIR)

from app.services.image_processing import generate_preview, crop_from_prompt
from app.services.model_client import ModelClient

def extract_zip(zip_path: str, output_dir: str) -> List[str]:
    """解压压缩文件"""
    extracted_files = []
    
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        # 检查并避免zip slip攻击
        for member in zip_ref.infolist():
            if member.filename.startswith("../") or "..\\" in member.filename:
                continue
            if member.is_dir():
                continue
            
            # 提取文件
            zip_ref.extract(member, output_dir)
            extracted_files.append(os.path.join(output_dir, member.filename))
    
    return extracted_files

def convert_to_jpg(image_path: str, output_dir: str) -> str:
    """将图片转换为jpg格式"""
    with PILImage.open(image_path) as img:
        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Generate output path
        filename = os.path.basename(image_path)
        name, _ = os.path.splitext(filename)
        output_path = os.path.join(output_dir, f"{name}.jpg")
        
        # Save as jpg
        img.save(output_path, quality=95, optimize=True)
        
        return output_path

def get_image_files(files: List[str]) -> List[str]:
    """从文件列表中筛选图片文件"""
    image_exts = [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"]
    image_files = []
    
    for file_path in files:
        if os.path.isfile(file_path):
            ext = os.path.splitext(file_path.lower())[1]
            if ext in image_exts:
                image_files.append(file_path)
    
    return image_files

def process_zip_file(zip_path: str, output_dir: str, api_key: str, base_url: str, model: str):
    """处理压缩文件中的所有图片"""
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 创建子目录
    unpack_dir = os.path.join(output_dir, "unpack")
    jpg_dir = os.path.join(output_dir, "jpg")
    preview_dir = os.path.join(output_dir, "previews")
    crop_dir = os.path.join(output_dir, "crops")
    
    for d in [unpack_dir, jpg_dir, preview_dir, crop_dir]:
        os.makedirs(d, exist_ok=True)
    
    # 解压压缩文件
    print(f"解压压缩文件: {os.path.basename(zip_path)}")
    extracted_files = extract_zip(zip_path, unpack_dir)
    print(f"  解压完成，共提取 {len(extracted_files)} 个文件")
    
    # 获取所有图片文件
    image_files = get_image_files(extracted_files)
    if not image_files:
        print(f"未在压缩文件中找到图片文件")
        return
    
    print(f"找到 {len(image_files)} 张图片")
    
    # 创建模型客户端
    model_client = ModelClient(
        api_key=api_key,
        base_url=base_url,
        model=model
    )
    
    # 定义新的裁切提示词
    crop_prompt = """Return ONLY one-line JSON. No markdown/backticks/extra text.

Goal: square crop for 1024x1024 training.
Priority: NEVER cut the head (hair/hat/ornaments fully inside) even if it reduces margin. If head is near an edge, let the crop touch that edge rather than cutting hair.

Coords normalized [0,1] in ORIGINAL image.

Rules:
1) Output subject_bbox, head_bbox (full hair), upper_body_bbox (may be null).
2) shot_type=medium: crop_square MUST fully contain head_bbox and upper_body_bbox (if present). Legs may be outside.
3) Head margin target: >=0.1 * crop_side, but if margin and full-head conflict, keep full head first.
4) Maximize crop_square.side; only shrink if needed to keep head+upper_body with required/possible margin.
5) If near-square and best crop ≈ whole image, set crop_square.side=1.0.
6) If no clear face/head OR subject too blurry/bokeh -> usable=false and set reject_reason.

Output schema:
{
  "subject_bbox": {"x1":0,"y1":0,"x2":1,"y2":1},
  "head_bbox": {"x1":0,"y1":0,"x2":1,"y2":1} | null,
  "upper_body_bbox": {"x1":0,"y1":0,"x2":1,"y2":1} | null,
  "crop_square": {"cx":0.5,"cy":0.5,"side":1.0},
  "shot_type": "closeup|medium|long",
  "confidence": 0.0,
  "usable": true|false,
  "reject_reason": "too_blurry|subject_not_clear|no_head_bbox|other" | null,
  "reason": "short"
}"""
    
    # 处理每张图片
    for i, image_path in enumerate(image_files):
        print(f"\n处理第 {i+1}/{len(image_files)}: {os.path.basename(image_path)}")

        jpg_path = convert_to_jpg(image_path, jpg_dir)
        print(f"  转换为jpg: {os.path.basename(jpg_path)}")

        preview_path = generate_preview(jpg_path, preview_dir, max_side=1200, quality=86)
        print(f"  生成预览: {os.path.basename(preview_path)}")

        print("  调用模型获取裁切坐标...")

        with open(preview_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode("utf-8")

        messages = [
            {
                "role": "system",
                "content": "You are a professional image analyst. Focus on identifying the main subject and recommending optimal crop coordinates based on the given constraints."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": crop_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                ]
            }
        ]

        try:
            response = model_client._call_model(messages)
            print(f"  模型响应: {response}")
            prompt_result = json.loads(response)

            usable = prompt_result.get("usable", True)
            reject_reason = prompt_result.get("reject_reason")
            if not usable:
                print(f"  标记为不可用，原因: {reject_reason}. 跳过保存。")
                continue

            crop_path = crop_from_prompt(jpg_path, prompt_result, crop_dir, quality=95)
            print(f"  生成裁切图: {os.path.basename(crop_path)}")

        except Exception as e:
            print(f"  处理失败: {type(e).__name__}: {str(e)}")
            print("  标记为不可用，跳过保存。")
            continue
    
    print(f"\n处理完成！结果保存在: {output_dir}")
    print(f"  解压文件: {unpack_dir}")
    print(f"  JPG图片: {jpg_dir}")
    print(f"  预览图片: {preview_dir}")
    print(f"  裁切图片: {crop_dir}")

def main():
    parser = argparse.ArgumentParser(description="从压缩文件中提取图片，使用新的提示词进行裁切")
    parser.add_argument("--zip-path", required=True, help="输入压缩文件路径")
    parser.add_argument("--output-dir", required=True, help="输出目录路径")
    parser.add_argument("--api-key", default="ms-cf491dd9-d8ee-4837-84a7-35c91778d589", help="ModelScope API Key")
    parser.add_argument("--base-url", default="https://api-inference.modelscope.cn/v1/", help="API服务地址")
    parser.add_argument("--model", default="Qwen/Qwen3-VL-30B-A3B-Instruct", help="使用的模型")
    
    args = parser.parse_args()
    
    # 验证输入压缩文件是否存在
    if not os.path.isfile(args.zip_path):
        print(f"错误：输入压缩文件 {args.zip_path} 不存在")
        return 1
    
    # 处理压缩文件
    process_zip_file(args.zip_path, args.output_dir, args.api_key, args.base_url, args.model)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

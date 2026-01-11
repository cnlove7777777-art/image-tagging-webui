#!/usr/bin/env python3
"""
测试提示词裁切功能的脚本

功能：
1. 选择文件夹
2. 将图片转换为jpg
3. 使用提示词进行裁切
4. 返回本地处理后的图片
"""

import os
import argparse
from PIL import Image as PILImage
from pathlib import Path
from typing import List

# 添加项目根目录到Python路径
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
import sys
sys.path.insert(0, ROOT_DIR)

from app.services.image_processing import generate_preview, crop_from_prompt
from app.services.model_client import ModelClient

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

def get_image_files(folder_path: str) -> List[str]:
    """获取文件夹中的所有图片文件"""
    image_exts = [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"]
    image_files = []
    
    for file in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file)
        if os.path.isfile(file_path):
            ext = os.path.splitext(file.lower())[1]
            if ext in image_exts:
                image_files.append(file_path)
    
    return image_files

def process_folder(input_folder: str, output_folder: str, api_key: str, base_url: str, model: str):
    """处理文件夹中的所有图片"""
    # 创建输出目录
    os.makedirs(output_folder, exist_ok=True)
    
    # 创建子目录
    jpg_dir = os.path.join(output_folder, "jpg")
    preview_dir = os.path.join(output_folder, "previews")
    crop_dir = os.path.join(output_folder, "crops")
    
    for d in [jpg_dir, preview_dir, crop_dir]:
        os.makedirs(d, exist_ok=True)
    
    # 获取所有图片文件
    image_files = get_image_files(input_folder)
    if not image_files:
        print(f"未在文件夹 {input_folder} 中找到图片文件")
        return
    
    print(f"找到 {len(image_files)} 张图片")
    
    # 创建模型客户端
    model_client = ModelClient(
        api_key=api_key,
        base_url=base_url,
        model=model
    )
    
    # 定义裁切提示词
    crop_prompt = """Return ONLY one-line JSON. No markdown, no backticks, no extra text. 
 
 Task: Recommend a square crop for 1024x1024 training. IMPORTANT: choose the LARGEST possible crop_square that still satisfies the constraints, so that the crop preserves as much original detail/context as possible. Prefer crop_square.side close to 1.0. 
 
 Coordinates are normalized [0,1] in ORIGINAL image. 
 
 Hard constraints: 
 1) Always output subject_bbox, head_bbox (include hair/hat/ornaments), upper_body_bbox (head+torso+hands if visible; may be null). 
 2) shot_type == "medium": crop_square MUST fully contain head_bbox AND upper_body_bbox (if upper_body_bbox is not null). Legs may be outside. 
 3) Keep head away from crop edges: if head_bbox exists, min margin >= 0.1 * crop_side (10% of crop size) is REQUIRED. 
 4) Among all crops that satisfy the above, maximize crop_square.side (largest possible). Only reduce side if needed to keep required bboxes inside and keep head margin. 
 5) If the image is already close to square and the best crop is basically the whole image, set crop_square.side=1.0 and center appropriately. 
 6) Evaluate image quality: if the main subject is too blurry, out of focus, or not clearly visible, mark as not usable. 
 
 Output schema: 
 { 
   "subject_bbox": {"x1":0.0,"y1":0.0,"x2":1.0,"y2":1.0}, 
   "head_bbox": {"x1":0.0,"y1":0.0,"x2":1.0,"y2":1.0} | null, 
   "upper_body_bbox": {"x1":0.0,"y1":0.0,"x2":1.0,"y2":1.0} | null, 
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
        
        # 转换为jpg
        jpg_path = convert_to_jpg(image_path, jpg_dir)
        print(f"  转换为jpg: {os.path.basename(jpg_path)}")
        
        # 生成预览图
        preview_path = generate_preview(jpg_path, preview_dir, max_side=1200, quality=86)
        print(f"  生成预览: {os.path.basename(preview_path)}")
        
        # 调用模型获取裁切坐标
        print("  调用模型获取裁切坐标...")
        
        # 创建模型调用消息
        messages = [
            {
                "role": "system",
                "content": "You are a professional image analyst. Focus on identifying the main subject and recommending optimal crop coordinates."
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": crop_prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"file://{preview_path}"
                        }
                    }
                ]
            }
        ]
        
        try:
            # 调用模型
            response = model_client._call_model(messages)
            print(f"  模型响应: {response}")
            
            # 解析响应
            import json
            prompt_result = json.loads(response)
            
            # 执行裁切
            crop_path = crop_from_prompt(jpg_path, prompt_result, crop_dir, quality=95)
            print(f"  生成裁切图: {os.path.basename(crop_path)}")
            
        except Exception as e:
            print(f"  处理失败: {str(e)}")
            continue
    
    print(f"\n处理完成！结果保存在: {output_folder}")
    print(f"  JPG图片: {jpg_dir}")
    print(f"  预览图片: {preview_dir}")
    print(f"  裁切图片: {crop_dir}")

def main():
    parser = argparse.ArgumentParser(description="测试提示词裁切功能")
    parser.add_argument("--input", required=True, help="输入文件夹路径")
    parser.add_argument("--output", default="./test_output", help="输出文件夹路径")
    parser.add_argument("--api-key", required=True, help="ModelScope API Key")
    parser.add_argument("--base-url", default="https://api-inference.modelscope.cn/v1/", help="API服务地址")
    parser.add_argument("--model", default="Qwen/Qwen3-VL-30B-A3B-Instruct", help="使用的模型")
    
    args = parser.parse_args()
    
    # 验证输入文件夹是否存在
    if not os.path.isdir(args.input):
        print(f"错误：输入文件夹 {args.input} 不存在")
        return 1
    
    # 处理文件夹
    process_folder(args.input, args.output, args.api_key, args.base_url, args.model)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

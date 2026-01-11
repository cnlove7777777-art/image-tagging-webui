import os
import sys
import zipfile
import shutil
from typing import List
from PIL import Image, ImageOps

# 添加后端目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.dedup_people import (
    extract_features,
    cluster,
    pick_kept,
    ImageMeta
)

def unzip_file(zip_path: str, extract_dir: str) -> None:
    """解压zip文件到指定目录"""
    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir)
    os.makedirs(extract_dir, exist_ok=True)
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
    
    print(f"已解压 {zip_path} 到 {extract_dir}")

def get_image_paths(input_dir: str) -> List[str]:
    """获取目录中所有图片路径"""
    exts = {'.jpg', '.jpeg', '.png', '.webp'}
    paths = []
    for root, _, files in os.walk(input_dir):
        for name in files:
            if os.path.splitext(name.lower())[1] in exts:
                paths.append(os.path.join(root, name))
    return sorted(paths)

def copy_kept_images(kept_indices: List[int], all_paths: List[str], output_dir: str) -> None:
    """将保留的图片复制到输出目录"""
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    for idx in kept_indices:
        src_path = all_paths[idx]
        filename = os.path.basename(src_path)
        dst_path = os.path.join(output_dir, filename)
        shutil.copy2(src_path, dst_path)
    
    print(f"已将 {len(kept_indices)} 张去重后的图片保存到 {output_dir}")

def main():
    # 配置参数
    zip_file_path = r"E:\OneDrive\桌面\automatic\lora-dataset-builder\测试图片集.zip"
    extract_dir = os.path.join(os.path.dirname(zip_file_path), "extracted_images")
    output_dir = os.path.join(os.path.dirname(zip_file_path), "dedup_result")
    
    # 解压zip文件
    print(f"正在解压 {zip_file_path}...")
    unzip_file(zip_file_path, extract_dir)
    
    # 获取所有图片路径
    print("正在获取图片路径...")
    image_paths = get_image_paths(extract_dir)
    print(f"共找到 {len(image_paths)} 张图片")
    
    if not image_paths:
        print("没有找到图片，程序退出")
        return
    
    # 提取特征
    print("正在提取图片特征...")
    features = extract_features(
        image_paths,
        max_side_analysis=1024,
        max_side_small=512,
        min_pose_conf=0.35,
        max_workers=4
    )
    
    # 聚类
    print("正在进行图片聚类...")
    clusters = cluster(features)
    print(f"共生成 {len(clusters)} 个聚类")
    
    # 选择保留的图片
    print("正在选择保留的图片...")
    kept_indices = pick_kept(clusters, features, keep_per_cluster=2)
    print(f"共选择保留 {len(kept_indices)} 张图片")
    
    # 复制保留的图片到输出目录
    print("正在保存去重结果...")
    copy_kept_images(kept_indices, image_paths, output_dir)
    
    # 清理临时目录
    print("正在清理临时文件...")
    shutil.rmtree(extract_dir)
    
    print("去重任务完成!")
    print(f"去重结果保存在: {output_dir}")
    print(f"输入图片数量: {len(image_paths)}")
    print(f"输出图片数量: {len(kept_indices)}")
    print(f"去重率: {((len(image_paths) - len(kept_indices)) / len(image_paths) * 100):.1f}%")

if __name__ == "__main__":
    main()

import os
import numpy as np
from PIL import Image as PILImage, ImageOps
import imagehash
from typing import List, Dict


def calculate_sharpness(image: PILImage.Image) -> float:
    """Calculate image sharpness using Laplacian variance"""
    # Convert to grayscale
    gray = ImageOps.grayscale(image)
    # Convert to numpy array
    array = np.array(gray)
    # Calculate Laplacian variance
    laplacian = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]])
    sharpness = np.var(np.convolve(array.flatten(), laplacian.flatten(), mode='same'))
    return float(sharpness)


def generate_preview(image_path: str, output_dir: str, max_side: int = 1200, quality: int = 86) -> str:
    """Generate preview image with max side"""
    with PILImage.open(image_path) as img:
        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Calculate new size while maintaining aspect ratio
        width, height = img.size
        if width > height:
            new_width = max_side
            new_height = int((height / width) * max_side)
        else:
            new_height = max_side
            new_width = int((width / height) * max_side)
        
        # Resize with high quality
        img = img.resize((new_width, new_height), PILImage.LANCZOS)
        
        # Generate output path
        filename = os.path.basename(image_path)
        name, ext = os.path.splitext(filename)
        output_path = os.path.join(output_dir, f"{name}_preview.jpg")
        
        # Save with specified quality
        img.save(output_path, quality=quality, optimize=True, progressive=True)
        
        return output_path


def crop_1024_from_original(image_path: str, x: float, y: float, output_dir: str, quality: int = 95) -> str:
    """Crop 1024x1024 square from original image, centered at (x,y)"""
    with PILImage.open(image_path) as img:
        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        width, height = img.size
        crop_size = min(width, height)
        
        # Calculate crop coordinates
        center_x = int(x * width)
        center_y = int(y * height)
        
        # Calculate crop box with boundary checks
        half_size = crop_size // 2
        left = max(0, center_x - half_size)
        top = max(0, center_y - half_size)
        right = min(width, center_x + half_size)
        bottom = min(height, center_y + half_size)
        
        # If crop box is not square, adjust
        if right - left != bottom - top:
            current_size = min(right - left, bottom - top)
            half_size = current_size // 2
            left = center_x - half_size
            top = center_y - half_size
            right = center_x + half_size
            bottom = center_y + half_size
            
            # Ensure within bounds
            if left < 0:
                left = 0
                right = current_size
            if right > width:
                right = width
                left = width - current_size
            if top < 0:
                top = 0
                bottom = current_size
            if bottom > height:
                bottom = height
                top = height - current_size
        
        # Crop image
        cropped = img.crop((left, top, right, bottom))
        
        # Resize to 1024x1024
        cropped = cropped.resize((1024, 1024), PILImage.LANCZOS)
        
        # Generate output path
        filename = os.path.basename(image_path)
        name, ext = os.path.splitext(filename)
        output_path = os.path.join(output_dir, f"{name}_crop.jpg")
        
        # Save with specified quality
        cropped.save(output_path, quality=quality, optimize=True, progressive=True)
        
        return output_path


def cluster_keep_topk(images: list, threshold: int = 6, keep_k: int = 2) -> list:
    """Cluster images by pHash and keep top K per cluster by sharpness"""
    clusters = []
    
    for image in images:
        phash = image["phash"]
        sharpness = image["sharpness"]
        
        # Try to find existing cluster
        found = False
        for cluster in clusters:
            # Calculate Hamming distance to cluster representative
            cluster_phash = cluster[0]["phash"]
            distance = imagehash.hex_to_hash(phash) - imagehash.hex_to_hash(cluster_phash)
            
            if distance <= threshold:
                # Add to cluster
                cluster.append(image)
                found = True
                break
        
        if not found:
            # Create new cluster
            clusters.append([image])
    
    # Keep top K images per cluster by sharpness
    kept_images = []
    for cluster in clusters:
        # Sort by sharpness descending
        cluster.sort(key=lambda x: x["sharpness"], reverse=True)
        # Keep top K
        kept_images.extend(cluster[:keep_k])
    
    return kept_images

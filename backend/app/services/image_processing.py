import os
import numpy as np
from PIL import Image as PILImage, ImageOps
import imagehash


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


def crop_1024_from_original(
    image_path: str,
    x: float,
    y: float,
    output_dir: str,
    quality: int = 95,
    side: float = 1.0,
) -> str:
    """Crop 1024x1024 square from original image, centered at (x,y) with optional side ratio (0-1)."""
    with PILImage.open(image_path) as img:
        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        width, height = img.size
        base_size = min(width, height)
        side_ratio = max(0.05, min(1.0, side if side is not None else 1.0))
        crop_size = max(1, int(base_size * side_ratio))
        
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


def get_crop_coords_from_prompt(image_path: str, prompt_result: dict) -> dict:
    """
    Calculate crop coordinates based on prompt result.
    Returns normalized coordinates for 1024x1024 square crop.
    """
    with PILImage.open(image_path) as img:
        width, height = img.size
    
    # Extract subject bbox from prompt result
    subject_bbox = prompt_result.get("subject_bbox", {"x1": 0.0, "y1": 0.0, "x2": 1.0, "y2": 1.0})
    
    # Convert normalized bbox to pixel coordinates
    x1 = int(subject_bbox["x1"] * width)
    y1 = int(subject_bbox["y1"] * height)
    x2 = int(subject_bbox["x2"] * width)
    y2 = int(subject_bbox["y2"] * height)
    
    # Calculate subject dimensions
    subject_width = x2 - x1
    subject_height = y2 - y1
    
    # Calculate ideal crop size
    # Prefer keeping full body if visible
    min_crop_size = max(subject_width, subject_height)
    
    # Add padding to keep head away from edges
    # Rule: keep head region at least 0.1 of crop side away from edges
    padding = int(0.1 * min_crop_size)
    
    # Calculate initial center
    center_x = (x1 + x2) // 2
    center_y = (y1 + y2) // 2
    
    # Calculate crop box
    half_crop = min_crop_size // 2
    left = max(0, center_x - half_crop - padding)
    top = max(0, center_y - half_crop - padding)
    right = min(width, center_x + half_crop + padding)
    bottom = min(height, center_y + half_crop + padding)
    
    # Ensure crop is square
    current_crop_width = right - left
    current_crop_height = bottom - top
    final_crop_size = max(current_crop_width, current_crop_height)
    
    # Recalculate center to ensure square
    center_x = (left + right) // 2
    center_y = (top + bottom) // 2
    
    half_final_size = final_crop_size // 2
    left = max(0, center_x - half_final_size)
    top = max(0, center_y - half_final_size)
    right = min(width, center_x + half_final_size)
    bottom = min(height, center_y + half_final_size)
    
    # If crop exceeds image boundaries, adjust
    if right - left < final_crop_size:
        # Adjust left and right
        current_width = right - left
        delta = final_crop_size - current_width
        left = max(0, left - delta // 2)
        right = min(width, right + (delta - delta // 2))
    
    if bottom - top < final_crop_size:
        # Adjust top and bottom
        current_height = bottom - top
        delta = final_crop_size - current_height
        top = max(0, top - delta // 2)
        bottom = min(height, bottom + (delta - delta // 2))
    
    # Normalize coordinates
    norm_left = left / width
    norm_top = top / height
    norm_right = right / width
    norm_bottom = bottom / height
    
    # Calculate center and side for square crop
    norm_center_x = (norm_left + norm_right) / 2
    norm_center_y = (norm_top + norm_bottom) / 2
    norm_side = max(norm_right - norm_left, norm_bottom - norm_top)
    
    return {
        "subject_bbox": subject_bbox,
        "crop_square": {
            "cx": norm_center_x,
            "cy": norm_center_y,
            "side": norm_side
        },
        "shot_type": prompt_result.get("shot_type", "medium"),
        "confidence": prompt_result.get("confidence", 0.0),
        "reason": prompt_result.get("reason", "default crop")
    }


def crop_from_prompt(image_path: str, prompt_result: dict, output_dir: str, quality: int = 95) -> str:
    """
    Crop 1024x1024 square from original image based on prompt result.
    """
    # Get crop coordinates
    crop_coords = get_crop_coords_from_prompt(image_path, prompt_result)
    
    # Use center coordinates for cropping
    cx = crop_coords["crop_square"]["cx"]
    cy = crop_coords["crop_square"]["cy"]
    side = crop_coords["crop_square"].get("side", 1.0)
    
    # Use existing crop function
    return crop_1024_from_original(image_path, cx, cy, output_dir, quality, side=side)

import os
import hashlib
from pathlib import Path


def calculate_md5(file_path: str) -> str:
    """Calculate MD5 hash of a file"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def ensure_dir(path: str) -> None:
    """Ensure directory exists, create if not"""
    os.makedirs(path, exist_ok=True)


def get_files_recursive(dir_path: str, extensions: list = None) -> list:
    """Get all files recursively from directory, optionally filtered by extensions"""
    files = []
    for root, _, filenames in os.walk(dir_path):
        for filename in filenames:
            if extensions:
                if any(filename.lower().endswith(ext) for ext in extensions):
                    files.append(os.path.join(root, filename))
            else:
                files.append(os.path.join(root, filename))
    return files


def get_file_size(file_path: str) -> int:
    """Get file size in bytes"""
    return os.path.getsize(file_path)


def get_relative_path(base_path: str, file_path: str) -> str:
    """Get relative path from base_path to file_path"""
    return os.path.relpath(file_path, base_path)


def safe_filename(filename: str) -> str:
    """Convert filename to safe format"""
    return ''.join(c for c in filename if c.isalnum() or c in ('_', '-', '.'))

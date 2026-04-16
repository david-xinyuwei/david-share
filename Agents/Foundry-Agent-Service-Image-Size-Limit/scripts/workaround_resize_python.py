#!/usr/bin/env python3
"""
Resize image before sending to Foundry Agent Service.
Keeps request body under the ~64KB gateway limit.

Usage:
    pip install Pillow
    python workaround_resize_python.py ./photo.jpg

Author: 魏新宇 (Xinyu Wei)
"""
import base64, json, sys, os
from io import BytesIO

def resize_and_encode(image_path_or_bytes, max_body_kb=60, max_width=1024, max_height=1024):
    """
    Resize image to fit within Agent Service body limit (~64KB).
    GPT-4o-mini detail:low uses 512x512, detail:auto up to 2048x2048.
    Resizing before sending does NOT reduce model understanding quality.
    
    Returns: dict with base64, originalKB, resizedKB, wasResized
    """
    from PIL import Image
    
    if isinstance(image_path_or_bytes, (str, os.PathLike)):
        with open(image_path_or_bytes, 'rb') as f:
            raw = f.read()
    else:
        raw = image_path_or_bytes
    
    original_kb = len(raw) / 1024
    
    # JSON overhead ~220 bytes; b64 expands 4/3x
    max_image_b64_kb = max_body_kb - 1
    max_image_bytes = int(max_image_b64_kb * 1024 * 3 / 4)
    
    if len(raw) <= max_image_bytes:
        return {
            'base64': base64.b64encode(raw).decode(),
            'originalKB': round(original_kb),
            'resizedKB': round(original_kb),
            'wasResized': False
        }
    
    # Resize
    img = Image.open(BytesIO(raw))
    img.thumbnail((max_width, max_height), Image.LANCZOS)
    
    quality = 80
    for _ in range(5):
        buf = BytesIO()
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        img.save(buf, format='JPEG', quality=quality)
        resized = buf.getvalue()
        if len(resized) <= max_image_bytes:
            break
        quality -= 10
        max_width = int(max_width * 0.8)
        max_height = int(max_height * 0.8)
        img.thumbnail((max_width, max_height), Image.LANCZOS)
    
    return {
        'base64': base64.b64encode(resized).decode(),
        'originalKB': round(original_kb),
        'resizedKB': round(len(resized) / 1024),
        'wasResized': True
    }


# --- Bash drop-in: pipe-compatible wrapper ---
# Replace: base64 < "$IMAGE_FILE" | tr -d '\n'
# With:    python workaround_resize_python.py "$IMAGE_FILE"
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python workaround_resize_python.py <image_file>", file=sys.stderr)
        sys.exit(1)
    
    result = resize_and_encode(sys.argv[1])
    
    if result['wasResized']:
        print(f"Resized: {result['originalKB']}KB -> {result['resizedKB']}KB", file=sys.stderr)
    
    # Output base64 to stdout (pipe-compatible with jq)
    sys.stdout.write(result['base64'])

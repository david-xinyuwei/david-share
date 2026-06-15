#!/usr/bin/env python3
"""
Generate End-to-End Request Flow diagram for Qwen3-Inference-Benchmark
Author: Xinyu Wei (魏新宇)
"""

from PIL import Image, ImageDraw, ImageFont
import os

# Colors
WHITE = (255, 255, 255)
BLACK = (51, 51, 51)
BLUE_BG = (232, 244, 255)       # #e8f4ff - client/server nodes
BLUE_BORDER = (0, 120, 212)     # #0078D4
GREEN_BG = (232, 255, 232)      # #e8ffe8 - GPU nodes
GREEN_BORDER = (16, 124, 16)    # #107C10
ORANGE_BG = (255, 243, 224)     # #fff3e0 - PP stage boxes
ORANGE_BORDER = (255, 140, 0)   # #FF8C00
GRAY = (128, 128, 128)
DARK_GRAY = (80, 80, 80)

# Canvas dimensions
WIDTH = 720
HEIGHT = 580

def get_font(size=14, bold=False):
    """Get font with fallback"""
    try:
        if bold:
            return ImageFont.truetype("C:\\Windows\\Fonts\\arialbd.ttf", size)
        return ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", size)
    except:
        return ImageFont.load_default()

def draw_rounded_rect(draw, coords, fill, outline, radius=8, width=2):
    """Draw rounded rectangle"""
    x1, y1, x2, y2 = coords
    # Draw filled rectangle
    draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
    draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
    # Draw corners
    draw.ellipse([x1, y1, x1 + 2*radius, y1 + 2*radius], fill=fill)
    draw.ellipse([x2 - 2*radius, y1, x2, y1 + 2*radius], fill=fill)
    draw.ellipse([x1, y2 - 2*radius, x1 + 2*radius, y2], fill=fill)
    draw.ellipse([x2 - 2*radius, y2 - 2*radius, x2, y2], fill=fill)
    # Draw border
    draw.arc([x1, y1, x1 + 2*radius, y1 + 2*radius], 180, 270, fill=outline, width=width)
    draw.arc([x2 - 2*radius, y1, x2, y1 + 2*radius], 270, 0, fill=outline, width=width)
    draw.arc([x1, y2 - 2*radius, x1 + 2*radius, y2], 90, 180, fill=outline, width=width)
    draw.arc([x2 - 2*radius, y2 - 2*radius, x2, y2], 0, 90, fill=outline, width=width)
    draw.line([x1 + radius, y1, x2 - radius, y1], fill=outline, width=width)
    draw.line([x1 + radius, y2, x2 - radius, y2], fill=outline, width=width)
    draw.line([x1, y1 + radius, x1, y2 - radius], fill=outline, width=width)
    draw.line([x2, y1 + radius, x2, y2 - radius], fill=outline, width=width)

def draw_arrow(draw, start, end, color=DARK_GRAY, width=2):
    """Draw arrow with arrowhead"""
    x1, y1 = start
    x2, y2 = end
    draw.line([x1, y1, x2, y2], fill=color, width=width)
    # Arrowhead
    arrow_size = 8
    if y2 > y1:  # Down arrow
        draw.polygon([(x2, y2), (x2 - arrow_size//2, y2 - arrow_size), 
                      (x2 + arrow_size//2, y2 - arrow_size)], fill=color)
    elif y2 < y1:  # Up arrow
        draw.polygon([(x2, y2), (x2 - arrow_size//2, y2 + arrow_size), 
                      (x2 + arrow_size//2, y2 + arrow_size)], fill=color)

def draw_bidirectional_arrow(draw, start, end, color=GREEN_BORDER, width=2):
    """Draw bidirectional arrow (◄──►)"""
    x1, y1 = start
    x2, y2 = end
    draw.line([x1, y1, x2, y2], fill=color, width=width)
    arrow_size = 6
    # Left arrow
    draw.polygon([(x1, y1), (x1 + arrow_size, y1 - arrow_size//2), 
                  (x1 + arrow_size, y1 + arrow_size//2)], fill=color)
    # Right arrow
    draw.polygon([(x2, y2), (x2 - arrow_size, y2 - arrow_size//2), 
                  (x2 - arrow_size, y2 + arrow_size//2)], fill=color)

def main():
    # Create canvas
    img = Image.new('RGB', (WIDTH, HEIGHT), WHITE)
    draw = ImageDraw.Draw(img)
    
    font = get_font(13)
    font_bold = get_font(13, bold=True)
    font_small = get_font(11)
    font_title = get_font(16, bold=True)
    
    # Title
    title = "End-to-End Request Flow"
    draw.text((WIDTH//2, 20), title, fill=BLACK, font=font_title, anchor="mm")
    
    y = 55
    center_x = WIDTH // 2
    
    # ============ Client Node ============
    box_w, box_h = 180, 36
    x1 = center_x - box_w//2
    draw_rounded_rect(draw, (x1, y, x1 + box_w, y + box_h), BLUE_BG, BLUE_BORDER)
    draw.text((center_x, y + box_h//2), "Client (HTTP :8000)", fill=BLACK, font=font_bold, anchor="mm")
    
    # Arrow down
    y += box_h
    draw_arrow(draw, (center_x, y + 5), (center_x, y + 30))
    
    # ============ API Server Node ============
    y += 35
    box_w = 260
    x1 = center_x - box_w//2
    draw_rounded_rect(draw, (x1, y, x1 + box_w, y + box_h), BLUE_BG, BLUE_BORDER)
    draw.text((center_x, y + box_h//2), "vLLM/SGLang API Server (node0)", fill=BLACK, font=font, anchor="mm")
    
    # Arrow down
    y += box_h
    draw_arrow(draw, (center_x, y + 5), (center_x, y + 30))
    
    # ============ PP Stage 0 Box ============
    y += 35
    stage_w, stage_h = 520, 90
    stage_x = center_x - stage_w//2
    draw_rounded_rect(draw, (stage_x, y, stage_x + stage_w, y + stage_h), ORANGE_BG, ORANGE_BORDER, radius=10)
    
    # Stage 0 title
    draw.text((stage_x + 15, y + 12), "PP Stage 0 (node0)", fill=ORANGE_BORDER, font=font_bold)
    
    # GPU boxes inside Stage 0
    gpu_w, gpu_h = 110, 40
    gpu0_x = stage_x + 40
    gpu1_x = stage_x + 200
    gpu_y = y + 38
    
    draw_rounded_rect(draw, (gpu0_x, gpu_y, gpu0_x + gpu_w, gpu_y + gpu_h), GREEN_BG, GREEN_BORDER, radius=6)
    draw.text((gpu0_x + gpu_w//2, gpu_y + gpu_h//2), "GPU0", fill=GREEN_BORDER, font=font_bold, anchor="mm")
    
    draw_rounded_rect(draw, (gpu1_x, gpu_y, gpu1_x + gpu_w, gpu_y + gpu_h), GREEN_BG, GREEN_BORDER, radius=6)
    draw.text((gpu1_x + gpu_w//2, gpu_y + gpu_h//2), "GPU1", fill=GREEN_BORDER, font=font_bold, anchor="mm")
    
    # Bidirectional arrow between GPUs
    draw_bidirectional_arrow(draw, (gpu0_x + gpu_w + 8, gpu_y + gpu_h//2), (gpu1_x - 8, gpu_y + gpu_h//2))
    draw.text(((gpu0_x + gpu_w + gpu1_x)//2, gpu_y + gpu_h//2 - 12), "NCCL/NVLink", fill=GREEN_BORDER, font=font_small, anchor="mm")
    
    # Right side annotations
    anno_x = stage_x + 330
    draw.text((anno_x, gpu_y + 5), "TP=2: All-reduce every layer", fill=DARK_GRAY, font=font_small)
    draw.text((anno_x, gpu_y + 22), "Bandwidth: 600 GB/s", fill=DARK_GRAY, font=font_small)
    
    # Layer info
    draw.text((gpu0_x + 70, gpu_y + gpu_h + 5), "(Layers 0-39)", fill=GRAY, font=font_small)
    
    # Arrow down with label
    y += stage_h
    center_arrow_x = center_x - 80
    draw_arrow(draw, (center_arrow_x, y + 5), (center_arrow_x, y + 45))
    draw.text((center_arrow_x + 15, y + 18), "NCCL over TCP/eth0 (~10 Gbps)", fill=GRAY, font=font_small)
    
    # ============ PP Stage 1 Box ============
    y += 50
    draw_rounded_rect(draw, (stage_x, y, stage_x + stage_w, y + stage_h), ORANGE_BG, ORANGE_BORDER, radius=10)
    
    # Stage 1 title
    draw.text((stage_x + 15, y + 12), "PP Stage 1 (node1)", fill=ORANGE_BORDER, font=font_bold)
    
    # GPU boxes inside Stage 1
    gpu_y = y + 38
    
    draw_rounded_rect(draw, (gpu0_x, gpu_y, gpu0_x + gpu_w, gpu_y + gpu_h), GREEN_BG, GREEN_BORDER, radius=6)
    draw.text((gpu0_x + gpu_w//2, gpu_y + gpu_h//2), "GPU2", fill=GREEN_BORDER, font=font_bold, anchor="mm")
    
    draw_rounded_rect(draw, (gpu1_x, gpu_y, gpu1_x + gpu_w, gpu_y + gpu_h), GREEN_BG, GREEN_BORDER, radius=6)
    draw.text((gpu1_x + gpu_w//2, gpu_y + gpu_h//2), "GPU3", fill=GREEN_BORDER, font=font_bold, anchor="mm")
    
    # Bidirectional arrow between GPUs
    draw_bidirectional_arrow(draw, (gpu0_x + gpu_w + 8, gpu_y + gpu_h//2), (gpu1_x - 8, gpu_y + gpu_h//2))
    draw.text(((gpu0_x + gpu_w + gpu1_x)//2, gpu_y + gpu_h//2 - 12), "NCCL/NVLink", fill=GREEN_BORDER, font=font_small, anchor="mm")
    
    # Right side annotations
    draw.text((anno_x, gpu_y + 5), "TP=2: All-reduce every layer", fill=DARK_GRAY, font=font_small)
    draw.text((anno_x, gpu_y + 22), "Bandwidth: 600 GB/s", fill=DARK_GRAY, font=font_small)
    
    # Layer info
    draw.text((gpu0_x + 70, gpu_y + gpu_h + 5), "(Layers 40-79)", fill=GRAY, font=font_small)
    
    # Arrow down with label
    y += stage_h
    draw_arrow(draw, (center_arrow_x, y + 5), (center_arrow_x, y + 45))
    draw.text((center_arrow_x + 15, y + 18), "NCCL over TCP/eth0 (result back)", fill=GRAY, font=font_small)
    
    # ============ Response Node ============
    y += 50
    box_w = 360
    x1 = center_x - box_w//2
    draw_rounded_rect(draw, (x1, y, x1 + box_w, y + box_h), BLUE_BG, BLUE_BORDER)
    draw.text((center_x, y + box_h//2), "API Server → HTTP Response → Client", fill=BLACK, font=font, anchor="mm")
    
    # Save
    output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "images", "request-flow.png")
    img.save(output_path, "PNG", dpi=(150, 150))
    print(f"✅ Generated: {output_path}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate PD Disaggregation architecture diagram based on real deployment.
Author: Xinyu Wei
"""
from PIL import Image, ImageDraw, ImageFont
import os

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'images')
os.makedirs(OUT_DIR, exist_ok=True)

W, H = 780, 620
img = Image.new('RGB', (W, H), 'white')
draw = ImageDraw.Draw(img)

try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
    font_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
    font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
except:
    font = font_bold = font_small = font_title = ImageFont.load_default()

# Colors
BLUE = (0, 120, 212)
BLUE_BG = (232, 244, 255)
ORANGE = (255, 140, 0)
ORANGE_BG = (255, 243, 224)
GREEN = (16, 124, 16)
GREEN_BG = (232, 255, 232)
PURPLE = (128, 0, 128)
PURPLE_BG = (245, 232, 255)
GRAY = (100, 100, 100)
GRAY_BG = (245, 245, 245)
RED = (200, 0, 0)

def box(x, y, w, h, fill, border, text, subfont=font, subtext=None):
    draw.rounded_rectangle([x, y, x+w, y+h], radius=8, fill=fill, outline=border, width=2)
    tw = draw.textlength(text, font=font_bold)
    draw.text((x + (w - tw) / 2, y + 8), text, fill=border, font=font_bold)
    if subtext:
        for i, line in enumerate(subtext):
            tw2 = draw.textlength(line, font=subfont)
            draw.text((x + (w - tw2) / 2, y + 28 + i * 16), line, fill=GRAY, font=subfont)

def arrow_down(x, y1, y2, label=None, color=(0,0,0)):
    draw.line([(x, y1), (x, y2-8)], fill=color, width=2)
    draw.polygon([(x-5, y2-8), (x+5, y2-8), (x, y2)], fill=color)
    if label:
        tw = draw.textlength(label, font=font_small)
        draw.text((x + 8, (y1+y2)/2 - 8), label, fill=color, font=font_small)

def arrow_right(x1, x2, y, label=None, color=(0,0,0)):
    draw.line([(x1, y), (x2-8, y)], fill=color, width=2)
    draw.polygon([(x2-8, y-5), (x2-8, y+5), (x2, y)], fill=color)
    if label:
        tw = draw.textlength(label, font=font_small)
        draw.text(((x1+x2)/2 - tw/2, y - 18), label, fill=color, font=font_small)

# Title
draw.text((W//2 - 200, 10), "PD Disaggregation Data Flow", fill=(0,0,0), font=font_title)
draw.text((W//2 - 220, 32), "Azure NC80adis_H100_v5  |  2× H100 NVL  |  NV12 NVLink", fill=GRAY, font=font_small)

# Client
box(310, 60, 160, 40, GRAY_BG, GRAY, "Client Request")

# Arrow down
arrow_down(390, 100, 130)

# Frontend
box(240, 130, 300, 55, BLUE_BG, BLUE, "Dynamo Frontend (Rust)",
    subtext=["Port 8000 | KV-Aware Router + Flash Indexer"])

# Arrow down to router decision
arrow_down(390, 185, 215, "Route to best worker")

# Two GPU boxes side by side
# GPU 0 - Prefill
box(40, 220, 330, 140, ORANGE_BG, ORANGE, "GPU 0: Prefill Worker",
    subtext=[
        "CUDA:0 | Port 8081 | DYN_SYSTEM_PORT=8081",
        "Model: Qwen2.5-32B (65GB FP16)",
        "Task: Compute KV Cache for input tokens",
        "1024 tokens → ~369ms (single GPU baseline)",
        "disaggregation-mode: prefill",
    ])

# GPU 1 - Decode
box(410, 220, 330, 140, GREEN_BG, GREEN, "GPU 1: Decode Worker",
    subtext=[
        "CUDA:1 | Port 8083 | DYN_SYSTEM_PORT=8083",
        "Model: Qwen2.5-32B (65GB FP16)",
        "Task: Generate output tokens from KV",
        "256 tokens @ ~26ms/tok | P99 ITL: 31ms",
        "disaggregation-mode: decode",
    ])

# NIXL arrow between GPUs
arrow_right(370, 410, 290, "NIXL KV Transfer", PURPLE)
draw.text((375, 300), "via NVLink ~900 GB/s", fill=PURPLE, font=font_small)

# Arrow from frontend to GPU 0
draw.line([(340, 185), (340, 195), (200, 195), (200, 220)], fill=ORANGE, width=2)
draw.polygon([(195, 220), (205, 220), (200, 228)], fill=ORANGE)
draw.text((210, 198), "① Prefill request", fill=ORANGE, font=font_small)

# Arrow from GPU 1 back down
arrow_down(575, 360, 395, "③ Token stream", GREEN)

# Client response
box(490, 395, 160, 40, GRAY_BG, GRAY, "Client Response")

# Infrastructure box at bottom
box(40, 460, 700, 70, PURPLE_BG, PURPLE, "Infrastructure (inside Docker container)",
    subtext=[
        "NATS v2.11.3 (JetStream) | etcd v3.5.21 | NIXL 1.0.1 | SGLang 0.5.10",
        "Container: nvcr.io/nvidia/ai-dynamo/sglang-runtime:1.0.1 (55.7 GB)",
    ])

# Label "② KV Transfer" on the NIXL arrow
draw.text((380, 275), "②", fill=RED, font=font_bold)

# Step labels
draw.text((40, 550), "① Client → Frontend → Router selects Prefill Worker (GPU 0)", fill=GRAY, font=font_small)
draw.text((40, 567), "② Prefill computes KV → NIXL transfers KV to Decode Worker (GPU 1) via NVLink", fill=GRAY, font=font_small)
draw.text((40, 584), "③ Decode generates tokens → streams back to Client", fill=GRAY, font=font_small)
draw.text((40, 601), "Key insight: Decode GPU never runs prefill → P99 ITL stays 31ms (zero interference)", fill=RED, font=font_small)

path = os.path.join(OUT_DIR, 'pd_disaggregation_architecture.png')
img.save(path)
print(f"Saved: {path}")

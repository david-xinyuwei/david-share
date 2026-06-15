#!/usr/bin/env python3
"""Generate corrected architecture diagram for vLLM Attention Backend Benchmark.
Author: Xinyu Wei (魏新宇)
"""
from PIL import Image, ImageDraw, ImageFont
import os

# === Color scheme ===
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
DARK_GRAY = (80, 80, 80)

# Blues - titles and headers
TITLE_BG = (0, 120, 212)         # Microsoft Blue
TITLE_TEXT = (255, 255, 255)

# Light blues - info boxes
INFO_BG = (232, 244, 255)        # #e8f4ff
INFO_BORDER = (0, 120, 212)      # #0078D4

# Oranges - warning/caution
WARN_BG = (255, 243, 224)        # #fff3e0
WARN_BORDER = (255, 140, 0)      # #FF8C00

# Greens - results/positive
GREEN_BG = (232, 255, 232)       # #e8ffe8
GREEN_BORDER = (16, 124, 16)     # #107C10

# Reds - negative/bug
RED_BG = (255, 232, 232)         # #ffe8e8
RED_BORDER = (200, 40, 40)

# Purples - scope/limitations
PURPLE_BG = (245, 232, 255)
PURPLE_BORDER = (128, 0, 128)

# Grays
GRAY_BG = (245, 245, 245)
GRAY_BORDER = (160, 160, 160)

W = 720
IMG_H = 980

def get_font(size=14, bold=False):
    """Try to get a nice font, fall back to default."""
    font_paths = [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    if bold:
        font_paths = [
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ] + font_paths
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()


def draw_rounded_rect(draw, xy, radius, fill, outline, width=2):
    """Draw a rounded rectangle."""
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def draw_arrow(draw, x, y_start, y_end, color=DARK_GRAY, width=2):
    """Draw a vertical arrow with arrowhead."""
    draw.line([(x, y_start), (x, y_end)], fill=color, width=width)
    # Arrowhead
    arrow_size = 6
    draw.polygon([
        (x, y_end),
        (x - arrow_size, y_end - arrow_size * 1.5),
        (x + arrow_size, y_end - arrow_size * 1.5),
    ], fill=color)


def draw_text_centered(draw, text, y, font, fill=BLACK, x_center=W // 2):
    """Draw text centered at x_center, at vertical position y."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text((x_center - tw // 2, y), text, font=font, fill=fill)
    return bbox[3] - bbox[1]


def draw_box_with_text(draw, x0, y0, x1, y1, lines, font, bg, border, text_color=BLACK, radius=10, bold_first=False):
    """Draw a rounded box with multiple centered text lines."""
    draw_rounded_rect(draw, (x0, y0, x1, y1), radius, fill=bg, outline=border, width=2)
    total_h = sum(draw.textbbox((0, 0), line, font=font)[3] - draw.textbbox((0, 0), line, font=font)[1] for line in lines)
    spacing = 4
    total_h += spacing * (len(lines) - 1)
    cy = y0 + (y1 - y0 - total_h) // 2
    cx = (x0 + x1) // 2
    for i, line in enumerate(lines):
        f = get_font(font.size, bold=True) if (bold_first and i == 0) else font
        bbox = draw.textbbox((0, 0), line, font=f)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text((cx - tw // 2, cy), line, font=f, fill=text_color)
        cy += th + spacing


def main():
    img = Image.new('RGB', (W, IMG_H), WHITE)
    draw = ImageDraw.Draw(img)

    font_title = get_font(18, bold=True)
    font_subtitle = get_font(13, bold=True)
    font_normal = get_font(12)
    font_small = get_font(11)
    font_tiny = get_font(10)

    y = 10
    margin = 30

    # === Title Bar ===
    draw_rounded_rect(draw, (margin, y, W - margin, y + 50), 8, fill=TITLE_BG, outline=TITLE_BG)
    draw_text_centered(draw, "vLLM Attention Backend Decision Flow", y + 6, font_title, fill=TITLE_TEXT)
    draw_text_centered(draw, "Scoped: vLLM 0.11.2 + H100 NVL + FP8 + 4K Context", y + 28, font_small, fill=(200, 220, 255))
    y += 60

    # === Step 1: Input ===
    draw_box_with_text(draw, 220, y, 500, y + 45,
                       ["User Request", "(model, dtype, context_len, concurrency)"],
                       font_small, INFO_BG, INFO_BORDER, bold_first=True)
    y += 45
    draw_arrow(draw, 360, y, y + 20)
    y += 25

    # === Step 2: Check FP8? ===
    # Diamond shape - draw as rotated square
    cx, cy_diamond = 360, y + 30
    diamond_r = 30
    draw.polygon([
        (cx, cy_diamond - diamond_r),
        (cx + diamond_r * 1.8, cy_diamond),
        (cx, cy_diamond + diamond_r),
        (cx - diamond_r * 1.8, cy_diamond),
    ], fill=WARN_BG, outline=WARN_BORDER, width=2)
    draw_text_centered(draw, "FP8 dtype?", cy_diamond - 8, font_subtitle, fill=DARK_GRAY)
    y += 65

    # Yes / No arrows
    # YES arrow (left) -> FP8 Bug path
    draw.line([(306, cy_diamond), (160, cy_diamond)], fill=WARN_BORDER, width=2)
    draw.line([(160, cy_diamond), (160, y + 5)], fill=WARN_BORDER, width=2)
    draw.polygon([(160, y + 5), (154, y - 5), (166, y - 5)], fill=WARN_BORDER)
    draw.text((200, cy_diamond - 18), "Yes (FP8)", font=font_small, fill=WARN_BORDER)

    # NO arrow (right) -> No bug
    draw.line([(414, cy_diamond), (560, cy_diamond)], fill=GREEN_BORDER, width=2)
    draw.line([(560, cy_diamond), (560, y + 5)], fill=GREEN_BORDER, width=2)
    draw.polygon([(560, y + 5), (554, y - 5), (566, y - 5)], fill=GREEN_BORDER)
    draw.text((430, cy_diamond - 18), "No (BF16/FP16)", font=font_small, fill=GREEN_BORDER)

    # === Left path: FP8 Bug ===
    box_y = y + 5
    draw_box_with_text(draw, 40, box_y, 280, box_y + 65,
                       ["FlashInfer FP8 Bug", "(Issue #9471)", "Tensor Core heuristic fails"],
                       font_small, RED_BG, RED_BORDER, bold_first=True)

    # === Right path: No bug ===
    draw_box_with_text(draw, 440, box_y, 680, box_y + 65,
                       ["No FP8 Bug", "FlashInfer works normally", "May match or beat FA2"],
                       font_small, GREEN_BG, GREEN_BORDER, bold_first=True)

    y = box_y + 70

    # Left arrow down
    draw_arrow(draw, 160, y, y + 20, color=RED_BORDER)
    # Right arrow down
    draw_arrow(draw, 560, y, y + 20, color=GREEN_BORDER)
    y += 25

    # === Left: FA2 recommendation (scoped) ===
    draw_box_with_text(draw, 40, y, 280, y + 55,
                       ["Recommend: FA2 (default)", "7.5% faster @ high concurrency", "vLLM 0.11.2 specific"],
                       font_small, INFO_BG, INFO_BORDER, bold_first=True)

    # === Right: Either works ===
    draw_box_with_text(draw, 440, y, 680, y + 55,
                       ["Either backend OK", "Test with YOUR config", "Consider CUDAGraph + FI"],
                       font_small, GREEN_BG, GREEN_BORDER, bold_first=True)

    y += 65

    # === Central: CUDAGraph Note ===
    draw_arrow(draw, 360, y - 35, y + 5, color=DARK_GRAY)
    draw_box_with_text(draw, 140, y + 5, 580, y + 55,
                       ["IMPORTANT: CUDAGraph NOT Tested", "FlashInfer has native CUDAGraph support - may change results"],
                       font_small, WARN_BG, WARN_BORDER, bold_first=True)

    y += 65

    # === Variables Not Tested section ===
    draw_arrow(draw, 360, y, y + 15, color=DARK_GRAY)
    y += 20

    draw_rounded_rect(draw, (margin, y, W - margin, y + 160), 10, fill=PURPLE_BG, outline=PURPLE_BORDER, width=2)
    draw_text_centered(draw, "Variables NOT Tested (Do NOT Generalize)", y + 8, font_subtitle, fill=PURPLE_BORDER)

    # Table of untested variables
    table_y = y + 30
    table_x = margin + 15
    rows = [
        ("CUDAGraph on/off", "FlashInfer native support may flip results"),
        ("Long Context (32K+)", "Ragged Tensor + Cascade Attention advantage"),
        ("BF16/FP16", "FP8 bug not applicable, FI may be equal/faster"),
        ("Newer vLLM/FI", "FlashInfer 0.6.x may fix FP8 heuristic"),
        ("SGLang", "Defaults to FlashInfer on Ampere/Ada GPUs"),
    ]
    for var, note in rows:
        draw.text((table_x, table_y), f"• {var}:", font=get_font(11, bold=True), fill=PURPLE_BORDER)
        draw.text((table_x + 200, table_y), note, font=font_tiny, fill=DARK_GRAY)
        table_y += 22

    y += 170

    # === Bottom: FlashInfer is MORE than attention ===
    draw_arrow(draw, 360, y, y + 15, color=DARK_GRAY)
    y += 20

    draw_rounded_rect(draw, (margin, y, W - margin, y + 100), 10, fill=GRAY_BG, outline=GRAY_BORDER, width=2)
    draw_text_centered(draw, "FlashInfer: Kernel Library & Generator (NOT just attention)", y + 8, font_subtitle, fill=DARK_GRAY)

    cols = [
        ("Attention", "Paged/Ragged/MLA\nCascade/Sparse/POD"),
        ("GEMM", "FP8/FP4\nGrouped GEMM"),
        ("MoE", "Fused MoE\nDeepSeek/Llama-4"),
        ("Other", "Sampling/Comm\nNorm/RoPE"),
    ]
    col_w = (W - 2 * margin - 40) // 4
    cx_start = margin + 25
    for i, (title, desc) in enumerate(cols):
        bx = cx_start + i * (col_w + 8)
        draw_rounded_rect(draw, (bx, y + 32, bx + col_w - 4, y + 90), 6, fill=WHITE, outline=GRAY_BORDER, width=1)
        bcx = bx + (col_w - 4) // 2
        th = draw.textbbox((0, 0), title, font=font_small)
        draw.text((bcx - (th[2] - th[0]) // 2, y + 35), title, font=get_font(11, bold=True), fill=DARK_GRAY)
        for j, line in enumerate(desc.split('\n')):
            lbb = draw.textbbox((0, 0), line, font=font_tiny)
            draw.text((bcx - (lbb[2] - lbb[0]) // 2, y + 52 + j * 14), line, font=font_tiny, fill=(120, 120, 120))

    y += 110

    # === Footer ===
    draw_text_centered(draw, "arXiv:2501.01005 (MLSys 2025) | FlashInfer v0.6.3 | SGLang Issue #5064", y + 5, font_tiny, fill=(150, 150, 150))
    y += 25

    # === Crop and save ===
    final_h = min(y + 10, IMG_H)
    img = img.crop((0, 0, W, final_h))

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "images")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "01-architecture.png")
    img.save(out_path, "PNG")
    print(f"Saved: {out_path} ({W}x{final_h})")


if __name__ == "__main__":
    main()

"""
Generate architecture diagram: SSIM vs LPIPS pipeline comparison.
Output: images/ssim_vs_lpips_pipeline.png
Author: Xinyu Wei
"""
from PIL import Image, ImageDraw, ImageFont
import os

# Colors
BLUE_BG = (232, 244, 255)
BLUE_BORDER = (0, 120, 212)
ORANGE_BG = (255, 243, 224)
ORANGE_BORDER = (255, 140, 0)
GREEN_BG = (232, 255, 232)
GREEN_BORDER = (16, 124, 16)
PURPLE_BG = (243, 232, 255)
PURPLE_BORDER = (128, 0, 128)
GRAY_BG = (245, 245, 245)
GRAY_BORDER = (128, 128, 128)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

WIDTH = 700
MARGIN = 20
BOX_H = 36
BOX_W = 280
SMALL_BOX_W = 120
ARROW_LEN = 30


def get_font(size=14, bold=False):
    """Try multiple font paths for cross-platform compatibility."""
    font_names = [
        "arial.ttf", "Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    if bold:
        font_names = [
            "arialbd.ttf", "Arial Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ] + font_names
    for name in font_names:
        try:
            return ImageFont.truetype(name, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def draw_box(draw, x, y, w, h, text, bg, border, font=None, text_color=BLACK):
    """Draw a rounded rectangle with centered text."""
    r = 8
    draw.rounded_rectangle([x, y, x + w, y + h], radius=r, fill=bg, outline=border, width=2)
    if font is None:
        font = get_font(13)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((x + (w - tw) / 2, y + (h - th) / 2), text, fill=text_color, font=font)


def draw_arrow_down(draw, x, y1, y2, color=GRAY_BORDER):
    """Draw a downward arrow."""
    draw.line([(x, y1), (x, y2)], fill=color, width=2)
    draw.polygon([(x - 5, y2 - 8), (x + 5, y2 - 8), (x, y2)], fill=color)


def draw_arrow_right(draw, x1, y, x2, color=GRAY_BORDER):
    """Draw a rightward arrow."""
    draw.line([(x1, y), (x2, y)], fill=color, width=2)
    draw.polygon([(x2 - 8, y - 5), (x2 - 8, y + 5), (x2, y)], fill=color)


def main():
    img = Image.new('RGB', (WIDTH, 850), WHITE)
    draw = ImageDraw.Draw(img)
    
    font_title = get_font(18, bold=True)
    font_normal = get_font(13)
    font_small = get_font(11)
    font_bold = get_font(13, bold=True)
    
    y = 15
    
    # Title
    draw.text((WIDTH // 2 - 140, y), "SSIM vs LPIPS Pipeline", fill=BLACK, font=font_title)
    y += 35
    
    # ===== Input images =====
    input_left_x = WIDTH // 2 - BOX_W // 2
    draw_box(draw, input_left_x, y, BOX_W, BOX_H, "Image A  &  Image B", BLUE_BG, BLUE_BORDER, font_bold)
    y += BOX_H
    
    # Split arrow
    mid_x = WIDTH // 2
    ssim_x = WIDTH // 4
    lpips_x = 3 * WIDTH // 4
    
    draw.line([(mid_x, y), (mid_x, y + 15)], fill=GRAY_BORDER, width=2)
    y += 15
    draw.line([(ssim_x, y), (lpips_x, y)], fill=GRAY_BORDER, width=2)
    draw.line([(ssim_x, y), (ssim_x, y + 15)], fill=GRAY_BORDER, width=2)
    draw.line([(lpips_x, y), (lpips_x, y + 15)], fill=GRAY_BORDER, width=2)
    draw_arrow_down(draw, ssim_x, y + 10, y + 25, GRAY_BORDER)
    draw_arrow_down(draw, lpips_x, y + 10, y + 25, GRAY_BORDER)
    y += 25
    
    # ===== SSIM side (left) =====
    col_w = 240
    ssim_left = ssim_x - col_w // 2
    lpips_left = lpips_x - col_w // 2
    
    # SSIM header
    draw_box(draw, ssim_left, y, col_w, BOX_H, "SSIM (Math)", ORANGE_BG, ORANGE_BORDER, font_bold)
    # LPIPS header
    draw_box(draw, lpips_left, y, col_w, BOX_H, "LPIPS (AI)", PURPLE_BG, PURPLE_BORDER, font_bold)
    y += BOX_H
    
    draw_arrow_down(draw, ssim_x, y, y + ARROW_LEN, ORANGE_BORDER)
    draw_arrow_down(draw, lpips_x, y, y + ARROW_LEN, PURPLE_BORDER)
    y += ARROW_LEN
    
    # SSIM Step 1
    draw_box(draw, ssim_left, y, col_w, BOX_H, "Sliding Window (7x7)", GRAY_BG, GRAY_BORDER, font_normal)
    # LPIPS Step 1
    draw_box(draw, lpips_left, y, col_w, BOX_H, "VGG-16 Forward Pass", GRAY_BG, GRAY_BORDER, font_normal)
    y += BOX_H
    
    draw_arrow_down(draw, ssim_x, y, y + ARROW_LEN, ORANGE_BORDER)
    draw_arrow_down(draw, lpips_x, y, y + ARROW_LEN, PURPLE_BORDER)
    y += ARROW_LEN
    
    # SSIM Step 2: 3 sub-boxes
    sub_w = 70
    gap = 10
    total_sub = sub_w * 3 + gap * 2
    sub_start = ssim_x - total_sub // 2
    draw_box(draw, sub_start, y, sub_w, BOX_H, "Lumi.", ORANGE_BG, ORANGE_BORDER, font_small)
    draw_box(draw, sub_start + sub_w + gap, y, sub_w, BOX_H, "Contr.", ORANGE_BG, ORANGE_BORDER, font_small)
    draw_box(draw, sub_start + 2 * (sub_w + gap), y, sub_w, BOX_H, "Struct.", ORANGE_BG, ORANGE_BORDER, font_small)
    
    # LPIPS Step 2: 5 layer features
    layer_w = 40
    layer_gap = 5
    total_layers = layer_w * 5 + layer_gap * 4
    layer_start = lpips_x - total_layers // 2
    for i in range(5):
        lx = layer_start + i * (layer_w + layer_gap)
        draw_box(draw, lx, y, layer_w, BOX_H, f"L{i+1}", PURPLE_BG, PURPLE_BORDER, font_small)
    y += BOX_H
    
    draw_arrow_down(draw, ssim_x, y, y + ARROW_LEN, ORANGE_BORDER)
    draw_arrow_down(draw, lpips_x, y, y + ARROW_LEN, PURPLE_BORDER)
    y += ARROW_LEN
    
    # SSIM Step 3
    draw_box(draw, ssim_left, y, col_w, BOX_H, "l(x,y) * c(x,y) * s(x,y)", ORANGE_BG, ORANGE_BORDER, font_normal)
    # LPIPS Step 3
    draw_box(draw, lpips_left, y, col_w, BOX_H, "|diff_i| x w_i  (i=1..5)", PURPLE_BG, PURPLE_BORDER, font_normal)
    y += BOX_H
    
    draw_arrow_down(draw, ssim_x, y, y + ARROW_LEN, ORANGE_BORDER)
    draw_arrow_down(draw, lpips_x, y, y + ARROW_LEN, PURPLE_BORDER)
    y += ARROW_LEN
    
    # SSIM Step 4
    draw_box(draw, ssim_left, y, col_w, BOX_H, "Average over windows", GRAY_BG, GRAY_BORDER, font_normal)
    # LPIPS Step 4
    draw_box(draw, lpips_left, y, col_w, BOX_H, "Sum weighted diffs", GRAY_BG, GRAY_BORDER, font_normal)
    y += BOX_H
    
    draw_arrow_down(draw, ssim_x, y, y + ARROW_LEN, ORANGE_BORDER)
    draw_arrow_down(draw, lpips_x, y, y + ARROW_LEN, PURPLE_BORDER)
    y += ARROW_LEN
    
    # Output scores
    draw_box(draw, ssim_left, y, col_w, BOX_H + 4, "SSIM = 0.0 ~ 1.0", GREEN_BG, GREEN_BORDER, font_bold)
    draw_box(draw, lpips_left, y, col_w, BOX_H + 4, "LPIPS = 0.0 ~ 1.0", GREEN_BG, GREEN_BORDER, font_bold)
    y += BOX_H + 4
    
    # Direction labels
    y += 5
    ssim_dir = "Higher = More Similar"
    lpips_dir = "Lower = More Similar"
    bbox1 = draw.textbbox((0, 0), ssim_dir, font=font_small)
    bbox2 = draw.textbbox((0, 0), lpips_dir, font=font_small)
    draw.text((ssim_x - (bbox1[2] - bbox1[0]) / 2, y), ssim_dir, fill=GREEN_BORDER, font=font_small)
    draw.text((lpips_x - (bbox2[2] - bbox2[0]) / 2, y), lpips_dir, fill=GREEN_BORDER, font=font_small)
    y += 30
    
    # ===== Comparison table =====
    y += 10
    draw.text((MARGIN, y), "Key Differences:", fill=BLACK, font=font_bold)
    y += 22
    
    table_data = [
        ("Property", "SSIM", "LPIPS"),
        ("Year", "2004", "2018"),
        ("Method", "Mathematical", "Neural Network"),
        ("Pixel-Aligned?", "Yes (sensitive)", "No (robust)"),
        ("GPU Required?", "No", "No (but faster)"),
        ("Model Size", "0 MB", "~528 MB (VGG)"),
        ("Speed", "Fast", "Moderate"),
    ]
    
    col_widths = [180, 200, 200]
    row_h = 28
    table_x = MARGIN + 20
    
    for i, row in enumerate(table_data):
        rx = table_x
        for j, cell in enumerate(row):
            if i == 0:
                bg = (220, 220, 220)
                f = font_bold
            else:
                bg = WHITE if i % 2 == 0 else (250, 250, 250)
                f = font_normal
            draw.rectangle([rx, y, rx + col_widths[j], y + row_h], fill=bg, outline=(200, 200, 200))
            bbox = draw.textbbox((0, 0), cell, font=f)
            tw = bbox[2] - bbox[0]
            draw.text((rx + 10, y + 5), cell, fill=BLACK, font=f)
            rx += col_widths[j]
        y += row_h
    
    # Crop
    final_height = y + 20
    img = img.crop((0, 0, WIDTH, final_height))
    
    os.makedirs("images", exist_ok=True)
    img.save("images/ssim_vs_lpips_pipeline.png", dpi=(150, 150))
    print(f"Saved: images/ssim_vs_lpips_pipeline.png ({img.size[0]}x{img.size[1]})")


if __name__ == "__main__":
    main()

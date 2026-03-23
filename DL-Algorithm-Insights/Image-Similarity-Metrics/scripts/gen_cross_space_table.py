"""Generate cross-space applicability table image for README.
Author: Xinyu Wei
"""
from PIL import Image, ImageDraw, ImageFont
import os

# Layout constants
COL_W = [120, 160, 200, 220]  # metric, pixel, latent, velocity
ROW_H = 52
HEADER_H = 90
PAD = 20

TOTAL_W = sum(COL_W) + PAD * 2
TOTAL_H = HEADER_H + ROW_H * 5 + PAD * 2 + 30  # 5 metrics + footer

# Colors
BG = "#FFFFFF"
HEADER_BG = "#1a1a2e"
HEADER_TEXT = "#FFFFFF"
ROW_EVEN = "#f8f9fa"
ROW_ODD = "#ffffff"
BORDER = "#dee2e6"
TEXT_COLOR = "#333333"
GREEN = "#28a745"
YELLOW = "#ffc107"
RED = "#dc3545"

# Data
METRICS = ["MSE", "SSIM", "LPIPS", "FID", "CLIP Score"]
HEADERS_EN = ["Metric", "Pixel Space\n[H×W×3]", "Latent Space\n[h×w×4]", "Velocity Field\n[h×w×4]"]
HEADERS_CN = ["指标", "像素空间\n[H×W×3]", "潜空间 (Latent)\n[h×w×4]", "速度场 (Velocity)\n[h×w×4]"]

# Status: "ok" = green check, "warn" = yellow warning, "no" = red X
STATUS = [
    ["ok", "ok", "ok"],       # MSE
    ["ok", "warn", "warn"],   # SSIM
    ["ok", "no", "no"],       # LPIPS
    ["ok", "no", "no"],       # FID
    ["ok", "no", "no"],       # CLIP Score
]


def draw_icon(draw, cx, cy, status, size=18):
    """Draw status icon centered at (cx, cy)."""
    if status == "ok":
        # Green checkmark circle
        r = size // 2
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=GREEN)
        # Checkmark
        pts = [(cx - 6, cy), (cx - 2, cy + 5), (cx + 7, cy - 5)]
        draw.line(pts, fill="white", width=3)
    elif status == "warn":
        # Yellow triangle
        s = size
        pts = [(cx, cy - s // 2), (cx - s // 2, cy + s // 2), (cx + s // 2, cy + s // 2)]
        draw.polygon(pts, fill=YELLOW)
        draw.text((cx - 1, cy - 4), "!", fill="#333", anchor="mm")
    elif status == "no":
        # Red X circle
        r = size // 2
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=RED)
        draw.line([(cx - 5, cy - 5), (cx + 5, cy + 5)], fill="white", width=3)
        draw.line([(cx - 5, cy + 5), (cx + 5, cy - 5)], fill="white", width=3)


def generate_table(headers, output_path):
    img = Image.new("RGB", (TOTAL_W, TOTAL_H), BG)
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", 16)
        font_bold = ImageFont.truetype("arialbd.ttf", 16)
        font_header = ImageFont.truetype("arialbd.ttf", 14)
        font_title = ImageFont.truetype("arialbd.ttf", 20)
        font_small = ImageFont.truetype("arial.ttf", 12)
    except OSError:
        font = ImageFont.load_default()
        font_bold = font
        font_header = font
        font_title = font
        font_small = font

    # Title
    title = "Cross-Space Applicability" if "Metric" in headers[0] else "跨空间适用性"
    draw.text((TOTAL_W // 2, 18), title, fill=TEXT_COLOR, font=font_title, anchor="mt")

    y_start = PAD + 30

    # Draw header row
    x = PAD
    for i, hdr in enumerate(headers):
        draw.rectangle([x, y_start, x + COL_W[i], y_start + HEADER_H], fill=HEADER_BG)
        draw.rectangle([x, y_start, x + COL_W[i], y_start + HEADER_H], outline=BORDER)
        # Multi-line header
        lines = hdr.split("\n")
        line_y = y_start + HEADER_H // 2 - len(lines) * 9
        for line in lines:
            draw.text((x + COL_W[i] // 2, line_y), line, fill=HEADER_TEXT, font=font_header, anchor="mt")
            line_y += 20
        x += COL_W[i]

    # Draw data rows
    for row_idx, metric in enumerate(METRICS):
        y = y_start + HEADER_H + row_idx * ROW_H
        bg = ROW_EVEN if row_idx % 2 == 0 else ROW_ODD
        x = PAD

        # Metric name column
        draw.rectangle([x, y, x + COL_W[0], y + ROW_H], fill=bg, outline=BORDER)
        draw.text((x + COL_W[0] // 2, y + ROW_H // 2), metric, fill=TEXT_COLOR, font=font_bold, anchor="mm")
        x += COL_W[0]

        # Status columns
        for col_idx in range(3):
            draw.rectangle([x, y, x + COL_W[col_idx + 1], y + ROW_H], fill=bg, outline=BORDER)
            cx = x + COL_W[col_idx + 1] // 2
            cy = y + ROW_H // 2
            draw_icon(draw, cx, cy, STATUS[row_idx][col_idx])
            x += COL_W[col_idx + 1]

    # Legend
    legend_y = y_start + HEADER_H + 5 * ROW_H + 10
    items = [("ok", "Fully applicable"), ("warn", "Computable but meaningless"), ("no", "Cannot work")]
    if "指标" in headers[0]:
        items = [("ok", "完全适用"), ("warn", "能算但无意义"), ("no", "无法使用")]
    lx = PAD + 20
    for status, label in items:
        draw_icon(draw, lx, legend_y + 8, status, size=14)
        draw.text((lx + 14, legend_y + 8), f"  {label}", fill=TEXT_COLOR, font=font_small, anchor="lm")
        lx += 200

    img.save(output_path, quality=95)
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    # Generate for both repos
    paths = [
        ("g:/github/david-share/DL-Algorithm-Insights/Image-Similarity-Metrics/images/cross_space_applicability.png", HEADERS_EN),
        ("g:/github/david-share/DL-Algorithm-Insights/Image-Similarity-Metrics/images/cross_space_applicability_cn.png", HEADERS_CN),
        ("g:/github/Backend-of-david-share/DL-Algorithm-Insights/Image-Similarity-Metrics/images/cross_space_applicability.png", HEADERS_EN),
        ("g:/github/Backend-of-david-share/DL-Algorithm-Insights/Image-Similarity-Metrics/images/cross_space_applicability_cn.png", HEADERS_CN),
    ]
    for path, headers in paths:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        generate_table(headers, path)

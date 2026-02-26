"""
Generate architecture diagrams for LLM Training Parallelism guide.
Author: Xinyu Wei

Generates 4 key diagrams:
1. parallelism_overview.png - DP vs TP vs PP visual comparison
2. zero_stages.png - ZeRO Stage 1/2/3 memory partitioning
3. tp_vs_zero.png - Critical difference: TP (compute with shard) vs ZeRO (reconstruct then compute)
4. 3d_parallelism.png - TP × PP × DP combination on real cluster
"""

from PIL import Image, ImageDraw, ImageFont
import os

os.makedirs("images", exist_ok=True)

# ── Color Palette ──
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY_TEXT = (80, 80, 80)
LIGHT_GRAY = (240, 240, 240)

# Blues - for DP / Parameters
BLUE_BG = (220, 235, 255)
BLUE_BORDER = (0, 100, 200)
BLUE_FILL = (100, 160, 230)
BLUE_DARK = (40, 80, 160)

# Oranges - for TP
ORANGE_BG = (255, 240, 220)
ORANGE_BORDER = (220, 120, 0)
ORANGE_FILL = (255, 165, 50)

# Greens - for PP / ZeRO success
GREEN_BG = (220, 245, 220)
GREEN_BORDER = (0, 140, 0)
GREEN_FILL = (80, 180, 80)

# Reds - for Gradients
RED_BG = (255, 225, 225)
RED_BORDER = (200, 50, 50)
RED_FILL = (220, 80, 80)

# Purples - for Optimizer States
PURPLE_BG = (235, 220, 255)
PURPLE_BORDER = (120, 50, 180)
PURPLE_FILL = (150, 100, 200)

# Yellows - for highlights
YELLOW_BG = (255, 255, 220)
YELLOW_BORDER = (180, 160, 0)

# Cyans - for ZeRO
CYAN_BG = (220, 250, 250)
CYAN_BORDER = (0, 150, 150)

try:
    font_title = ImageFont.truetype("arial.ttf", 22)
    font_subtitle = ImageFont.truetype("arial.ttf", 18)
    font_normal = ImageFont.truetype("arial.ttf", 14)
    font_small = ImageFont.truetype("arial.ttf", 12)
    font_tiny = ImageFont.truetype("arial.ttf", 11)
except:
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        font_subtitle = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
        font_normal = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
        font_tiny = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
    except:
        font_title = ImageFont.load_default()
        font_subtitle = font_title
        font_normal = font_title
        font_small = font_title
        font_tiny = font_title


def draw_rounded_rect(draw, bbox, radius, fill, outline, width=2):
    """Draw a rounded rectangle."""
    x0, y0, x1, y1 = bbox
    draw.rounded_rectangle(bbox, radius=radius, fill=fill, outline=outline, width=width)


def draw_arrow(draw, x1, y1, x2, y2, color=BLACK, width=2):
    """Draw an arrow from (x1,y1) to (x2,y2)."""
    draw.line([(x1, y1), (x2, y2)], fill=color, width=width)
    # Arrowhead
    import math
    angle = math.atan2(y2 - y1, x2 - x1)
    arrow_len = 10
    arrow_angle = math.pi / 6
    ax1 = x2 - arrow_len * math.cos(angle - arrow_angle)
    ay1 = y2 - arrow_len * math.sin(angle - arrow_angle)
    ax2 = x2 - arrow_len * math.cos(angle + arrow_angle)
    ay2 = y2 - arrow_len * math.sin(angle + arrow_angle)
    draw.polygon([(x2, y2), (int(ax1), int(ay1)), (int(ax2), int(ay2))], fill=color)


def text_center(draw, text, x, y, font, fill=BLACK):
    """Draw text centered at (x, y)."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((x - tw // 2, y - th // 2), text, font=font, fill=fill)


# ════════════════════════════════════════════════════════
# Diagram 1: Parallelism Overview (DP vs TP vs PP)
# ════════════════════════════════════════════════════════
def generate_parallelism_overview():
    W, H = 900, 700
    img = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(img)

    # Title
    text_center(draw, "Data Parallelism vs Tensor Parallelism vs Pipeline Parallelism", W // 2, 20, font_title, BLUE_DARK)
    text_center(draw, "How each parallelism strategy distributes a 4-layer model across 2 GPUs", W // 2, 48, font_small, GRAY_TEXT)

    # ── Original Model ──
    ox, oy = 50, 80
    draw.text((ox, oy), "Original Model:", font=font_subtitle, fill=BLACK)
    colors = [BLUE_FILL, ORANGE_FILL, GREEN_FILL, RED_FILL]
    labels = ["Layer 0", "Layer 1", "Layer 2", "Layer 3"]
    for i in range(4):
        x = ox + 180 + i * 130
        draw_rounded_rect(draw, (x, oy, x + 110, oy + 35), 6, colors[i], BLACK, 2)
        text_center(draw, labels[i], x + 55, oy + 17, font_normal, WHITE)

    # ── Data Parallelism ──
    section_y = 150
    draw_rounded_rect(draw, (20, section_y, W - 20, section_y + 175), 10, BLUE_BG, BLUE_BORDER, 2)
    draw.text((35, section_y + 8), "Data Parallelism (DP)", font=font_subtitle, fill=BLUE_DARK)
    draw.text((35, section_y + 32), "Each GPU has full model copy, processes different data batches", font=font_small, fill=GRAY_TEXT)

    for gpu_idx in range(2):
        gx = 60 + gpu_idx * 420
        gy = section_y + 58
        draw_rounded_rect(draw, (gx, gy, gx + 380, gy + 100), 8, WHITE, BLUE_BORDER, 1)
        draw.text((gx + 10, gy + 5), f"GPU {gpu_idx}  (Data Batch {gpu_idx})", font=font_normal, fill=BLUE_DARK)
        for i in range(4):
            bx = gx + 15 + i * 90
            by = gy + 35
            draw_rounded_rect(draw, (bx, by, bx + 80, by + 50), 5, colors[i], BLACK, 1)
            text_center(draw, labels[i], bx + 40, by + 15, font_small, WHITE)
            text_center(draw, "Full W", bx + 40, by + 35, font_tiny, WHITE)

    # AllReduce arrow
    draw.text((430, section_y + 135), "AllReduce gradients", font=font_small, fill=BLUE_DARK)
    draw.line([(350, section_y + 150), (530, section_y + 150)], fill=BLUE_DARK, width=2)
    draw_arrow(draw, 350, section_y + 150, 320, section_y + 150, BLUE_DARK, 2)
    draw_arrow(draw, 530, section_y + 150, 560, section_y + 150, BLUE_DARK, 2)

    # ── Tensor Parallelism ──
    section_y = 345
    draw_rounded_rect(draw, (20, section_y, W - 20, section_y + 175), 10, ORANGE_BG, ORANGE_BORDER, 2)
    draw.text((35, section_y + 8), "Tensor Parallelism (TP)", font=font_subtitle, fill=ORANGE_BORDER)
    draw.text((35, section_y + 32), "Each GPU has partial weights of ALL layers, processes SAME data", font=font_small, fill=GRAY_TEXT)

    for gpu_idx in range(2):
        gx = 60 + gpu_idx * 420
        gy = section_y + 58
        draw_rounded_rect(draw, (gx, gy, gx + 380, gy + 100), 8, WHITE, ORANGE_BORDER, 1)
        draw.text((gx + 10, gy + 5), f"GPU {gpu_idx}  (Same Data)", font=font_normal, fill=ORANGE_BORDER)
        half = "Left" if gpu_idx == 0 else "Right"
        for i in range(4):
            bx = gx + 15 + i * 90
            by = gy + 35
            # Partial fill - use lighter color to indicate half
            c = tuple(min(255, v + 60) for v in colors[i])
            draw_rounded_rect(draw, (bx, by, bx + 80, by + 50), 5, c, colors[i], 1)
            text_center(draw, labels[i], bx + 40, by + 15, font_small, BLACK)
            text_center(draw, f"{half} Half", bx + 40, by + 35, font_tiny, BLACK)

    draw.text((410, section_y + 135), "AllReduce per layer", font=font_small, fill=ORANGE_BORDER)
    draw.line([(350, section_y + 150), (530, section_y + 150)], fill=ORANGE_BORDER, width=2)
    draw_arrow(draw, 350, section_y + 150, 320, section_y + 150, ORANGE_BORDER, 2)
    draw_arrow(draw, 530, section_y + 150, 560, section_y + 150, ORANGE_BORDER, 2)

    # ── Pipeline Parallelism ──
    section_y = 540
    draw_rounded_rect(draw, (20, section_y, W - 20, section_y + 145), 10, GREEN_BG, GREEN_BORDER, 2)
    draw.text((35, section_y + 8), "Pipeline Parallelism (PP)", font=font_subtitle, fill=GREEN_BORDER)
    draw.text((35, section_y + 32), "Each GPU has FULL weights of SOME layers, processes same data sequentially", font=font_small, fill=GRAY_TEXT)

    for gpu_idx in range(2):
        gx = 60 + gpu_idx * 420
        gy = section_y + 58
        draw_rounded_rect(draw, (gx, gy, gx + 380, gy + 70), 8, WHITE, GREEN_BORDER, 1)
        draw.text((gx + 10, gy + 5), f"GPU {gpu_idx}  (Stage {gpu_idx})", font=font_normal, fill=GREEN_BORDER)
        start = gpu_idx * 2
        for i in range(2):
            bx = gx + 15 + i * 170
            by = gy + 30
            draw_rounded_rect(draw, (bx, by, bx + 150, by + 30), 5, colors[start + i], BLACK, 1)
            text_center(draw, f"{labels[start + i]} (Full W)", bx + 75, by + 15, font_small, WHITE)

    # P2P arrow between GPUs
    draw_arrow(draw, 440, section_y + 93, 480, section_y + 93, GREEN_BORDER, 3)
    draw.text((420, section_y + 108), "P2P activations", font=font_small, fill=GREEN_BORDER)

    img.save("images/parallelism_overview.png", quality=95)
    print("Generated: images/parallelism_overview.png")


# ════════════════════════════════════════════════════════
# Diagram 2: ZeRO Stages
# ════════════════════════════════════════════════════════
def generate_zero_stages():
    W, H = 900, 750
    img = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(img)

    text_center(draw, "ZeRO Optimization Stages: Memory Partitioning", W // 2, 20, font_title, BLUE_DARK)
    text_center(draw, "Progressive partitioning of model states across GPUs (4 GPU example)", W // 2, 48, font_small, GRAY_TEXT)

    # Legend
    lx, ly = 30, 70
    items = [
        ("Parameters (W)", BLUE_FILL),
        ("Gradients (G)", RED_FILL),
        ("Optimizer States (OS)", PURPLE_FILL),
        ("Partitioned (1/N)", LIGHT_GRAY),
    ]
    for i, (label, color) in enumerate(items):
        x = lx + i * 210
        draw.rectangle((x, ly, x + 20, ly + 15), fill=color, outline=BLACK)
        draw.text((x + 25, ly), label, font=font_small, fill=BLACK)

    stages = [
        ("No ZeRO (Standard DP)", "Each GPU stores full copy of everything", [
            ("GPU 0", [(BLUE_FILL, "W (full)"), (RED_FILL, "G (full)"), (PURPLE_FILL, "OS (full)")]),
            ("GPU 1", [(BLUE_FILL, "W (full)"), (RED_FILL, "G (full)"), (PURPLE_FILL, "OS (full)")]),
            ("GPU 2", [(BLUE_FILL, "W (full)"), (RED_FILL, "G (full)"), (PURPLE_FILL, "OS (full)")]),
            ("GPU 3", [(BLUE_FILL, "W (full)"), (RED_FILL, "G (full)"), (PURPLE_FILL, "OS (full)")]),
        ]),
        ("ZeRO Stage 1", "Partition Optimizer States only", [
            ("GPU 0", [(BLUE_FILL, "W (full)"), (RED_FILL, "G (full)"), (PURPLE_FILL, "OS 1/4")]),
            ("GPU 1", [(BLUE_FILL, "W (full)"), (RED_FILL, "G (full)"), (PURPLE_FILL, "OS 1/4")]),
            ("GPU 2", [(BLUE_FILL, "W (full)"), (RED_FILL, "G (full)"), (PURPLE_FILL, "OS 1/4")]),
            ("GPU 3", [(BLUE_FILL, "W (full)"), (RED_FILL, "G (full)"), (PURPLE_FILL, "OS 1/4")]),
        ]),
        ("ZeRO Stage 2", "Partition Optimizer States + Gradients", [
            ("GPU 0", [(BLUE_FILL, "W (full)"), (RED_FILL, "G 1/4"), (PURPLE_FILL, "OS 1/4")]),
            ("GPU 1", [(BLUE_FILL, "W (full)"), (RED_FILL, "G 1/4"), (PURPLE_FILL, "OS 1/4")]),
            ("GPU 2", [(BLUE_FILL, "W (full)"), (RED_FILL, "G 1/4"), (PURPLE_FILL, "OS 1/4")]),
            ("GPU 3", [(BLUE_FILL, "W (full)"), (RED_FILL, "G 1/4"), (PURPLE_FILL, "OS 1/4")]),
        ]),
        ("ZeRO Stage 3", "Partition Everything (W + G + OS)", [
            ("GPU 0", [(BLUE_FILL, "W 1/4"), (RED_FILL, "G 1/4"), (PURPLE_FILL, "OS 1/4")]),
            ("GPU 1", [(BLUE_FILL, "W 1/4"), (RED_FILL, "G 1/4"), (PURPLE_FILL, "OS 1/4")]),
            ("GPU 2", [(BLUE_FILL, "W 1/4"), (RED_FILL, "G 1/4"), (PURPLE_FILL, "OS 1/4")]),
            ("GPU 3", [(BLUE_FILL, "W 1/4"), (RED_FILL, "G 1/4"), (PURPLE_FILL, "OS 1/4")]),
        ]),
    ]

    y = 100
    for stage_name, desc, gpus in stages:
        # Stage header
        draw_rounded_rect(draw, (20, y, W - 20, y + 145), 8, LIGHT_GRAY, BLACK, 1)
        draw.text((35, y + 5), stage_name, font=font_subtitle, fill=BLUE_DARK)
        draw.text((35, y + 28), desc, font=font_small, fill=GRAY_TEXT)

        # GPUs
        gpu_w = 190
        for gi, (gpu_name, components) in enumerate(gpus):
            gx = 35 + gi * (gpu_w + 10)
            gy = y + 50
            draw_rounded_rect(draw, (gx, gy, gx + gpu_w, gy + 85), 5, WHITE, BLACK, 1)
            draw.text((gx + 5, gy + 3), gpu_name, font=font_small, fill=BLACK)

            # Draw stacked bars for each component
            bar_x = gx + 8
            bar_y = gy + 22
            bar_h = 18
            for ci, (color, label) in enumerate(components):
                is_partitioned = "1/4" in label
                bar_width = 40 if is_partitioned else gpu_w - 16
                actual_color = color if not is_partitioned else tuple(min(255, v + 80) for v in color)
                draw.rectangle((bar_x, bar_y, bar_x + bar_width, bar_y + bar_h),
                               fill=actual_color, outline=color)
                # Label
                lbl_x = bar_x + bar_width + 5 if is_partitioned else bar_x + 5
                draw.text((lbl_x, bar_y + 1), label, font=font_tiny, fill=BLACK)
                bar_y += bar_h + 3

        y += 155

    # Memory savings annotation
    y += 5
    draw.text((30, y), "Memory per GPU:  No ZeRO = 16x  |  Stage 1 = 4x+2x  |  Stage 2 = 2x+2x  |  Stage 3 = 16x/N",
              font=font_normal, fill=BLUE_DARK)
    draw.text((30, y + 20), "(For model size M, x = M bytes.  OS uses ~12x with Adam FP32, G uses ~2x, W uses ~2x in FP16)",
              font=font_small, fill=GRAY_TEXT)

    img.save("images/zero_stages.png", quality=95)
    print("Generated: images/zero_stages.png")


# ════════════════════════════════════════════════════════
# Diagram 3: TP vs ZeRO - The Critical Difference
# ════════════════════════════════════════════════════════
def generate_tp_vs_zero():
    W, H = 900, 620
    img = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(img)

    text_center(draw, "TP vs ZeRO Stage 3: The Critical Difference", W // 2, 20, font_title, BLUE_DARK)
    text_center(draw, "Both split weights across GPUs, but compute differently", W // 2, 48, font_small, GRAY_TEXT)

    # ── TP Section ──
    tp_y = 75
    draw_rounded_rect(draw, (20, tp_y, W - 20, tp_y + 245), 10, ORANGE_BG, ORANGE_BORDER, 2)
    draw.text((35, tp_y + 8), "Tensor Parallelism (TP=2)", font=font_subtitle, fill=ORANGE_BORDER)
    draw.text((35, tp_y + 32), "Store partial weights -> Compute with partial weights -> AllReduce result", font=font_small, fill=GRAY_TEXT)

    # Step 1: Store
    sx = 50
    sy = tp_y + 65
    draw.text((sx, sy - 15), "1. Storage", font=font_normal, fill=BLACK)
    for i in range(2):
        gx = sx + i * 200
        draw_rounded_rect(draw, (gx, sy, gx + 180, sy + 55), 5, WHITE, ORANGE_BORDER, 1)
        draw.text((gx + 8, sy + 5), f"GPU {i}", font=font_small, fill=ORANGE_BORDER)
        half = "Left" if i == 0 else "Right"
        draw_rounded_rect(draw, (gx + 8, sy + 25, gx + 88, sy + 45), 3, ORANGE_FILL, BLACK, 1)
        text_center(draw, f"W {half}", gx + 48, sy + 35, font_tiny, WHITE)

    # Step 2: Compute
    cx = 470
    draw.text((cx, sy - 15), "2. Compute", font=font_normal, fill=BLACK)
    for i in range(2):
        gx = cx + i * 200
        draw_rounded_rect(draw, (gx, sy, gx + 180, sy + 55), 5, WHITE, ORANGE_BORDER, 1)
        draw.text((gx + 8, sy + 5), f"GPU {i}", font=font_small, fill=ORANGE_BORDER)
        half = "Left" if i == 0 else "Right"
        draw_rounded_rect(draw, (gx + 8, sy + 25, gx + 88, sy + 45), 3, ORANGE_FILL, BLACK, 1)
        text_center(draw, f"X * W_{half}", gx + 48, sy + 35, font_tiny, WHITE)
        draw.text((gx + 95, sy + 28), "= Y_part", font=font_tiny, fill=BLACK)

    draw_arrow(draw, 440, sy + 30, 465, sy + 30, BLACK, 2)

    # Step 3: AllReduce
    sy2 = sy + 75
    draw.text((sx, sy2 - 5), "3. AllReduce", font=font_normal, fill=BLACK)
    draw_rounded_rect(draw, (sx + 120, sy2, sx + 750, sy2 + 45), 5, YELLOW_BG, ORANGE_BORDER, 2)
    text_center(draw, "AllReduce(Y_left, Y_right) -> Y_full  (every layer needs this!)", sx + 435, sy2 + 22, font_normal, ORANGE_BORDER)

    # Key point
    sy3 = sy2 + 55
    draw_rounded_rect(draw, (sx, sy3, sx + 800, sy3 + 35), 5, (255, 240, 240), RED_BORDER, 2)
    text_center(draw, "KEY: Each GPU only computes PARTIAL result. Never sees full weights during compute.", sx + 400, sy3 + 17, font_normal, RED_BORDER)

    # ── ZeRO Section ──
    zr_y = 335
    draw_rounded_rect(draw, (20, zr_y, W - 20, zr_y + 270), 10, CYAN_BG, CYAN_BORDER, 2)
    draw.text((35, zr_y + 8), "ZeRO Stage 3 (N=2)", font=font_subtitle, fill=CYAN_BORDER)
    draw.text((35, zr_y + 32), "Store partial weights -> All-Gather full weights -> Compute with full weights -> Discard", font=font_small, fill=GRAY_TEXT)

    # Step 1: Store
    sx = 50
    sy = zr_y + 65
    draw.text((sx, sy - 15), "1. Storage", font=font_normal, fill=BLACK)
    for i in range(2):
        gx = sx + i * 200
        draw_rounded_rect(draw, (gx, sy, gx + 180, sy + 55), 5, WHITE, CYAN_BORDER, 1)
        draw.text((gx + 8, sy + 5), f"GPU {i}", font=font_small, fill=CYAN_BORDER)
        draw_rounded_rect(draw, (gx + 8, sy + 25, gx + 88, sy + 45), 3, BLUE_FILL, BLACK, 1)
        text_center(draw, f"W 1/2", gx + 48, sy + 35, font_tiny, WHITE)

    # Step 2: All-Gather
    cx = 470
    draw.text((cx, sy - 15), "2. All-Gather", font=font_normal, fill=BLACK)
    for i in range(2):
        gx = cx + i * 200
        draw_rounded_rect(draw, (gx, sy, gx + 180, sy + 55), 5, WHITE, CYAN_BORDER, 1)
        draw.text((gx + 8, sy + 5), f"GPU {i}", font=font_small, fill=CYAN_BORDER)
        draw_rounded_rect(draw, (gx + 8, sy + 25, gx + 168, sy + 45), 3, BLUE_FILL, BLACK, 1)
        text_center(draw, "W FULL", gx + 88, sy + 35, font_tiny, WHITE)

    draw_arrow(draw, 440, sy + 30, 465, sy + 30, BLACK, 2)

    # Step 3: Compute with full weights
    sy2 = sy + 75
    draw.text((sx, sy2 - 5), "3. Compute (full W)", font=font_normal, fill=BLACK)
    for i in range(2):
        gx = sx + i * 200
        draw_rounded_rect(draw, (gx, sy2, gx + 180, sy2 + 50), 5, WHITE, CYAN_BORDER, 1)
        draw.text((gx + 8, sy2 + 5), f"GPU {i} (own data batch)", font=font_tiny, fill=CYAN_BORDER)
        draw_rounded_rect(draw, (gx + 8, sy2 + 22, gx + 168, sy2 + 42), 3, GREEN_FILL, BLACK, 1)
        text_center(draw, "X_i * W_FULL = Y_full", gx + 88, sy2 + 32, font_tiny, WHITE)

    # Step 4: Discard
    draw.text((cx, sy2 - 5), "4. Discard & move on", font=font_normal, fill=BLACK)
    draw_rounded_rect(draw, (cx, sy2, cx + 380, sy2 + 50), 5, WHITE, CYAN_BORDER, 1)
    draw.text((cx + 10, sy2 + 8), "After computing this layer:", font=font_small, fill=BLACK)
    draw.text((cx + 10, sy2 + 28), "Discard full W, keep only own 1/N shard", font=font_small, fill=RED_BORDER)

    # Key point
    sy3 = sy2 + 60
    draw_rounded_rect(draw, (sx, sy3, sx + 800, sy3 + 35), 5, (220, 255, 220), GREEN_BORDER, 2)
    text_center(draw, "KEY: Each GPU reconstructs FULL weights before compute. Same math as single-GPU!", sx + 400, sy3 + 17, font_normal, GREEN_BORDER)

    img.save("images/tp_vs_zero.png", quality=95)
    print("Generated: images/tp_vs_zero.png")


# ════════════════════════════════════════════════════════
# Diagram 4: 3D Parallelism
# ════════════════════════════════════════════════════════
def generate_3d_parallelism():
    W, H = 900, 650
    img = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(img)

    text_center(draw, "3D Parallelism: TP x PP x DP", W // 2, 20, font_title, BLUE_DARK)
    text_center(draw, "Example: 8 GPUs with TP=2, PP=2, DP=2", W // 2, 48, font_small, GRAY_TEXT)

    # Main layout: 2 DP groups, each with 2 PP stages, each with 2 TP ranks
    dp_colors = [(220, 235, 255), (255, 240, 220)]
    dp_borders = [BLUE_BORDER, ORANGE_BORDER]
    dp_labels = ["DP Rank 0", "DP Rank 1"]

    y_start = 80
    for dp_idx in range(2):
        dx = 30 + dp_idx * 440
        dy = y_start
        # DP group box
        draw_rounded_rect(draw, (dx, dy, dx + 420, dy + 260), 10, dp_colors[dp_idx], dp_borders[dp_idx], 2)
        draw.text((dx + 10, dy + 8), dp_labels[dp_idx], font=font_subtitle, fill=dp_borders[dp_idx])
        draw.text((dx + 10, dy + 30), f"Data Batch {dp_idx}", font=font_small, fill=GRAY_TEXT)

        for pp_idx in range(2):
            px = dx + 15 + pp_idx * 205
            py = dy + 55
            # PP stage box
            pp_color = GREEN_BG if pp_idx == 0 else PURPLE_BG
            pp_border = GREEN_BORDER if pp_idx == 0 else PURPLE_BORDER
            draw_rounded_rect(draw, (px, py, px + 190, py + 190), 8, pp_color, pp_border, 1)
            draw.text((px + 8, py + 5), f"PP Stage {pp_idx}", font=font_normal, fill=pp_border)
            layer_range = "Layer 0-46" if pp_idx == 0 else "Layer 47-93"
            draw.text((px + 8, py + 25), f"({layer_range})", font=font_small, fill=GRAY_TEXT)

            for tp_idx in range(2):
                tx = px + 10 + tp_idx * 88
                ty = py + 50
                # TP rank box (GPU)
                gpu_num = dp_idx * 4 + pp_idx * 2 + tp_idx
                draw_rounded_rect(draw, (tx, ty, tx + 80, ty + 125), 5, WHITE, BLACK, 1)
                text_center(draw, f"GPU {gpu_num}", tx + 40, ty + 12, font_small, BLACK)
                draw.text((tx + 5, ty + 28), f"TP Rank {tp_idx}", font=font_tiny, fill=ORANGE_BORDER)

                # Weight shard indicator
                half = "Left" if tp_idx == 0 else "Right"
                draw_rounded_rect(draw, (tx + 5, ty + 48, tx + 75, ty + 68), 3, ORANGE_FILL, BLACK, 1)
                text_center(draw, f"W {half}", tx + 40, ty + 58, font_tiny, WHITE)

                # Layer indicator
                draw_rounded_rect(draw, (tx + 5, ty + 75, tx + 75, ty + 95), 3,
                                  GREEN_FILL if pp_idx == 0 else PURPLE_FILL, BLACK, 1)
                text_center(draw, layer_range, tx + 40, ty + 85, font_tiny, WHITE)

                # NVLink label
                if tp_idx == 0:
                    draw.text((tx + 55, ty + 100), "NVLink", font=font_tiny, fill=ORANGE_BORDER)
                    draw.line([(tx + 80, ty + 108), (tx + 88, ty + 108)], fill=ORANGE_BORDER, width=2)

            # PP arrow
            if pp_idx == 0:
                draw_arrow(draw, px + 190, py + 100, px + 205, py + 100, GREEN_BORDER, 2)

    # DP sync arrow
    dp_arrow_y = y_start + 280
    draw.line([(240, dp_arrow_y), (660, dp_arrow_y)], fill=BLUE_DARK, width=2)
    draw_arrow(draw, 240, dp_arrow_y, 210, dp_arrow_y, BLUE_DARK, 2)
    draw_arrow(draw, 660, dp_arrow_y, 690, dp_arrow_y, BLUE_DARK, 2)
    text_center(draw, "DP: AllReduce gradients between replicas", W // 2, dp_arrow_y + 12, font_normal, BLUE_DARK)

    # Communication summary
    sy = 410
    draw_rounded_rect(draw, (20, sy, W - 20, sy + 220), 10, LIGHT_GRAY, BLACK, 1)
    draw.text((35, sy + 8), "Communication Patterns Summary", font=font_subtitle, fill=BLACK)

    table_data = [
        ("Parallelism", "What it splits", "Communication", "When", "Bandwidth Need"),
        ("DP", "Data batches", "AllReduce (gradients)", "After backward", "Medium"),
        ("TP", "Weight matrices", "AllReduce (activations)", "Every layer", "Very High (NVLink)"),
        ("PP", "Layer groups", "P2P (activations)", "Stage boundaries", "Low (Ethernet OK)"),
        ("ZeRO-1", "Optimizer states", "AllGather (OS)", "Optimizer step", "Low"),
        ("ZeRO-2", "OS + Gradients", "ReduceScatter (G)", "After backward", "Medium"),
        ("ZeRO-3", "OS + G + Params", "AllGather (W)", "Every layer fwd/bwd", "High"),
    ]

    ty = sy + 35
    col_widths = [90, 180, 200, 140, 150]
    col_x = [40]
    for w in col_widths[:-1]:
        col_x.append(col_x[-1] + w)

    for row_idx, row in enumerate(table_data):
        row_y = ty + row_idx * 25
        bg = LIGHT_GRAY if row_idx == 0 else WHITE if row_idx % 2 == 1 else (248, 248, 255)
        draw.rectangle((35, row_y - 2, W - 35, row_y + 22), fill=bg)
        for ci, cell in enumerate(row):
            f = font_small if row_idx == 0 else font_tiny
            c = BLACK if row_idx == 0 else GRAY_TEXT
            draw.text((col_x[ci], row_y + 2), cell, font=f, fill=c)

    img.save("images/3d_parallelism.png", quality=95)
    print("Generated: images/3d_parallelism.png")


# ════════════════════════════════════════════════════════
# Generate all diagrams
# ════════════════════════════════════════════════════════
if __name__ == "__main__":
    generate_parallelism_overview()
    generate_zero_stages()
    generate_tp_vs_zero()
    generate_3d_parallelism()
    print("\nAll diagrams generated successfully!")

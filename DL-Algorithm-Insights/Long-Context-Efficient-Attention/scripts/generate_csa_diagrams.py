#!/usr/bin/env python3
"""Generate CSA/HCA pipeline diagrams in the style of KV-Cache-Deep-Dive PIL images.
Output: images/csa_pipeline.png, images/hca_pipeline.png, images/three_dimensions.png
"""
import os
from PIL import Image, ImageDraw, ImageFont

# Color palette (matching KV-Cache-Deep-Dive style)
LIGHT_BLUE = "#E3F2FD"      # outer container
LIGHT_PURPLE = "#EDE7F6"    # inner node
LIGHT_GREEN = "#E8F5E9"     # output node
LIGHT_ORANGE = "#FFF3E0"    # alternative path
BORDER_BLUE = "#1976D2"
BORDER_PURPLE = "#7E57C2"
BORDER_GREEN = "#43A047"
BORDER_ORANGE = "#F57C00"
TEXT_DARK = "#212121"
TEXT_GRAY = "#616161"
ARROW_COLOR = "#424242"

# Try to load a clean font (Arial / DejaVu)
def get_font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def draw_rounded_rect(draw, xy, radius, fill, outline, width=2):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def draw_centered_text(draw, xy, text, font, fill=TEXT_DARK):
    x, y = xy
    if isinstance(text, str):
        lines = text.split("\n")
    else:
        lines = text
    line_h = font.size + 4
    total_h = line_h * len(lines)
    start_y = y - total_h // 2
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        draw.text((x - w // 2, start_y + i * line_h), line, font=font, fill=fill)


def draw_arrow(draw, start, end, color=ARROW_COLOR, width=2):
    draw.line([start, end], fill=color, width=width)
    # arrowhead
    import math
    dx, dy = end[0] - start[0], end[1] - start[1]
    angle = math.atan2(dy, dx)
    head_len = 10
    head_angle = math.radians(25)
    p1 = (end[0] - head_len * math.cos(angle - head_angle),
          end[1] - head_len * math.sin(angle - head_angle))
    p2 = (end[0] - head_len * math.cos(angle + head_angle),
          end[1] - head_len * math.sin(angle + head_angle))
    draw.polygon([end, p1, p2], fill=color)


# =============================================================================
# Diagram 1: CSA Pipeline (4 stages)
# =============================================================================
def draw_csa_pipeline():
    W, H = 1100, 1400
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    title_font = get_font(28, bold=True)
    stage_font = get_font(20, bold=True)
    body_font = get_font(16)
    small_font = get_font(13)

    # Title
    draw_centered_text(d, (W // 2, 35), "CSA Pipeline: Compressed Sparse Attention", title_font)

    # Input box
    cx = W // 2
    box_w = 600
    y = 90
    draw_rounded_rect(d, (cx - box_w // 2, y, cx + box_w // 2, y + 60), 10, LIGHT_PURPLE, BORDER_PURPLE)
    draw_centered_text(d, (cx, y + 30), "Input: Hidden States H ∈ R^(B × N × D)\n(N = sequence length, e.g. 1M tokens)", body_font)

    # Arrow down
    draw_arrow(d, (cx, y + 60), (cx, y + 95))

    # Stage 1: Block KV Compression
    y = 200
    box_h = 200
    draw_rounded_rect(d, (cx - 450, y, cx + 450, y + box_h), 12, LIGHT_BLUE, BORDER_BLUE, width=2)
    draw_centered_text(d, (cx, y + 22), "Stage 1: Block KV Compression", stage_font, fill=BORDER_BLUE)

    # Inner: 3 small boxes side by side
    inner_y = y + 55
    inner_w = 270
    gap = 15
    total_inner_w = 3 * inner_w + 2 * gap
    start_x = cx - total_inner_w // 2

    for i, (title, text) in enumerate([
        ("KV Projection", "C = W_kv × H\n(B, N, c)"),
        ("Gate Scoring", "Z = W_gate × H + APE\n(B, N, c)"),
        ("Gated Pooling", "Reshape to (n_blocks, m, c)\nKV_compressed = Σ softmax(Z) · C"),
    ]):
        bx = start_x + i * (inner_w + gap)
        draw_rounded_rect(d, (bx, inner_y, bx + inner_w, inner_y + 110), 8, LIGHT_PURPLE, BORDER_PURPLE)
        draw_centered_text(d, (bx + inner_w // 2, inner_y + 25), title, body_font, fill=BORDER_PURPLE)
        draw_centered_text(d, (bx + inner_w // 2, inner_y + 70), text, small_font)

    # output annotation
    draw_centered_text(d, (cx, y + box_h - 18),
                       "Output: Compressed KV ∈ R^(B × N/m × c) — m tokens compressed to 1 entry",
                       small_font, fill=TEXT_GRAY)

    # Arrow
    draw_arrow(d, (cx, y + box_h), (cx, y + box_h + 35))

    # Stage 2: Lightning Indexer
    y = 450
    box_h = 220
    draw_rounded_rect(d, (cx - 450, y, cx + 450, y + box_h), 12, LIGHT_BLUE, BORDER_BLUE, width=2)
    draw_centered_text(d, (cx, y + 22), "Stage 2: Lightning Indexer (FP4 acceleration)", stage_font, fill=BORDER_BLUE)

    inner_y = y + 55
    for i, (title, text) in enumerate([
        ("Latent Query", "c_t^Q = W_DQ × h_t\n(MLA-style low-rank Q)"),
        ("Index Score", "I(t,s) = Σ w_h · ReLU(q_h · K_s)\n(per compressed block s)"),
        ("Top-k Select", "topk_idx = top-k(I)\n(keep only k most relevant blocks)"),
    ]):
        bx = start_x + i * (inner_w + gap)
        draw_rounded_rect(d, (bx, inner_y, bx + inner_w, inner_y + 130), 8, LIGHT_PURPLE, BORDER_PURPLE)
        draw_centered_text(d, (bx + inner_w // 2, inner_y + 28), title, body_font, fill=BORDER_PURPLE)
        draw_centered_text(d, (bx + inner_w // 2, inner_y + 80), text, small_font)

    draw_centered_text(d, (cx, y + box_h - 18),
                       "Output: Top-k indices ∈ R^(B × n_heads × k) — sparse selection",
                       small_font, fill=TEXT_GRAY)

    draw_arrow(d, (cx, y + box_h), (cx, y + box_h + 35))

    # Stage 3: Sparse Core Attention
    y = 720
    box_h = 180
    draw_rounded_rect(d, (cx - 450, y, cx + 450, y + box_h), 12, LIGHT_BLUE, BORDER_BLUE, width=2)
    draw_centered_text(d, (cx, y + 22), "Stage 3: Sparse Core Attention (MQA)", stage_font, fill=BORDER_BLUE)

    inner_y = y + 55
    inner_w2 = 420
    gap2 = 30
    total = 2 * inner_w2 + gap2
    sx = cx - total // 2
    for i, (title, text) in enumerate([
        ("Gather Selected KV", "Gather k compressed entries\n+ sliding window KV (recent n tokens)"),
        ("MQA Attention", "o = softmax(q × KV^T / √d) × KV\n(Multi-Query: shared KV across heads)"),
    ]):
        bx = sx + i * (inner_w2 + gap2)
        draw_rounded_rect(d, (bx, inner_y, bx + inner_w2, inner_y + 90), 8, LIGHT_PURPLE, BORDER_PURPLE)
        draw_centered_text(d, (bx + inner_w2 // 2, inner_y + 25), title, body_font, fill=BORDER_PURPLE)
        draw_centered_text(d, (bx + inner_w2 // 2, inner_y + 60), text, small_font)

    draw_centered_text(d, (cx, y + box_h - 18),
                       "+ Attention Sink: learnable logit allows Σ attention < 1",
                       small_font, fill=TEXT_GRAY)

    draw_arrow(d, (cx, y + box_h), (cx, y + box_h + 35))

    # Stage 4: Output Projection
    y = 950
    box_h = 130
    draw_rounded_rect(d, (cx - 450, y, cx + 450, y + box_h), 12, LIGHT_BLUE, BORDER_BLUE, width=2)
    draw_centered_text(d, (cx, y + 22), "Stage 4: Grouped Low-Rank Output Projection", stage_font, fill=BORDER_BLUE)
    draw_centered_text(d, (cx, y + 75),
                       "o_grouped → W_oa (low-rank) → W_ob → output (B, N, D)\n"
                       "Reduces output projection params by O(n_groups)",
                       body_font)

    draw_arrow(d, (cx, y + box_h), (cx, y + box_h + 35))

    # Output box
    y = 1120
    draw_rounded_rect(d, (cx - 300, y, cx + 300, y + 60), 10, LIGHT_GREEN, BORDER_GREEN)
    draw_centered_text(d, (cx, y + 30), "Output: Hidden States ∈ R^(B × N × D)", body_font, fill=BORDER_GREEN)

    # Footer
    draw_centered_text(d, (W // 2, H - 50),
                       "Complexity: O(N/m + k) per token — sub-linear in N\n"
                       "KV cache: N/m compressed entries (e.g. 1M tokens, m=4 → 250K entries)",
                       small_font, fill=TEXT_GRAY)

    img.save("images/csa_pipeline.png", "PNG")
    print(f"CSA pipeline saved: {W}×{H}")


# =============================================================================
# Diagram 2: HCA Pipeline (3 stages, no indexer)
# =============================================================================
def draw_hca_pipeline():
    W, H = 1100, 1100
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    title_font = get_font(28, bold=True)
    stage_font = get_font(20, bold=True)
    body_font = get_font(16)
    small_font = get_font(13)

    draw_centered_text(d, (W // 2, 35), "HCA Pipeline: Heavily Compressed Attention", title_font)

    cx = W // 2
    inner_w = 270
    gap = 15
    total_inner_w = 3 * inner_w + 2 * gap
    start_x = cx - total_inner_w // 2

    # Input
    y = 90
    box_w = 600
    draw_rounded_rect(d, (cx - box_w // 2, y, cx + box_w // 2, y + 60), 10, LIGHT_PURPLE, BORDER_PURPLE)
    draw_centered_text(d, (cx, y + 30),
                       "Input: Hidden States H ∈ R^(B × N × D)",
                       body_font)

    draw_arrow(d, (cx, y + 60), (cx, y + 95))

    # Stage 1: Heavy Block Compression
    y = 200
    box_h = 220
    draw_rounded_rect(d, (cx - 450, y, cx + 450, y + box_h), 12, LIGHT_ORANGE, BORDER_ORANGE, width=2)
    draw_centered_text(d, (cx, y + 22), "Stage 1: Heavy Block Compression (m' >> m)", stage_font, fill=BORDER_ORANGE)

    inner_y = y + 55
    for i, (title, text) in enumerate([
        ("KV Projection", "C = W_kv × H\n(B, N, c)"),
        ("Gate Scoring", "Z = W_gate × H + APE\n(B, N, c)"),
        ("Heavy Pooling", "Reshape to (n_blocks, m', c)\nm' ≫ m (e.g. m'=64 vs m=4)"),
    ]):
        bx = start_x + i * (inner_w + gap)
        draw_rounded_rect(d, (bx, inner_y, bx + inner_w, inner_y + 130), 8, LIGHT_PURPLE, BORDER_PURPLE)
        draw_centered_text(d, (bx + inner_w // 2, inner_y + 28), title, body_font, fill=BORDER_PURPLE)
        draw_centered_text(d, (bx + inner_w // 2, inner_y + 80), text, small_font)

    draw_centered_text(d, (cx, y + box_h - 18),
                       "Output: Heavily Compressed KV ∈ R^(B × N/m' × c) — extreme compression",
                       small_font, fill=TEXT_GRAY)

    draw_arrow(d, (cx, y + box_h), (cx, y + box_h + 35))

    # Stage 2: Dense Attention (NO indexer)
    y = 470
    box_h = 180
    draw_rounded_rect(d, (cx - 450, y, cx + 450, y + box_h), 12, LIGHT_ORANGE, BORDER_ORANGE, width=2)
    draw_centered_text(d, (cx, y + 22), "Stage 2: Dense Attention (NO Indexer)", stage_font, fill=BORDER_ORANGE)

    inner_y = y + 55
    inner_w2 = 420
    gap2 = 30
    total = 2 * inner_w2 + gap2
    sx = cx - total // 2
    for i, (title, text) in enumerate([
        ("Use ALL Compressed", "No top-k selection needed\n(N/m' is already tiny)"),
        ("MQA Dense Attention", "o = softmax(q × KV^T / √d) × KV\nover all N/m' entries + window"),
    ]):
        bx = sx + i * (inner_w2 + gap2)
        draw_rounded_rect(d, (bx, inner_y, bx + inner_w2, inner_y + 90), 8, LIGHT_PURPLE, BORDER_PURPLE)
        draw_centered_text(d, (bx + inner_w2 // 2, inner_y + 25), title, body_font, fill=BORDER_PURPLE)
        draw_centered_text(d, (bx + inner_w2 // 2, inner_y + 60), text, small_font)

    draw_centered_text(d, (cx, y + box_h - 18),
                       "Why no Indexer? After m' compression, N/m' is small enough to attend densely.",
                       small_font, fill=TEXT_GRAY)

    draw_arrow(d, (cx, y + box_h), (cx, y + box_h + 35))

    # Stage 3: Output Projection
    y = 700
    box_h = 130
    draw_rounded_rect(d, (cx - 450, y, cx + 450, y + box_h), 12, LIGHT_ORANGE, BORDER_ORANGE, width=2)
    draw_centered_text(d, (cx, y + 22), "Stage 3: Grouped Low-Rank Output Projection", stage_font, fill=BORDER_ORANGE)
    draw_centered_text(d, (cx, y + 75),
                       "Same as CSA Stage 4 — o_grouped → W_oa → W_ob → (B, N, D)",
                       body_font)

    draw_arrow(d, (cx, y + box_h), (cx, y + box_h + 35))

    # Output
    y = 870
    draw_rounded_rect(d, (cx - 300, y, cx + 300, y + 60), 10, LIGHT_GREEN, BORDER_GREEN)
    draw_centered_text(d, (cx, y + 30), "Output: Hidden States ∈ R^(B × N × D)", body_font, fill=BORDER_GREEN)

    # Footer
    draw_centered_text(d, (W // 2, H - 50),
                       "Complexity: O(N/m') per token — linear but with very small constant\n"
                       "KV cache: N/m' entries (e.g. 1M tokens, m'=64 → 15.6K entries)",
                       small_font, fill=TEXT_GRAY)

    img.save("images/hca_pipeline.png", "PNG")
    print(f"HCA pipeline saved: {W}×{H}")


# =============================================================================
# Diagram 3: Three Orthogonal Compression Dimensions
# =============================================================================
def draw_three_dimensions():
    W, H = 1200, 850
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    title_font = get_font(28, bold=True)
    dim_font = get_font(20, bold=True)
    body_font = get_font(16)
    small_font = get_font(13)

    draw_centered_text(d, (W // 2, 35), "Three Orthogonal KV Cache Compression Dimensions", title_font)
    draw_centered_text(d, (W // 2, 75),
                       "These three dimensions are independent and can be combined freely.\n"
                       "DeepSeek-V4 = MLA (D1) + CSA/HCA (D3); Hybrid Mamba = D2; Standard GQA = D1 only.",
                       small_font, fill=TEXT_GRAY)

    # Three columns
    col_w = 360
    col_h = 580
    gap = 30
    total_w = 3 * col_w + 2 * gap
    start_x = (W - total_w) // 2
    y_top = 130

    cols = [
        {
            "title": "Dimension 1: Within-Layer\nKV Head Compression",
            "color": LIGHT_BLUE,
            "border": BORDER_BLUE,
            "items": [
                ("MHA", "1 KV head per Q head\nBaseline (largest cache)"),
                ("GQA", "g groups share 1 KV head\nLlama 3, Qwen3"),
                ("MQA", "All Q heads share 1 KV head\nPaLM"),
                ("MLA", "Low-rank latent K/V projection\nDeepSeek-V2/V3"),
            ],
            "summary": "Reduces per-token KV cache size",
        },
        {
            "title": "Dimension 2: Cross-Layer\nLayer Replacement",
            "color": LIGHT_ORANGE,
            "border": BORDER_ORANGE,
            "items": [
                ("All Attention", "Every layer has KV cache\nGPT-4, Llama 3"),
                ("Hybrid Linear", "30/40 layers Linear Attn\nQwen3.5"),
                ("Hybrid Mamba", "46/52 layers Mamba\nNemotron-3-Nano"),
                ("Sliding Window", "Limit each layer to local\nMistral"),
            ],
            "summary": "Reduces number of layers with KV cache",
        },
        {
            "title": "Dimension 3 (NEW):\nSequence-Length Compression",
            "color": LIGHT_GREEN,
            "border": BORDER_GREEN,
            "items": [
                ("Standard", "1 KV entry per token\nAll prior architectures"),
                ("CSA (m=4)", "m tokens → 1 entry + top-k\nDeepSeek-V4 (NEW)"),
                ("HCA (m'=64)", "m' >> m, dense attend\nDeepSeek-V4 (NEW)"),
                ("Sparse Selection", "Lightning Indexer FP4\nDeepSeek-V4 (NEW)"),
            ],
            "summary": "Reduces number of KV entries per layer",
        },
    ]

    for i, col in enumerate(cols):
        x = start_x + i * (col_w + gap)
        # Header
        draw_rounded_rect(d, (x, y_top, x + col_w, y_top + 70), 12, col["color"], col["border"], width=2)
        draw_centered_text(d, (x + col_w // 2, y_top + 35), col["title"], dim_font, fill=col["border"])
        # Items
        item_h = 95
        item_gap = 10
        item_y = y_top + 90
        for j, (name, desc) in enumerate(col["items"]):
            iy = item_y + j * (item_h + item_gap)
            draw_rounded_rect(d, (x + 15, iy, x + col_w - 15, iy + item_h), 8, LIGHT_PURPLE, BORDER_PURPLE)
            draw_centered_text(d, (x + col_w // 2, iy + 25), name, body_font, fill=BORDER_PURPLE)
            draw_centered_text(d, (x + col_w // 2, iy + 60), desc, small_font)
        # Summary
        sy = item_y + len(col["items"]) * (item_h + item_gap) + 5
        draw_centered_text(d, (x + col_w // 2, sy + 15),
                           col["summary"], small_font, fill=col["border"])

    # Bottom note
    draw_centered_text(d, (W // 2, H - 35),
                       "DeepSeek-V4 is the first production model to combine D1 (MLA) + D3 (CSA/HCA).\n"
                       "Cross-reference: KV-Cache-Deep-Dive covers D1 and D2 in depth.",
                       small_font, fill=TEXT_GRAY)

    img.save("images/three_dimensions.png", "PNG")
    print(f"Three dimensions diagram saved: {W}×{H}")


if __name__ == "__main__":
    os.makedirs("images", exist_ok=True)
    draw_csa_pipeline()
    draw_hca_pipeline()
    draw_three_dimensions()
    print("All diagrams generated.")

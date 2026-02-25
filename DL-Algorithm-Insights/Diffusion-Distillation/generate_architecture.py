"""
Generate architecture diagrams for Diffusion Distillation topic.
Produces: two_stage_pipeline.png
Author: Xinyu Wei (魏新宇)
"""

from PIL import Image, ImageDraw, ImageFont
import os

# Color palette
BLUE_BG = (232, 244, 255)
BLUE_BORDER = (0, 120, 212)
ORANGE_BG = (255, 243, 224)
ORANGE_BORDER = (255, 140, 0)
GREEN_BG = (232, 255, 232)
GREEN_BORDER = (16, 124, 16)
PURPLE_BG = (243, 232, 255)
PURPLE_BORDER = (112, 0, 160)
GRAY_BG = (245, 245, 245)
GRAY_BORDER = (108, 108, 108)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
DARK_GRAY = (68, 68, 68)
RED_BG = (255, 232, 232)
RED_BORDER = (196, 0, 0)


def load_font(size):
    """Load font with fallback."""
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
    except Exception:
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", size)
        except Exception:
            return ImageFont.load_default()


def load_bold_font(size):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except Exception:
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", size)
        except Exception:
            return ImageFont.load_default()


def draw_rounded_box(draw, x, y, w, h, bg, border, radius=8, border_width=2):
    draw.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=bg, outline=border, width=border_width)


def draw_text_centered(draw, x, y, w, h, text, font, color=BLACK):
    """Draw text centered inside a box."""
    lines = text.split('\n')
    line_h = h // len(lines)
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        tx = x + (w - tw) // 2
        ty = y + i * line_h + (line_h - (bbox[3] - bbox[1])) // 2
        draw.text((tx, ty), line, fill=color, font=font)


def draw_arrow(draw, x1, y1, x2, y2, color=DARK_GRAY, width=2):
    """Draw a horizontal or vertical arrow."""
    draw.line([x1, y1, x2, y2], fill=color, width=width)
    # Arrowhead
    if x2 > x1:  # right arrow
        draw.polygon([(x2, y2), (x2 - 10, y2 - 5), (x2 - 10, y2 + 5)], fill=color)
    elif x2 < x1:  # left arrow
        draw.polygon([(x2, y2), (x2 + 10, y2 - 5), (x2 + 10, y2 + 5)], fill=color)
    elif y2 > y1:  # down arrow
        draw.polygon([(x2, y2), (x2 - 5, y2 - 10), (x2 + 5, y2 - 10)], fill=color)
    else:  # up arrow
        draw.polygon([(x2, y2), (x2 - 5, y2 + 10), (x2 + 5, y2 + 10)], fill=color)


def generate_two_stage_pipeline():
    """
    Two-stage diffusion distillation pipeline:
    Stage 1: SFT LoRA training on base model
    Stage 2: Trajectory distillation (Teacher offline → Student LoRA)
    """
    W, H = 760, 480
    img = Image.new('RGB', (W, H), WHITE)
    draw = ImageDraw.Draw(img)

    f12 = load_font(12)
    f13 = load_font(13)
    f14 = load_font(14)
    f_bold = load_bold_font(14)
    f_bold_lg = load_bold_font(16)
    f11 = load_font(11)

    # ─── Title ───
    title = "Two-Stage Diffusion Distillation Training Pipeline"
    bbox = draw.textbbox((0, 0), title, font=f_bold_lg)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, 14), title, fill=BLACK, font=f_bold_lg)

    # ─── Stage 1 header ───
    draw_rounded_box(draw, 20, 44, 340, 26, BLUE_BG, BLUE_BORDER, radius=6)
    draw_text_centered(draw, 20, 44, 340, 26, "Stage 1: SFT (Supervised Fine-Tuning)", f_bold, BLUE_BORDER)

    # Base model box
    draw_rounded_box(draw, 30, 84, 130, 52, GRAY_BG, GRAY_BORDER)
    draw_text_centered(draw, 30, 84, 130, 52, "Base Model\n(Frozen)", f13, DARK_GRAY)

    # Training data
    draw_rounded_box(draw, 30, 154, 130, 52, ORANGE_BG, ORANGE_BORDER)
    draw_text_centered(draw, 30, 154, 130, 52, "Training Data\n(image pairs)", f13, ORANGE_BORDER)

    # SFT LoRA
    draw_rounded_box(draw, 190, 110, 130, 52, BLUE_BG, BLUE_BORDER)
    draw_text_centered(draw, 190, 110, 130, 52, "SFT LoRA\nTraining", f13, BLUE_BORDER)

    # Merged model (Stage 1 output)
    draw_rounded_box(draw, 190, 190, 130, 44, GREEN_BG, GREEN_BORDER)
    draw_text_centered(draw, 190, 190, 130, 44, "Merged Model\n(step-N)", f13, GREEN_BORDER)

    # Arrows Stage 1
    draw_arrow(draw, 162, 110, 188, 136)       # base model → SFT
    draw_arrow(draw, 162, 180, 188, 155)       # training data → SFT
    draw_arrow(draw, 255, 162, 255, 188)       # SFT → merged model

    # ─── Stage 2 header ───
    draw_rounded_box(draw, 390, 44, 350, 26, PURPLE_BG, PURPLE_BORDER, radius=6)
    draw_text_centered(draw, 390, 44, 350, 26, "Stage 2: Trajectory Distillation", f_bold, PURPLE_BORDER)

    # Teacher (= merged model)
    draw_rounded_box(draw, 400, 84, 130, 52, GREEN_BG, GREEN_BORDER)
    draw_text_centered(draw, 400, 84, 130, 52, "Teacher\n(Merged Model)", f13, GREEN_BORDER)

    # Arrow from stage 1 output to teacher
    draw_arrow(draw, 322, 212, 390, 110)

    # Trajectory collection
    draw_rounded_box(draw, 400, 154, 130, 44, ORANGE_BG, ORANGE_BORDER)
    draw_text_centered(draw, 400, 154, 130, 44, "Trajectory\nCollection", f13, ORANGE_BORDER)

    # Arrow teacher → trajectory
    draw_arrow(draw, 465, 136, 465, 152)

    # Stored trajectories
    draw_rounded_box(draw, 400, 216, 130, 44, GRAY_BG, GRAY_BORDER)
    draw_text_centered(draw, 400, 216, 130, 44, "Stored Trajectories\n(latent tensors)", f12, DARK_GRAY)
    draw_arrow(draw, 465, 198, 465, 214)

    # Distill LoRA training
    draw_rounded_box(draw, 560, 154, 158, 52, PURPLE_BG, PURPLE_BORDER)
    draw_text_centered(draw, 560, 154, 158, 52, "Distill LoRA\nTraining", f13, PURPLE_BORDER)

    draw_arrow(draw, 530, 180, 558, 180)       # trajectories → distill
    draw_arrow(draw, 530, 238, 590, 208)       # stored traj → distill

    # Distill LoRA output
    draw_rounded_box(draw, 560, 224, 158, 44, PURPLE_BG, PURPLE_BORDER)
    draw_text_centered(draw, 560, 224, 158, 44, "Distill LoRA\n(+fast inference)", f13, PURPLE_BORDER)
    draw_arrow(draw, 639, 206, 639, 222)

    # ─── Inference modes (bottom) ───
    draw_rounded_box(draw, 20, 310, 340, 26, GRAY_BG, GRAY_BORDER, radius=6)
    draw_text_centered(draw, 20, 310, 340, 26, "Inference", f_bold, DARK_GRAY)

    draw_rounded_box(draw, 30, 350, 150, 44, GRAY_BG, GRAY_BORDER)
    draw_text_centered(draw, 30, 350, 150, 44, "Merged Model\nLoRA OFF → 40–50 steps", f11, DARK_GRAY)

    draw_rounded_box(draw, 200, 350, 150, 44, GREEN_BG, GREEN_BORDER)
    draw_text_centered(draw, 200, 350, 150, 44, "Merged Model\nLoRA ON → 8 steps", f11, GREEN_BORDER)

    # Labels under boxes
    draw.text((55, 398), "High quality, high latency", fill=GRAY_BORDER, font=f11)
    draw.text((203, 398), "~4.6× faster, similar quality", fill=GREEN_BORDER, font=f11)

    # Connect stage 2 distill lora to inference
    draw_arrow(draw, 639, 270, 639, 330)
    # Vertical line down to inference area
    draw.line([639, 330, 639, 372], fill=DARK_GRAY, width=2)
    draw.line([639, 372, 275, 372], fill=DARK_GRAY, width=2)
    draw_arrow(draw, 275, 372, 275, 396)

    # Key numbers annotation
    draw_rounded_box(draw, 400, 310, 340, 80, (255, 252, 230), (200, 160, 0), radius=6, border_width=1)
    draw.text((415, 318), "Key Numbers (H100, 20B DiT, 5 epochs)", fill=(160, 120, 0), font=f11)
    draw.text((415, 336), "Training loss:  0.0084 → 0.0052  (↓38%)", fill=DARK_GRAY, font=f11)
    draw.text((415, 352), "Teacher: 40 steps  →  44.0s per image", fill=DARK_GRAY, font=f11)
    draw.text((415, 368), "Student:   8 steps  →   9.5s per image  (4.6× faster)", fill=GREEN_BORDER, font=f11)

    # Crop to final height
    final_h = 420
    img = img.crop((0, 0, W, final_h))
    return img


if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(__file__), "images")
    os.makedirs(out_dir, exist_ok=True)

    img = generate_two_stage_pipeline()
    out_path = os.path.join(out_dir, "two_stage_pipeline.png")
    img.save(out_path)
    print(f"✅ Saved: {out_path}  ({img.width}×{img.height})")

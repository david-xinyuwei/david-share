#!/usr/bin/env python3
"""Generate the conceptual OPD diagrams used by the README files.

Usage:
    python3 scripts/generate_diagrams.py --output-dir images
"""
import argparse
import os
from textwrap import wrap


def load_font(size, bold=False):
    from PIL import ImageFont

    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def draw_wrapped_text(draw, xy, text, font, fill, max_chars, line_gap=6, anchor=None):
    left, top = xy
    lines = []
    for paragraph in text.split("\n"):
        lines.extend(wrap(paragraph, max_chars) or [""])
    current_top = top
    for line in lines:
        draw.text((left, current_top), line, font=font, fill=fill, anchor=anchor)
        bbox = draw.textbbox((left, current_top), line, font=font, anchor=anchor)
        current_top += (bbox[3] - bbox[1]) + line_gap
    return current_top


def draw_box(draw, bounds, title, body, fill, outline, title_color="#111827"):
    left, top, right, bottom = bounds
    title_font = load_font(24, bold=True)
    body_font = load_font(18)
    draw.rounded_rectangle(bounds, radius=8, fill=fill, outline=outline, width=2)
    draw.text((left + 24, top + 20), title, font=title_font, fill=title_color)
    draw_wrapped_text(draw, (left + 24, top + 62), body, body_font, "#374151", max_chars=max(18, (right - left) // 14))


def draw_arrow(draw, start, end, color="#475569", width=4):
    draw.line([start, end], fill=color, width=width)
    end_x, end_y = end
    if end[0] >= start[0]:
        points = [(end_x, end_y), (end_x - 14, end_y - 8), (end_x - 14, end_y + 8)]
    else:
        points = [(end_x, end_y), (end_x + 14, end_y - 8), (end_x + 14, end_y + 8)]
    draw.polygon(points, fill=color)


def add_border(image):
    from PIL import Image, ImageDraw

    padding = 24
    border = 1
    canvas = Image.new("RGB", (image.width + 2 * (padding + border), image.height + 2 * (padding + border)), "white")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, 0, canvas.width - 1, canvas.height - 1], outline="#dcdee2", width=border)
    canvas.paste(image, (padding + border, padding + border))
    return canvas


def generate_offline_vs_opd(output_dir):
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (1280, 640), "#f8fafc")
    draw = ImageDraw.Draw(image)
    title_font = load_font(32, bold=True)
    subtitle_font = load_font(20)
    draw.text((40, 32), "Offline Distillation vs On-Policy Distillation", font=title_font, fill="#0f172a")
    draw.text((40, 76), "The key difference is whose trajectories the student trains on.", font=subtitle_font, fill="#475569")

    draw_box(draw, (70, 150, 570, 540), "Offline Distillation", "1. Teacher generates answers\n2. Student imitates teacher trajectories\n3. Student later rolls out on a distribution it was not trained on", "#eff6ff", "#2563eb")
    draw_box(draw, (710, 150, 1210, 540), "On-Policy Distillation", "1. Student generates its own answers\n2. Teacher scores those exact student tokens\n3. Student updates on the distribution it will visit at inference time", "#fff7ed", "#ea580c")

    draw_arrow(draw, (570, 340), (710, 340), color="#64748b", width=5)

    output_path = os.path.join(output_dir, "opd_vs_offline.png")
    add_border(image).save(output_path)
    print(f"Saved {output_path}")


def generate_multi_teacher_opd(output_dir):
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (1280, 760), "#f8fafc")
    draw = ImageDraw.Draw(image)
    title_font = load_font(32, bold=True)
    label_font = load_font(18, bold=True)
    small_font = load_font(16)
    draw.text((40, 28), "Multi-Expert On-Policy Distillation", font=title_font, fill="#0f172a")
    draw.text((40, 72), "One student rollout is scored by multiple specialist teachers; only the student is updated.", font=small_font, fill="#475569")

    draw_box(draw, (60, 180, 310, 330), "Student", "Samples its own trajectory\nπ_θ(y | prompt)", "#ecfdf5", "#16a34a")
    draw_box(draw, (390, 175, 650, 335), "Rollout", "Prompt + student tokens\nThis is the on-policy path", "#f1f5f9", "#64748b")
    draw_box(draw, (760, 120, 1030, 230), "Math Teacher", "math-token logits", "#eff6ff", "#2563eb")
    draw_box(draw, (760, 265, 1030, 375), "Code Teacher", "code-token logits", "#eef2ff", "#4f46e5")
    draw_box(draw, (760, 410, 1030, 520), "Writing Teacher", "style-token logits", "#fdf2f8", "#db2777")
    draw_box(draw, (760, 555, 1030, 665), "Other Experts", "agent, reasoning, translation", "#fefce8", "#ca8a04")
    draw_box(draw, (1070, 305, 1240, 485), "Weighted KL", "Σ_i weighted KL\nupdates student only", "#fff7ed", "#ea580c")

    draw_arrow(draw, (310, 255), (390, 255), color="#16a34a")
    for teacher_midpoint in [(760, 175), (760, 320), (760, 465), (760, 610)]:
        draw_arrow(draw, (650, 255), teacher_midpoint, color="#64748b", width=3)
    for teacher_midpoint in [(1030, 175), (1030, 320), (1030, 465), (1030, 610)]:
        draw_arrow(draw, teacher_midpoint, (1070, 395), color="#ea580c", width=3)
    draw.text((500, 700), "Gradient step changes θ in the student; teacher weights stay frozen.", font=label_font, fill="#dc2626")

    output_path = os.path.join(output_dir, "multi_teacher_opd.png")
    add_border(image).save(output_path)
    print(f"Saved {output_path}")


def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parser = argparse.ArgumentParser(description="Generate README concept diagrams for the OPD repo.")
    parser.add_argument("--output-dir", default=os.path.join(repo_root, "images"), help="Directory for generated PNG files")
    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    generate_offline_vs_opd(args.output_dir)
    generate_multi_teacher_opd(args.output_dir)


if __name__ == "__main__":
    main()
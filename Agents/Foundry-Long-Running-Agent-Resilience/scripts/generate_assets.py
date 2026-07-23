#!/usr/bin/env python3
"""Generate deterministic documentation images for the validation kit."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "images"
WIDTH = 1600
HEIGHT = 900


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    names = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
    ]
    for name in names:
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def centered(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, text_font, fill: str) -> None:
    left, top, right, bottom = box
    bounds = draw.multiline_textbbox((0, 0), text, font=text_font, spacing=8, align="center")
    text_width = bounds[2] - bounds[0]
    text_height = bounds[3] - bounds[1]
    draw.multiline_text(
        ((left + right - text_width) / 2, (top + bottom - text_height) / 2),
        text,
        font=text_font,
        fill=fill,
        spacing=8,
        align="center",
    )


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: str) -> None:
    draw.line((start, end), fill=color, width=8)
    x, y = end
    draw.polygon([(x, y), (x - 22, y - 14), (x - 22, y + 14)], fill=color)


def background() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), "#F4F7FA")
    draw = ImageDraw.Draw(image)
    for x in range(0, WIDTH, 40):
        draw.line((x, 0, x, HEIGHT), fill="#E8EEF3", width=1)
    for y in range(0, HEIGHT, 40):
        draw.line((0, y, WIDTH, y), fill="#E8EEF3", width=1)
    return image, draw


def evidence_pipeline() -> None:
    image, draw = background()
    draw.text((70, 55), "Evidence-first resilience validation", font=font(52, True), fill="#16212B")
    draw.text(
        (72, 125),
        "Failure injection is only the midpoint; recovery proof must reach a terminal workload result.",
        font=font(24),
        fill="#425466",
    )
    colors = ["#1363DF", "#D9485F", "#D98E04", "#0F8B6D", "#5F4BB6"]
    labels = [
        "Authenticated\nhosted run",
        "Checkpoint +\nfailure\ninjection",
        "Reconnect +\nprotocol\nevidence",
        "Sanitization\nboundary",
        "Public\nattestation +\nhash manifest",
    ]
    boxes = []
    x = 70
    for color, label in zip(colors, labels, strict=True):
        box = (x, 295, x + 250, 555)
        boxes.append(box)
        draw.rounded_rectangle(box, radius=16, fill="white", outline=color, width=6)
        draw.rounded_rectangle((x, 295, x + 250, 345), radius=16, fill=color)
        centered(draw, (x + 18, 350, x + 232, 535), label, font(22, True), "#17212B")
        x += 305
    for left, right in zip(boxes, boxes[1:]):
        arrow(draw, (left[2] + 10, 425), (right[0] - 12, 425), "#617487")
    draw.rounded_rectangle((70, 690, 1530, 800), radius=14, fill="#17212B")
    centered(
        draw,
        (95, 700, 1505, 790),
        "Public boundary: no raw logs, credentials, endpoints, resource IDs, private source, or deployment recipe",
        font(21, True),
        "#FFFFFF",
    )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT / "evidence-pipeline.png", optimize=True)


def scenario_coverage() -> None:
    image, draw = background()
    draw.text((70, 55), "Eight main scenarios, four proof patterns", font=font(52, True), fill="#16212B")
    draw.text(
        (72, 125),
        "The matrix validates workload behavior, not deployment status alone.",
        font=font(24),
        fill="#425466",
    )
    cards = [
        ((70, 245, 760, 470), "Research durability", "Python + .NET\nResponses + Invocations\n18 phases | checkpoint | failure | resume", "#1363DF"),
        ((840, 245, 1530, 470), "Graph + human approval", "Invocations + Responses\napproval checkpoint | restart | resume | completion", "#D9485F"),
        ((70, 535, 760, 760), "Durable workflow", "persisted stage outputs\ntemporary host unavailability\nterminal round-trip result", "#0F8B6D"),
        ((840, 535, 1530, 760), "Steering", "materially different follow-up\nqueued while active\nnew answer reaches completion", "#D98E04"),
    ]
    for box, title, details, color in cards:
        draw.rounded_rectangle(box, radius=18, fill="white", outline=color, width=6)
        draw.rectangle((box[0], box[1], box[0] + 18, box[3]), fill=color)
        draw.text((box[0] + 48, box[1] + 35), title, font=font(34, True), fill="#17212B")
        draw.multiline_text(
            (box[0] + 48, box[1] + 98),
            details,
            font=font(24),
            fill="#425466",
            spacing=12,
        )
    draw.text((70, 830), "Sanitized authenticated-run attestations | Raw private evidence withheld", font=font(22, True), fill="#5F4BB6")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT / "scenario-coverage.png", optimize=True)


def main() -> int:
    evidence_pipeline()
    scenario_coverage()
    print("Generated 2 documentation images.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

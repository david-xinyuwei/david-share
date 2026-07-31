#!/usr/bin/env python3
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH = 1280
HEIGHT = 720
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def font(size: int, bold: bool = False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT, size)


def wrap_text(draw, text, text_font, max_width):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=text_font)[2] <= max_width:
            current = candidate
        else:
            if not current:
                raise ValueError(f"Text token is wider than its container: {word}")
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_bounded_text(draw, position, text, text_font, fill, bounds):
    x, y = position
    left, top, right, bottom = draw.textbbox((x, y), text, font=text_font)
    x1, y1, x2, y2 = bounds
    if left < x1 or top < y1 or right > x2 or bottom > y2:
        raise ValueError(
            f"Text exceeds bounds: {text!r} bbox={(left, top, right, bottom)} "
            f"bounds={bounds}"
        )
    draw.text(position, text, font=text_font, fill=fill)


def box(draw, xy, title, lines, fill, border):
    draw.rounded_rectangle(xy, radius=8, fill=fill, outline=border, width=2)
    x1, y1, x2, y2 = xy
    title_font = font(21, True)
    title_lines = wrap_text(draw, title, title_font, x2 - x1 - 36)
    if len(title_lines) > 2:
        raise ValueError(f"Card title requires more than two lines: {title!r}")
    title_y = y1 + 14
    for title_line in title_lines:
        draw_bounded_text(
            draw,
            (x1 + 18, title_y),
            title_line,
            title_font,
            "#17202a",
            (x1 + 16, y1 + 10, x2 - 16, y2 - 10),
        )
        title_y += 25
    body_font = font(16)
    y = title_y + 10
    for line in lines:
        draw_bounded_text(
            draw,
            (x1 + 18, y),
            line,
            body_font,
            "#34495e",
            (x1 + 16, y1 + 10, x2 - 16, y2 - 10),
        )
        y += 24


def arrow(draw, start, end, color="#5d6d7e"):
    draw.line([start, end], fill=color, width=4)
    x, y = end
    draw.polygon([(x, y), (x - 12, y - 7), (x - 12, y + 7)], fill=color)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the SWE-bench workflow diagram.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "images"
        / "swebench_workflow.png",
    )
    args = parser.parse_args()

    image = Image.new("RGB", (WIDTH, HEIGHT), "#ffffff")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH, 94), fill="#17202a")
    draw.text((52, 22), "How SWE-bench Evaluates an OSS Model", font=font(34, True), fill="#ffffff")
    draw.text(
        (54, 64),
        "Generation creates a patch; the official Docker harness decides whether it resolves the issue.",
        font=font(17),
        fill="#d5d8dc",
    )

    box(
        draw,
        (42, 142, 282, 342),
        "1. Verified Task",
        ["Issue text", "Base commit", "Test patch", "FAIL_TO_PASS", "PASS_TO_PASS"],
        "#f4f6f7",
        "#85929e",
    )
    box(
        draw,
        (332, 142, 572, 342),
        "2. Agent Generation",
        ["mini-swe-agent", "OSS model endpoint", "bash tool calls", "Trajectory + patch", "No scoring yet"],
        "#eaf2f8",
        "#2e86c1",
    )
    box(
        draw,
        (622, 142, 862, 342),
        "3. Frozen Artifacts",
        ["preds.json", "*.traj.json", "Effective config", "Run manifest", "SHA-256 evidence"],
        "#fef9e7",
        "#b7950b",
    )
    box(
        draw,
        (912, 142, 1238, 342),
        "4. Official Docker Harness",
        ["Restore task image", "Apply candidate patch", "Apply test patch", "Run authoritative tests", "Enforce timeout + cleanup"],
        "#fbeee6",
        "#ca6f1e",
    )

    arrow(draw, (282, 242), (332, 242))
    arrow(draw, (572, 242), (622, 242))
    arrow(draw, (862, 242), (912, 242))

    draw.rounded_rectangle((180, 410, 1100, 565), radius=8, fill="#e8f8f5", outline="#148f77", width=2)
    draw.text((210, 432), "5. Official Outcome", font=font(26, True), fill="#0e6251")
    draw.text((210, 479), "Resolved", font=font(24, True), fill="#117864")
    draw.text((355, 481), "FAIL_TO_PASS passes and PASS_TO_PASS remains green", font=font(18), fill="#34495e")
    draw.text((210, 520), "Not-Pass", font=font(24, True), fill="#a93226")
    draw.text((340, 522), "Unresolved, Empty, or Error remain distinct categories", font=font(18), fill="#34495e")
    draw.line([(1075, 342), (1075, 385), (640, 385), (640, 410)], fill="#148f77", width=4)
    draw.polygon([(640, 410), (633, 398), (647, 398)], fill="#148f77")

    draw.rounded_rectangle((42, 615, 1238, 682), radius=8, fill="#f8f9f9", outline="#ccd1d1", width=1)
    draw.text((66, 633), "Best practice:", font=font(18, True), fill="#17202a")
    draw.text(
        (225, 633),
        "freeze versions and IDs before generation; retry infrastructure failures separately;",
        font=font(17),
        fill="#34495e",
    )
    draw.text(
        (225, 657),
        "freeze dispute sets once; never use dynamic best-of retests.",
        font=font(17),
        fill="#34495e",
    )

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, optimize=True)
    print(f"WORKFLOW_DIAGRAM=PASS path={output} size={image.size}")


if __name__ == "__main__":
    main()
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


def draw_bounded_text(draw, position, text, text_font, fill, bounds):
    left, top, right, bottom = draw.textbbox(position, text, font=text_font)
    x1, y1, x2, y2 = bounds
    if left < x1 or top < y1 or right > x2 or bottom > y2:
        raise ValueError(f"Text exceeds bounds: {text!r} bbox={(left, top, right, bottom)} bounds={bounds}")
    draw.text(position, text, font=text_font, fill=fill)


def panel(draw, xy, title, lines, fill, border, title_color):
    draw.rounded_rectangle(xy, radius=8, fill=fill, outline=border, width=2)
    x1, y1, x2, y2 = xy
    bounds = (x1 + 16, y1 + 10, x2 - 16, y2 - 10)
    draw_bounded_text(draw, (x1 + 22, y1 + 16), title, font(21, True), title_color, bounds)
    y = y1 + 52
    for line in lines:
        draw_bounded_text(draw, (x1 + 22, y), line, font(16), "#34495e", bounds)
        y += 26


def arrow(draw, start, end, color="#5d6d7e"):
    draw.line([start, end], fill=color, width=4)
    x, y = end
    draw.polygon([(x, y), (x - 12, y - 7), (x - 12, y + 7)], fill=color)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the SWE-bench component-role diagram.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "images" / "swebench_roles.png",
    )
    args = parser.parse_args()

    image = Image.new("RGB", (WIDTH, HEIGHT), "#ffffff")
    draw = ImageDraw.Draw(image)

    draw.rectangle((0, 0, WIDTH, 92), fill="#17202a")
    draw.text((44, 20), "Who Does What in a SWE-bench Run", font=font(30, True), fill="#ffffff")
    draw.text(
        (46, 60),
        "The model is the candidate, the agent is its hands, the harness is the judge.",
        font=font(15),
        fill="#d5d8dc",
    )

    panel(
        draw,
        (42, 122, 318, 332),
        "1. Exam paper",
        ["SWE-bench Verified", "500 real GitHub issues", "Repo snapshot per task", "Official tests per task"],
        "#f4f6f7",
        "#85929e",
        "#17202a",
    )
    panel(
        draw,
        (348, 122, 624, 332),
        "2. Candidate",
        ["Model under test", "Runs on GPU VM or Foundry", "Thinks and emits commands", "No direct file access"],
        "#eaf2f8",
        "#2e86c1",
        "#1b4f72",
    )
    panel(
        draw,
        (654, 122, 930, 332),
        "3. Hands",
        ["mini-swe-agent", "Gives the model bash", "Runs commands, feeds back", "Writes preds.json"],
        "#e8f8f5",
        "#148f77",
        "#0e6251",
    )
    panel(
        draw,
        (960, 122, 1236, 332),
        "4. Judge",
        ["Official SWE-bench harness", "One Docker image per task", "Runs the project tests", "Decides Resolved or not"],
        "#fbeee6",
        "#ca6f1e",
        "#9c4a06",
    )

    for x1, x2 in ((318, 348), (624, 654), (930, 960)):
        arrow(draw, (x1 + 4, 227), (x2 - 4, 227))

    panel(
        draw,
        (42, 372, 624, 642),
        "Agent harness = mini-swe-agent",
        [
            "Prompt templates live in swebench.yaml",
            "System and instance templates are sent",
            "to the model under test on every task",
            "Model client and tool-parsing modules",
            "Replaceable: another agent is allowed,",
            "but changing it changes the score",
        ],
        "#e8f8f5",
        "#148f77",
        "#0e6251",
    )
    panel(
        draw,
        (654, 372, 1236, 642),
        "Test harness = swebench.harness",
        [
            "0 prompt templates, 0 model calls",
            "Docker build, run, and grading only",
            "Compares FAIL_TO_PASS and PASS_TO_PASS",
            "Same English word, older meaning:",
            "a test runner, not agent scaffolding",
            "Not replaceable: it defines the score",
        ],
        "#fbeee6",
        "#ca6f1e",
        "#9c4a06",
    )

    draw.rounded_rectangle((42, 662, 1236, 706), radius=8, fill="#f8f9f9", outline="#ccd1d1", width=1)
    draw.text(
        (66, 675),
        "Platform choice only moves box 2; boxes 3 and 4 never change. That is why one code path covers every endpoint.",
        font=font(16),
        fill="#34495e",
    )

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, optimize=True)
    print(f"ROLES_DIAGRAM=PASS path={output} size={image.size}")


if __name__ == "__main__":
    main()

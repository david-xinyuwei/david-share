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


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the public MiMo-V2.5-Pro SWE-bench result.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "images" / "mimo_swebench_result.png",
    )
    args = parser.parse_args()

    image = Image.new("RGB", (WIDTH, HEIGHT), "#ffffff")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH, 104), fill="#17202a")
    draw.text((48, 22), "MiMo-V2.5-Pro on SWE-bench Verified", font=font(32, True), fill="#ffffff")
    draw.text((50, 67), "Official harness evaluation of one frozen 500-prediction set", font=font(16), fill="#d5d8dc")

    draw.rounded_rectangle((50, 142, 520, 390), radius=10, fill="#e8f8f5", outline="#148f77", width=3)
    draw.text((82, 170), "Resolved rate", font=font(24, True), fill="#0e6251")
    draw.text((82, 220), "72.00%", font=font(64, True), fill="#117864")
    draw.text((82, 306), "360 / 500", font=font(32, True), fill="#17202a")
    draw.text((82, 350), "Full submitted denominator", font=font(17), fill="#34495e")

    outcomes = [
        ("Resolved", 360, "#148f77"),
        ("Unresolved", 112, "#ca6f1e"),
        ("Empty patch", 27, "#85929e"),
        ("Harness error", 1, "#a93226"),
    ]
    x0, y0, bar_width = 600, 145, 610
    scale = bar_width / 500
    y = y0
    for label, value, color in outcomes:
        draw.text((600, y), label, font=font(17, True), fill="#17202a")
        draw.text((1170, y), str(value), font=font(17, True), fill="#17202a", anchor="ra")
        draw.rounded_rectangle((600, y + 27, 1210, y + 50), radius=5, fill="#ecf0f1")
        draw.rounded_rectangle((600, y + 27, 600 + max(4, int(value * scale)), y + 50), radius=5, fill=color)
        y += 76

    draw.rounded_rectangle((50, 452, 1230, 612), radius=10, fill="#f8f9f9", outline="#ccd1d1", width=2)
    draw.text((78, 475), "Arithmetic closure", font=font(22, True), fill="#17202a")
    draw.text((78, 520), "360 Resolved + 112 Unresolved = 472 Completed", font=font(21), fill="#34495e")
    draw.text((78, 558), "472 Completed + 27 Empty + 1 Error = 500 Submitted", font=font(21), fill="#34495e")

    draw.text((52, 652), "Scope: official evaluation of supplied predictions; model generation was not rerun for this result.", font=font(16), fill="#7b241c")
    draw.text((52, 680), "Pinned SWE-bench commit: f7bbbb2 | Timeout: 1800s | Error: one timed-out test", font=font(15), fill="#5d6d7e")

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, optimize=True)
    print(f"MIMO_RESULT_DIAGRAM=PASS path={output} size={image.size}")


if __name__ == "__main__":
    main()

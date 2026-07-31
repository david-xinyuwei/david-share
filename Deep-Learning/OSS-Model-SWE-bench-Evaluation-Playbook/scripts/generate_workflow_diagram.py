#!/usr/bin/env python3
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH = 1280
HEIGHT = 720
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def font(size: int, bold: bool = False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT, size)


def box(draw, xy, title, lines, fill, border):
    draw.rounded_rectangle(xy, radius=8, fill=fill, outline=border, width=2)
    x1, y1, _, _ = xy
    draw.text((x1 + 18, y1 + 16), title, font=font(23, True), fill="#17202a")
    y = y1 + 56
    for line in lines:
        draw.text((x1 + 18, y), line, font=font(17), fill="#34495e")
        y += 28


def arrow(draw, start, end, color="#5d6d7e"):
    draw.line([start, end], fill=color, width=4)
    x, y = end
    draw.polygon([(x, y), (x - 12, y - 7), (x - 12, y + 7)], fill=color)


def main() -> None:
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

    output = Path(__file__).resolve().parents[1] / "images" / "swebench_workflow.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, optimize=True)
    print(f"WORKFLOW_DIAGRAM=PASS path={output} size={image.size}")


if __name__ == "__main__":
    main()
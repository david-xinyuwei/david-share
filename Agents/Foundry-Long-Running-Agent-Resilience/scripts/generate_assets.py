#!/usr/bin/env python3
"""Generate deterministic documentation images for the validation kit."""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "images"
WIDTH = 1600
HEIGHT = 900


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    names = [name for name in [
        os.environ.get("LRA_CJK_FONT"),
        "C:/Windows/Fonts/NotoSansSC-VF.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
    ] if name]
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


def evidence_pipeline(*, localized: bool = False) -> None:
    image, draw = background()
    title = "证据优先的韧性验证" if localized else "Evidence-first resilience validation"
    subtitle = (
        "故障注入只是中点；恢复证据必须覆盖到 workload 的最终状态。"
        if localized
        else "Failure injection is only the midpoint; recovery proof must reach a terminal workload result."
    )
    draw.text((70, 55), title, font=font(52, True), fill="#16212B")
    draw.text(
        (72, 125),
        subtitle,
        font=font(24),
        fill="#425466",
    )
    colors = ["#1363DF", "#D9485F", "#D98E04", "#0F8B6D", "#5F4BB6"]
    labels = (
        [
            "Authenticated\nHosted run",
            "Checkpoint +\n故障注入",
            "重连 +\nProtocol 证据",
            "脱敏\n边界",
            "Public attestation\n+ hash manifest",
        ]
        if localized
        else [
            "Authenticated\nhosted run",
            "Checkpoint +\nfailure\ninjection",
            "Reconnect +\nprotocol\nevidence",
            "Sanitization\nboundary",
            "Public\nattestation +\nhash manifest",
        ]
    )
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
    boundary = (
        "公开边界：不包含 raw log、credential、endpoint、resource ID、私有源码或部署配方"
        if localized
        else "Public boundary: no raw logs, credentials, endpoints, resource IDs, private source, or deployment recipe"
    )
    centered(
        draw,
        (95, 700, 1505, 790),
        boundary,
        font(21, True),
        "#FFFFFF",
    )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    suffix = "-cn" if localized else ""
    image.save(OUTPUT / f"evidence-pipeline{suffix}.png", optimize=True)


def scenario_coverage(*, localized: bool = False) -> None:
    image, draw = background()
    title = "八个主场景，四类证据模式" if localized else "Eight main scenarios, four proof patterns"
    subtitle = (
        "Matrix 验证 workload behavior，而不是只看 deployment status。"
        if localized
        else "The matrix validates workload behavior, not deployment status alone."
    )
    draw.text((70, 55), title, font=font(52, True), fill="#16212B")
    draw.text(
        (72, 125),
        subtitle,
        font=font(24),
        fill="#425466",
    )
    cards = (
        [
            ((70, 245, 760, 470), "Research durability", "Python + .NET\nResponses + Invocations\n18 phases | checkpoint | failure | resume", "#1363DF"),
            ((840, 245, 1530, 470), "Graph + human approval", "Invocations + Responses\napproval checkpoint | restart | resume | completion", "#D9485F"),
            ((70, 535, 760, 760), "Durable workflow", "持久化 stage output\nTemporary host unavailability\nTerminal round-trip result", "#0F8B6D"),
            ((840, 535, 1530, 760), "Steering", "Materially different follow-up\nActive turn 期间 queued\n新输入达到 completion", "#D98E04"),
        ]
        if localized
        else [
            ((70, 245, 760, 470), "Research durability", "Python + .NET\nResponses + Invocations\n18 phases | checkpoint | failure | resume", "#1363DF"),
            ((840, 245, 1530, 470), "Graph + human approval", "Invocations + Responses\napproval checkpoint | restart | resume | completion", "#D9485F"),
            ((70, 535, 760, 760), "Durable workflow", "persisted stage outputs\ntemporary host unavailability\nterminal round-trip result", "#0F8B6D"),
            ((840, 535, 1530, 760), "Steering", "materially different follow-up\nqueued while active\nnew answer reaches completion", "#D98E04"),
        ]
    )
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
    footer = (
        "作者证明的脱敏 campaign 结果 | Raw private evidence 不公开"
        if localized
        else "Author-attested sanitized campaign results | Raw private evidence withheld"
    )
    draw.text((70, 830), footer, font=font(22, True), fill="#5F4BB6")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    suffix = "-cn" if localized else ""
    image.save(OUTPUT / f"scenario-coverage{suffix}.png", optimize=True)


def resilience_architecture(*, localized: bool = False) -> None:
    image, draw = background()
    title = "长任务 Agent：责任边界" if localized else "Long-running agents: responsibility boundaries"
    subtitle = (
        "把 Foundry 公开能力、Preview long-running layer、workload 与 observer 分开。"
        if localized
        else "Separate public Foundry capabilities, the preview long-running layer, workload logic, and observation."
    )
    draw.text((70, 55), title, font=font(48, True), fill="#16212B")
    draw.text((72, 125), subtitle, font=font(22), fill="#425466")
    layers = (
        [
            ("Foundry Hosting（公开）", "Session / conversation | Identity | Endpoint | Lifecycle", "#1363DF"),
            ("Long-running capability（Campaign observation）", "Durable task state | Recovery entry | Reconnectable events | Steering", "#5F4BB6"),
            ("Workload proof", "Research | Human approval | Workflow | Active-turn steering", "#0F8B6D"),
            ("Observer + Evidence", "Failure injection | Cursor | Final read | Sanitization | Commitment", "#D98E04"),
        ]
        if localized
        else [
            ("Foundry hosting (public)", "Session / conversation | Identity | Endpoint | Lifecycle", "#1363DF"),
            ("Long-running capability (campaign observation)", "Durable task state | Recovery entry | Reconnectable events | Steering", "#5F4BB6"),
            ("Workload proof", "Research | Human approval | Workflow | Active-turn steering", "#0F8B6D"),
            ("Observer + evidence", "Failure injection | Cursor | Final read | Sanitization | Commitment", "#D98E04"),
        ]
    )
    top = 220
    boxes = []
    for heading, details, color in layers:
        box = (120, top, 1480, top + 125)
        boxes.append(box)
        draw.rounded_rectangle(box, radius=18, fill="white", outline=color, width=6)
        draw.rectangle((120, top, 145, top + 125), fill=color)
        draw.text((175, top + 22), heading, font=font(27, True), fill="#17212B")
        draw.text((175, top + 72), details, font=font(21), fill="#425466")
        top += 155
    for upper, lower in zip(boxes, boxes[1:], strict=False):
        draw.line((800, upper[3] + 5, 800, lower[1] - 5), fill="#617487", width=7)
        draw.polygon(
            [(800, lower[1] - 3), (786, lower[1] - 24), (814, lower[1] - 24)],
            fill="#617487",
        )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    suffix = "-cn" if localized else ""
    image.save(OUTPUT / f"resilience-architecture{suffix}.png", optimize=True)


def main() -> int:
    for localized in (False, True):
        evidence_pipeline(localized=localized)
        resilience_architecture(localized=localized)
        scenario_coverage(localized=localized)
    print("Generated 6 localized documentation images.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

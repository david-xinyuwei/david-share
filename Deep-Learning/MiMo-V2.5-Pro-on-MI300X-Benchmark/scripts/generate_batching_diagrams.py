#!/usr/bin/env python3
"""Generate the request-lifecycle and KV-capacity diagrams used by the READMEs."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "images"
WIDTH = 1800
HEIGHT = 1080
PADDING = 28

BG = "#ffffff"
INK = "#202124"
MUTED = "#5f6368"
BORDER = "#d7dce2"
BLUE = "#285f9e"
BLUE_BG = "#edf4ff"
GREEN = "#237a45"
GREEN_BG = "#eaf7ee"
ORANGE = "#c65d1e"
ORANGE_BG = "#fff3e8"
PURPLE = "#7048c8"
PURPLE_BG = "#f3efff"
RED = "#b23a3a"
RED_BG = "#fff0f0"
GRAY_BG = "#f7f8fa"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = ["DejaVuSans-Bold.ttf", "arialbd.ttf"] if bold else ["DejaVuSans.ttf", "arial.ttf"]
    prefixes = [
        "/usr/share/fonts/truetype/dejavu/",
        "",
    ]
    for prefix in prefixes:
        for name in names:
            try:
                return ImageFont.truetype(prefix + name, size)
            except OSError:
                continue
    return ImageFont.load_default()


F_TITLE = font(48, True)
F_SUBTITLE = font(25)
F_SECTION = font(31, True)
F_CARD = font(27, True)
F_BODY = font(24)
F_BODY_BOLD = font(24, True)
F_SMALL = font(20)
F_FORMULA = font(27, True)


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    return image, ImageDraw.Draw(image)


def rounded(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    fill: str,
    outline: str = BORDER,
    width: int = 3,
    radius: int = 12,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def centered(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, color: str, face) -> None:
    draw.text(xy, text, fill=color, font=face, anchor="mm")


def lines(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    values: list[str],
    color: str = INK,
    face=F_BODY,
    gap: int = 34,
) -> None:
    for index, value in enumerate(values):
        draw.text((x, y + index * gap), value, fill=color, font=face)


def arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    color: str = MUTED,
    width: int = 5,
) -> None:
    draw.line((start, end), fill=color, width=width)
    x1, y1 = start
    x2, y2 = end
    if abs(x2 - x1) >= abs(y2 - y1):
        direction = 1 if x2 > x1 else -1
        points = [(x2, y2), (x2 - 18 * direction, y2 - 10), (x2 - 18 * direction, y2 + 10)]
    else:
        direction = 1 if y2 > y1 else -1
        points = [(x2, y2), (x2 - 10, y2 - 18 * direction), (x2 + 10, y2 - 18 * direction)]
    draw.polygon(points, fill=color)


def save(image: Image.Image, name: str) -> None:
    IMAGES.mkdir(parents=True, exist_ok=True)
    framed = Image.new("RGB", (WIDTH + 2 * PADDING, HEIGHT + 2 * PADDING), BG)
    framed.paste(image, (PADDING, PADDING))
    ImageDraw.Draw(framed).rectangle(
        (0, 0, framed.width - 1, framed.height - 1), outline=BORDER, width=1
    )
    path = IMAGES / name
    framed.save(path, "PNG", optimize=True)
    print(f"Saved {path} ({framed.width}x{framed.height})")


def request_lifecycle() -> None:
    image, draw = canvas()
    centered(draw, (WIDTH // 2, 50), "PD Disaggregation: Independent Prefill and Decode Batches", INK, F_TITLE)
    centered(
        draw,
        (WIDTH // 2, 100),
        "One request flows through both stages, but each stage owns its batch and tuning plane.",
        MUTED,
        F_SUBTITLE,
    )

    card_y, card_h, card_w, gap = 180, 360, 360, 65
    xs = [55, 55 + card_w + gap, 55 + 2 * (card_w + gap), 55 + 3 * (card_w + gap)]
    cards = [
        ("Client pressure", BLUE_BG, BLUE, ["Total requests: N = 16", "In-flight cap: C = 16", "Each request: 64K / 1K", "Client load, not server BS"]),
        ("Prefill scheduler", GREEN_BG, GREEN, ["Request BS: #new-seq", "Token BS: #new-token", "P-node chunk cap: 32K", "Prefill-owned tuning"]),
        ("KV-transfer contract", PURPLE_BG, PURPLE, ["Per-request KV ownership", "KV moves Prefill -> Decode", "Usage grows with sequence", "Layout / dtype must match"]),
        ("Decode scheduler", ORANGE_BG, ORANGE, ["Decode BS: #running-req", "Dynamic at each step", "Independent of Prefill BS", "PD record: mode 4 / peak 5"]),
    ]

    for x, (title, fill, color, body) in zip(xs, cards):
        rounded(draw, (x, card_y, x + card_w, card_y + card_h), fill, color)
        centered(draw, (x + card_w // 2, card_y + 48), title, color, F_CARD)
        lines(draw, x + 28, card_y + 100, body, gap=52)

    for index in range(3):
        arrow(draw, (xs[index] + card_w + 8, card_y + card_h // 2), (xs[index + 1] - 8, card_y + card_h // 2))

    rounded(draw, (70, 600, 1730, 855), GRAY_BG, BORDER, width=2)
    centered(draw, (WIDTH // 2, 635), "Independent tuning planes after PD disaggregation", INK, F_SECTION)
    rounded(draw, (105, 675, 855, 825), GREEN_BG, GREEN, width=2)
    centered(draw, (480, 705), "Prefill instance: its own BS and controls", GREEN, F_CARD)
    lines(
        draw,
        140,
        750,
        [
            "Request BS / token BS / chunk size",
            "chunked-prefill-size | max-prefill-tokens | prefill-max-requests",
        ],
        face=F_SMALL,
        gap=36,
    )
    rounded(draw, (945, 675, 1695, 825), ORANGE_BG, ORANGE, width=2)
    centered(draw, (1320, 705), "Decode instance: its own BS and controls", ORANGE, F_CARD)
    lines(
        draw,
        980,
        750,
        [
            "Dynamic running-request BS / admission ceiling",
            "max-running-requests | Decode execution and memory settings",
        ],
        face=F_SMALL,
        gap=36,
    )

    rounded(draw, (70, 885, 1730, 1025), BLUE_BG, BLUE, width=2)
    centered(draw, (WIDTH // 2, 915), "Do not mix the two measured 64K / 1K records", BLUE, F_SECTION)
    draw.text((115, 954), "1P1D PD c16:", fill=PURPLE, font=F_BODY_BOLD)
    draw.text((315, 954), "observed Decode BS mode 4 / peak 5", fill=INK, font=F_BODY)
    draw.text((900, 954), "Single-node exact64:", fill=ORANGE, font=F_BODY_BOLD)
    draw.text((1300, 954), "actual Decode BS 16", fill=INK, font=F_BODY)
    centered(
        draw,
        (WIDTH // 2, 998),
        "The headline BS16 record is a non-PD capacity experiment; neither record proves a Prefill request BS of 16.",
        MUTED,
        F_SMALL,
    )
    save(image, "request_batching_lifecycle.png")


def xiaomi_protocol_batches() -> None:
    image, draw = canvas()
    centered(draw, (WIDTH // 2, 50), "Xiaomi Community Protocol: Two Independent Batch Planes", INK, F_TITLE)
    centered(
        draw,
        (WIDTH // 2, 100),
        "Client load feeds Prefill; only completed KV enters the Decode running-request population.",
        MUTED,
        F_SUBTITLE,
    )

    rounded(draw, (70, 160, 520, 525), BLUE_BG, BLUE)
    centered(draw, (295, 205), "1. Client workload", BLUE, F_SECTION)
    lines(
        draw,
        112,
        260,
        [
            "Prefill load: C_client = 32",
            "Each request has its own ISL",
            "Decode workload: 16K / 1K",
            "Client load != server batch",
        ],
        gap=56,
    )

    rounded(draw, (675, 160, 1125, 525), GREEN_BG, GREEN)
    centered(draw, (900, 205), "2. Prefill scheduler", GREEN, F_SECTION)
    lines(
        draw,
        717,
        260,
        [
            "Chunk cap: 32K tokens",
            "Request batch: #new-seq(t)",
            "Token batch: #new-token(t)",
            "Both are runtime-dynamic",
        ],
        gap=56,
    )

    rounded(draw, (1280, 160, 1730, 525), ORANGE_BG, ORANGE)
    centered(draw, (1505, 205), "3. Decode scheduler", ORANGE, F_SECTION)
    lines(
        draw,
        1322,
        260,
        [
            "Per-DP targets: BS64 / BS96",
            "Evidence: #running-req(t)",
            "KV capacity may limit occupancy",
            "Decode target != Prefill BS",
        ],
        gap=56,
    )

    arrow(draw, (535, 342), (660, 342), BLUE, 6)
    arrow(draw, (1140, 342), (1265, 342), PURPLE, 6)
    centered(draw, (598, 312), "requests", MUTED, F_SMALL)
    centered(draw, (1202, 312), "per-request KV", MUTED, F_SMALL)

    rounded(draw, (70, 580, 1730, 790), GRAY_BG, BORDER, width=2)
    centered(draw, (WIDTH // 2, 620), "What is fixed, and what is measured", INK, F_SECTION)
    columns = [105, 660, 1215]
    labels = [
        ("Client-side fixed input", BLUE, ["max-concurrency=32", "ISL / OSL and request count"]),
        ("Prefill runtime evidence", GREEN, ["#new-seq distribution", "#new-token distribution"]),
        ("Decode target + evidence", ORANGE, ["per-DP target: 64 or 96", "actual #running-req distribution"]),
    ]
    for x, (title, color, body) in zip(columns, labels):
        draw.text((x, 665), title, fill=color, font=F_CARD)
        lines(draw, x, 715, body, face=F_SMALL, gap=34)

    rounded(draw, (70, 835, 1730, 1025), RED_BG, RED, width=2)
    centered(draw, (WIDTH // 2, 872), "No one-to-one Prefill-BS -> Decode-BS mapping", RED, F_SECTION)
    centered(
        draw,
        (WIDTH // 2, 928),
        "C_client=32 does not mean Prefill BS32.  A 32K chunk cap does not mean request BS32.",
        INK,
        F_BODY_BOLD,
    )
    centered(
        draw,
        (WIDTH // 2, 978),
        "The Prefill side must supply enough KV; the Decode side must prove actual occupancy at per-DP BS64 or BS96.",
        MUTED,
        F_BODY,
    )
    save(image, "xiaomi_protocol_batch_planes.png")


def kv_capacity() -> None:
    image, draw = canvas()
    centered(draw, (WIDTH // 2, 50), "Long-ISL Capacity: Sequence Length x Active Requests", INK, F_TITLE)
    centered(
        draw,
        (WIDTH // 2, 100),
        "Single-node exact64 example (non-PD): KV capacity constrains actual concurrency.",
        MUTED,
        F_SUBTITLE,
    )

    rounded(draw, (70, 165, 1730, 370), PURPLE_BG, PURPLE)
    centered(draw, (WIDTH // 2, 205), "Capacity model", PURPLE, F_SECTION)
    centered(draw, (WIDTH // 2, 265), "sum_i (ISL_i + generated_i + reserved_i) <= K_pool", INK, F_FORMULA)
    centered(
        draw,
        (WIDTH // 2, 318),
        "Homogeneous raw upper bound:  B_raw = floor(K_pool / (ISL + OSL))",
        MUTED,
        F_BODY,
    )
    centered(
        draw,
        (WIDTH // 2, 356),
        "Fragmentation, allocation pages, MTP state and safety reserve reduce the usable batch.",
        MUTED,
        F_SMALL,
    )

    pool_x, pool_y, pool_w, pool_h = 100, 440, 1600, 115
    rounded(draw, (pool_x, pool_y, pool_x + pool_w, pool_y + pool_h), GRAY_BG, BORDER, width=2)
    used_ratio = 1_064_960 / 1_442_464
    used_w = int(pool_w * used_ratio)
    draw.rounded_rectangle(
        (pool_x, pool_y, pool_x + used_w, pool_y + pool_h),
        radius=10,
        fill=ORANGE_BG,
        outline=ORANGE,
        width=3,
    )
    centered(draw, (pool_x + used_w // 2, pool_y + pool_h // 2), "64K / 1K x 16 = 1,064,960 tokens (73.8%)", ORANGE, F_BODY_BOLD)
    centered(
        draw,
        (pool_x + used_w + (pool_w - used_w) // 2, pool_y + pool_h // 2),
        "377,504-token raw margin",
        MUTED,
        F_BODY_BOLD,
    )
    centered(draw, (WIDTH // 2, 590), "Measured full-attention KV pool K_pool = 1,442,464 tokens", PURPLE, F_SECTION)

    rounded(draw, (70, 650, 850, 995), BLUE_BG, BLUE)
    centered(draw, (460, 690), "Non-PD exact64 BS16 example", BLUE, F_SECTION)
    example = [
        "Per request: 65,536 input + 1,024 output",
        "16 x 66,560 = 1,064,960 token positions",
        "1,064,960 / 1,442,464 = 73.8% raw use",
        "Scheduler log: full token usage 0.73-0.74",
        "Observed: #running-req=16, #queue-req=0",
    ]
    lines(draw, 115, 750, example, gap=48)

    rounded(draw, (950, 650, 1730, 995), GREEN_BG, GREEN)
    centered(draw, (1340, 690), "Measured subset and open points", GREEN, F_SECTION)
    future = [
        "Measured: 128K / 192K, OSL=1K, actual BS4",
        "64K anchor and 255K actual-BS4 point remain open",
        "Equal-KV-load planning: 64Kx16, 128Kx8,",
        "192Kx5, 255Kx4 (planning only)",
        "256K input + 1K output is invalid at context=262,151",
    ]
    lines(draw, 995, 750, future, gap=48)
    save(image, "kv_capacity_relationship.png")


def main() -> None:
    request_lifecycle()
    xiaomi_protocol_batches()
    kv_capacity()


if __name__ == "__main__":
    main()
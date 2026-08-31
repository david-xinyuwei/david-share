from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "images"
EVIDENCE = ROOT / "evidence"
QWEN32_RESULTS = EVIDENCE / "runs" / "qwen3-32b-h200-trtllm-50rps" / "results"

WIDTH = 1600
HEIGHT = 900
BACKGROUND = "#F7F4ED"
INK = "#18313B"
MUTED = "#60727C"
BLUE = "#246493"
BLUE_LIGHT = "#DCEAF5"
GREEN = "#2F7D57"
GREEN_LIGHT = "#DFEEE5"
TEAL = "#087A80"
TEAL_LIGHT = "#D9EFF0"
RED = "#B83B3B"
WHITE = "#FFFFFF"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "segoeuib.ttf" if bold else "segoeui.ttf"
    path = Path("C:/Windows/Fonts") / name
    return ImageFont.truetype(str(path), size)


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    return image, ImageDraw.Draw(image)


def text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    value: str,
    size: int,
    *,
    color: str = INK,
    bold: bool = False,
    anchor: str | None = None,
    align: str = "left",
) -> None:
    draw.text(xy, value, fill=color, font=font(size, bold), anchor=anchor, align=align)


def box(
    draw: ImageDraw.ImageDraw,
    bounds: tuple[int, int, int, int],
    title: str,
    lines: list[str],
    *,
    border: str,
    header: str,
    title_size: int = 29,
    body_size: int = 25,
) -> None:
    left, top, right, bottom = bounds
    draw.rounded_rectangle(bounds, radius=14, fill=WHITE, outline=border, width=3)
    draw.rectangle((left + 2, top + 2, right - 2, top + 58), fill=header)
    draw.line((left, top + 58, right, top + 58), fill=border, width=3)
    text(draw, (left + 18, top + 17), title, title_size, color=border, bold=True)
    y = top + 78
    for line in lines:
        text(draw, (left + 18, y), line, body_size)
        y += body_size + 11


def arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    color: str = BLUE,
    width: int = 7,
    dashed: bool = False,
) -> None:
    x1, y1 = start
    x2, y2 = end
    if dashed:
        segments = 10
        for index in range(segments):
            if index % 2 == 0:
                sx = x1 + (x2 - x1) * index / segments
                sy = y1 + (y2 - y1) * index / segments
                ex = x1 + (x2 - x1) * (index + 1) / segments
                ey = y1 + (y2 - y1) * (index + 1) / segments
                draw.line((sx, sy, ex, ey), fill=color, width=width)
    else:
        draw.line((x1, y1, x2, y2), fill=color, width=width)
    if abs(x2 - x1) >= abs(y2 - y1):
        direction = 1 if x2 > x1 else -1
        points = [(x2, y2), (x2 - 18 * direction, y2 - 13), (x2 - 18 * direction, y2 + 13)]
    else:
        direction = 1 if y2 > y1 else -1
        points = [(x2, y2), (x2 - 13, y2 - 18 * direction), (x2 + 13, y2 - 18 * direction)]
    draw.polygon(points, fill=color)


def footer(draw: ImageDraw.ImageDraw, left: str, right: str) -> None:
    draw.line((72, 846, 1528, 846), fill="#C7D1D5", width=2)
    text(draw, (72, 862), left, 19, color=MUTED)
    text(draw, (1528, 862), right, 19, color=MUTED, anchor="ra")


def save(image: Image.Image, name: str) -> None:
    path = IMAGES / name
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=True)
    raw = path.read_bytes()
    print(f"{name}\t{len(raw)}\t{hashlib.sha256(raw).hexdigest()}")


def configuration_problem() -> None:
    image, draw = canvas()
    text(draw, (72, 54), "Capacity is a constrained search, not a model lookup", 48, bold=True)
    text(
        draw,
        (72, 119),
        "Comparable GPU estimates require model, traffic, service objectives, runtime, and hardware to be frozen together.",
        25,
        color=MUTED,
    )

    box(draw, (72, 205, 408, 350), "MODEL", ["Architecture and precision", "Context and KV behavior"], border=BLUE, header=BLUE_LIGHT)
    box(draw, (72, 362, 408, 507), "WORKLOAD", ["ISL, OSL, prefix", "Rate, concurrency, bursts"], border=BLUE, header=BLUE_LIGHT)
    box(draw, (72, 519, 408, 664), "SERVICE OBJECTIVES", ["TTFT, TPOT, latency", "Goodput and error limits"], border=BLUE, header=BLUE_LIGHT, title_size=25)
    box(draw, (72, 676, 408, 821), "PLATFORM", ["GPU, topology, backend"], border=BLUE, header=BLUE_LIGHT)

    draw.rounded_rectangle((570, 292, 1030, 706), radius=18, fill=WHITE, outline=TEAL, width=4)
    text(draw, (800, 345), "CONFIGURATION SEARCH", 35, color=TEAL, bold=True, anchor="ma")
    text(draw, (800, 409), "Memory feasibility", 27, anchor="ma")
    text(draw, (800, 462), "Serving mode and parallelism", 27, anchor="ma")
    text(draw, (800, 515), "Batch, worker, and replica shape", 27, anchor="ma")
    text(draw, (800, 568), "Predicted latency and throughput", 27, anchor="ma")
    text(draw, (800, 636), "Rank under the declared constraints", 24, color=MUTED, anchor="ma")
    arrow(draw, (408, 500), (570, 500), color=BLUE)

    box(draw, (1190, 210, 1528, 370), "GPU CAPACITY", ["Minimum modeled scale", "plus explicit reserve"], border=GREEN, header=GREEN_LIGHT)
    box(draw, (1190, 420, 1528, 580), "TOPOLOGY", ["Agg / Disagg", "TP / PP / DP / EP"], border=GREEN, header=GREEN_LIGHT)
    box(draw, (1190, 630, 1528, 790), "CANDIDATES", ["Predicted metrics", "Generated configurations"], border=GREEN, header=GREEN_LIGHT)
    arrow(draw, (1030, 500), (1190, 500), color=GREEN)
    footer(draw, "Original explanatory diagram", "General OSS model capacity-planning contract")
    save(image, "configuration-problem.png")


def first_row(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as handle:
        return next(csv.DictReader(handle))


def metric_card(
    draw: ImageDraw.ImageDraw,
    bounds: tuple[int, int, int, int],
    title: str,
    row: dict[str, str],
    *,
    selected: bool,
) -> None:
    left, top, right, bottom = bounds
    color = GREEN if selected else BLUE
    header = GREEN_LIGHT if selected else BLUE_LIGHT
    draw.rounded_rectangle(bounds, radius=14, fill=WHITE, outline=color, width=4)
    draw.rectangle((left + 2, top + 2, right - 2, top + 70), fill=header)
    draw.line((left, top + 70, right, top + 70), fill=color, width=4)
    text(draw, (left + 28, top + 21), title, 29, color=color, bold=True)
    gpus = int(row["total_gpus_needed"])
    replicas = int(row["replicas_needed"])
    per_replica = int(row["num_total_gpus"])
    cluster_rps = float(row["request_rate"]) * replicas
    text(draw, ((left + right) // 2, top + 155), str(gpus), 92, color=color, bold=True, anchor="mm")
    text(draw, ((left + right) // 2, top + 232), "H200 GPUs", 31, bold=True, anchor="mm")
    text(draw, ((left + right) // 2, top + 294), f"{replicas} replicas x {per_replica} GPU{'s' if per_replica != 1 else ''}", 25, color=MUTED, anchor="mm")
    if title.startswith("AGGREGATED"):
        detail = f"TP{row['tp']} / PP{row['pp']}  |  batch {row['bs']}"
    else:
        detail = f"Prefill TP{row['(p)tp']}  |  Decode TP{row['(d)tp']}"
    text(draw, ((left + right) // 2, top + 342), detail, 24, color=MUTED, anchor="mm")
    columns = [(left + 88, "req/s", f"{cluster_rps:.2f}"), ((left + right) // 2, "TTFT", f"{float(row['ttft']):.2f} ms"), (right - 88, "TPOT", f"{float(row['tpot']):.2f} ms")]
    for x, label, value in columns:
        text(draw, (x, top + 445), label, 21, color=MUTED, bold=True, anchor="mm")
        text(draw, (x, top + 493), value, 25, bold=True, anchor="mm")


def qwen32_example() -> None:
    agg = first_row(QWEN32_RESULTS / "agg" / "best_config_topn.csv")
    disagg = first_row(QWEN32_RESULTS / "disagg" / "best_config_topn.csv")
    selected_agg = int(agg["total_gpus_needed"]) <= int(disagg["total_gpus_needed"])
    image, draw = canvas()
    text(draw, (72, 51), "Worked example: synthetic 50 req/s capacity point", 46, bold=True)
    text(draw, (72, 116), "Qwen3-32B-FP8 | H200 SXM | TensorRT-LLM | ISL 4000 | OSL 1000 | TTFT <= 2000 ms | TPOT <= 30 ms", 24, color=MUTED)
    metric_card(draw, (72, 228, 775, 762), "AGGREGATED - SELECTED" if selected_agg else "AGGREGATED", agg, selected=selected_agg)
    metric_card(draw, (825, 228, 1528, 762), "DISAGGREGATED - SELECTED" if not selected_agg else "DISAGGREGATED", disagg, selected=not selected_agg)
    text(draw, (800, 808), "CPU-OFFLINE PREDICTION | SILICON DATABASE", 25, color=TEAL, bold=True, anchor="mm")
    text(draw, (800, 842), "GPU BENCHMARK: NOT RUN", 25, color=RED, bold=True, anchor="mm")
    save(image, "qwen3-32b-h200-canary.png")


def main() -> None:
    configuration_problem()
    qwen32_example()


if __name__ == "__main__":
    main()
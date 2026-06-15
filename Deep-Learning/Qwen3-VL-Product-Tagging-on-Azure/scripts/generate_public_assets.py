import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "images"
SAMPLES = ROOT / "data" / "sample_images"
CANVAS = (1280, 720)
TALL = (1280, 900)
TEXT = "#111827"
MUTED = "#4b5563"
BLUE = "#2563eb"
GREEN = "#059669"
ORANGE = "#d97706"
RED = "#dc2626"
PANEL = "#f8fafc"
BORDER = "#dcdee2"


def wsl_windows_font(name):
    return "/mnt/" + "c/Windows/Fonts/" + name


def font(size, bold=False):
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        wsl_windows_font("segoeuib.ttf") if bold else wsl_windows_font("segoeui.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            pass
    return ImageFont.load_default()


def font_zh(size, bold=False):
    candidates = [
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        wsl_windows_font("msyhbd.ttc") if bold else wsl_windows_font("msyh.ttc"),
        "C:/Windows/Fonts/simhei.ttf" if bold else "C:/Windows/Fonts/simsun.ttc",
        wsl_windows_font("simhei.ttf") if bold else wsl_windows_font("simsun.ttc"),
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            pass
    return font(size, bold)

TITLE = font(30, True)
H1 = font(22, True)
H2 = font(19, True)
BODY = font(18)
SMALL = font(16)
CODE = font(16)


def save(canvas, path):
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, canvas.width - 1, canvas.height - 1), outline=BORDER, width=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path, optimize=True)


def text(draw, xy, value, fill=TEXT, fnt=BODY):
    draw.text(xy, value, fill=fill, font=fnt)


def wrap(draw, xy, value, width, line_height=22, fill=TEXT, fnt=BODY, max_lines=None):
    import textwrap

    x, y = xy
    lines = []
    for raw in str(value).splitlines():
        lines.extend(textwrap.wrap(raw, max(10, width // 9)) or [""])
    if max_lines and len(lines) > max_lines:
        lines = lines[: max_lines - 1] + ["..."]
    for line in lines:
        draw.text((x, y), line, fill=fill, font=fnt)
        y += line_height
    return y


def panel(draw, box, title, color=BLUE):
    draw.rounded_rectangle(box, radius=8, fill=PANEL, outline=BORDER, width=1)
    x0, y0, x1, _ = box
    draw.rectangle((x0, y0, x1, y0 + 36), fill=color)
    draw.text((x0 + 12, y0 + 8), title, fill="white", font=H2)


def sample_image():
    SAMPLES.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (900, 900), "#f3f4f6")
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((120, 120, 780, 820), radius=42, fill="#e5e7eb", outline="#cbd5e1", width=3)
    draw.polygon([(450, 170), (620, 275), (560, 395), (450, 330), (340, 395), (280, 275)], fill="#1e3a8a")
    draw.rounded_rectangle((315, 275, 585, 740), radius=34, fill="#1f2937")
    draw.line((450, 330, 450, 735), fill="#93c5fd", width=5)
    draw.polygon([(315, 300), (210, 560), (290, 610), (360, 375)], fill="#111827")
    draw.polygon([(585, 300), (690, 560), (610, 610), (540, 375)], fill="#111827")
    draw.ellipse((395, 210, 505, 320), fill="#f9fafb", outline="#93c5fd", width=4)
    draw.text((250, 800), "synthetic product sample", fill=MUTED, font=font(28, True))
    save(img, SAMPLES / "synthetic_jacket.png")


def architecture():
    c = Image.new("RGB", CANVAS, "white")
    d = ImageDraw.Draw(c)
    text(d, (40, 32), "Qwen3-VL Product Tagging Reference Architecture", fnt=TITLE)
    text(d, (40, 75), "Schema-first pipeline: image + product text -> strict JSON -> business metrics", fill=MUTED, fnt=BODY)
    boxes = [
        ((55, 170, 255, 300), "Product\nImage", BLUE),
        ((55, 420, 255, 550), "Title / Description\nTaxonomy Hint", BLUE),
        ((335, 285, 545, 435), "Prompt Builder\nSchema + version", ORANGE),
        ((625, 285, 845, 435), "Qwen3-VL\nServing Endpoint", GREEN),
        ((920, 180, 1190, 300), "JSON Parser\nSchema Validation", BLUE),
        ((920, 420, 1190, 545), "Metrics + Error Pool\nFine-tuning Loop", RED),
    ]
    for box, label, color in boxes:
        d.rounded_rectangle(box, radius=10, fill="#f8fafc", outline=color, width=3)
        wrap(d, (box[0] + 18, box[1] + 32), label, box[2] - box[0] - 36, 25, TEXT, H1)
    arrows = [((255, 235), (335, 345)), ((255, 485), (335, 370)), ((545, 360), (625, 360)), ((845, 360), (920, 240)), ((1045, 300), (1045, 420)), ((920, 485), (845, 415))]
    for start, end in arrows:
        d.line((start, end), fill="#64748b", width=4)
        d.ellipse((end[0] - 5, end[1] - 5, end[0] + 5, end[1] + 5), fill="#64748b")
    save(c, IMAGES / "solution_architecture.png")


def quality_gates():
    c = Image.new("RGB", CANVAS, "white")
    d = ImageDraw.Draw(c)
    text(d, (40, 32), "VLM Product Tagging Quality Gates", fnt=TITLE)
    text(d, (40, 75), "Do not promote a model because it serves requests; promote it after business gates pass.", fill=MUTED)
    gates = [
        ("Q0", "Image-observed smoke", "HTTP 200 + visible image content appears in output", BLUE),
        ("Q1", "Schema gate", "Strict JSON parses against product_tag.schema.json", GREEN),
        ("Q2", "Quality gate", "Category accuracy and field F1 pass business threshold", ORANGE),
        ("Q3", "Serving gate", "P50/P95 latency and images/sec pass target", RED),
        ("Q4", "Drift gate", "Hard samples stay stable across model and prompt updates", "#7c3aed"),
    ]
    x = 55
    for idx, (code, title, desc, color) in enumerate(gates):
        y = 170 + idx * 96
        d.rounded_rectangle((x, y, 1185, y + 70), radius=10, fill=PANEL, outline=BORDER, width=1)
        d.rounded_rectangle((x + 15, y + 12, x + 85, y + 58), radius=8, fill=color)
        text(d, (x + 32, y + 22), code, fill="white", fnt=H1)
        text(d, (x + 115, y + 12), title, fnt=H1)
        text(d, (x + 115, y + 40), desc, fill=MUTED, fnt=BODY)
    save(c, IMAGES / "quality_gates.png")


def quality_gates_cn():
    c = Image.new("RGB", CANVAS, "white")
    d = ImageDraw.Draw(c)
    title_font = font_zh(30, True)
    subtitle_font = font_zh(20)
    heading_font = font_zh(22, True)
    body_font = font_zh(18)
    text(d, (40, 32), "VLM 商品打标：上线前五道检查", fnt=title_font)
    text(d, (40, 75), "不要因为接口能返回就上线；先确认图片、格式、质量、性能和回归稳定性都过关。", fill=MUTED, fnt=subtitle_font)
    gates = [
        ("Q0", "图片输入检查", "确认模型真的用到了输入图片，而不是只根据 prompt 生成", BLUE),
        ("Q1", "JSON 格式检查", "输出能解析成 JSON，并符合 product_tag.schema.json", GREEN),
        ("Q2", "业务质量检查", "Category accuracy 和 field F1 达到业务阈值", ORANGE),
        ("Q3", "服务能力检查", "P50/P95 latency、吞吐和并发错误率达标", RED),
        ("Q4", "改动后不退步", "改模型、prompt 或 parser 后，关键样本不能退步", "#7c3aed"),
    ]
    x = 55
    for idx, (code, title_text, desc, color) in enumerate(gates):
        y = 170 + idx * 96
        d.rounded_rectangle((x, y, 1185, y + 70), radius=10, fill=PANEL, outline=BORDER, width=1)
        d.rounded_rectangle((x + 15, y + 12, x + 85, y + 58), radius=8, fill=color)
        text(d, (x + 32, y + 21), code, fill="white", fnt=H1)
        text(d, (x + 115, y + 10), title_text, fnt=heading_font)
        text(d, (x + 115, y + 40), desc, fill=MUTED, fnt=body_font)
    save(c, IMAGES / "quality_gates_cn.png")


def load_summary():
    return json.loads((ROOT / "data" / "public_validation_summary.json").read_text(encoding="utf-8"))


def load_analysis_examples():
    return json.loads((ROOT / "data" / "sample_analysis_examples.json").read_text(encoding="utf-8"))


def pct(value):
    return f"{value * 100:.1f}%"


def num(value, digits=1):
    return f"{value:.{digits}f}"


def metric_card(draw, box, title, rows, color=BLUE):
    panel(draw, box, title, color)
    x0, y0, x1, _ = box
    y = y0 + 52
    for label, value in rows:
        text(draw, (x0 + 16, y), label, fill=MUTED, fnt=SMALL)
        text(draw, (x1 - 145, y), value, fill=TEXT, fnt=H2)
        y += 31


def bar(draw, x, y, width, value, max_value, color, label):
    draw.rounded_rectangle((x, y, x + width, y + 18), radius=5, fill="#e5e7eb")
    fill_width = int(width * value / max_value) if max_value else 0
    draw.rounded_rectangle((x, y, x + fill_width, y + 18), radius=5, fill=color)
    text(draw, (x + width + 12, y - 3), label, fill=TEXT, fnt=SMALL)


def short_list(values):
    return ", ".join(values) if values else "[]"


def set_f1(pred, gold):
    p = {x.lower() for x in (pred or [])}
    g = {x.lower() for x in (gold or [])}
    if not p and not g:
        return 1.0
    if not p or not g:
        return 0.0
    inter = p & g
    if not inter:
        return 0.0
    prec = len(inter) / len(p)
    rec = len(inter) / len(g)
    return 2 * prec * rec / (prec + rec)


def thumbnail(path, size):
    image = Image.open(path).convert("RGB")
    image.thumbnail(size)
    canvas = Image.new("RGB", size, "white")
    x = (size[0] - image.width) // 2
    y = (size[1] - image.height) // 2
    canvas.paste(image, (x, y))
    return canvas


def input_examples():
    c = Image.new("RGB", (1280, 1020), "white")
    d = ImageDraw.Draw(c)
    payload = load_analysis_examples()
    examples = payload["examples"]

    text(d, (36, 30), "Real Input Examples: Image, Prompt, Gold Tags, Model Outputs", fnt=TITLE)
    text(d, (36, 72), "Public Fashionpedia-style samples used for image-observed validation and fine-tuning error analysis.", fill=MUTED)

    prompt_box = (36, 115, 1225, 258)
    panel(d, prompt_box, "Prompt used for both samples", BLUE)
    wrap(d, (58, 170), f"System: {payload['prompt']['system']}", 1120, 21, TEXT, SMALL, 3)
    wrap(d, (58, 218), f"User: {payload['prompt']['user']}", 1120, 21, TEXT, SMALL, 2)

    y0 = 300
    for idx, example in enumerate(examples):
        x0 = 36 + idx * 610
        panel(d, (x0, y0, x0 + 575, 945), example["sample_id"], GREEN if idx == 0 else ORANGE)
        image = thumbnail(ROOT / example["image"], (255, 170))
        c.paste(image, (x0 + 18, y0 + 55))
        draw = ImageDraw.Draw(c)
        draw.rectangle((x0 + 18, y0 + 55, x0 + 273, y0 + 225), outline=BORDER, width=1)
        wrap(d, (x0 + 292, y0 + 58), example["visible_focus"], 250, 22, TEXT, SMALL, 5)

        rows = [
            ("Gold", example["gold"], GREEN, None),
            ("T0 base", example["t0_prediction"], RED, example["gold"]),
            ("T1 QLoRA", example["t1_prediction"], BLUE, example["gold"]),
        ]
        y = y0 + 250
        for label, values, color, gold in rows:
            text(d, (x0 + 18, y), label, fill=color, fnt=H2)
            tag_x = x0 + 165
            wrap(d, (tag_x, y), f"cat={values['category']} | detail={short_list(values.get('detail_tags'))} | co={short_list(values.get('co_garments'))}", 380, 20, TEXT, SMALL, 4)
            if gold is not None:
                df1 = set_f1(values.get("detail_tags"), gold.get("detail_tags"))
                cf1 = set_f1(values.get("co_garments"), gold.get("co_garments"))
                text(d, (tag_x, y + 62), f"detail F1={df1:.0%}  co F1={cf1:.0%}", fill=MUTED, fnt=SMALL)
            y += 84
        wrap(d, (x0 + 18, y + 10), f"Analysis: {example['analysis']}", 525, 21, MUTED, SMALL, 5)

    text(d, (36, 980), "Takeaway: the repo includes the actual input images, gold labels, and before/after model outputs, not only aggregate metrics.", fill=MUTED, fnt=SMALL)
    save(c, IMAGES / "real_input_examples.png")


def fine_tuning_evidence(summary):
    c = Image.new("RGB", TALL, "white")
    d = ImageDraw.Draw(c)
    ft = summary["fine_tuning"]
    metrics = ft["metrics"]
    training = ft["training"]
    examples = ft["examples"]

    text(d, (36, 30), "Fine-Tuning Evidence: T0 vs Decoder QLoRA vs Vision Escalation", fnt=TITLE)
    text(d, (36, 72), "Real public-taxonomy validation summary: 50 validation images, no category hint, same parser and prompt.", fill=MUTED)

    colors = [ORANGE, GREEN, BLUE]
    for idx, item in enumerate(metrics):
        x0 = 36 + idx * 410
        metric_card(
            d,
            (x0, 120, x0 + 380, 295),
            item["stage"],
            [
                ("Detail-tag F1", pct(item["detail_f1"])),
                ("Co-garment F1", pct(item["co_garments_f1"])),
                ("Category acc.", pct(item["category_accuracy"])),
                ("P50 / P95", f"{item['latency_p50_ms']:.0f} / {item['latency_p95_ms']:.0f} ms"),
            ],
            colors[idx],
        )

    panel(d, (36, 330, 615, 560), "Metric movement", BLUE)
    y = 385
    max_value = max(max(m["detail_f1"], m["co_garments_f1"]) for m in metrics)
    for item, color in zip(metrics, colors):
        text(d, (58, y - 4), item["stage"], fnt=SMALL)
        bar(d, 250, y, 230, item["detail_f1"], max_value, color, f"detail {pct(item['detail_f1'])}")
        y += 28
        bar(d, 250, y, 230, item["co_garments_f1"], max_value, "#94a3b8", f"co {pct(item['co_garments_f1'])}")
        y += 42

        panel(d, (650, 330, 1225, 560), "Training format and scope", GREEN)
        snippet = """{"messages": [
    {"role": "user", "content": "<image> Return tag JSON."},
    {"role": "assistant", "content": "{...gold tags...}"}
], "images": ["path/to/image.jpg"]}"""
        wrap(d, (670, 385), snippet, 530, 18, TEXT, CODE, 5)
    wrap(
        d,
                (670, 488),
        f"T1 used {training['train_images']} training images, {training['validation_images']} validation images, {training['steps']} decoder QLoRA steps, {training['train_seconds']}s train + {training['merge_seconds']}s merge on one H100 NVL.",
        525,
                20,
        MUTED,
        SMALL,
        3,
    )

    panel(d, (36, 600, 1225, 835), "Same validation samples: before and after", ORANGE)
    x_positions = [58, 455, 840]
    headers = ["Gold label", "T0 base prediction", "T1 decoder QLoRA prediction"]
    for x, header in zip(x_positions, headers):
        text(d, (x, 648), header, fnt=H2)
    y = 684
    for example in examples:
        gold = example["gold"]
        t0 = example["t0_prediction"]
        t1 = example["t1_prediction"]
        text(d, (58, y), example["sample_id"], fill=MUTED, fnt=SMALL)
        wrap(d, (58, y + 25), f"cat={gold['category']} | detail={short_list(gold['detail_tags'])} | co={short_list(gold['co_garments'])}", 360, 20, TEXT, SMALL, 3)
        wrap(d, (455, y + 25), f"cat={t0['category']} | detail={short_list(t0['detail_tags'])} | co={short_list(t0['co_garments'])}", 355, 20, TEXT, SMALL, 3)
        wrap(d, (840, y + 25), f"cat={t1['category']} | detail={short_list(t1['detail_tags'])} | co={short_list(t1['co_garments'])}", 355, 20, TEXT, SMALL, 3)
        y += 76

    text(d, (36, 858), "Takeaway: decoder QLoRA improved field alignment; training vision layers did not beat T1 on this small-data run.", fill=MUTED, fnt=SMALL)
    save(c, IMAGES / "fine_tuning_evidence.png")


def line_chart(draw, box, series):
    x0, y0, x1, y1 = box
    draw.rectangle(box, outline=BORDER, width=1)
    max_y = max(max(item["throughput_rps"]) for item in series)
    conc = series[0]["concurrency"]
    for tick in [0, 15, 30, 45, 60]:
        y = y1 - int((y1 - y0 - 30) * tick / 60) - 20
        draw.line((x0 + 45, y, x1 - 20, y), fill="#e5e7eb", width=1)
        text(draw, (x0 + 8, y - 9), str(tick), fill=MUTED, fnt=SMALL)
    colors = [BLUE, ORANGE, GREEN]
    for item, color in zip(series, colors):
        points = []
        for idx, value in enumerate(item["throughput_rps"]):
            x = x0 + 60 + idx * ((x1 - x0 - 100) // (len(conc) - 1))
            y = y1 - int((y1 - y0 - 55) * value / max_y) - 25
            points.append((x, y))
        draw.line(points, fill=color, width=4)
        for point in points:
            draw.ellipse((point[0] - 4, point[1] - 4, point[0] + 4, point[1] + 4), fill=color)
    for idx, value in enumerate(conc):
        x = x0 + 52 + idx * ((x1 - x0 - 100) // (len(conc) - 1))
        text(draw, (x, y1 - 22), str(value), fill=MUTED, fnt=SMALL)


def inference_evidence(summary):
    c = Image.new("RGB", TALL, "white")
    d = ImageDraw.Draw(c)
    inf = summary["inference"]
    series = inf["base64_engine_comparison"]
    text(d, (36, 30), "Inference Evidence: Throughput, Tail Latency, Resolution", fnt=TITLE)
    text(d, (36, 72), "Same image payload style, same prompt, same max tokens, same parser; base64 removes network fetch variance.", fill=MUTED)
    panel(d, (36, 120, 835, 555), "Base64 VLM serving throughput (req/s)", BLUE)
    line_chart(d, (65, 175, 805, 500), series)
    legend_y = 515
    for idx, item in enumerate(series):
        color = [BLUE, ORANGE, GREEN][idx]
        d.rectangle((90 + idx * 240, legend_y, 110 + idx * 240, legend_y + 14), fill=color)
        text(d, (120 + idx * 240, legend_y - 4), item["engine"], fill=TEXT, fnt=SMALL)

    panel(d, (870, 120, 1225, 555), "High-concurrency point", GREEN)
    y = 180
    for item in series:
        idx = item["concurrency"].index(32)
        wrap(d, (890, y), f"{item['engine']}: {item['throughput_rps'][idx]:.2f} req/s, P50 {item['p50_ms'][idx]:.0f} ms, P95 {item['p95_ms'][idx]:.0f} ms at concurrency 32", 315, 24, TEXT, BODY, 4)
        y += 108

    panel(d, (36, 590, 1225, 835), "Resolution sweep on vLLM FP8", ORANGE)
    headers = ["Resolution", "Concurrency", "Req/s", "P50", "P95", "Prompt tok"]
    xs = [58, 385, 570, 700, 820, 950]
    for x, h in zip(xs, headers):
        text(d, (x, 645), h, fnt=H2)
    y = 690
    for item in inf["resolution_comparison_fp8"]:
        values = [
            item["resolution"],
            str(item["concurrency"]),
            num(item["throughput_rps"], 2),
            f"{item['p50_ms']:.0f} ms",
            f"{item['p95_ms']:.0f} ms",
            str(item["prompt_tokens_avg"]),
        ]
        for x, value in zip(xs, values):
            text(d, (x, y), value, fill=TEXT, fnt=SMALL)
        y += 34
    text(d, (36, 858), "Takeaway: vLLM FP8 produced the strongest high-concurrency baseline; resolution changes must be measured with the target prompt.", fill=MUTED, fnt=SMALL)
    save(c, IMAGES / "inference_evidence.png")


def quantization_evidence(summary):
    c = Image.new("RGB", TALL, "white")
    d = ImageDraw.Draw(c)
    rows = summary["quantization"]["tournament"]
    text(d, (36, 30), "Quantization Evidence: Business Quality Beats Latency Alone", fnt=TITLE)
    text(d, (36, 72), "Same validation prompts and business gates; a fast quantized model is rejected if field metrics collapse.", fill=MUTED)

    panel(d, (36, 120, 610, 560), "Detail-tag F1 by candidate", BLUE)
    max_f1 = max(row["detail_f1"] for row in rows)
    y = 185
    for row in rows:
        color = RED if row["candidate"] == "vLLM dynamic FP8" else GREEN if row["rank"] == 1 else ORANGE
        label = f"{row['candidate']}  {pct(row['detail_f1'])}"
        bar(d, 70, y, 365, row["detail_f1"], max_f1, color, label)
        y += 58

    panel(d, (645, 120, 1225, 560), "Tournament table", GREEN)
    headers = ["Candidate", "Cat", "Detail", "Co", "P50", "Decision"]
    xs = [665, 900, 975, 1060, 1135, 665]
    for x, h in zip(xs[:5], headers[:5]):
        text(d, (x, 176), h, fnt=H2)
    y = 214
    for row in rows:
        text(d, (665, y), row["candidate"][:22], fnt=SMALL)
        text(d, (900, y), pct(row["category_accuracy"]), fnt=SMALL)
        text(d, (975, y), pct(row["detail_f1"]), fnt=SMALL)
        text(d, (1060, y), pct(row["co_garments_f1"]), fnt=SMALL)
        text(d, (1135, y), f"{row['p50_ms']}ms", fnt=SMALL)
        y += 43

    panel(d, (36, 595, 600, 835), "Decision", ORANGE)
    wrap(d, (58, 650), "Official FP8 was the champion: best overall field quality without a custom calibration workflow. AWQ 4-bit was the best INT4 fallback and nearly matched FP8 on detail F1.", 505, 24, TEXT, BODY, 5)
    panel(d, (630, 595, 1225, 835), "Rejected fast path", RED)
    dynamic = next(row for row in rows if row["candidate"] == "vLLM dynamic FP8")
    wrap(d, (652, 650), f"Dynamic online FP8 had the best-looking latency ({dynamic['p50_ms']} ms P50) but failed Q2: category accuracy {pct(dynamic['category_accuracy'])}, detail F1 {pct(dynamic['detail_f1'])}, co-garment F1 {pct(dynamic['co_garments_f1'])}.", 540, 24, TEXT, BODY, 5)
    text(d, (36, 858), "Takeaway: quantization is accepted only after Q0-Q2 business quality gates pass; HTTP 200 and low latency are not enough.", fill=MUTED, fnt=SMALL)
    save(c, IMAGES / "quantization_evidence.png")


def evidence():
    summary = load_summary()
    input_examples()
    fine_tuning_evidence(summary)
    inference_evidence(summary)
    quantization_evidence(summary)


def main():
    sample_image()
    architecture()
    quality_gates()
    quality_gates_cn()
    evidence()
    print("Generated public images and sample image")


if __name__ == "__main__":
    main()

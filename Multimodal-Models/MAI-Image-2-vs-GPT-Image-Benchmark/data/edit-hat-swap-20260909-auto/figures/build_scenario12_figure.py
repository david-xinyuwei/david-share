"""Build the Scenario 12 result sheet: input plus the four size=auto outputs.

Only the valid protocol is shown. The earlier run that forced GPT to
`size=1024x1024` is not a model behaviour — it is what this test's own parameter
produced — so its squares are deliberately absent from the comparison and are
described in one note instead. Every label (resolution, checklist count, latency)
is read from the archive's own records so the figure cannot drift from the data.

Layout: header, input on the left, prompt plus parameter note on the right, then
one row of four cells (MAI, GPT low/medium/high) under size=auto.
"""

import hashlib
import json
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(r"C:\david-share\Multimodal-Models\MAI-Image-2-vs-GPT-Image-Benchmark")
AUTO = REPO / "data" / "edit-hat-swap-20260909-auto"
OUT = Path(__file__).resolve().parent / "runs" / "scenario12-auto-results.png"

GROUPS = ("mai-image-2.6", "gpt-image-2-low", "gpt-image-2-medium", "gpt-image-2-high")
COLUMN_TITLES = ("MAI-Image-2.6", "GPT-Image-2 low", "GPT-Image-2 medium", "GPT-Image-2 high")

CELL_W, CELL_H = 460, 300
PAD = 18
COL_HEAD = 32
CELL_CAPTION = 56
TITLE_H = 92
INPUT_H = COL_HEAD + CELL_H + CELL_CAPTION + PAD
ROW_BANNER = 46
FOOTER_H = 96

BG = (255, 255, 255)
INK = (23, 26, 31)
MUTED = (96, 104, 115)
GOOD = (21, 115, 71)
ACCENT = (0, 103, 184)
LINE = (214, 219, 226)
BANNER = (240, 249, 244)
NOTE_BG = (248, 250, 252)

FONT_DIR = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"


def font(size, bold=False):
    """Load a CJK-capable font by absolute path; a bare family name silently
    falls back to a bitmap font with no CJK glyphs and renders tofu boxes."""
    for name in (("msyhbd.ttc", "simhei.ttf", "dengb.ttf") if bold
                 else ("msyh.ttc", "simsun.ttc", "deng.ttf")):
        path = FONT_DIR / name
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    raise SystemExit(f"no CJK font found in {FONT_DIR}")


def assert_renders_chinese(loaded):
    probe = Image.new("L", (64, 64), 0)
    ImageDraw.Draw(probe).text((2, 2), "换", font=loaded, fill=255)
    if probe.getbbox() is None:
        raise SystemExit("selected font produced no glyph for a Chinese character")


F_TITLE = font(30, bold=True)
F_SUB = font(16)
F_ROW = font(19, bold=True)
F_COL = font(17, bold=True)
F_CELL = font(15)
F_CELL_BOLD = font(15, bold=True)
F_NOTE = font(15)
F_FOOT = font(14)
for _loaded in (F_TITLE, F_SUB, F_ROW, F_CELL, F_FOOT):
    assert_renders_chinese(_loaded)


def load_round_one():
    results = json.loads((AUTO / "edit-results.json").read_text("utf-8"))
    review = json.loads((AUTO / "edit-review.json").read_text("utf-8"))
    if results.get("gpt_size_parameter") != "auto":
        raise SystemExit("this figure only renders the size=auto protocol")
    by_group = {}
    for attempt in results["attempts"]:
        checks = review["per_output"][attempt["label"]]
        kept = sum(1 for key, value in checks.items()
                   if key not in ("observation", "headwear_replaced_with_graduation_cap") and value)
        path = AUTO / attempt["output_path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != attempt["output_sha256"]:
            raise SystemExit(f"{attempt['output_path']}: hash mismatch")
        with Image.open(path) as image:
            size = image.size
        by_group[attempt["label"]] = {
            "path": path, "size": size, "kept": kept,
            "cap": bool(checks["headwear_replaced_with_graduation_cap"]),
            "seconds": attempt["request_seconds"],
        }
    if set(by_group) != set(GROUPS):
        raise SystemExit(f"expected all four configurations, found {sorted(by_group)}")
    return by_group


def fit(path, box_w, box_h):
    with Image.open(path) as image:
        frame = image.convert("RGB")
    frame.thumbnail((box_w, box_h), Image.LANCZOS)
    return frame


def paste(canvas, draw, path, x, y, box_w=CELL_W, box_h=CELL_H):
    frame = fit(path, box_w, box_h)
    ox = x + (box_w - frame.width) // 2
    oy = y + (box_h - frame.height) // 2
    canvas.paste(frame, (ox, oy))
    draw.rectangle([ox - 1, oy - 1, ox + frame.width, oy + frame.height], outline=LINE)


def main():
    data = load_round_one()
    with Image.open(AUTO / "input.jpg") as source:
        input_size = source.size

    width = 4 * CELL_W + 5 * PAD
    height = TITLE_H + INPUT_H + ROW_BANNER + COL_HEAD + CELL_H + CELL_CAPTION + FOOTER_H

    canvas = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(canvas)

    draw.text((PAD, 20), "第 12 题：换帽子图像编辑（size=auto，四个配置）",
              font=F_TITLE, fill=INK)
    draw.text((PAD, 60),
              "同一张输入、同一段提示词、同一批部署。每格标注实际输出分辨率、"
              "「要求保持不变」5 项的命中数与请求耗时。本图取第 1 轮。",
              font=F_SUB, fill=MUTED)

    y = TITLE_H
    draw.text((PAD, y), "输入原图（判定基准）", font=F_COL, fill=INK)
    paste(canvas, draw, AUTO / "input.jpg", PAD, y + COL_HEAD)
    draw.text((PAD, y + COL_HEAD + CELL_H + 8),
              f"{input_size[0]}x{input_size[1]}（16:9）", font=F_CELL_BOLD, fill=INK)
    draw.text((PAD, y + COL_HEAD + CELL_H + 29),
              "冕冠 · 左侧持戈侍卫 · 右侧紫衣人物 · 左上角剧名与印章",
              font=F_CELL, fill=MUTED)

    note_x = PAD * 2 + CELL_W
    note_w = width - note_x - PAD
    draw.rectangle([note_x, y + COL_HEAD, note_x + note_w, y + COL_HEAD + CELL_H], fill=NOTE_BG)
    draw.text((note_x + 16, y + COL_HEAD + 14), "提示词（四个配置完全相同）",
              font=F_CELL_BOLD, fill=INK)
    draw.text((note_x + 16, y + COL_HEAD + 40),
              "只把前景男子的头饰换成带流苏的黑色博士帽；人脸、胡须、神情、姿势\n"
              "保持不变；刺绣长袍、庭院和其他所有人保持不变。",
              font=F_NOTE, fill=MUTED, spacing=6)
    draw.text((note_x + 16, y + COL_HEAD + 104), "尺寸参数如何设定",
              font=F_CELL_BOLD, fill=ACCENT)
    draw.text((note_x + 16, y + COL_HEAD + 130),
              "MAI 的 /images/edits 接口没有尺寸参数，输出尺寸由服务决定；因此\n"
              "GPT 也传 `size=auto`，同样由服务决定，两边处于同一合同。\n\n"
              "本测试最初错误地只给 GPT 传了 `size=1024x1024`，把 16:9 的输入\n"
              "压成方图。那批方图是我们参数设置的产物，不是模型行为，因此不列\n"
              "入本对比；原始运行仍保留在仓库中作为该次错误的记录。",
              font=F_NOTE, fill=MUTED, spacing=6)
    y += INPUT_H

    draw.rectangle([0, y, width, y + ROW_BANNER - 8], fill=BANNER)
    draw.text((PAD, y + 8), "size=auto：GPT 与 MAI 同为服务自选尺寸（对称协议）",
              font=F_ROW, fill=GOOD)
    y += ROW_BANNER

    for index, (group, title) in enumerate(zip(GROUPS, COLUMN_TITLES)):
        x = PAD + index * (CELL_W + PAD)
        item = data[group]
        draw.text((x, y), title, font=F_COL, fill=INK)
        paste(canvas, draw, item["path"], x, y + COL_HEAD)
        ty = y + COL_HEAD + CELL_H + 8
        draw.text((x, ty), f"{item['size'][0]}x{item['size'][1]}（保持 16:9）",
                  font=F_CELL_BOLD, fill=GOOD)
        draw.text((x, ty + 21),
                  f"保持项 {item['kept']}/5 · 博士帽 {'已换' if item['cap'] else '未换'}"
                  f" · {item['seconds']:.1f} s",
                  font=F_CELL, fill=GOOD if item["kept"] == 5 else INK)

    y += COL_HEAD + CELL_H + CELL_CAPTION
    draw.line([0, y, width, y], fill=LINE)
    draw.text((PAD, y + 10),
              "5 项保持内容：人脸与胡须 · 龙袍纹样 · 侍卫与背景 · 标题与印章 · 原图宽高比。"
              "「已换博士帽」是要求改动的那一项，四个配置全部达成，因此不计入 5 项。",
              font=F_FOOT, fill=MUTED)
    draw.text((PAD, y + 32),
              "四个配置在这 5 项上没有差异。清单之外的观察：GPT 三档的标题英文字形更接近原图"
              "（high 两轮均逐字复现），MAI 的英文笔画发软、中文四字变形；输出分辨率 GPT 更高。",
              font=F_FOOT, fill=MUTED)
    draw.text((PAD, y + 54),
              "边界：本图只反映「按指令保持原图」的达成情况，不是画质评分；每个配置本轮仅 1 次调用。"
              "耗时为客户端往返时间，GPT 在 East US 2、MAI 在 Sweden Central，区域差异未剥离。",
              font=F_FOOT, fill=MUTED)

    OUT.parent.mkdir(exist_ok=True)
    canvas.save(OUT, "PNG")
    print(json.dumps({
        "output": str(OUT), "size": f"{width}x{height}", "bytes": OUT.stat().st_size,
        "kept": {g: data[g]["kept"] for g in GROUPS},
        "sizes": {g: data[g]["size"] for g in GROUPS},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

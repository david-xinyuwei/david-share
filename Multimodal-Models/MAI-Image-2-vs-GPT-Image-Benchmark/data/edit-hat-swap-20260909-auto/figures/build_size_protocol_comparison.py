"""Build one comparison sheet: input, fixed-square protocol, and size=auto protocol.

Reads only published evidence. Every cell label (resolution, preservation count)
comes from the archives' own records, not from prose, so the figure cannot drift
away from the data it illustrates.

Layout, top to bottom:
  row 0  the input photograph, shown once as the reference all cells are judged against
  row 1  size=1024x1024 (the first, asymmetric protocol)  - MAI, GPT low/medium/high
  row 2  size=auto      (the corrected, symmetric protocol) - same four configurations
"""

import hashlib
import json
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(r"C:\david-share\Multimodal-Models\MAI-Image-2-vs-GPT-Image-Benchmark")
FIXED = REPO / "data" / "edit-hat-swap-20260908"
AUTO = REPO / "data" / "edit-hat-swap-20260909-auto"
OUT = Path(__file__).resolve().parent / "runs" / "protocol-comparison.png"

GROUPS = ("mai-image-2.6", "gpt-image-2-low", "gpt-image-2-medium", "gpt-image-2-high")
COLUMN_TITLES = ("MAI-Image-2.6", "GPT-Image-2 low", "GPT-Image-2 medium", "GPT-Image-2 high")

CELL_W, CELL_H = 460, 300           # image box per cell
PAD = 18
COL_HEAD = 34                        # column title strip
CELL_CAPTION = 58                    # two caption lines under each image
ROW_HEAD = 64                        # row banner (protocol name + note)
TITLE_H = 96
FOOTER_H = 74

BG = (255, 255, 255)
INK = (23, 26, 31)
MUTED = (96, 104, 115)
BAD = (176, 42, 42)
GOOD = (21, 115, 71)
LINE = (214, 219, 226)
BANNER_BAD = (253, 242, 242)
BANNER_GOOD = (240, 249, 244)


FONT_DIR = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"


def font(size, bold=False):
    """Load a CJK-capable font by absolute path.

    Loading by bare family name silently falls back to a bitmap font with no CJK
    glyphs, which renders every Chinese label as tofu boxes. Fail loudly instead.
    """
    candidates = (("msyhbd.ttc", "simhei.ttf", "dengb.ttf") if bold
                  else ("msyh.ttc", "simsun.ttc", "deng.ttf"))
    for name in candidates:
        path = FONT_DIR / name
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    raise SystemExit(f"no CJK font found in {FONT_DIR}; tried {candidates}")


def assert_renders_chinese(loaded):
    """A CJK glyph must occupy real width; tofu or a missing glyph does not."""
    probe = Image.new("L", (64, 64), 0)
    ImageDraw.Draw(probe).text((2, 2), "换", font=loaded, fill=255)
    if probe.getbbox() is None:
        raise SystemExit("selected font produced no glyph for a Chinese character")


F_TITLE = font(30, bold=True)
F_SUB = font(16)
F_ROW = font(19, bold=True)
F_ROW_NOTE = font(15)
F_COL = font(17, bold=True)
F_CELL = font(15)
F_CELL_BOLD = font(15, bold=True)
F_FOOT = font(14)
for _loaded in (F_TITLE, F_SUB, F_ROW, F_CELL, F_FOOT):
    assert_renders_chinese(_loaded)


def load_round_one(archive):
    """Round-1 records plus the review, keyed by configuration."""
    results = json.loads((archive / "edit-results.json").read_text("utf-8"))
    review = json.loads((archive / "edit-review.json").read_text("utf-8"))
    by_group = {}
    for attempt in results["attempts"]:
        checks = review["per_output"][attempt["label"]]
        kept = sum(1 for key, value in checks.items()
                   if key != "observation" and key != "headwear_replaced_with_graduation_cap" and value)
        path = archive / attempt["output_path"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != attempt["output_sha256"]:
            raise SystemExit(f"{archive.name}/{attempt['output_path']}: hash mismatch")
        with Image.open(path) as image:
            size = image.size
        by_group[attempt["label"]] = {
            "path": path, "size": size, "kept": kept,
            "cap": bool(checks["headwear_replaced_with_graduation_cap"]),
            "seconds": attempt["request_seconds"],
        }
    return results.get("gpt_size_parameter", "1024x1024"), by_group


def fit(path, box_w, box_h):
    with Image.open(path) as image:
        frame = image.convert("RGB")
    frame.thumbnail((box_w, box_h), Image.LANCZOS)
    return frame


def draw_cell(canvas, draw, item, x, y, label_lines):
    frame = fit(item["path"], CELL_W, CELL_H)
    ox = x + (CELL_W - frame.width) // 2
    oy = y + (CELL_H - frame.height) // 2
    canvas.paste(frame, (ox, oy))
    draw.rectangle([ox - 1, oy - 1, ox + frame.width, oy + frame.height], outline=LINE)
    ty = y + CELL_H + 8
    for text, colour, use_bold in label_lines:
        draw.text((x, ty), text, font=(F_CELL_BOLD if use_bold else F_CELL), fill=colour)
        ty += 21


def main():
    fixed_size, fixed = load_round_one(FIXED)
    auto_size, auto = load_round_one(AUTO)
    if fixed_size != "1024x1024" or auto_size != "auto":
        raise SystemExit(f"unexpected protocols: {fixed_size!r} and {auto_size!r}")

    with Image.open(AUTO / "input.jpg") as source:
        input_size = source.size

    grid_w = 4 * CELL_W + 5 * PAD
    input_h = COL_HEAD + CELL_H + CELL_CAPTION
    row_h = ROW_HEAD + COL_HEAD + CELL_H + CELL_CAPTION + PAD
    width = grid_w
    height = TITLE_H + input_h + 2 * row_h + FOOTER_H

    canvas = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(canvas)

    draw.text((PAD, 22), "换帽子图像编辑：固定方图 与 size=auto 两种协议对比",
              font=F_TITLE, fill=INK)
    draw.text((PAD, 62),
              "同一张输入、同一段提示词、同一批部署；每格标注实际输出分辨率与「要求保持不变」5 项的命中数。"
              "每个协议各取第 1 轮。",
              font=F_SUB, fill=MUTED)

    # Row 0: the input, shown once.
    y = TITLE_H
    draw.text((PAD, y), "输入原图（判定基准）", font=F_COL, fill=INK)
    frame = fit(AUTO / "input.jpg", CELL_W, CELL_H)
    canvas.paste(frame, (PAD, y + COL_HEAD))
    draw.rectangle([PAD - 1, y + COL_HEAD - 1, PAD + frame.width, y + COL_HEAD + frame.height],
                   outline=LINE)
    draw.text((PAD, y + COL_HEAD + CELL_H + 8),
              f"{input_size[0]}x{input_size[1]}（16:9）", font=F_CELL_BOLD, fill=INK)
    draw.text((PAD, y + COL_HEAD + CELL_H + 29),
              "冕冠 · 左侧持戈侍卫 · 右侧紫衣人物 · 左上角剧名与印章", font=F_CELL, fill=MUTED)
    notes_x = PAD * 2 + CELL_W
    draw.text((notes_x, y + COL_HEAD),
              "提示词（四个配置完全相同）：只把前景男子的头饰换成带流苏的黑色博士帽；\n"
              "人脸、胡须、神情、姿势保持不变；刺绣长袍、庭院和其他所有人保持不变。\n\n"
              "MAI 的编辑接口没有尺寸参数，两种协议下都由服务自选尺寸。\n"
              "因此「固定 1024x1024」只约束了 GPT 一方，属于不对称协议；\n"
              "size=auto 让两边同为「服务自选」，才是对称比较。",
              font=F_CELL, fill=MUTED, spacing=6)
    y += input_h

    rows = (
        ("协议 A：固定 size=1024x1024（最初做法，已作废）",
         "只有 GPT 被强制方图；MAI 无此参数 → 单边约束", BANNER_BAD, fixed, BAD),
        ("协议 B：size=auto（当前做法）",
         "GPT 与 MAI 同为服务自选尺寸 → 对称协议", BANNER_GOOD, auto, GOOD),
    )
    for banner, note, banner_bg, data, accent in rows:
        draw.rectangle([0, y, width, y + ROW_HEAD - 8], fill=banner_bg)
        draw.text((PAD, y + 8), banner, font=F_ROW, fill=accent)
        draw.text((PAD, y + 34), note, font=F_ROW_NOTE, fill=MUTED)
        head_y = y + ROW_HEAD
        for index, (group, title) in enumerate(zip(GROUPS, COLUMN_TITLES)):
            x = PAD + index * (CELL_W + PAD)
            item = data[group]
            draw.text((x, head_y), title, font=F_COL, fill=INK)
            square = item["size"][0] == item["size"][1]
            kept_colour = GOOD if item["kept"] == 5 else BAD
            draw_cell(canvas, draw, item, x, head_y + COL_HEAD, [
                (f"{item['size'][0]}x{item['size'][1]}" + ("（方图）" if square else "（保持 16:9）"),
                 BAD if square else GOOD, True),
                (f"保持项 {item['kept']}/5 · 博士帽 {'已换' if item['cap'] else '未换'}"
                 f" · {item['seconds']:.1f} s", kept_colour, False),
            ])
        y += row_h

    draw.line([0, y - 4, width, y - 4], fill=LINE)
    draw.text((PAD, y + 6),
              "5 项保持内容：人脸与胡须 · 龙袍纹样 · 侍卫与背景 · 标题与印章 · 原图宽高比。"
              "「已换博士帽」是要求改动的那一项，两种协议下全部达成，因此不计入 5 项。",
              font=F_FOOT, fill=MUTED)
    draw.text((PAD, y + 28),
              "边界：本图只反映「按指令保持原图」的达成情况，不是画质评分；每档每协议仅 1 次调用，"
              "两协议运行于不同日期。宽高比一项由参数几何决定；其余 4 项与方图约束一致，但尚未做单变量对照。",
              font=F_FOOT, fill=MUTED)

    OUT.parent.mkdir(exist_ok=True)
    canvas.save(OUT, "PNG")
    print(json.dumps({
        "output": str(OUT), "size": f"{width}x{height}",
        "bytes": OUT.stat().st_size,
        "fixed_kept": {g: fixed[g]["kept"] for g in GROUPS},
        "auto_kept": {g: auto[g]["kept"] for g in GROUPS},
        "fixed_sizes": {g: fixed[g]["size"] for g in GROUPS},
        "auto_sizes": {g: auto[g]["size"] for g in GROUPS},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

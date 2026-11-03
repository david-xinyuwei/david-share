"""Render bilingual architecture diagrams and document previews from local sources."""
import argparse
import hashlib
import html
import json
import math
import os
import re
import statistics
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DOCUMENT_PAIRS = (
    ("README_CN.md", "README.md", 6, 5),
    ("文档/核心技术_微调与端侧运行.md", "文档/Core-Technology.md", 4, 2),
    ("文档/评测与端侧结果全集.md", "文档/Evaluation-Results.md", 36, 7),
    ("文档/操作步骤全本.md", "文档/Operations-Guide.md", 8, 20),
    ("文档/微调与端侧验证报告_20261027-130700.md", "文档/Finetuning-and-On-Device-Validation-Report.md", 20, 1),
)
INK = "#243746"
BLUE = "#0078D4"
GREY = "#D9E1E7"
MUTED = "#536471"
LANE_FILL = "#F3F5F7"
CARD_LINE = "#B8CEDF"
SCORE_GREY = "#687C8A"
READ = "#D83B01"   # Microsoft Office orange accent, used only for the pointer head's readout positions
WIDTH = 1200       # layout coordinates; the README displays every diagram at 900 px
HEIGHT = 680       # shared height of the inference, validation and decision diagrams; training() uses 728 (two lanes)
SCALE = 2          # raster at twice the layout size so labels stay crisp at the display width
LANE_RIGHT = WIDTH - 24
OWNER_DIVIDER = 264   # owner column 24..264, content from CARD_LEFT
CARD_LEFT, CARD_WIDTH, CARD_STEP = 280, 268, 308   # three columns: 280, 588, 896 (right edge 1164)


class Diagram:
    """Azure Architecture Center style: blue title bar, grey ownership lanes, white component cards, legend, footnote."""

    def __init__(self, title, subtitle, font_path, height=HEIGHT, scale=SCALE):
        self.s = scale
        self.image = Image.new("RGB", (WIDTH * scale, height * scale), "white")
        self.draw = ImageDraw.Draw(self.image)
        font = lambda size: ImageFont.truetype(str(font_path), size * scale)
        self.title_font, self.node_font, self.owner_font, self.detail_font = font(26), font(21), font(18), font(16)
        self.small_font, self.badge_font = font(14), font(12)
        self.icons_used = set()
        self.draw.rectangle(self.box(0, 0, WIDTH, 58), fill=BLUE)
        self.text((28, 13), title, self.title_font, 1140, "white")
        self.text((28, 70), subtitle, self.detail_font, 1144, MUTED)

    def box(self, left, top, right, bottom):
        return tuple(round(value * self.s) for value in (left, top, right, bottom))

    def point(self, x, y):
        return (round(x * self.s), round(y * self.s))

    def width_of(self, text, font):
        return self.draw.textlength(text, font=font) / self.s

    overflow = None   # set to a list to collect over-wide labels instead of raising (layout dry run)

    def text(self, position, text, font, max_width, fill):
        width = self.width_of(text, font)
        if width > max_width:
            if Diagram.overflow is None:
                raise ValueError(f"Diagram label is too wide: {text}")
            Diagram.overflow.append(f"{text!r}: {width:.0f} > {max_width:.0f}")
        self.draw.text(self.point(*position), text, font=font, fill=fill)

    def icon(self, name, position, size=48):
        folder = ROOT / "images" / "vendor"
        ledger = json.loads((folder / "sources.json").read_text(encoding="utf-8"))
        record = next(entry for entry in ledger["icons"] if entry["name"] == name)
        for field in ("original", "raster"):
            raw = (folder / record[field]).read_bytes()
            if hashlib.sha256(raw).hexdigest() != record[field + "_sha256"]:
                raise ValueError(f"Vendor icon differs from its source ledger: {name}")
        with Image.open(folder / record["raster"]) as source:
            icon = source.convert("RGBA")
            icon.thumbnail((size * self.s, size * self.s), Image.Resampling.LANCZOS)
            self.image.paste(icon, self.point(*position), icon)
        self.icons_used.add(name)

    def lane(self, top, bottom, owner, caption, icon=None, right=LANE_RIGHT):
        """One ownership lane: grey band, owner column on the left (optional ledgered icon), content to the right."""
        self.draw.rounded_rectangle(self.box(24, top, right, bottom), radius=8 * self.s, fill=LANE_FILL, outline=GREY, width=self.s)
        x = 40
        if icon:
            self.icon(icon, (40, top + 14), 36)
            x = 84
        self.text((x, top + 14), owner, self.owner_font, OWNER_DIVIDER - 8 - x, INK)
        for index, line in enumerate(caption.split("\n")):
            self.text((x, top + 42 + 20 * index), line, self.small_font, OWNER_DIVIDER - 8 - x, MUTED)
        self.draw.line([self.point(OWNER_DIVIDER, top + 12), self.point(OWNER_DIVIDER, bottom - 12)], fill=GREY, width=self.s)

    def card(self, left, top, title, detail="", icon=None, badges=(), step=None, width=CARD_WIDTH, height=None, muted=False, compact=False):
        """One component or artifact: white card, optional ledgered icon or step number, one or two detail lines, text badges.
        compact=True sets detail lines in the 14 px small font at 19 px leading, for narrow cards (five across a lane)."""
        lines = [line for line in detail.split("\n") if line]
        detail_font, leading = (self.small_font, 19) if compact else (self.detail_font, 22)
        height = height or 56 + leading * len(lines) + (28 if badges else 0)
        outline = GREY if muted else CARD_LINE
        self.draw.rounded_rectangle(self.box(left, top, left + width, top + height), radius=6 * self.s, fill="white", outline=outline, width=self.s)
        x = left + 14
        if icon:
            self.icon(icon, (x, top + 10), 32)
            x += 42
        if step:
            cx, cy, r = left + 27, top + 24, 12
            self.draw.ellipse(self.box(cx - r, cy - r, cx + r, cy + r), fill=BLUE)
            self.draw.text(self.point(cx - self.width_of(step, self.small_font) / 2, cy - 9), step, font=self.small_font, fill="white")
            x = left + (44 if compact else 50)
        self.text((x, top + 11), title, self.node_font, left + width - x - (6 if compact else 10), MUTED if muted else INK)
        for index, line in enumerate(lines):
            self.text((left + 14, top + 44 + leading * index), line, detail_font, width - 24, MUTED)
        bx, by = left + 14, top + height - 32
        for badge in badges:
            bw = self.width_of(badge, self.badge_font) + 16
            self.draw.rounded_rectangle(self.box(bx, by, bx + bw, by + 20), radius=10 * self.s, fill="white", outline=MUTED, width=self.s)
            self.text((bx + 8, by + 2), badge, self.badge_font, bw, INK)
            bx += bw + 8
        return (left, top, left + width, top + height)

    def arrow(self, points, color=BLUE, head=True, dashed=False):
        scaled = [self.point(*point) for point in points]
        if dashed:
            dash, gap = 7 * self.s, 5 * self.s
            for (x0, y0), (x1, y1) in zip(scaled, scaled[1:]):
                length = math.hypot(x1 - x0, y1 - y0)
                ux, uy = ((x1 - x0) / length, (y1 - y0) / length) if length else (0, 0)
                run = 0
                while run < length:
                    stop = min(run + dash, length)
                    self.draw.line([(x0 + ux * run, y0 + uy * run), (x0 + ux * stop, y0 + uy * stop)], fill=color, width=2 * self.s)
                    run = stop + gap
        else:
            self.draw.line(scaled, fill=color, width=2 * self.s, joint="curve")
        if head:
            previous, end = scaled[-2:]
            angle = math.atan2(end[1] - previous[1], end[0] - previous[0])
            size = 10 * self.s
            triangle = [end] + [(end[0] - size * math.cos(angle + offset), end[1] - size * math.sin(angle + offset)) for offset in (-0.48, 0.48)]
            self.draw.polygon(triangle, fill=color)

    def legend(self, top, items):
        """items: (kind, label) with kind in lane | card | arrow | score | read | back | badge."""
        x = 28
        for kind, label in items:
            if kind == "lane":
                self.draw.rounded_rectangle(self.box(x, top + 3, x + 22, top + 17), radius=3 * self.s, fill=LANE_FILL, outline=GREY, width=self.s)
            elif kind == "card":
                self.draw.rounded_rectangle(self.box(x, top + 3, x + 22, top + 17), radius=3 * self.s, fill="white", outline=CARD_LINE, width=self.s)
            elif kind == "badge":
                self.draw.rounded_rectangle(self.box(x, top + 2, x + 22, top + 18), radius=8 * self.s, fill="white", outline=MUTED, width=self.s)
            elif kind == "back":
                self.arrow([(x, top + 10), (x + 22, top + 10)], color=READ, dashed=True)
            else:
                self.arrow([(x, top + 10), (x + 22, top + 10)], color={"score": SCORE_GREY, "read": READ}.get(kind, BLUE))
            self.text((x + 30, top), label, self.small_font, 360, MUTED)
            x += 30 + self.width_of(label, self.small_font) + 26
        if x > LANE_RIGHT:
            raise ValueError("Legend is too wide for the canvas")

    def footnote(self, top, *lines):
        for index, line in enumerate(lines):
            self.text((28, top + 20 * index), line, self.small_font, 1144, MUTED)

    def save(self, path):
        self.image.save(path)
        return {"file": path.name, "width": self.image.width, "height": self.image.height,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "vendor_icons": sorted(self.icons_used)}


def legend_items(label, score=False):
    items = [("lane", label("泳道：归属方", "Lane: owner")), ("card", label("卡片：组件或产物", "Card: component or artifact")),
             ("arrow", label("蓝色箭头：数据流", "Blue arrow: data flow"))]
    if score:
        items.append(("score", label("灰色箭头：标准答案只供评分", "Grey arrow: labels, scoring only")))
    items.append(("badge", label("徽章：无官方图标的软件", "Badge: software without an icon")))
    return items


ICON_NOTE = ("图标：Microsoft Azure 架构图标与 Fluent UI 系统图标，来源、条款与哈希见 images/vendor/sources.json。",
             "Icons: Microsoft Azure architecture icons and Fluent UI system icons; sources, terms and hashes in images/vendor/sources.json.")


def training(font_path, language="zh"):
    """Workflow illustration: development feedback is separate from frozen independent acceptance."""
    label = lambda chinese, english: english if language == "en" else chinese
    manifest = json.loads((ROOT / "data/contoso/final/manifest.json").read_text(encoding="utf-8"))
    counts = [manifest[name]["records"] for name in ("train.jsonl", "train_cf.jsonl", "train_cf2.jsonl")]
    d = Diagram(label("业务微调、校准、评测、导出与量化", "Business fine-tuning, calibration, evaluation, export and quantization"),
                label("开发数据指导迭代；冻结权重与温度后做独立验收，量化文件还需在目标设备复核",
                    "Development guides iteration; freeze weights and temperature for independent acceptance, then validate the quantized file on device"), font_path, height=728)
    cw = CARD_WIDTH
    c1, c2, c3 = (CARD_LEFT + index * CARD_STEP for index in range(3))
    d.lane(104, 236, label("客户笔记本", "Customer laptop"), label("本地，厂商所有\n准备数据，部署 GGUF", "Local; vendor-owned\nPrepares data, runs GGUF"), icon="laptop")
    d.card(c1, 116, label("业务训练集", "Training set"), label(f"FT {counts[0]:,} / FT-cf {counts[1]:,}\nC {counts[2]:,} 条\n各配方 + 1,000 条回放", f"FT {counts[0]:,} / FT-cf {counts[1]:,}\nC {counts[2]:,} records\nEach + 1,000 replay"), icon="file", width=cw, compact=True)
    d.card(c2, 116, label("数据切分", "Data splits"), label("训练、校准、开发隔离\n开发集反馈改进\n独立测试只做终验", "Train / calibration / dev\nDevelopment feedback\nSeparate final acceptance"), icon="file", width=cw, compact=True)
    d.card(c3, 116, label("量化 GGUF", "Quantized"), label("Q8_0 / Q4_K_M\n温度随文件保存\n按最终设备复核", "GGUF Q8_0 / Q4_K_M\nTemperature inside\nValidate on target device"), icon="file", width=cw, compact=True)
    # five equal cards in the host lane: 5 x 164 px with 12 px gaps fill CARD_LEFT..LANE_RIGHT-16 (280..1160); compact detail font
    sw, sg, sh = 164, 12, 160   # equal card height: four compact detail lines + one badge row
    s1, s2, s3, s4, s5 = (CARD_LEFT + index * (sw + sg) for index in range(5))
    d.lane(258, 606, label("Azure 训练主机", "Azure training host"), label("云侧，厂商租用\n1× H100 NVL\n3–4 只用 CPU", "Cloud; vendor-rented\n1× H100 NVL\nSteps 3–4: CPU only"), icon="azure-vm")
    model = d.card(s1, 274, label("Kev 发布版", "Released Kev"), label("0.8B / 4B，开放权重\n已训练的 LoRA + 指针头", "0.8B / 4B, open weights\nTrained LoRA + head"), icon="file", width=206, compact=True)
    step_top = 402
    d.card(s1, step_top, label("监督微调", "Fine-tune"), label("LoRA r16 + 指针头\n各配方独立训练\n训练数据更新权重", "LoRA r16 + head\nIndependent recipes\nUpdate weights"), step="1", width=sw, height=sh, badges=("PyTorch", "Kev"), compact=True)
    d.card(s2, step_top, label("温度校准", "Calibrate"), label("权重不动，只拟一个 T\n不改任何一题答案\n只动 ② 把握真不真", "Weights frozen; fit T\nChanges no answer\nMoves only ②"), step="2", width=sw, height=sh, badges=("Kev",), compact=True)
    d.card(s3, step_top, label("开发评估", "Dev review"), label("开发集诊断错误\n人工决定下一步\n不是独立终验", "Diagnose dev errors\nHuman decision\nNot final testing"), width=sw, height=sh, badges=("Kev",), compact=True)
    d.card(s4, step_top, label("导出 GGUF", "Export"), label("合并 LoRA 进基座\n保存温度参数\n核对最终导出文件", "Merge LoRA weights\nRetain temperature\nVerify exported file"), step="3", width=sw, height=sh, badges=("llama.cpp",), compact=True)
    d.card(s5, step_top, label("量化", "Quantize"), label("训练后量化，不重训\nQ8_0 / Q4_K_M\n逐题复核答案与概率\n文件大小见实测表", "PTQ, no retraining\nQ8_0 / Q4_K_M\nCheck predictions\nSizes: results"), step="4", width=sw, height=sh, badges=("llama.cpp",), compact=True)
    bottom = step_top + sh
    cards_bottom = 116 + 56 + 19 * 3
    d.arrow([(c1 + cw - 20, cards_bottom), (c1 + cw - 20, step_top - 12), (s1 + sw - 38, step_top - 12), (s1 + sw - 38, step_top)])
    d.arrow([(s1 + sw / 2, model[3]), (s1 + sw / 2, step_top)])
    d.arrow([(c2 + cw / 2 - 34, cards_bottom), (c2 + cw / 2 - 34, step_top - 20), (s2 + sw / 2, step_top - 20), (s2 + sw / 2, step_top)])
    d.arrow([(c2 + cw / 2 + 34, cards_bottom), (c2 + cw / 2 + 34, step_top - 28), (s3 + sw / 2, step_top - 28), (s3 + sw / 2, step_top)])
    d.arrow([(s1 + sw, step_top + 64), (s2, step_top + 64)])
    d.arrow([(s2 + sw, step_top + 64), (s3, step_top + 64)])
    d.arrow([(s3 + sw, step_top + 64), (s4, step_top + 64)])
    d.arrow([(s4 + sw, step_top + 64), (s5, step_top + 64)])
    d.arrow([(s3 + 40, bottom), (s3 + 40, bottom + 22), (s1 + sw / 2, bottom + 22), (s1 + sw / 2, bottom)], color=READ, dashed=True)   # accuracy fell -> retrain
    d.arrow([(s3 + sw - 40, bottom), (s3 + sw - 40, bottom + 11), (s2 + sw / 2, bottom + 11), (s2 + sw / 2, bottom)], color=READ, dashed=True)   # probabilities off -> refit T
    d.arrow([(s5 + sw / 2, step_top), (s5 + sw / 2, 246), (c3 + cw / 2, 246), (c3 + cw / 2, cards_bottom)])
    d.legend(620, [("lane", label("泳道：执行位置", "Lane: location")), ("card", label("卡片：组件或产物", "Card: component or artifact")),
                   ("arrow", label("蓝色：数据流", "Blue: data flow")), ("back", label("橙色虚线：人工开发反馈", "Orange dashed: human feedback")),
                   ("badge", label("徽章：无图标的软件", "Badge: software without icon"))])
    d.footnote(650, label("原创流程图。FT、FT-cf、C 从发布版独立训练；样本数取自 data/contoso/final/manifest.json，回放参数取自训练脚本。",
                          "Original workflow. FT, FT-cf and C start independently from the release; sample counts: data/contoso/final/manifest.json; replay: training scripts."),
               label("开发反馈不等于独立终验。回退为人工决策；脚本不自动重训或发布。导出、量化只用 CPU；最终文件需目标设备验收。",
                   "Development feedback is not final acceptance. Retraining and release are human decisions. Export/PTQ use CPU; validate the final file on device."),
               label(*ICON_NOTE))
    return d


def inference(font_path, language="zh"):
    label = lambda chinese, english: english if language == "en" else chinese
    d = Diagram(label("端侧业务判断", "On-device business decisions"),
                label("业务应用发出请求，llama-server 在笔记本 CPU 上回答；全程没有云端模型调用", "The business application sends a request and llama-server answers on the laptop CPU; no cloud model is called"), font_path)
    c1, c2, c3 = CARD_LEFT, CARD_LEFT + CARD_STEP, CARD_LEFT + 2 * CARD_STEP
    d.lane(104, 236, label("业务应用", "Business application"), label("厂商所有\n决定后续动作", "Vendor-owned\nDecides what happens next"))
    d.card(c1, 116, label("业务输入", "Business input"), label("客户原话 + 设备字段\n待回答的问题，无标签", "Message + device fields\nQuestions, no labels"), icon="file")
    d.card(c3, 116, label("后续动作", "Next action"), label("派单、转人工或补问\n由应用自行决定", "Dispatch, hand off or ask again\nDecided by the application"))
    d.lane(258, 418, label("客户笔记本", "Customer laptop"), label("厂商所有\n骁龙 X Elite，CPU", "Vendor-owned\nSnapdragon X Elite, CPU"), icon="laptop")
    d.card(c1, 274, label("微调 GGUF", "Fine-tuned GGUF"), label("合并 LoRA + 指针头\n温度已写入元数据", "Merged LoRA + pointer head\nTemperature in metadata"), icon="file", height=128)
    d.card(c2, 274, "llama-server", label("本机 HTTP 服务\nPOST /v1/systemone", "Local HTTP server\nPOST /v1/systemone"), badges=("llama.cpp b11935",))
    d.card(c3, 274, label("结构化答案", "Structured answers"), label("选项 / 是非 / 等级\n温度缩放后的概率", "Choice / yes-no / ordinal\nProbabilities scaled by T"), height=128)
    d.lane(440, 540, label("云端服务", "Cloud services"), label("本步骤不涉及", "Not involved in this step"))
    d.card(c1, 452, label("无云端模型请求", "No cloud-model request"), label("不训练；不替用户执行维修、联网或工具调用", "No training; no repair, network or tool action on the user's behalf"), width=CARD_WIDTH * 2 + CARD_STEP - CARD_WIDTH, height=76, muted=True)
    mid1, mid3 = c1 + CARD_WIDTH / 2, c3 + CARD_WIDTH / 2
    d.arrow([(mid1, 216), (mid1, 246), (c2 + 90, 246), (c2 + 90, 274)])            # input -> llama-server
    d.arrow([(c1 + CARD_WIDTH, 338), (c2, 338)])                                   # GGUF loaded by llama-server
    d.arrow([(c2 + CARD_WIDTH, 338), (c3, 338)])                                   # answers
    d.arrow([(mid3, 274), (mid3, 216)])                                            # answers -> application
    d.legend(566, legend_items(label))
    d.footnote(598, label("原创解释图。依据：scripts/systemone_client.py、scripts/run_engine_eval.ps1，以及 llama.cpp b11935 的 tools/server/server-decision.cpp。",
                          "Original explanatory diagram. Sources: scripts/systemone_client.py, scripts/run_engine_eval.ps1 and tools/server/server-decision.cpp at llama.cpp b11935."),
               label(*ICON_NOTE),
               label("推理在笔记本完成，业务动作由应用另行决定；测试阶段的独立拓扑见下一张图。", "Inference happens on the laptop and the application decides the action; the separate test topology is in the next diagram."))
    return d


def validation(font_path, language="zh"):
    label = lambda chinese, english: english if language == "en" else chinese
    d = Diagram(label("测试拓扑与评分边界", "Test topology and scoring boundaries"),
                label("同一测试集走两条独立推理路径；业务准确率与引擎一致率是两个不同的指标", "The same test set runs through two independent inference paths; task accuracy and engine agreement are different metrics"), font_path)
    c1, c2 = CARD_LEFT, CARD_LEFT + CARD_STEP
    score_left, score_right, lane_right = 884, LANE_RIGHT, 860
    d.lane(104, 236, label("测试数据", "Test data"), label("规则代码算标签\n同一批记录", "Labels from policy code\nSame records"), icon="file")
    d.card(c1, 116, label("同一测试集", "Same test set"), label("无标签输入给两条路径\n标准答案只给评分程序", "Unlabeled inputs to both paths\nLabels go to scoring only"), icon="file")
    d.lane(258, 418, label("Azure GPU 主机", "Azure GPU host"), label("厂商租用\nH100 NVL", "Vendor-rented\nH100 NVL"), icon="azure-vm", right=lane_right)
    d.card(c2, 274, label("PyTorch 评测", "PyTorch evaluation"), label("kev.benchmark，CUDA\n保存逐题答案与概率", "kev.benchmark on CUDA\nSaves per-question answers"), badges=("PyTorch", "Kev"))
    d.lane(440, 600, label("客户笔记本", "Customer laptop"), label("厂商所有\n骁龙 X Elite\nCPU / Adreno GPU", "Vendor-owned\nSnapdragon X Elite\nCPU / Adreno GPU"), icon="laptop", right=lane_right)
    d.card(c2, 456, label("端侧评测", "Device evaluation"), label("run_engine_eval.ps1\n答案、请求耗时、进程内存", "run_engine_eval.ps1\nAnswers, request time, memory"), badges=("llama.cpp b11935",))
    # scoring box beside the two inference lanes: runs on the laptop, never updates the model
    d.draw.rounded_rectangle(d.box(score_left, 258, score_right, 600), radius=8 * d.s, fill="white", outline=CARD_LINE, width=d.s)
    d.text((score_left + 16, 270), label("评分程序", "Scoring program"), d.node_font, 260, INK)
    d.text((score_left + 16, 300), label("笔记本上运行，不更新模型", "Runs on the laptop, no model updates"), d.small_font, 260, MUTED)
    d.draw.line([d.point(score_left + 16, 328), d.point(score_right - 16, 328)], fill=GREY, width=d.s)
    d.text((score_left + 16, 346), label("业务准确率", "Task accuracy"), d.node_font, 260, INK)
    d.text((score_left + 16, 376), label("每条路径的预测对照标准答案", "Each path's predictions vs. labels"), d.small_font, 260, MUTED)
    d.text((score_left + 16, 396), label("两条路径分别评分", "Each path is scored separately"), d.small_font, 260, MUTED)
    d.draw.line([d.point(score_left + 16, 428), d.point(score_right - 16, 428)], fill=GREY, width=d.s)
    d.text((score_left + 16, 446), label("引擎一致率", "Engine agreement"), d.node_font, 260, INK)
    d.text((score_left + 16, 476), label("两条路径的答案逐题互比", "Both paths' answers, per question"), d.small_font, 260, MUTED)
    d.text((score_left + 16, 496), label("不看标准答案", "Does not look at the labels"), d.small_font, 260, MUTED)
    d.draw.line([d.point(score_left + 16, 528), d.point(score_right - 16, 528)], fill=GREY, width=d.s)
    d.text((score_left + 16, 546), label("准确率 ≠ 一致率", "Accuracy ≠ agreement"), d.node_font, 260, INK)
    d.text((score_left + 16, 576), label("引擎可以一致但都答错", "Both engines can agree and be wrong"), d.small_font, 260, MUTED)
    mid1 = c1 + CARD_WIDTH / 2
    d.arrow([(mid1, 216), (mid1, 338), (c2, 338)])                                 # test set -> PyTorch path
    d.arrow([(mid1, 338), (mid1, 520), (c2, 520)])                                 # test set -> device path
    d.arrow([(c2 + CARD_WIDTH, 338), (score_left, 338)])                           # PyTorch answers -> scoring
    d.arrow([(c2 + CARD_WIDTH, 520), (score_left, 520)])                           # device answers -> scoring
    d.arrow([(c1 + CARD_WIDTH, 150), (1030, 150), (1030, 258)], color=SCORE_GREY)  # labels -> scoring only
    d.text((640, 128), label("标准答案只供评分", "Labels: scoring only"), d.small_font, 300, SCORE_GREY)
    d.legend(620, legend_items(label, score=True))
    d.footnote(648, label("原创解释图。依据：scripts/remote_pipeline_v2.sh、scripts/run_engine_eval.ps1、scripts/parity.py。请求耗时在笔记本客户端计量，排除加载与预热。",
                          "Original explanatory diagram. Sources: scripts/remote_pipeline_v2.sh, run_engine_eval.ps1, parity.py. Request time: laptop client, excluding loading and warm-up."))
    return d


def decision(font_path, language="zh"):
    """How Kev answers one question in a single forward pass: packed sequence -> frozen backbone + LoRA -> pointer head.
    Facts: kev/model.py@2074cc44 (SPECIAL delimiters, encode(), PointerHead q/k dp=256, _readout, temperature)."""
    label = lambda chinese, english: english if language == "en" else chinese
    d = Diagram(label("Kev 决策模型：一次前向怎么出答案", "Kev decision model: one forward pass to an answer"),
                label("模型读完题目和全部选项，只在 K+1 个位置读数、给每个选项打分；不生成任何文字", "The model reads the question and every option, reads K+1 positions, scores each option; no text is generated"), font_path)
    read = READ
    # --- lane 1: packed input sequence ---------------------------------------------------------------
    d.lane(104, 236, label("输入序列", "Input sequence"), label("一条记录，拼成一行\n题目 + 全部选项", "One record as one row\nquestion + all options"), icon="file")
    rows = ([(label("<state> 客户原话 + 设备字段", "<state> message + device fields"), INK), (label("<q> 题目", "<q> question"), INK)],
            [(label("<opt> 选项 1 </opt>", "<opt> option 1 </opt>"), read), (label("<opt> 选项 2 </opt>", "<opt> option 2 </opt>"), read),
             ("…", INK), (label("<opt> 选项 K </opt>", "<opt> option K </opt>"), read), ("<decide>", read)])
    for line, tokens in enumerate(rows):
        top = 120 + 42 * line
        widths = [d.width_of(text, d.detail_font) + 18 for text, _ in tokens]
        if CARD_LEFT + sum(widths) + 6 * (len(tokens) - 1) > LANE_RIGHT - 16:
            raise ValueError("Token row is too wide for the lane")
        x = CARD_LEFT
        for (text, colour), width in zip(tokens, widths):
            d.draw.rounded_rectangle(d.box(x, top, x + width, top + 34), radius=5 * d.s, fill="white", outline=colour, width=d.s if colour == INK else 2 * d.s)
            d.text((x + 9, top + 7), text, d.detail_font, width - 12, colour)
            x += width + 6
    d.text((CARD_LEFT, 206), label("橙框 = 指针头读取隐状态的位置：每个选项结尾的 </opt>，和末尾的 <decide>；K 个选项共读 K + 1 个位置", "Orange = positions the pointer head reads: each option's closing </opt> and the final <decide>; K options → K + 1 reads"), d.small_font, 900, MUTED)
    # --- lane 2: backbone -------------------------------------------------------------------------------
    d.lane(258, 418, label("主干", "Backbone"), label("Qwen3.5-Base\n0.8B / 4B", "Qwen3.5-Base\n0.8B / 4B"))
    d.card(CARD_LEFT, 274, label("冻结的基座权重", "Frozen base weights"), label("不带词表输出层\n不生成 token", "No vocabulary output layer\nGenerates no token"), badges=("PyTorch",))
    d.card(CARD_LEFT + CARD_STEP, 274, label("LoRA 适配器（秩 16）", "LoRA adapters (rank 16)"), label("挂在全部线性投影上\n微调时唯一在动的主干参数", "On every linear projection\nThe only trained backbone part"), badges=("Kev",))
    d.card(CARD_LEFT + 2 * CARD_STEP, 274, label("隐状态", "Hidden states"), label("每个 token 位置一个向量\n只取 K + 1 个位置", "One vector per token position\nOnly K + 1 positions are used"), height=100)
    # --- lane 3: pointer head ---------------------------------------------------------------------------
    d.lane(440, 600, label("指针头", "Pointer head"), label("两个线性层 q、k\n输出 256 维", "Two linear layers q, k\n256 dimensions"))
    d.card(CARD_LEFT, 456, "q", label("读 <decide> 位置\n= 对整道题的理解", "Reads the <decide> position\n= the question as a whole"), badges=("Kev",))
    d.card(CARD_LEFT + CARD_STEP, 456, "k", label("读每个 </opt> 位置\n= 对每个选项的理解", "Reads each </opt> position\n= each option"), badges=("Kev",))
    d.card(CARD_LEFT + 2 * CARD_STEP, 456, label("打分 → 概率", "Score → probability"), label("z_i = k(h_opt_i)·q(h_decide) / 16\nsoftmax(z / T)，T 来自 GGUF", "z_i = k(h_opt_i)·q(h_decide) / 16\nsoftmax(z / T), T from the GGUF"), height=100)
    # arrows: sequence -> backbone, backbone -> hidden -> q and k, q & k -> score
    mid1, mid2, mid3 = CARD_LEFT + CARD_WIDTH / 2, CARD_LEFT + CARD_STEP + CARD_WIDTH / 2, CARD_LEFT + 2 * CARD_STEP + CARD_WIDTH / 2
    d.arrow([(mid1, 216), (mid1, 274)])
    d.arrow([(CARD_LEFT + CARD_WIDTH, 338), (CARD_LEFT + CARD_STEP, 338)])
    d.arrow([(CARD_LEFT + CARD_STEP + CARD_WIDTH, 338), (CARD_LEFT + 2 * CARD_STEP, 338)])
    d.arrow([(mid3, 374), (mid3, 430), (mid1, 430), (mid1, 456)], color=read)      # <decide> hidden state -> q
    d.arrow([(mid3, 430), (mid2, 430), (mid2, 456)], color=read)                   # </opt> hidden states -> k
    d.arrow([(CARD_LEFT + CARD_WIDTH, 520), (CARD_LEFT + CARD_STEP, 520)])
    d.arrow([(CARD_LEFT + CARD_STEP + CARD_WIDTH, 520), (CARD_LEFT + 2 * CARD_STEP, 520)])
    d.legend(620, [("lane", label("泳道：模型的一层", "Lane: model layer")), ("card", label("卡片：组件", "Card: component")),
                   ("arrow", label("蓝色：数据流", "Blue: data flow")), ("read", label("橙色：指针头读取的位置", "Orange: positions the head reads")),
                   ("badge", label("徽章：无图标的软件", "Badge: software without an icon"))])
    d.footnote(648, label("原创解释图。依据：kev/model.py @ 2074cc44（SPECIAL 分隔标记、encode()、PointerHead、_readout）。聊天模型则是逐 token 生成文字再解析。",
                          "Original explanatory diagram. Source: kev/model.py @ 2074cc44 (SPECIAL delimiters, encode(), PointerHead, _readout). A chat model would generate text and parse it."))
    return d


def model_loading_seconds(log_path):
    text = (ROOT / log_path).read_text(encoding="utf-8-sig")
    timestamp = r"^(\d+)\.(\d{2})\.(\d{3})\.(\d{3})\s+.*?"
    starts = re.findall(timestamp + r"\bload_model:\s+loading model", text, re.M)
    ends = re.findall(timestamp + r"\bserver_run_i:\s+model loaded", text, re.M)
    if len(starts) != 1 or len(ends) != 1:
        raise ValueError(f"Expected one model-loading interval: {log_path}")

    def microseconds(parts):
        minutes, seconds, milliseconds, remainder = map(int, parts)
        return (minutes * 60 + seconds) * 1_000_000 + milliseconds * 1_000 + remainder

    elapsed = microseconds(ends[0]) - microseconds(starts[0])
    if elapsed <= 0:
        raise ValueError(f"Invalid model-loading interval: {log_path}")
    return f"{elapsed / 1_000_000:.3f}"


def sync_model_loading_tables():
    from markdown_it import MarkdownIt

    path = ROOT / "文档/评测与端侧结果全集.md"
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    parser = MarkdownIt("commonmark", {"html": True}).enable("table")
    replacements = []
    for token in parser.parse(text):
        if token.type != "table_open":
            continue
        start, end = token.map
        if (not lines[start].startswith(("| 模型（0.8B，骁龙", "| 模型（4B，骁龙"))
            or "模型加载阶段耗时" not in lines[start]):
            continue
        size = "0.8b" if "0.8B" in lines[start] else "4b"
        entries = [[cell.strip() for cell in line.strip().split("|")[1:-1]] for line in lines[start:end]]
        entries[0][5] = "单条任务处理耗时（工单 / 助手，毫秒，中位数）"
        entries[0][7] = "模型加载阶段耗时（秒，日志）"
        for entry in entries[2:]:
            if entry[0].startswith("原始发布版 B0"):
                recipe = "released"
            elif entry[0].startswith("微调 FT-cf"):
                recipe = "ftcf"
            elif entry[0].startswith("微调 FT，"):
                recipe = "ft"
            else:
                raise ValueError(f"No recorded loading run for: {entry[0]}")
            quantization = "Q8_0" if "Q8_0" in entry[0] else "Q4_K_M"
            run = f"{recipe}-kev-{size}-{quantization}-cpu"
            entry[7] = model_loading_seconds(report_sources()["device_results"] / run / "server.log")
        replacements.append((start, end, "".join("| " + " | ".join(entry) + " |\n" for entry in entries)))
    if len(replacements) != 2:
        raise ValueError("Expected both laptop inference tables")
    for start, end, replacement in reversed(replacements):
        lines[start:end] = [replacement]
    path.write_text("".join(lines), encoding="utf-8")


INFERENCE_CONFIGURATIONS = (
        ("0.8B", "released-kev-0.8b-Q8_0-cpu", "原始发布版 B0，官方 Q8_0 包"),
        ("0.8B", "ftcf-kev-0.8b-Q8_0-cpu", "微调 FT-cf，Q8_0"),
        ("0.8B", "ft-kev-0.8b-Q4_K_M-cpu", "微调 FT，Q4_K_M（独立 FT 配方，非 FT-cf）"),
        ("0.8B", "r2c-kev-0.8b-Q8_0-cpu", "第二轮 C，Q8_0（交付）"),
        ("4B", "released-kev-4b-Q4_K_M-cpu", "原始发布版 B0，官方 Q4_K_M 包"),
        ("4B", "ftcf-kev-4b-Q8_0-cpu", "微调 FT-cf，Q8_0"),
        ("4B", "ftcf-kev-4b-Q4_K_M-cpu", "微调 FT-cf，Q4_K_M"),
)


def report_sources():
    text = (ROOT / "README_CN.md").read_text(encoding="utf-8")
    matches = re.findall(r"<!-- REPORT:SOURCES\s+(.*?)\s+-->", text, re.S)
    if len(matches) != 1:
        raise ValueError("Expected one REPORT:SOURCES configuration in README_CN.md")
    sources = json.loads(matches[0])
    expected = {"first_summary", "round2_summary", "device_results", "round2_device_results"}
    if set(sources) != expected:
        raise ValueError("Report source configuration must name both summaries and both device campaigns")
    paths = {}
    for name, relative in sources.items():
        if not isinstance(relative, str) or Path(relative).is_absolute():
            raise ValueError(f"Report source must be project-relative: {name}")
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT.resolve()):
            raise ValueError(f"Report source is outside the project: {name}")
        if not (path.is_file() if name.endswith("summary") else path.is_dir()):
            raise ValueError(f"Report source is missing or has the wrong type: {name}: {relative}")
        paths[name] = path
    return paths


def single_question_tables(campaign=None):
    models = INFERENCE_CONFIGURATIONS
    datasets = (("test_support", "工单·同分布"), ("test_assistant", "助手·同分布"),
                ("ood_support", "工单·分布外"), ("ood_assistant", "助手·分布外"))
    manifest = json.loads((ROOT / "data/contoso/final/manifest.json").read_text(encoding="utf-8"))
    if campaign is None:
        campaigns = sorted(path for path in (ROOT / "验证结果").glob("单题端侧评测_骁龙_*") if path.is_dir())
        campaign = campaigns[-1] if campaigns else None
    tables = []
    has_results = False
    for size in ("0.8B", "4B"):
        lines = [f"| 模型（{size}，骁龙 X Elite CPU，默认参数） | 测试集（题数） | 单题准确率（%，含失败题） | 单次分类中位延迟（毫秒） | 校准误差 ECE（0–1，越低越好） | 有效概率覆盖率（%） |",
                 "|---|---|---|---|---|---|"]
        for model_size, model_id, label in models:
            if model_size != size:
                continue
            for dataset, dataset_label in datasets:
                expected = manifest[f"{dataset}.jsonl"]
                cells = ["待测"] * 4
                summary_path = Path(campaign) / model_id / dataset / "summary.json" if campaign else None
                if summary_path and summary_path.is_file():
                    result = json.loads(summary_path.read_text(encoding="utf-8-sig"))
                    run = json.loads((summary_path.parents[1] / "run.json").read_text(encoding="utf-8-sig"))
                    if (run.get("request_mode") != "single_question" or run.get("architecture") != "ARM64"
                            or not re.search(r"X Elite|X1E80100", " ".join(run.get("cpu", [])), re.I)
                            or run.get("label") != model_id or run.get("backend") != "cpu"
                            or not run.get("build", "").startswith("b11935")
                            or any(flag not in run.get("server_args", "") for flag in
                                   ("-c 8192", "-b 2048", "-ub 2048", "--cache-ram 0"))):
                        raise ValueError(f"Single-question device/configuration mismatch: {summary_path}")
                    count = expected["questions"]
                    method = result.get("method", {})
                    if (result.get("request_mode") != "single_question" or result.get("questions") != count
                            or result.get("requests") != count or result.get("questions_answered", 0) + result.get("errors", 0) != count
                            or result.get("records") != expected["records"] or method.get("limit_records") != 0
                            or method.get("concurrency") != 1 or method.get("warmup_requests") != 2
                            or method.get("calibration") != "top_label_ece_10_equal_width_bins"
                            or result.get("provenance", {}).get("input_sha256") != expected["sha256"]):
                        raise ValueError(f"Single-question method/input/denominator mismatch: {summary_path}")
                    rows_path = summary_path.with_name("rows.jsonl")
                    if hashlib.sha256(rows_path.read_bytes()).hexdigest() != result["provenance"].get("rows_sha256"):
                        raise ValueError(f"Single-question raw-output hash mismatch: {summary_path}")
                    calibration = result["calibration"]
                    if (calibration["n"] != result["questions_answered"] or result["latency_ms"]["n"] != calibration["n"]
                            or not math.isclose(result["accuracy"], result["questions_correct"] / count)
                            or not math.isclose(calibration["coverage"], calibration["n"] / count)):
                        raise ValueError(f"Single-question metric denominator mismatch: {summary_path}")
                    cells = [f"{result['accuracy']:.1%}",
                             f"{result['latency_ms']['p50']:,.0f}" if calibration["n"] else "无有效回答",
                             f"{calibration['ece']:.3f}" if calibration["n"] else "无有效回答",
                             f"{calibration['coverage']:.1%}"]
                    has_results = True
                lines.append(f"| {label} | {dataset_label}（{expected['questions']:,} 题） | " + " | ".join(cells) + " |")
        tables.append("\n".join(lines))
    return "\n\n".join(tables) if has_results else ""


def record_request_tables():
    from systemone_client import calibration_summary, score_answer

    sources = report_sources()
    tables = []
    for size in ("0.8B", "4B"):
        lines = [f"| 模型（{size}，骁龙 X Elite CPU，默认参数） | 测试集（题数） | 逐题准确率（%，含失败题） | 处理完整请求中位时间（秒，每次3道判断） | 校准误差 ECE（0–1，越低越好） | 有效概率覆盖率（%） |",
                 "|---|---|---|---|---|---|"]
        for model_size, model_id, label in INFERENCE_CONFIGURATIONS:
            if model_size != size:
                continue
            campaign = sources["round2_device_results" if model_id.startswith("r2c-") else "device_results"]
            for workload, dataset_label in (("support", "工单·同分布"), ("assistant", "助手·同分布")):
                run_path = campaign / model_id / workload
                raw_rows = [json.loads(line) for line in (run_path / "rows.jsonl").read_text(encoding="utf-8-sig").splitlines() if line.strip()]
                records = [json.loads(line) for line in (ROOT / f"data/contoso/final/test_{workload}.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
                if len(raw_rows) != len(records) or [row["i"] for row in raw_rows] != list(range(len(records))):
                    raise ValueError(f"Historical request coverage mismatch: {run_path}")
                scores, latencies = [], []
                total_questions = sum(len(record["questions"]) for record in records)
                for raw, record in zip(raw_rows, records):
                    if "error" in raw:
                        continue
                    if set(raw["questions"]) != set(record["questions"]):
                        raise ValueError(f"Historical question set mismatch: {run_path}")
                    latencies.append(raw["latency_ms"])
                    for question_id, question in record["questions"].items():
                        saved = raw["questions"][question_id]
                        if saved["label"] != question["label"]:
                            raise ValueError(f"Historical label mismatch: {run_path}/{raw['i']}/{question_id}")
                        answer = ({"noul": saved["p"]} if question["type"] == "noul" else
                                  {"choice": saved["pred"], "probabilities": saved["p"]})
                        score = score_answer(question, answer)
                        if score["pred"] != saved["pred"] or score["ok"] != saved["ok"]:
                            raise ValueError(f"Historical scoring mismatch: {run_path}/{raw['i']}/{question_id}")
                        scores.append(score)
                calibration = calibration_summary(scores)
                accuracy = sum(score["ok"] for score in scores) / total_questions
                if not latencies or calibration["ece"] is None:
                    raise ValueError(f"No usable historical measurements: {run_path}")
                lines.append(f"| {label} | {dataset_label}（{total_questions:,} 题） | {accuracy:.1%} | "
                             f"**{statistics.median(latencies) / 1000:.3f}** | {calibration['ece']:.3f} | "
                             f"{len(scores) / total_questions:.1%} |")
        tables.append("\n".join(lines))
    return "\n\n".join(tables)


def calibration_table():
    from calibration_boundary import analyse

    sources = report_sources()
    datasets = (("test_support", "工单·同分布"), ("test_assistant", "助手·同分布"),
                ("ood_support", "工单·分布外"), ("ood_assistant", "助手·分布外"))
    lines = ["| 模型与测试集（GPU / PyTorch） | 准确率（%，案例组95%区间） | ECE：当前温度（0–1，案例组95%区间） | 当前温度 T | 网格内最低 ECE（0–1，样本内） | 对应 T | 网格内 ECE 降幅（样本内） |",
             "|---|---|---|---|---|---|---|"]
    for size, recipe, label, source_name in (("0.8b", "ftcf", "0.8B FT-cf", "first_summary"),
                                           ("4b", "ftcf", "4B FT-cf", "first_summary"),
                                           ("0.8b", "r2-C", "0.8B 第二轮 C", "round2_summary")):
        runs = sources[source_name].parent.parent / "runs" / size
        for dataset, dataset_label in datasets:
            result = analyse(runs / f"{recipe}-{dataset}/rows.json", ROOT / f"data/contoso/final/{dataset}.jsonl")
            lower, upper = result["bootstrap_95_at_served"]["acc_95"]
            ece_lower, ece_upper = result["bootstrap_95_at_served"]["ece_95"]
            boundary = "（边界）" if result["temperature_search"]["best_at_grid_boundary"] else ""
            lines.append(f"| {label}，{dataset_label}（{result['rows']:,} 题） | "
                         f"{result['accuracy']:.1%}（{lower:.1%}–{upper:.1%}） | "
                         f"{result['at_served']['ece']:.3f}（{ece_lower:.3f}–{ece_upper:.3f}） | "
                         f"{result['served_T']:.2f} | {result['ece_at_best_T']:.3f} | "
                         f"{result['best_T_for_ece_in_sample']:.2f}{boundary} | {result['ece_decrease_on_grid']:.3f} |")
    return "\n".join(lines)


def saved_request_examples(language="zh"):
    samples = (("test_support", "订单询问：队列选择正确", "Order enquiry: correct queue"),
               ("test_assistant", "保修咨询：助手工具选择正确", "Warranty enquiry: correct assistant tool"),
               ("ood_support", "意外损坏：模型选错队列", "Accidental damage: incorrect queue"))
    sections = []
    for example_index, (dataset, chinese, english) in enumerate(samples, 1):
        relative = f"验证结果/单题接口验收_20261102-161257/{dataset}/rows.jsonl"
        row = json.loads((ROOT / relative).read_text(encoding="utf-8").splitlines()[0])
        question_id, scored = next(iter(row["questions"].items()))
        if row.get("status") != "ok" or len(row["request"]["questions"]) != 1:
            raise ValueError(f"Example is not a completed single-question request: {relative}")
        elapsed = row["latency_ms"] / 1000
        if language == "zh":
            sections += [f"#### 例 {example_index}：{chinese}", "",
                         f"题目 `{question_id}`；模型输出 `{scored['pred']}`，规则标签 `{scored['label']}`，"
                         f"判定：{'答对' if scored['ok'] else '答错'}。本次单题请求实测 **{elapsed:.3f} 秒**，不是中位数。"
                         f"[完整原始记录](../{relative})（第 1 条）。", ""]
            captions = ("实际输入（未发送标签）：", "实际输出（完整响应）：")
        else:
            sections += [f"#### Example {example_index}: {english}", "",
                         f"Question `{question_id}`; prediction `{scored['pred']}`, policy label `{scored['label']}`: "
                         f"{'correct' if scored['ok'] else 'incorrect'}. This single request took **{elapsed:.3f} seconds**, not a median. "
                         f"[Complete raw record](../{relative}) (first row).", ""]
            captions = ("Actual request (labels excluded):", "Actual output (complete response):")
        for offset, (caption, value) in enumerate(zip(captions, (row["request"], row["response"])), 1):
            block = "```json\n" + json.dumps(value, ensure_ascii=False, indent=2) + "\n```"
            if language == "en":
                fence_index = 2 * (example_index - 1) + offset
                block = f"<!-- SOURCE:FENCE:{fence_index} -->\n{block}\n<!-- /SOURCE:FENCE:{fence_index} -->"
            sections += [caption, "", block, ""]
    return "\n".join(sections).rstrip()


def overview_blocks():
    from markdown_it import MarkdownIt

    parser = MarkdownIt("commonmark", {"html": True}).enable("table")
    detail = (ROOT / "文档/评测与端侧结果全集.md").read_text(encoding="utf-8")

    def tables_after(heading):
        text = detail[detail.index(heading):]
        lines = text.splitlines(keepends=True)
        return ["".join(lines[token.map[0]:token.map[1]]).strip()
                for token in parser.parse(text) if token.type == "table_open"]

    def rows(table):
        result = []
        for token in parser.parse(table):
            if token.type == "tr_open":
                result.append([])
            elif token.type == "inline":
                result[-1].append(token.content)
        return result

    sources = report_sources()
    first = json.loads(sources["first_summary"].read_text(encoding="utf-8"))
    second = json.loads(sources["round2_summary"].read_text(encoding="utf-8"))
    datasets = (("test_support", "工单·同分布"), ("test_assistant", "助手·同分布"),
                ("ood_support", "工单·分布外"), ("ood_assistant", "助手·分布外"))
    accuracy = ["| 参数规模 | 测试集（题数） | GPU 准确率：发布版 | GPU 准确率：FT-cf<br>业务样本 3,832 条，训练 2 遍 | GPU 准确率：C<br>业务样本 4,038 条，训练 4 遍 | 最终方案相对发布版提升（百分点） |",
                "|---|---|---|---|---|---|"]
    for size in ("0.8b", "4b"):
        for dataset, label in datasets:
            entry = first["sets"][f"{size}/{dataset}"]
            baseline, tuned = entry["b0"], entry["ftcf"]
            final = second["sets"][dataset]["questions"]["r2-C"] if size == "0.8b" else tuned
            if not baseline["n"] == tuned["n"] == final["n"]:
                raise ValueError(f"Overview question-count mismatch: {size}/{dataset}")
            counts = []
            for result in (baseline, tuned, final):
                correct = round(result["n"] * result["acc"])
                if abs(correct / result["n"] - result["acc"]) > 1e-12:
                    raise ValueError(f"Overview accuracy has no matching integer count: {size}/{dataset}")
                counts.append(correct)
            gain = (counts[2] - counts[0]) / final["n"] * 100
            final_cell = f"**{final['acc']:.1%}**" if size == "0.8b" else "未做"
            accuracy.append(f"| {size.upper()} | {label}（{final['n']:,} 题） | {baseline['acc']:.1%} | {tuned['acc']:.1%} | {final_cell} | +{gain:.1f} |")

    precision = tables_after("#### 从原始模型到量化微调模型")[:2]
    for table in precision:
        if any("BF16 未量化" in row[0] for row in rows(table)[1:]):
            raise ValueError("GPU-only BF16 reference must not appear in the laptop inference tables")
    device = next(table for table in tables_after("#### 换到 x86-64 CPU")
                  if rows(table)[0][0].startswith("指标（骁龙"))
    values = {row[0]: row[2] for row in rows(device)[1:]}

    def field(prefix):
        return next(value for name, value in values.items() if name.startswith(prefix))

    def numeric(value):
        return re.findall(r"\d[\d,]*(?:\.\d+)?%?", value)

    support = numeric(field("工单准确率"))[0]
    assistant = numeric(field("助手准确率"))[0]
    parity = " / ".join(numeric(field("答案一致率"))[:2])
    latency = " / ".join(numeric(field("工单 / 助手请求耗时"))[:2])
    peak = numeric(field("峰值工作集"))[0]
    weight = numeric(field("模型文件"))[0]
    load = model_loading_seconds(sources["round2_device_results"] / "r2c-kev-0.8b-Q8_0-cpu/server.log")
    quantization = next(row[1] for row in rows(precision[0])[1:] if row[0] == "微调 FT-cf，Q8_0")
    precision[0] += f"\n| 第二轮 C，Q8_0（交付） | {quantization} | {weight} | {support} / {assistant} | {parity} | {latency} | {peak} | {load} |"
    return {"ACCURACY": "\n".join(accuracy), "INFERENCE": record_request_tables(),
            "LEGACY_INFERENCE": "\n\n".join(precision),
            "LEVERS": tables_after("#### 推理优化：测过哪些杠杆")[0],
            "HARDWARE": tables_after("### 6. 需要什么硬件")[0]}


def overview_for_readme():
    source = ROOT / "文档/评测与端侧结果全集.md"

    def rebase(match):
        parsed = urlsplit(match.group(1))
        if parsed.scheme or parsed.netloc:
            return match.group()
        target = (source.parent / unquote(parsed.path)).resolve() if parsed.path else source
        path = os.path.relpath(target, ROOT).replace("\\", "/")
        return "](" + urlunsplit(("", "", path, parsed.query, parsed.fragment)) + ")"

    return {name: re.sub(r"\]\(([^)]+)\)", rebase, text) for name, text in overview_blocks().items()
            if name in ("ACCURACY", "INFERENCE")}


def long_input_note(language="zh"):
    values = json.loads((ROOT / "验证结果/端侧引擎_x64长输入真题_20261101-224312/summary/long_numbers.json").read_text(encoding="utf-8"))
    records = values["scored"] + values["rejected"]
    correct, questions = values["long_acc_frac"].split("/")
    if language == "zh":
        return (f"- **边界必须一起看。** 数据是模拟的；{records} 条长历史工单中，{values['rejected']} 条超窗口被拒；"
                f"其余 {values['scored']} 条的 {questions} 道题仅答对 {correct} 道（{values['long_acc']}，不含被拒请求）。"
                "这组长输入只在 x86-64 测过，不能用上面的短输入成绩替代。"
                "[长输入原题与结果](文档/评测与端侧结果全集.md#long-real)")
    return (f"- **Keep the limits with the headline.** Data is simulated. Of {records} long-history records, "
            f"{values['rejected']} exceed the context window and are rejected. On the remaining {values['scored']} records, "
            f"C answers {correct}/{questions} questions correctly ({values['long_acc']}, excluding rejected requests). "
            "This test ran only on x86-64, and short-input accuracy cannot substitute for it. "
            "[Long-input cases and results](文档/Evaluation-Results.md#long-real)")


def validate_overview(text):
    for name, expected in overview_for_readme().items():
        expression = re.compile(rf"<!-- OVERVIEW:{name} -->\n(.*?)\n<!-- /OVERVIEW:{name} -->", re.S)
        matches = expression.findall(text)
        if matches != [expected]:
            raise ValueError(f"README overview differs from its saved source: {name}")
    if long_input_note() not in text:
        raise ValueError("README long-input denominator differs from its saved source")


def sync_overview():
    sync_model_loading_tables()
    for language, filename in (("zh", "文档/评测与端侧结果全集.md"), ("en", "文档/Evaluation-Results.md")):
        example_path = ROOT / filename
        example_text = example_path.read_text(encoding="utf-8")
        example_text, replacements = re.subn(r"<!-- REQUEST:EXAMPLES -->.*?<!-- /REQUEST:EXAMPLES -->",
                                             lambda _: "<!-- REQUEST:EXAMPLES -->\n" + saved_request_examples(language)
                                             + "\n<!-- /REQUEST:EXAMPLES -->", example_text, flags=re.S)
        if replacements != 1:
            raise ValueError(f"Missing or duplicated request examples marker: {filename}")
        example_path.write_text(example_text, encoding="utf-8")
    detail_path = ROOT / "文档/评测与端侧结果全集.md"
    detail = detail_path.read_text(encoding="utf-8")
    detail, replacements = re.subn(r"<!-- (?:SINGLE|RECORD):INFERENCE -->.*?<!-- /(?:SINGLE|RECORD):INFERENCE -->",
                                   lambda _: "<!-- RECORD:INFERENCE -->\n" + record_request_tables()
                                   + "\n<!-- /RECORD:INFERENCE -->", detail, flags=re.S)
    if replacements != 1:
        raise ValueError("Missing or duplicated recorded-request results marker")
    detail, replacements = re.subn(r"<!-- TABLE:CALIBRATION_DIAGNOSTIC -->.*?<!-- /TABLE:CALIBRATION_DIAGNOSTIC -->",
                                   lambda _: "<!-- TABLE:CALIBRATION_DIAGNOSTIC -->\n" + calibration_table()
                                   + "\n<!-- /TABLE:CALIBRATION_DIAGNOSTIC -->", detail, flags=re.S)
    if replacements != 1:
        raise ValueError("Missing or duplicated calibration diagnostic marker")
    detail_path.write_text(detail, encoding="utf-8")
    path = ROOT / "README_CN.md"
    text = path.read_text(encoding="utf-8")
    introduction = (
        "下面两表保留七个部署配置的真实骁龙记录。处理时间是模型已加载后，从发出一个完整工单或助手请求到收到答案的中位数，单位为秒；"
        "每次请求包含三道判断，不是模型加载时间，也不是独立一道分类的中位数，不能除以三换算。"
        "每个配置使用 llama.cpp b11935 CPU、默认参数、并发 1，测量 170 条工单和 159 条助手请求，排除加载与两次预热。"
        "准确率、处理时间和 ECE 都从各自同一轮骁龙记录重算；ECE 采用 10 个等宽置信度分箱，越接近 0 越好，"
        "不是 Microsoft-Decision-1 官网的百分制分数。独立单题全量评测仍未完成，不与本表混用。"
        "[计量单位、校准定义与单题补测边界](文档/评测与端侧结果全集.md#single-question)。"
    )
    text, replacements = re.subn(r"^下面两表(?:保留|只列).*$", lambda _: introduction, text, flags=re.M)
    if replacements != 1:
        raise ValueError("Missing or duplicated laptop inference introduction")
    recipe = (
        "发布版不做业务微调；FT-cf 用 3,832 条业务样本训练 2 遍，C 增加 206 条变体后用 4,038 条训练 4 遍。"
        "两者都额外混入 1,000 条 Kev 通用回放，从同一个发布版独立训练，不是接着第一轮模型续训。"
        "4B 没做 C，最终提升以 FT-cf 计；0.8B 以 C 计。提升从未取整的答对题数计算。"
    )
    text, replacements = re.subn(r"^发布版(?:不训练|不做业务微调).*$", lambda _: recipe, text, flags=re.M)
    if replacements != 1:
        raise ValueError("Missing or duplicated training recipe note")
    for name in ("LEVERS", "HARDWARE"):
        text = re.sub(rf"<!-- OVERVIEW:{name} -->.*?<!-- /OVERVIEW:{name} -->\n?", "", text, flags=re.S)
    for name, content in overview_for_readme().items():
        expression = re.compile(rf"<!-- OVERVIEW:{name} -->.*?<!-- /OVERVIEW:{name} -->", re.S)
        if len(expression.findall(text)) != 1:
            raise ValueError(f"Missing or duplicated overview marker: {name}")
        text = expression.sub(lambda _: f"<!-- OVERVIEW:{name} -->\n{content}\n<!-- /OVERVIEW:{name} -->", text)
    text, replacements = re.subn(r"^- \*\*边界必须一起看。\*\*.*$", lambda _: long_input_note(), text, flags=re.M)
    if replacements != 1:
        raise ValueError("Missing or duplicated long-input summary")
    validate_overview(text)
    path.write_text(text, encoding="utf-8")


def sync_english_documents():
    from markdown_it import MarkdownIt
    from fill_report_tables import localize_block

    sync_overview()
    pairs = tuple((ROOT / chinese, ROOT / english, tables, fences)
                  for chinese, english, tables, fences in DOCUMENT_PAIRS)
    names = {Path(chinese).name: Path(english).name for chinese, english, _, _ in DOCUMENT_PAIRS}
    names["[NOTES]_实验协议_20261027-124000.md"] = "Experiment-Protocol.md"
    parser = MarkdownIt("commonmark", {"html": True}).enable("table")
    results = []
    for source, target, expected_tables, expected_fences in pairs:
        source_text = source.read_text(encoding="utf-8")
        source_lines = source_text.splitlines(keepends=True)
        fragments = {"TABLE": [], "FENCE": []}
        for token in parser.parse(source_text):
            if token.type in ("table_open", "fence"):
                kind = "TABLE" if token.type == "table_open" else "FENCE"
                fragments[kind].append("".join(source_lines[token.map[0]:token.map[1]]).rstrip())
        if (len(fragments["TABLE"]), len(fragments["FENCE"])) != (expected_tables, expected_fences):
            raise ValueError(f"Source structure changed; review the bilingual mapping: {source.name}")
        text = target.read_text(encoding="utf-8")
        for kind, blocks in fragments.items():
            for index, block in enumerate(blocks, 1):
                opening = f"<!-- SOURCE:{kind}:{index} -->"
                closing = f"<!-- /SOURCE:{kind}:{index} -->"
                expression = re.compile(re.escape(opening) + r".*?" + re.escape(closing), re.S)
                if len(expression.findall(text)) != 1:
                    raise ValueError(f"Missing or duplicated bilingual source anchor: {target.name} {kind} {index}")
                content = localize_block(block) if kind == "TABLE" else block
                if kind == "TABLE":
                    def target_link(match):
                        parsed = urlsplit(match.group(1))
                        if parsed.scheme or parsed.netloc:
                            return match.group()
                        path = unquote(parsed.path)
                        filename = path.rsplit("/", 1)[-1]
                        if filename in names:
                            path = path[:-len(filename)] + names[filename]
                        return "](" + urlunsplit(("", "", path, parsed.query, parsed.fragment)) + ")"
                    content = re.sub(r"\]\(([^)]+)\)", target_link, content)
                text = expression.sub(lambda _: opening + "\n" + content + "\n" + closing, text)
        if target.name == "README.md":
            introduction = (
                "The two tables retain real Snapdragon measurements for all seven deployment configurations. Processing time is the median from sending a complete support or assistant request to receiving its answers after the model is loaded, in seconds. "
                "Each request contains three decisions. This is neither model-loading time nor the median for a standalone classification, and dividing it by three does not measure that latency. "
                "Each configuration uses llama.cpp b11935 CPU, default settings and concurrency 1, with 170 support and 159 assistant requests, excluding loading and two warm-ups. "
                "Accuracy, processing time and ECE are recalculated from each configuration's same recorded Snapdragon run. ECE uses 10 equal-width confidence bins and is better closer to 0; it is not the Microsoft-Decision-1 website's percentage-scale score. "
                "Full standalone single-question evaluation is still incomplete and is not mixed into this table. "
                "[Timing units, calibration and the single-question boundary](文档/Evaluation-Results.md#single-question)."
            )
            text, replacements = re.subn(r"^The two tables (?:retain|list).*$", lambda _: introduction, text, flags=re.M)
            if replacements != 1:
                raise ValueError("Missing or duplicated English laptop inference introduction")
            recipe = (
                "Released means no business fine-tuning. FT-cf uses 3,832 business records for 2 epochs; C adds 206 variants and uses 4,038 records for 4 epochs. "
                "Both also mix in 1,000 Kev replay records and train independently from the same released checkpoint; C does not continue from the FT-cf checkpoint. "
                "The 4B model has no C run, so its final gain uses FT-cf; 0.8B uses C. Gains are calculated from unrounded correct-answer counts."
            )
            text, replacements = re.subn(r"^Released means.*$", lambda _: recipe, text, flags=re.M)
            if replacements != 1:
                raise ValueError("Missing or duplicated English training recipe note")
            text, replacements = re.subn(r"^- \*\*Keep the limits with the headline\.\*\*.*$",
                                         lambda _: long_input_note("en"), text, flags=re.M)
            if replacements != 1:
                raise ValueError("Missing or duplicated English long-input summary")
        target.write_text(text, encoding="utf-8")
        parsed_target = parser.parse(text)
        if sum(token.type == "table_open" for token in parsed_target) != expected_tables:
            raise ValueError(f"Bilingual table count mismatch: {target.name}")
        original_code = [token.content for token in parser.parse(source_text) if token.type == "fence"]
        translated_code = [token.content for token in parsed_target if token.type == "fence"]
        if original_code != translated_code:
            raise ValueError(f"Bilingual code-block drift: {target.name}")
        results.append({"source": str(source.relative_to(ROOT)), "target": str(target.relative_to(ROOT)),
                        "tables": expected_tables, "code_blocks": expected_fences})
    return results


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if attributes.get("id"):
            self.ids.add(attributes["id"])
        for name in (("src",) if tag == "img" else ("href",) if tag == "a" else ()):
            if attributes.get(name):
                self.paths.append(attributes[name])


def preview_documents(only=None):
    from markdown_it import MarkdownIt

    sources = [ROOT / name for chinese, english, _, _ in DOCUMENT_PAIRS for name in (chinese, english)]
    sources += [ROOT / "文档" / "[NOTES]_实验协议_20261027-124000.md", ROOT / "文档" / "Experiment-Protocol.md"]
    pages = {}
    style = """*{box-sizing:border-box}body{margin:0;color:#1f2328;background:#fff;font:16px/1.7 'Segoe UI','Microsoft YaHei',sans-serif;letter-spacing:0}
main{max-width:980px;margin:0 auto;padding:32px 32px 80px;overflow-wrap:break-word}h1{font-size:30px;line-height:1.35;margin:0 0 20px}
h2{font-size:25px;border-bottom:2px solid #0078d4;padding-bottom:9px;margin-top:44px}h3{font-size:21px;margin-top:32px}
h4{font-size:17px;margin-top:24px}a{color:#0969da;text-underline-offset:3px}img{max-width:100%;height:auto}blockquote{border-left:3px solid #d1d9e0;margin:20px 0;padding-left:16px;color:#59636e}
pre{background:#f6f8fa;padding:16px;overflow-x:auto;border-radius:5px;font-size:13px;line-height:1.55}code{font-family:Consolas,monospace}
:not(pre)>code{background:#eff1f3;padding:2px 4px;border-radius:3px;overflow-wrap:anywhere}.table-scroll{overflow-x:auto;margin:18px 0;max-width:100%}
table{border-collapse:collapse;font-size:14px;width:100%;line-height:1.6}th,td{border:1px solid #d1d9e0;padding:10px 12px;min-width:76px;vertical-align:top;overflow-wrap:break-word}
th{background:#edf3f8;text-align:left;font-weight:600}tr:nth-child(even){background:#f8fafc}li{margin:7px 0}.figure-scroll{max-width:100%;overflow-x:auto;margin:18px 0}.figure-scroll img{display:block;margin:auto}p:has(>em:only-child){font-size:14px;color:#536471}
@media(max-width:600px){main{padding:20px 16px 48px}h1{font-size:26px}h2{font-size:23px}table{min-width:600px}th,td{padding:8px 10px}.figure-scroll img{max-width:none;min-width:760px;width:760px}}
"""
    for source in sources:
        parser = MarkdownIt("commonmark", {"html": True}).enable("table")
        tokens = parser.parse(source.read_text(encoding="utf-8"))
        slugs = {}
        opening = source.name in ("README.md", "README_CN.md")
        for index, token in enumerate(tokens):
            if opening and token.type == "heading_open" and token.tag == "h3":
                token.attrSet("class", "readme-first-section")
                opening = False
            elif opening and token.type in ("heading_open", "paragraph_open", "blockquote_open"):
                token.attrSet("class", "readme-opening")
            if token.type == "html_block" and token.content.lstrip().startswith("<img "):
                token.content = '<div class="figure-scroll">' + token.content + '</div>\n'
            if token.type == "heading_open":
                heading = tokens[index + 1].content
                slug = re.sub(r"[^\w\s-]", "", heading.lower()).replace(" ", "-")
                occurrence = slugs.get(slug, 0)
                slugs[slug] = occurrence + 1
                token.attrSet("id", slug if not occurrence else f"{slug}-{occurrence}")
        parser.renderer.rules["table_open"] = lambda tokens, index, options, env: '<div class="table-scroll"><table>\n'
        parser.renderer.rules["table_close"] = lambda tokens, index, options, env: '</table></div>\n'
        body = parser.renderer.render(tokens, parser.options, {})
        references = References()
        references.feed(body)
        pages[source.resolve()] = (body, references, tokens, parser)
    checked = 0
    broken = []
    for source, (_, references, _, _) in pages.items():
        for reference in references.paths:
            parsed = urlsplit(reference)
            if parsed.scheme or parsed.netloc:
                continue
            target = (source.parent / unquote(parsed.path)).resolve() if parsed.path else source
            if not target.exists():
                broken.append(f"Broken local link in {source.name}: {reference}")
            if parsed.fragment and target in pages and unquote(parsed.fragment) not in pages[target][1].ids:
                broken.append(f"Broken anchor in {source.name}: {reference}")
            checked += 1
    if broken:
        raise ValueError("\n".join(broken))
    written = 0
    for source, (_, _, tokens, parser) in pages.items():
        if only is not None and source.name not in only:
            continue
        for token in tokens:
            for child in token.children or []:
                if child.type == "link_open":
                    parsed = urlsplit(child.attrGet("href") or "")
                    if not parsed.scheme and parsed.path:
                        target = (source.parent / unquote(parsed.path)).resolve()
                        if target in pages:
                            child.attrSet("href", urlunsplit(("", "", parsed.path[:-3] + ".preview.html", parsed.query, parsed.fragment)))
        body = parser.renderer.render(tokens, parser.options, {})
        destination = source.with_suffix(".preview.html")
        language = "zh-CN" if source.name == "README_CN.md" or re.search(r"[\u4e00-\u9fff]", source.stem) else "en"
        page_style = style
        if source.name in ("README.md", "README_CN.md"):
            page_style += "h1.readme-opening{margin-bottom:12px}p.readme-opening{margin:10px 0}blockquote.readme-opening{margin:12px 0}h2.readme-opening{margin-top:20px;margin-bottom:12px;padding-bottom:6px}h3.readme-first-section{margin-top:20px}\n"
        destination.write_text(f'<!doctype html><html lang="{language}"><meta charset="utf-8">'
                               '<meta name="viewport" content="width=device-width,initial-scale=1">'
                               f'<title>{html.escape(source.stem)}</title><style>{page_style}</style><main>{body}</main></html>', encoding="utf-8")
        written += 1
    return {"pages": written, "local_links_checked": checked}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, default=Path("C:/Windows/Fonts/msyh.ttc"))
    parser.add_argument("--out", type=Path, default=ROOT / "images")
    parser.add_argument("--preview", action="store_true", help="validate links and render ignored local HTML previews")
    parser.add_argument("--sync-english", action="store_true", help="fill English source-backed tables and unchanged code blocks")
    arguments = parser.parse_args()
    if not arguments.font.is_file():
        parser.error("Provide --font with a locally installed CJK TrueType/OpenType font")
    arguments.out.mkdir(parents=True, exist_ok=True)
    assets = []
    for name, factory, sources in (
        ("training", training, ["scripts/remote_pipeline_v2.sh", "scripts/remote_cf_round.sh", "scripts/remote_export_gguf.sh",
                    "https://github.com/jaredpalmer/kev/blob/2074cc44256200bb37540103fa4572901faa10f3/scripts/calibrate_checkpoint.py"]),
        ("inference", inference, ["scripts/systemone_client.py", "scripts/run_engine_eval.ps1",
                      "https://github.com/ggml-org/llama.cpp/blob/b11935/tools/server/server-decision.cpp"]),
        ("validation", validation, ["scripts/remote_pipeline_v2.sh", "scripts/run_engine_eval.ps1", "scripts/parity.py"]),
        ("decision", decision, ["https://github.com/jaredpalmer/kev/blob/2074cc44256200bb37540103fa4572901faa10f3/kev/model.py"]),
    ):
        for language in ("zh", "en"):
            suffix = "" if language == "zh" else "-en"
            asset = factory(arguments.font, language).save(arguments.out / f"{name}{suffix}.png")
            asset.update({"kind": "original explanatory diagram", "language": language, "sources": sources,
                          "proves": "how Kev scores options in one forward pass, as implemented in kev/model.py" if name == "decision"
                                   else "project workflow, execution placement and scoring boundaries",
                          "does_not_prove": "model accuracy or runtime success"})
            assets.append(asset)
    leaderboard = arguments.out / "kev-leaderboard.png"
    if leaderboard.is_file():
        with Image.open(leaderboard) as official:
            official.verify()
            dimensions = official.size
        assets.append({"file": leaderboard.name, "width": dimensions[0], "height": dimensions[1],
                       "sha256": hashlib.sha256(leaderboard.read_bytes()).hexdigest(),
                       "kind": "unchanged producer-published figure", "owner": "Jared Palmer / Kev",
                       "source": "https://raw.githubusercontent.com/jaredpalmer/kev/2074cc44256200bb37540103fa4572901faa10f3/docs/kev-family.png",
                       "license": "Apache-2.0", "crop": "none",
                       "proves": "producer-reported transfer-v4 development comparison at commit 2074cc44",
                       "does_not_prove": "this project's vendor-task accuracy, laptop latency, or universal model ranking"})
    ledger = {"generator": "scripts/render_diagrams.py", "font": arguments.font.name,
              "reference": "https://github.com/jaredpalmer/kev/blob/2074cc44256200bb37540103fa4572901faa10f3/README.md",
              "selection": "Upstream model/accuracy and playground figures do not describe this project's training, export and laptop validation paths.",
              "visual_scope": "Azure Architecture Center style: blue title bar, grey lanes, white component cards, legend and source footnote; "
                              "official Microsoft icons identify actual hosts and file artifacts, text badges identify PyTorch, Kev and llama.cpp, which have no ledgered icon; "
                              f"rendered at {SCALE}x the {WIDTH}x{HEIGHT} layout (training: {WIDTH}x728, with execution-location lanes).",
              "icon_sources": "vendor/sources.json",
              "assets": assets}
    (arguments.out / "provenance.json").write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    bilingual = sync_english_documents() if arguments.sync_english else None
    preview = preview_documents() if arguments.preview else None
    print(json.dumps({"status": "PASS", "assets": assets, "bilingual": bilingual, "preview": preview}, ensure_ascii=False))


if __name__ == "__main__":
    main()
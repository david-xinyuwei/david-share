"""Render bilingual architecture diagrams and document previews from local sources."""
import argparse
import hashlib
import html
import json
import math
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
INK = "#243746"
BLUE = "#0078D4"
GREY = "#D9E1E7"
MUTED = "#536471"
LANE_FILL = "#F3F5F7"
CARD_LINE = "#B8CEDF"
SCORE_GREY = "#687C8A"
READ = "#D83B01"   # Microsoft Office orange accent, used only for the pointer head's readout positions
WIDTH = 1200       # layout coordinates; the README displays every diagram at 900 px
HEIGHT = 680       # one shared height for the three diagrams
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

    def card(self, left, top, title, detail="", icon=None, badges=(), step=None, width=CARD_WIDTH, height=None, muted=False):
        """One component or artifact: white card, optional ledgered icon or step number, one or two detail lines, text badges."""
        lines = [line for line in detail.split("\n") if line]
        height = height or 56 + 22 * len(lines) + (28 if badges else 0)
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
            x = left + 50
        self.text((x, top + 11), title, self.node_font, left + width - x - 10, MUTED if muted else INK)
        for index, line in enumerate(lines):
            self.text((left + 14, top + 44 + 22 * index), line, self.detail_font, width - 24, MUTED)
        bx, by = left + 14, top + height - 32
        for badge in badges:
            bw = self.width_of(badge, self.badge_font) + 16
            self.draw.rounded_rectangle(self.box(bx, by, bx + bw, by + 20), radius=10 * self.s, fill="white", outline=MUTED, width=self.s)
            self.text((bx + 8, by + 2), badge, self.badge_font, bw, INK)
            bx += bw + 8
        return (left, top, left + width, top + height)

    def arrow(self, points, color=BLUE, head=True):
        scaled = [self.point(*point) for point in points]
        self.draw.line(scaled, fill=color, width=2 * self.s, joint="curve")
        if head:
            previous, end = scaled[-2:]
            angle = math.atan2(end[1] - previous[1], end[0] - previous[0])
            size = 10 * self.s
            triangle = [end] + [(end[0] - size * math.cos(angle + offset), end[1] - size * math.sin(angle + offset)) for offset in (-0.48, 0.48)]
            self.draw.polygon(triangle, fill=color)

    def legend(self, top, items):
        """items: (kind, label) with kind in lane | card | arrow | score | read | badge."""
        x = 28
        for kind, label in items:
            if kind == "lane":
                self.draw.rounded_rectangle(self.box(x, top + 3, x + 22, top + 17), radius=3 * self.s, fill=LANE_FILL, outline=GREY, width=self.s)
            elif kind == "card":
                self.draw.rounded_rectangle(self.box(x, top + 3, x + 22, top + 17), radius=3 * self.s, fill="white", outline=CARD_LINE, width=self.s)
            elif kind == "badge":
                self.draw.rounded_rectangle(self.box(x, top + 2, x + 22, top + 18), radius=8 * self.s, fill="white", outline=MUTED, width=self.s)
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
    label = lambda chinese, english: english if language == "en" else chinese
    d = Diagram(label("业务微调与模型导出", "Business fine-tuning and model export"),
                label("业务数据在笔记本准备，GPU 主机训练、校准并导出，GGUF 文件回到笔记本", "Business data is prepared on the laptop; the GPU host trains, calibrates and exports; the GGUF file returns to the laptop"), font_path)
    c1, c2, c3 = CARD_LEFT, CARD_LEFT + CARD_STEP, CARD_LEFT + 2 * CARD_STEP
    d.lane(104, 236, label("客户笔记本", "Customer laptop"), label("厂商所有\n数据准备", "Vendor-owned\nData preparation"), icon="laptop")
    d.card(c1, 116, label("业务训练集", "Training set"), label("标注样本 2,147 条\n+ 1,000 条 Kev 回放", "2,147 labeled records\n+ 1,000 Kev replay records"), icon="file")
    d.card(c2, 116, label("Kev 发布版", "Released Kev"), label("0.8B / 4B，开放权重\n已训练的 LoRA + 指针头", "0.8B / 4B, open weights\nTrained LoRA + pointer head"), icon="file")
    d.card(c3, 116, label("校准集", "Calibration set"), label("与训练样本分开\n只用于拟合温度", "Separate from training\nFits temperature only"), icon="file")
    d.lane(258, 418, label("Azure 训练主机", "Azure training host"), label("厂商租用\n1× H100 NVL", "Vendor-rented\n1× H100 NVL"), icon="azure-vm")
    d.card(c1, 274, label("监督微调", "Fine-tuning"), label("LoRA r16 + 指针头\nFT 与 FT-cf 独立训练", "LoRA r16 + pointer head\nIndependent FT and FT-cf"), step="1", badges=("PyTorch", "Kev"))
    d.card(c2, 274, label("温度校准", "Calibration"), label("固定全部权重\n只拟合温度 T", "All weights frozen\nFit temperature T only"), step="2", badges=("Kev",))
    d.card(c3, 274, label("CPU 导出", "CPU export"), label("合并 LoRA 进基座\nGGUF + 温度元数据", "Merge LoRA into the base\nGGUF + temperature metadata"), step="3", badges=("llama.cpp",))
    d.lane(440, 540, label("客户笔记本", "Customer laptop"), label("厂商所有\n端侧部署", "Vendor-owned\nDevice deployment"), icon="laptop")
    d.card(c3, 452, "GGUF", label("Q8_0 / Q4_K_M，温度在文件内", "Q8_0 / Q4_K_M, T inside the file"), icon="file", height=76)
    mid1, mid2, mid3 = c1 + CARD_WIDTH / 2, c2 + CARD_WIDTH / 2, c3 + CARD_WIDTH / 2
    d.arrow([(c1 + 80, 216), (c1 + 80, 274)])                                      # training set -> fine-tuning
    d.arrow([(mid2, 216), (mid2, 246), (c1 + 200, 246), (c1 + 200, 274)])          # released Kev -> fine-tuning (--init_from)
    d.arrow([(mid3, 216), (mid3, 246), (mid2, 246), (mid2, 274)])                  # calibration set -> calibration
    d.arrow([(c1 + CARD_WIDTH, 338), (c2, 338)])
    d.arrow([(c2 + CARD_WIDTH, 338), (c3, 338)])
    d.arrow([(mid3, 402), (mid3, 452)])                                            # export -> GGUF on the laptop
    d.legend(566, legend_items(label))
    d.footnote(598, label("原创解释图。依据：scripts/remote_pipeline_v2.sh、remote_cf_round.sh、remote_export_gguf.sh，以及 Kev commit 2074cc44 的 calibrate_checkpoint.py。",
                          "Original explanatory diagram. Sources: scripts/remote_pipeline_v2.sh, remote_cf_round.sh, remote_export_gguf.sh and calibrate_checkpoint.py at Kev commit 2074cc44."),
               label(*ICON_NOTE),
               label("微调、校准和 CPU 导出都在同一主机完成；端侧推理不会触发这些步骤。", "Fine-tuning, calibration and CPU export share one host; device inference does not run these stages."))
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


def sync_english_documents():
    from markdown_it import MarkdownIt
    from fill_report_tables import localize_block

    pairs = ((ROOT / "README_CN.md", ROOT / "README.md", 30, 22),
             (ROOT / "文档" / "微调与端侧验证报告_20261027-130700.md",
              ROOT / "文档" / "Finetuning-and-On-Device-Validation-Report.md", 20, 1))
    names = {"微调与端侧验证报告_20261027-130700.md": "Finetuning-and-On-Device-Validation-Report.md",
             "[NOTES]_实验协议_20261027-124000.md": "Experiment-Protocol.md", "README_CN.md": "README.md"}
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

    sources = [ROOT / "README.md", ROOT / "README_CN.md",
               ROOT / "文档" / "微调与端侧验证报告_20261027-130700.md",
               ROOT / "文档" / "Finetuning-and-On-Device-Validation-Report.md",
               ROOT / "文档" / "[NOTES]_实验协议_20261027-124000.md",
               ROOT / "文档" / "Experiment-Protocol.md"]
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
    for source, (_, references, _, _) in pages.items():
        for reference in references.paths:
            parsed = urlsplit(reference)
            if parsed.scheme or parsed.netloc:
                continue
            target = (source.parent / unquote(parsed.path)).resolve() if parsed.path else source
            if not target.exists():
                raise ValueError(f"Broken local link in {source.name}: {reference}")
            if parsed.fragment and target in pages and unquote(parsed.fragment) not in pages[target][1].ids:
                raise ValueError(f"Broken anchor in {source.name}: {reference}")
            checked += 1
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
              "visual_scope": "Azure Architecture Center style: blue title bar, grey ownership lanes, white component cards, legend and source footnote; "
                              "official Microsoft icons identify actual hosts and file artifacts, text badges identify PyTorch, Kev and llama.cpp, which have no ledgered icon; "
                              f"rendered at {SCALE}x the {WIDTH}x{HEIGHT} layout.",
              "icon_sources": "vendor/sources.json",
              "assets": assets}
    (arguments.out / "provenance.json").write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    bilingual = sync_english_documents() if arguments.sync_english else None
    preview = preview_documents() if arguments.preview else None
    print(json.dumps({"status": "PASS", "assets": assets, "bilingual": bilingual, "preview": preview}, ensure_ascii=False))


if __name__ == "__main__":
    main()
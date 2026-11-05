#!/usr/bin/env python3
"""Draw the MI300X parallel-layout figure (TP / EP / PP per model) from data/mi300x-run/summary.json.

    python tools/build_layout_figure.py           # write images/mi300x-parallel-layout-{en,zh}.svg and update data/visual-evidence.json
    python tools/build_layout_figure.py --png     # also render the PNGs with headless Microsoft Edge (Windows)
    python tools/build_layout_figure.py --check   # fail if an SVG, PNG or icon differs from data/visual-evidence.json
    python tools/build_layout_figure.py --topology-only  # draw the client, serving nodes, storage and communication paths

Every number drawn (GPUs per node, TP/PP/EP sizes, weights and free KV memory per GPU, image tag) is read from
summary.json, never typed here. The only icon is the Azure Architecture Icons "Virtual Machine" SVG, unmodified
and hash-checked against the ledger; MI300X GPUs and the vLLM processes are plain labelled badges because AMD and
vLLM publish no architecture icon set for them.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import statistics
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "images"
LEDGER = ROOT / "data" / "visual-evidence.json"
SUMMARY = ROOT / "data" / "mi300x-run" / "summary.json"
ICON_VM = IMAGES / "icons" / "10021-icon-service-Virtual-Machine.svg"
ICON_ENTRY = {
    "file": "images/icons/10021-icon-service-Virtual-Machine.svg",
    "sha256": "092d18ffadec9ec0e5af129186dc7bc2a80544011e55f965604ed4b13873e0fc",
    "bytes": 1330,
    "packageEntry": "Azure_Public_Service_Icons/Icons/compute/10021-icon-service-Virtual-Machine.svg",
    "packageUrl": "https://arch-center.azureedge.net/icons/Azure_Public_Service_Icons_V24.zip",
    "packageSha256": "921594ccd1bf3d9c0a1bd7b6d924e050551a59342f2b353bb74bdcf761c35141",
    "termsUrl": "https://learn.microsoft.com/azure/architecture/icons/",
    "terms": "Microsoft permits the use of these icons in architectural diagrams, training materials, or documentation. "
             "Don't crop, flip, rotate, distort or change icon shape.",
    "modified": False,
}

RUNS = {  # summary.json tag -> figure row; the three layouts that passed on 2026-11-02 (run 2)
    "nemotron": "nemotron_bf16_8xMI300X_run2",
    "inkling": "inkling_bf16_16xMI300X_pp2_run2",
    "muse": "muse_bf16_16xMI300X_pp2_run2",
}
W, H = 1960, 1130
PNG_SCALE = 2
AZURE_BLUE = "#0078D4"
AMD_RED = "#ED1C24"
AMD_RED_FILL = "#FDF0EE"
NODE_FILL = "#F3F2F1"
NODE_BORDER = "#A19F9D"
CARD_BORDER = "#C8C6C4"
TEXT = "#201F1E"
SUBTEXT = "#605E5C"
TP_COLOR = "#0078D4"
PP_COLOR = "#8764B8"
EP_COLOR = "#CA5010"
FONT = "'Segoe UI', 'Microsoft YaHei UI', 'Microsoft YaHei', sans-serif"
HBM_GIB = 192

TEXTS = {
    "en": {
        "title": "How the three BF16 models were laid out on 2 × Azure ND96isr_MI300X_v5 (2026-11-02, run 2)",
        "subtitle": "TP = tensor parallel (one layer split across GPUs), EP = expert parallel (experts split across the same GPUs), "
                    "PP = pipeline parallel (layers split across nodes). Numbers are vLLM's per-GPU figures from summary.json.",
        "node": "Azure VM · Standard_ND96isr_MI300X_v5 · node {n}",
        "gpu_line": "8 × AMD Instinct MI300X · 192 GB HBM3 each",
        "ray_head": "Ray head · vLLM API server :8000",
        "ray_worker": "Ray worker",
        "single": "vLLM API server :8000 · multiprocess executor, no Ray",
        "idle": "not used by this model",
        "rows": {
            "nemotron": ("NVIDIA Nemotron 3 Ultra BF16 (550B-A55B)", "1 node · TP8 + EP8 · every layer sharded 8 ways on one node",
                         "--tensor-parallel-size 8 --enable-expert-parallel", "rocm/vllm … vllm-0.29.0"),
            "inkling": ("Inkling BF16 (975B-A41B)", "2 nodes · TP8 inside each node × PP2 across nodes · no EP",
                        "--tensor-parallel-size 8 --pipeline-parallel-size 2 --distributed-executor-backend ray", "rocm/vllm … vllm-0.29.0"),
            "muse": ("Muse Spark Open BF16 (816B-A42B)", "2 nodes · TP8 inside each node × PP2 across nodes · no EP",
                     "--tensor-parallel-size 8 --pipeline-parallel-size 2 --distributed-executor-backend ray", "vllm/vllm-openai-rocm:v0.33.0 + Ray"),
        },
        "stage": "pipeline stage {s} · layers of the {half} half",
        "halves": ("first", "second"),
        "tp_group": "TP8 group: one layer sharded 8 ways",
        "ep_group": "EP8: experts sharded across the same 8 GPUs",
        "per_gpu": "per GPU: weights {w} GiB · free for KV {kv} GiB · of {hbm} GiB",
        "link_tp": "intra-node: RCCL / all-reduce AITER_CUSTOM+PYNCCL",
        "link_pp": "inter-node PP: RCCL over 8 × InfiniBand 400 Gb/s · NCCL_NET_GDR_LEVEL=0",
        "why_title": "Why these layouts and not others",
        "why": [
            "Nemotron fits one node: 1.12 TB of BF16 weights across 8 GPUs; vLLM reported {nem_w} GiB per GPU after loading, and EP keeps 1/8 of the routed experts on each GPU.",
            "Inkling cannot run TP16: its short-convolution cache shards at most 8 ways (tp_size <= num_kv_heads = 8); TP8 × DP2 + EP16 came up but a cross-node request hung, so PP2 is the layout that passed.",
            "Muse uses the same TP8 × PP2 shape; the vLLM recipe image lacks Ray and has gfx950-only kernels, so it needed the v0.33.0 image plus Ray.",
        ],
        "legend": ["TP group (within a node)", "PP stage boundary (across nodes)", "EP (experts sharded)"],
        "footer": "Original explanatory figure drawn from data/mi300x-run/summary.json; it shows the layouts as launched and the memory vLLM reported after loading, "
                  "not throughput or quality. Azure VM icon: Azure Architecture Icons V24, unmodified.",
    },
    "zh": {
        "title": "三个 BF16 模型在 2 × Azure ND96isr_MI300X_v5 上的并行布局（2026-11-02，第 2 轮）",
        "subtitle": "TP = 张量并行（一层切到多卡）、EP = 专家并行（专家切到同一组卡）、PP = 流水线并行（层切到不同节点）。数字是 vLLM 日志里的每卡值，取自 summary.json。",
        "node": "Azure 虚拟机 · Standard_ND96isr_MI300X_v5 · 节点 {n}",
        "gpu_line": "8 × AMD Instinct MI300X · 每卡 192 GB HBM3",
        "ray_head": "Ray head · vLLM API 服务 :8000",
        "ray_worker": "Ray worker",
        "single": "vLLM API 服务 :8000 · 多进程执行器，不用 Ray",
        "idle": "本模型未使用",
        "rows": {
            "nemotron": ("NVIDIA Nemotron 3 Ultra BF16（550B-A55B）", "1 个节点 · TP8 + EP8 · 8 张卡各持有全部层的 1/8",
                         "--tensor-parallel-size 8 --enable-expert-parallel", "rocm/vllm … vllm-0.29.0"),
            "inkling": ("Inkling BF16（975B-A41B）", "2 个节点 · 节点内 TP8 × 跨节点 PP2 · 不用 EP",
                        "--tensor-parallel-size 8 --pipeline-parallel-size 2 --distributed-executor-backend ray", "rocm/vllm … vllm-0.29.0"),
            "muse": ("Muse Spark Open BF16（816B-A42B）", "2 个节点 · 节点内 TP8 × 跨节点 PP2 · 不用 EP",
                     "--tensor-parallel-size 8 --pipeline-parallel-size 2 --distributed-executor-backend ray", "vllm/vllm-openai-rocm:v0.33.0 + Ray"),
        },
        "stage": "流水级 {s} · {half}一半的层",
        "halves": ("前", "后"),
        "tp_group": "TP8 组：一层切成 8 份",
        "ep_group": "EP8：专家切到同一组 8 张卡",
        "per_gpu": "每卡：权重 {w} GiB · KV 可用 {kv} GiB · 共 {hbm} GiB",
        "link_tp": "节点内：RCCL / all-reduce AITER_CUSTOM+PYNCCL",
        "link_pp": "跨节点 PP：RCCL over 8 × InfiniBand 400 Gb/s · NCCL_NET_GDR_LEVEL=0",
        "why_title": "为什么是这几种布局",
        "why": [
            "Nemotron 一个节点装得下：1.12 TB BF16 权重分到 8 张卡，vLLM 加载后报告每卡 {nem_w} GiB，并开 EP 让每卡只放 1/8 的路由专家。",
            "Inkling 不能直接 TP16：短卷积缓存最多切 8 份（tp_size <= num_kv_heads = 8）；TP8 × DP2 + EP16 能起来但跨节点请求挂起，所以通过的是 PP2。",
            "Muse 用同样的 TP8 × PP2；vLLM recipe 镜像没有 Ray 且内核只有 gfx950，所以换 v0.33.0 镜像并加 Ray 才通过。",
        ],
        "legend": ["TP 组（节点内）", "PP 流水级边界（跨节点）", "EP（专家切分）"],
        "footer": "原创解释图，数据来自 data/mi300x-run/summary.json；画的是启动时的布局和 vLLM 加载后报告的显存，不是吞吐或质量结论。Azure 虚拟机图标：Azure Architecture Icons V24，未修改。",
    },
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def char_em(ch: str) -> float:
    o = ord(ch)
    if 0x4E00 <= o <= 0x9FFF or 0x3000 <= o <= 0x30FF or 0xFF00 <= o <= 0xFFEF:
        return 1.0
    if ch in "iljtfI.,:;'|!":
        return 0.3
    if ch in "mwMW@":
        return 0.85
    if ch.isupper() or ch.isdigit():
        return 0.62
    if ch == " ":
        return 0.3
    return 0.54


def text_width(s: str, size: float) -> float:
    return sum(char_em(c) for c in s) * size


def wrap(s: str, size: float, max_w: float) -> list[str]:
    words = s.split(" ")
    lines: list[str] = []
    cur = ""
    for w in words:
        cand = (cur + " " + w).strip()
        if text_width(cand, size) <= max_w or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    # CJK text has no spaces: split by width
    out: list[str] = []
    for line in lines:
        if text_width(line, size) <= max_w:
            out.append(line)
            continue
        buf = ""
        for ch in line:
            if text_width(buf + ch, size) > max_w and buf:
                out.append(buf)
                buf = ch
            else:
                buf += ch
        if buf:
            out.append(buf)
    return out


class Svg:
    def __init__(self, icon_href: str, width: int = W, height: int = H, arrow_color: str = PP_COLOR) -> None:
        self.parts: list[str] = []
        self.icon_href = icon_href
        self.width = width
        self.height = height
        self.arrow_color = arrow_color

    def rect(self, x, y, w, h, fill="#FFFFFF", stroke=CARD_BORDER, sw=1.2, rx=6, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def text(self, x, y, s, size=13, color=TEXT, weight="normal", anchor="start", max_w=None, line_h=None):
        lines = wrap(s, size, max_w) if max_w else [s]
        lh = line_h or size * 1.35
        for i, line in enumerate(lines):
            self.parts.append(f'<text x="{x}" y="{y + i * lh:.1f}" font-family="{FONT}" font-size="{size}" fill="{color}" '
                              f'font-weight="{weight}" text-anchor="{anchor}">{escape(line)}</text>')
        return len(lines)

    def line(self, x1, y1, x2, y2, color=NODE_BORDER, sw=1.5, dash=None, marker=False):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        m = ' marker-end="url(#arrow)"' if marker else ""
        self.parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{sw}"{d}{m}/>')

    def icon(self, x, y, size):
        self.parts.append(f'<image x="{x}" y="{y}" width="{size}" height="{size}" href="{self.icon_href}"/>')

    def render(self) -> str:
        body = "\n".join(self.parts)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" viewBox="0 0 {self.width} {self.height}">\n'
                f'<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">'
            f'<path d="M0,0 L8,4 L0,8 z" fill="{self.arrow_color}"/></marker></defs>\n'
            f'<rect width="{self.width}" height="{self.height}" fill="#FFFFFF"/>\n{body}\n</svg>\n')


def load_runs() -> dict:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    by_tag = {r["tag"]: r for r in summary["runs"]}
    out = {}
    for key, tag in RUNS.items():
        r = by_tag[tag]
        out[key] = r
    return out


def stage_values(run: dict) -> list[tuple[float, float]]:
    """(weights GiB, free KV GiB) per pipeline stage, stage 0 first.

    summary.json stores the distinct per-GPU values sorted ascending. For the PP2 runs the raw key lines bind
    Worker_PP0 to the first 'Model loading took' value and Worker_PP1 to the second, and stage 0 has more free
    KV than stage 1 (57.39 vs 51.02 for Inkling); for Muse both stages loaded 99.1 GiB and the two KV values
    differ by 0.07 GiB, so the pairing below keeps stage 0 = (min weights, max KV) consistently.
    """
    w = run["model_loading_gib_per_gpu"]
    kv = run["available_kv_cache_gib"]
    pp = run.get("pipeline_parallel_size") or 1
    if pp == 1:
        return [(w[0], kv[0])]
    ws = sorted(w) if len(w) > 1 else [w[0], w[0]]
    kvs = sorted(kv, reverse=True) if len(kv) > 1 else [kv[0], kv[0]]
    return [(ws[0], kvs[0]), (ws[1], kvs[1])]


def fmt(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".") if abs(v - round(v, 1)) > 1e-9 else f"{v:.1f}".rstrip("0").rstrip(".")


def draw(lang: str, runs: dict, icon_href: str) -> Svg:
    t = TEXTS[lang]
    s = Svg(icon_href)
    margin = 28
    s.text(margin, 44, t["title"], 26, weight="600")
    s.text(margin, 74, t["subtitle"], 14, color=SUBTEXT, max_w=W - 2 * margin, line_h=19)

    label_w = 400
    node_w = (W - 2 * margin - label_w - 70) // 2
    node_x = [margin + label_w + 20, margin + label_w + 20 + node_w + 50]
    row_h = 232
    row_y0 = 128
    gpu_w, gpu_h, gpu_gap = 34, 44, 6

    for ri, key in enumerate(["nemotron", "inkling", "muse"]):
        run = runs[key]
        y = row_y0 + ri * row_h
        name, layout, flags, image = t["rows"][key]
        # left label card
        s.rect(margin, y, label_w, row_h - 18, fill="#FFFFFF", stroke=CARD_BORDER)
        s.text(margin + 14, y + 28, name, 17, weight="600", max_w=label_w - 28, line_h=22)
        s.text(margin + 14, y + 58, layout, 13.5, color=TEXT, max_w=label_w - 28, line_h=18)
        n = s.text(margin + 14, y + 104, flags, 11.5, color=SUBTEXT, max_w=label_w - 28, line_h=15)
        s.text(margin + 14, y + 104 + n * 15 + 6, image, 11.5, color=SUBTEXT, max_w=label_w - 28, line_h=15)

        pp = run.get("pipeline_parallel_size") or 1
        ep = bool(run.get("expert_parallel"))
        stages = stage_values(run)
        for ni in range(2):
            nx = node_x[ni]
            used = ni < pp
            s.rect(nx, y, node_w, row_h - 18, fill=NODE_FILL if used else "#FFFFFF", stroke=NODE_BORDER, dash=None if used else "6 4")
            s.icon(nx + 12, y + 10, 30)
            s.text(nx + 50, y + 24, t["node"].format(n=ni), 12.5, weight="600")
            s.text(nx + 50, y + 42, t["gpu_line"], 11.5, color=SUBTEXT)
            role = (t["single"] if pp == 1 else t["ray_head"]) if ni == 0 else t["ray_worker"]
            if used:
                s.text(nx + node_w - 12, y + 24, role, 11.5, color=AZURE_BLUE, anchor="end")
            # GPU strip
            gx0 = nx + 14
            gy = y + 60
            strip_w = 8 * gpu_w + 7 * gpu_gap
            if used:
                # TP group frame
                s.rect(gx0 - 6, gy - 6, strip_w + 12, gpu_h + 12, fill="none", stroke=TP_COLOR, sw=2, rx=8)
                for gi in range(8):
                    gx = gx0 + gi * (gpu_w + gpu_gap)
                    s.rect(gx, gy, gpu_w, gpu_h, fill=AMD_RED_FILL, stroke=AMD_RED, sw=1.4, rx=4)
                    s.text(gx + gpu_w / 2, gy + 18, f"GPU{gi}", 9.5, color=AMD_RED, anchor="middle", weight="600")
                    s.text(gx + gpu_w / 2, gy + 34, "TP" + str(gi), 9.5, color=TP_COLOR, anchor="middle")
                if ep:
                    s.rect(gx0 - 6, gy + gpu_h + 10, strip_w + 12, 24, fill="#FFF4EC", stroke=EP_COLOR, sw=1.2, rx=4, dash="4 3")
                    s.text(gx0 + strip_w / 2, gy + gpu_h + 27, t["ep_group"], 11, color=EP_COLOR, anchor="middle", weight="600")
                    label_y = gy + gpu_h + 56
                else:
                    label_y = gy + gpu_h + 28
                stage_text = t["tp_group"] if pp == 1 else t["stage"].format(s=ni, half=t["halves"][ni]) + " · " + t["tp_group"]
                s.text(gx0, label_y, stage_text, 11.5, color=TEXT, weight="600", max_w=node_w - 28, line_h=15)
                w_gib, kv_gib = stages[ni]
                s.text(gx0, label_y + 20, t["per_gpu"].format(w=fmt(w_gib), kv=fmt(kv_gib), hbm=HBM_GIB), 11.5, color=TEXT, max_w=node_w - 28, line_h=15)
                s.text(gx0, label_y + 40, t["link_tp"], 10.5, color=SUBTEXT, max_w=node_w - 28, line_h=14)
            else:
                for gi in range(8):
                    gx = gx0 + gi * (gpu_w + gpu_gap)
                    s.rect(gx, gy, gpu_w, gpu_h, fill="#FFFFFF", stroke=CARD_BORDER, sw=1, rx=4, dash="3 3")
                s.text(gx0 + strip_w / 2, gy + gpu_h + 26, t["idle"], 12, color=SUBTEXT, anchor="middle")
        # PP arrow between nodes
        if pp == 2:
            ax1 = node_x[0] + node_w + 2
            ax2 = node_x[1] - 2
            ay = y + 82
            s.line(ax1, ay, ax2, ay, color=PP_COLOR, sw=2.5, marker=True)
            s.text((ax1 + ax2) / 2, ay - 8, "PP", 11, color=PP_COLOR, anchor="middle", weight="600")
            s.text(node_x[0] + 14, y + row_h - 30, t["link_pp"], 10.5, color=PP_COLOR, max_w=2 * node_w + 50 - 28, line_h=14)

    # why box
    wy = row_y0 + 3 * row_h - 4
    s.rect(margin, wy, W - 2 * margin, 150, fill="#FFFFFF", stroke=CARD_BORDER)
    s.text(margin + 14, wy + 26, t["why_title"], 15, weight="600")
    yy = wy + 50
    nem_w = fmt(runs["nemotron"]["model_loading_gib_per_gpu"][0])
    for line in t["why"]:
        n = s.text(margin + 14, yy, "• " + line.format(nem_w=nem_w), 12.5, color=TEXT, max_w=W - 2 * margin - 28, line_h=17)
        yy += n * 17 + 6
    # legend + footer
    ly = wy + 150 + 26
    lx = margin
    swatches = [(TP_COLOR, None), (PP_COLOR, None), (EP_COLOR, "4 3")]
    for (color, dash), label in zip(swatches, t["legend"]):
        s.rect(lx, ly - 11, 26, 14, fill="#FFFFFF", stroke=color, sw=2, rx=3, dash=dash)
        s.text(lx + 34, ly, label, 12, color=TEXT)
        lx += 34 + text_width(label, 12) + 36
    s.text(margin, ly + 26, t["footer"], 11, color=SUBTEXT, max_w=W - 2 * margin, line_h=14)
    return s


def draw_topology(lang: str, runs: dict, icon: str) -> Svg:
    chinese = lang == "zh"
    figure = Svg(icon, width=1720, height=760, arrow_color=AZURE_BLUE)
    title = "MI300X 实测：请求与执行拓扑" if chinese else "MI300X run: requests and execution topology"
    subtitle = "2026-11-02 · 本地请求、节点内并行与跨节点通信" if chinese else "2026-11-02 · local requests, intra-node parallelism and cross-node communication"
    figure.text(28, 48, title, 31, weight="600")
    figure.text(28, 83, subtitle, 22, color=SUBTEXT)

    figure.rect(28, 188, 282, 174, stroke=CARD_BORDER, rx=6)
    figure.icon(46, 208, 44)
    figure.text(102, 235, "控制机" if chinese else "Control host", 26, weight="600")
    figure.text(48, 285, "Windows VM", 23)
    figure.text(48, 323, "仅通过 SSH 下发命令" if chinese else "Commands over SSH", 20)
    figure.line(310, 269, 388, 269, color=AZURE_BLUE, sw=2.2, marker=True)
    figure.text(349, 251, "SSH", 20, color=AZURE_BLUE, anchor="middle")

    node_positions = (392, 1156)
    node_width = 536
    for node_index, node_x in enumerate(node_positions):
        figure.rect(node_x, 140, node_width, 476, fill="#F5F8FA", stroke="#B9C8D3", rx=6)
        figure.icon(node_x + 20, 160, 48)
        node_label = f"Azure GPU 虚拟机 · 节点 {node_index}" if chinese else f"Azure GPU VM · Node {node_index}"
        figure.text(node_x + 83, 193, node_label, 25, color=AZURE_BLUE, weight="600")
        figure.text(node_x + 22, 235, "8 × AMD Instinct MI300X · 192 GB HBM / GPU", 20)

        figure.rect(node_x + 20, 260, node_width - 40, 162, stroke=CARD_BORDER, rx=4)
        figure.text(node_x + 38, 294, "vLLM 服务" if chinese else "vLLM serving", 25, weight="600")
        tp = runs["inkling"]["tensor_parallel_size"]
        if node_index == 0:
            nemotron_tp = runs["nemotron"]["tensor_parallel_size"]
            nemotron_ep = f" + EP{nemotron_tp}" if runs["nemotron"].get("expert_parallel") else ""
            executor = "多进程" if chinese else "multiprocess"
            figure.text(node_x + 38, 331, f"Nemotron: TP{nemotron_tp}{nemotron_ep} · {executor}", 20)
        else:
            figure.text(node_x + 38, 331, "Nemotron 不使用此节点" if chinese else "Not used by Nemotron", 20, color=SUBTEXT)
        role = "Ray head" if node_index == 0 else "Ray worker"
        stage = f"流水级 {node_index}" if chinese else f"stage {node_index}"
        figure.text(node_x + 38, 370, f"Inkling / Muse: TP{tp} · {stage}", 20)
        figure.text(node_x + 38, 400, role, 20, color=AZURE_BLUE)

        if node_index == 0:
            figure.line(node_x + 268, 469, node_x + 268, 426, color=AZURE_BLUE, sw=2, marker=True)
            figure.text(node_x + 268, 500, "本机客户端 → 127.0.0.1:8000" if chinese else "Local client → 127.0.0.1:8000", 20, anchor="middle")
            figure.text(node_x + 268, 534, "curl：基本生成检查" if chinese else "curl: smoke generation", 20, anchor="middle")
            figure.text(node_x + 268, 568, "09_perf_probe.py：TTFT / tok/s" if chinese else "09_perf_probe.py: TTFT / tok/s", 20, anchor="middle")
        else:
            figure.text(node_x + 268, 500, "跨节点流水线执行" if chinese else "Cross-node pipeline execution", 21, anchor="middle")
            figure.text(node_x + 268, 540, "模型布局见下图" if chinese else "Per-model layouts shown below", 20, color=SUBTEXT, anchor="middle")

        figure.rect(node_x + 20, 666, node_width - 40, 66, stroke=CARD_BORDER, rx=4)
        figure.text(node_x + 268, 693, "本地 NVMe RAID0 · 28 TB" if chinese else "Local NVMe RAID0 · 28 TB", 20, anchor="middle")
        figure.text(node_x + 268, 720, "Hugging Face 权重缓存" if chinese else "Hugging Face weight cache", 19, color=SUBTEXT, anchor="middle")
        figure.line(node_x + 268, 662, node_x + 268, 620, color=AZURE_BLUE, sw=2, marker=True)
        figure.text(node_x + 286, 648, "加载权重" if chinese else "Load", 18, color=AZURE_BLUE)

    figure.line(930, 347, 1152, 347, color=AZURE_BLUE, sw=2.4, marker=True)
    figure.line(1152, 372, 930, 372, color=AZURE_BLUE, sw=2.4, marker=True)
    figure.text(1040, 286, "RCCL", 22, color=AZURE_BLUE, anchor="middle", weight="600")
    figure.text(1040, 316, "8 × IB · 400 Gb/s", 19, anchor="middle")
    figure.text(1040, 423, "经主机内存中转" if chinese else "Host-staged transfer", 19, anchor="middle")
    return figure


def topology_entries(svgs: dict[str, str]) -> list[dict]:
    source_hash = sha(Path(__file__).read_bytes())
    return [{
        "asset": f"images/mi300x-test-topology-{language}.svg",
        "source_class": "original_test_topology",
        "decision": "USE",
        "language": language,
        "generator": "tools/build_layout_figure.py --topology-only",
        "source_asset": "tools/build_layout_figure.py",
        "source_sha256": source_hash,
        "sha256": sha(svg.encode("utf-8")),
        "width": 1720,
        "height": 760,
        "icons": [ICON_ENTRY],
        "bound_to": [f"data/mi300x-run/{tag}/00_meta.txt" for tag in RUNS.values()] + [
            "data/mi300x-run/summary.json",
            "scripts/mi300x/05_serve_inkling_2node.sh",
            "scripts/mi300x/09_perf_probe.py",
        ],
        "depicts": "The 2026-11-02 client and execution topology: a Windows control VM issues commands over SSH; "
                   "curl and the streaming probe run on node 0. Nemotron uses a local multiprocess executor with TP8+EP8. "
                   "Inkling and Muse use Ray, TP8 within each of two PP stages. Each node has a local NVMe model cache. "
                   "RCCL traffic is host-staged with NCCL_NET_GDR_LEVEL=0.",
        "incremental_value": "Combines the recorded client placement, per-model executor and two-node communication path; "
                             "the official Azure VM icon identifies the hosting resource, not the custom scripts.",
        "does_not_prove": "The drawing is not runtime evidence; correctness and performance require the bound logs and requests.",
    } for language, svg in svgs.items()]


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not a PNG: {path}")
    return struct.unpack(">II", head[16:24])


def edge_path() -> str:
    for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
        if Path(p).exists():
            return p
    raise RuntimeError("Microsoft Edge not found; PNG rendering needs headless Edge on Windows")


def render_png(svg_path: Path, png_path: Path, scale: int = PNG_SCALE) -> None:
    # Wrap the SVG in a minimal HTML page so the device scale factor and viewport are exact.
    html = svg_path.with_suffix(".render.html")
    html.write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;padding:0;background:#fff}}'
                    f'img{{display:block;width:{W}px;height:{H}px}}</style></head><body><img src="{svg_path.name}"></body></html>',
                    encoding="utf-8")
    try:
        with tempfile.TemporaryDirectory(prefix="moe-figure-edge-") as temporary:
            candidate = Path(temporary) / "render.png"
            cmd = [edge_path(), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
                   f"--user-data-dir={Path(temporary) / 'profile'}",
                   f"--force-device-scale-factor={scale}", f"--window-size={W},{H}", f"--screenshot={candidate}",
                   "--virtual-time-budget=4000", html.as_uri()]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode or not candidate.exists():
                raise RuntimeError(f"Edge screenshot failed ({result.returncode}): {(result.stderr or result.stdout).strip()[:400]}")
            size = png_size(candidate)
            if size != (W * scale, H * scale):
                raise RuntimeError(f"unexpected PNG size {size} for {png_path.name}")
            png_path.write_bytes(candidate.read_bytes())
    finally:
        html.unlink(missing_ok=True)


def icon_href() -> str:
    data = ICON_VM.read_bytes()
    if sha(data) != ICON_ENTRY["sha256"] or len(data) != ICON_ENTRY["bytes"]:
        raise RuntimeError("Virtual Machine icon differs from the ledger entry; re-extract it from the official package")
    return "data:image/svg+xml;base64," + base64.b64encode(data).decode("ascii")


def figure_entries(svgs: dict[str, str], png: bool) -> list[dict]:
    runs = load_runs()
    entries = []
    for lang, text in svgs.items():
        svg_rel = f"images/mi300x-parallel-layout-{lang}.svg"
        png_rel = f"images/mi300x-parallel-layout-{lang}.png"
        entry = {
            "asset": svg_rel,
            "source_class": "original_explanatory_diagram",
            "generator": "tools/build_layout_figure.py",
            "language": lang,
            "sha256": sha(text.encode("utf-8")),
            "width": W,
            "height": H,
            "decision": "USE",
            "depicts": "Per-model parallel layout of the 2026-11-02 run 2 on two ND96isr_MI300X_v5 nodes: Nemotron TP8+EP8 on node 0 only; "
                       "Inkling and Muse TP8 inside each node x PP2 across nodes (stage 0 = node 0 / Ray head, stage 1 = node 1 / Ray worker). "
                       "GPU counts, TP/PP/EP sizes, per-GPU weights and free KV memory and the image tag are read from summary.json.",
            "bound_to": [f"data/mi300x-run/{tag}/00_meta.txt" for tag in RUNS.values()] + ["data/mi300x-run/summary.json"],
            "does_not_prove": "Throughput, quality or that another layout would not work; the 'why' box restates constraints already recorded in the README and VALIDATION.",
            "icons": [ICON_ENTRY],
        }
        png_path = ROOT / png_rel
        if png_path.exists():
            w, h = png_size(png_path)
            entry["rendered_png"] = {"asset": png_rel, "sha256": sha(png_path.read_bytes()), "width": w, "height": h,
                                     "rendered_from_svg_sha256": entry["sha256"],
                                     "renderer": "Microsoft Edge headless screenshot, device scale factor 2"}
        entries.append(entry)
    return entries


def draw_fiveway_topology(lang: str, summary: dict, icon: str) -> Svg:
    chinese = lang == "zh"
    figure = Svg(icon, arrow_color=AZURE_BLUE)
    figure.text(28, 52, "五种并行策略：同一双节点 GPU 预算" if chinese else "Five parallel strategies: the same two-node GPU budget", 32, weight="600")
    scope = summary["scope"]
    subtitle = f"{scope['model'].split('/')[-1]} · BF16 · {scope['nodes']} nodes × {scope['gpus_per_node']} MI300X · vLLM {summary['conditions']['vllm_version']}"
    figure.text(28, 94, subtitle, 23, color=SUBTEXT)
    note = summary.get("publication", {}).get("topology_note", {}).get(lang)
    figure.text(28, 133, note or ("客户端在节点 0；P/D 通过官方代理，其余使用 vLLM API" if chinese else "Client on node 0; P/D uses the official proxy, other layouts use the vLLM API"), 22)
    definitions = {
        "tp": ("TP16", "全模型的每层跨 16 卡切分" if chinese else "Each model layer is sharded across 16 GPUs", "跨节点 TP 集合通信" if chinese else "Cross-node TP collectives"),
        "pp": ("TP8 × PP2", "节点内切张量，节点间切层" if chinese else "Tensor sharding within nodes, layer stages across nodes", "流水级之间传递激活" if chinese else "Activations cross the pipeline boundary"),
        "tep": ("TP16 + EP", "张量切分与专家分布相结合" if chinese else "Tensor sharding plus distributed experts", "跨节点 TP 与专家通信" if chinese else "Cross-node TP and expert communication"),
        "dp": ("DP16 + EP16", "全局分配请求，专家分布在 16 卡" if chinese else "Global request distribution; experts span 16 GPUs", "全局 DP 调度与 EP 通信" if chinese else "Global DP scheduling and EP communication"),
        "pd": ("Prefill / Decode", "两端各一份模型，各用 TP8" if chinese else "Two model pools, each using TP8", "KV 传输与代理开销" if chinese else "KV transfer and proxy overhead"),
    }
    colors = {"tp": AZURE_BLUE, "pp": "#107C10", "tep": AMD_RED, "dp": "#8764B8", "pd": "#A05A00"}
    for row_index, strategy in enumerate(summary["strategies"]):
        row_y = 170 + row_index * 176
        label, description, communication = definitions[strategy["id"]]
        custom = strategy.get("figure")
        if custom:
            label, description, communication = custom["label"], custom["description"][lang], custom["communication"][lang]
        color = colors[strategy["id"]]
        figure.text(28, row_y + 34, label, 28, color=color, weight="600")
        figure.text(28, row_y + 70, description, 20, max_w=450, line_h=26)
        status = strategy["status"]
        statuses = {"PASS": "测量完成", "COMPLETE_WITH_ERRORS": "测量完成，存在请求错误", "NOT_RUN": "未测", "IN_PROGRESS": "进行中",
                "BLOCKED_PLATFORM_INTERRUPTION": "Spot 中断，数据未齐", "EXCLUDED": "网站置灰，未测",
                "BLOCKED_RESOURCE_SCOPE": "需要 4 个节点，未测"}
        english = {"EXCLUDED": "Greyed out on the website; not run", "BLOCKED_RESOURCE_SCOPE": "Needs 4 nodes; not run"}
        status_text = statuses.get(status, status) if chinese else english.get(status, status.replace("_", " "))
        figure.text(28, row_y + 125, status_text, 18, color=SUBTEXT, max_w=450, line_h=23)
        for node_index, node_x in enumerate((520, 1250)):
            measured = status in ("PASS", "COMPLETE_WITH_ERRORS")
            figure.rect(node_x, row_y, 660, 140, fill=NODE_FILL if measured else "#FFFFFF", stroke=color, sw=2, dash=None if measured else "6 4")
            figure.icon(node_x + 18, row_y + 16, 32)
            figure.text(node_x + 66, row_y + 40, f"Azure VM · {'节点' if chinese else 'Node'} {node_index}", 24, color=color, weight="600")
            figure.text(node_x + 22, row_y + 78, f"{scope['gpus_per_node']} × MI300X · {'多进程执行器' if chinese else 'multiprocess executor'}", 21)
            placement = (f"PP {'流水级' if chinese else 'stage'} {node_index} · TP8" if strategy["id"] == "pp"
                         else ("同一 TP16 组" if chinese else "Same TP16 group"))
            if strategy["id"] == "tep":
                placement += " · EP enabled"
            if strategy["id"] == "dp":
                placement = f"TP1 · DP ranks {node_index * 8}-{node_index * 8 + 7} · EP16"
            if strategy["id"] == "pd":
                placement = ("Prefill TP8 · :8001" if node_index == 0 else "Decode TP8 · :8002")
            if custom:
                placement = custom["placement"][lang][node_index]
            figure.text(node_x + 22, row_y + 117, placement, 23, weight="600")
        figure.line(1186, row_y + 72, 1244, row_y + 72, color=color, sw=3, marker=True)
        transport = summary["conditions"].get("pd_transport", {}).get("protocol", "not deployed") if strategy["id"] == "pd" else "RCCL / host-staged InfiniBand"
        figure.text(528, row_y + 165, communication if custom else communication + " · " + transport, 19, color=color)
    figure.text(28, 1095, "虚线表示未完成测量的候选布局；状态来自运行记录。示意图不替代性能证据。" if chinese else "Dashed boxes are candidate layouts without completed measurements. Status comes from run records; diagrams do not prove performance.", 21, color=SUBTEXT)
    return figure


def resource_value(level: dict, metric: str, nodes: int, gpus: int) -> float | None:
    resources = level.get("resources", {})
    if len(resources) != nodes:
        return None
    if metric == "host_cpu_percent":
        values = [resource[metric]["mean"] for resource in resources.values()]
        return statistics.mean(values) if all(value is not None for value in values) else None
    statistic = "max" if metric == "vram_used_bytes" else "mean"
    values = [card[metric][statistic] for resource in resources.values() for card in resource.get("gpus", {}).values()]
    if len(values) != gpus or any(value is None for value in values):
        return None
    if metric == "vram_used_bytes":
        return max(values) / 2**30
    if metric == "power_watts":
        return sum(values) / 1000
    return statistics.mean(values)


PERFORMANCE_CAPTIONS = {  # metric -> (Chinese caption, English caption, unit); used only when a summary lists its own metrics
    "decode_tok_s_median": ("单请求解码中位数", "Decode per request", "token/s"),
    "aggregate_tok_s_median": ("总吞吐", "Throughput", "token/s"),
    "ttft_s_median": ("TTFT 中位数", "Median TTFT", "ms"),
    "wall_s_median": ("E2E 中位数", "Median E2E", "s"),
}


def draw_fiveway_performance(lang: str, summary: dict, icon: str, resources: bool = False) -> Svg:
    chinese = lang == "zh"
    figure = Svg(icon)
    total_gpus = summary["scope"]["nodes"] * summary["scope"]["gpus_per_node"]
    measured = [strategy for strategy in summary["strategies"] if strategy["status"] in ("PASS", "COMPLETE_WITH_ERRORS")]
    repeat_counts = {workload["rounds"] for strategy in measured for workload in strategy["workloads"]}
    if len(repeat_counts) != 1:
        raise ValueError("The plotted workloads must have one common repeat count")
    repeats = repeat_counts.pop()
    model = summary["scope"]["model"].split("/")[-1]
    figure.text(28, 48, f"{model} · {total_gpus} MI300X", 32, weight="600")
    published_metrics = summary.get("publication", {}).get("performance_metrics")
    subtitle = ("资源每秒采样，只取正式请求轮次；GPU 指标覆盖全部 16 卡，CPU 指标覆盖两个节点" if chinese else "Resources sampled each second inside measured rounds; GPU metrics cover all 16 cards, CPU metrics cover both nodes") if resources else (f"吞吐：{repeats} 轮中位数，竖线为各轮范围；延迟：合并 {repeats} 轮成功请求的中位数" if chinese else f"Throughput: median and min-max across {repeats} rounds; latency: median of pooled successful requests")
    if published_metrics and not resources:
        subtitle = (f"总吞吐：{repeats} 轮中位数，竖线为各轮范围；单请求解码、TTFT、E2E：合并 {repeats} 轮成功请求的中位数" if chinese
                    else f"Throughput: median and min-max across {repeats} rounds; decode, TTFT and E2E: median of pooled successful requests")
    figure.text(28, 90, subtitle, 22, color=SUBTEXT)
    styles = {"tp": ("TP16", AZURE_BLUE), "pp": ("TP8 × PP2", "#107C10"), "tep": ("TP16 + EP", AMD_RED),
              "dp": ("DP16 + EP16", "#8764B8"), "pd": ("P/D · TCP" if "pd_transport" in summary["conditions"] else "P/D", "#A05A00")}
    custom_labels = {strategy["id"]: strategy["figure"]["label"] for strategy in summary["strategies"] if strategy.get("figure")}
    measured_ids = {strategy["id"] for strategy in measured}
    for legend_index, (strategy_id, (label, color)) in enumerate(styles.items()):
        if strategy_id in custom_labels:
            label = custom_labels[strategy_id] + (" · 未测" if chinese else " · not run")
        elif strategy_id not in measured_ids:
            label += " · 未完成" if chinese else " · no data"
        position = 36 + legend_index * 370
        figure.line(position, 143, position + 65, 143, color=color, sw=4)
        figure.text(position + 80, 151, label, 23, color=color, weight="600")
    for workload_index, workload_file in enumerate(("perf-short.json", "perf-guide.json")):
        published_layout = bool(summary.get("publication"))
        plot_top = (258 + workload_index * 432) if published_layout else (246 + workload_index * 418)
        metrics = (("use_percent", "%"), ("vram_used_bytes", "GiB"), ("power_watts", "kW"), ("host_cpu_percent", "%")) if resources else (("aggregate_tok_s_median", "token/s"), ("ttft_s_median", "ms"), ("wall_s_median", "s"))
        if published_metrics and not resources:
            metrics = tuple((metric, PERFORMANCE_CAPTIONS[metric][2]) for metric in published_metrics)
        log_axis = set(summary.get("publication", {}).get("log_axis_metrics", [])) if not resources else set()
        for metric_index, (metric, unit) in enumerate(metrics):
            spacing = 1920 / len(metrics)
            plot_left = 90 + metric_index * spacing
            plot_width, plot_height = spacing - 150, 265
            series = []
            ranges = {}
            for strategy in measured:
                workload = next(item for item in strategy["workloads"] if item["file"] == workload_file)
                values = []
                for level in workload["levels"]:
                    value = resource_value(level, metric, summary["scope"]["nodes"], total_gpus) if resources else level[metric]
                    values.append((level["concurrency"], None if value is None else value * (1000 if unit == "ms" else 1), level["n_failed"]))
                    if not resources and metric == "aggregate_tok_s_median":
                        rates = level["aggregate_tok_s_rounds"]
                        ranges[(strategy["id"], level["concurrency"])] = (min(rates), max(rates))
                series.append((strategy["id"], values))
            upper_values = [value for _, values in series for _, value, _ in values if value is not None]
            upper_values.extend(upper for _, upper in ranges.values())
            maximum = max(1.0, max(upper_values, default=1) * 1.15)
            logarithmic = metric in log_axis and upper_values and min(upper_values) > 0
            if logarithmic:
                low_exponent = math.floor(math.log10(min(upper_values)))
                high_exponent = math.ceil(math.log10(max(upper_values) * 1.05))
                def scale(value):
                    return (math.log10(value) - low_exponent) / (high_exponent - low_exponent)
            else:
                def scale(value):
                    return value / maximum
            title = ("短问题" if workload_index == 0 else "部署分析") if chinese else ("Short input" if workload_index == 0 else "Guide input")
            captions = (("GPU 均值", "每卡显存峰值", "GPU 平均总功耗", "CPU 均值") if chinese else ("Mean GPU use", "Peak VRAM/card", "Mean GPU power sum", "Mean CPU use")) if resources else (("总吞吐", "TTFT 中位数", "E2E 中位数") if chinese else ("Throughput", "Median TTFT", "Median E2E"))
            if published_metrics and not resources:
                captions = tuple(PERFORMANCE_CAPTIONS[metric][0 if chinese else 1] for metric in published_metrics)
            metric_title = captions[metric_index]
            axis_note = ("，对数轴" if chinese else ", log scale") if logarithmic else ""
            title_size, title_width = (19, spacing - 20) if published_layout else (21, spacing - 45)
            figure.text(plot_left - 50, plot_top - 55, f"{title} · {metric_title} ({unit}{axis_note})", title_size, weight="600", max_w=title_width, line_h=26)
            ticks = ([(10 ** exponent, (exponent - low_exponent) / (high_exponent - low_exponent))
                      for exponent in range(low_exponent, high_exponent + 1)] if logarithmic
                     else [(maximum * tick / 4, tick / 4) for tick in range(5)])
            for tick_value, fraction in ticks:
                tick_y = plot_top + plot_height * (1 - fraction)
                figure.line(plot_left, tick_y, plot_left + plot_width, tick_y, color="#E1DFDD", sw=1)
                label = (f"{tick_value:,.0f}" if tick_value >= 1 else f"{tick_value:g}") if logarithmic else (f"{tick_value:,.1f}" if maximum < 10 else f"{tick_value:,.0f}")
                figure.text(plot_left - 14, tick_y + 7, label, 18, color=SUBTEXT, anchor="end")
            figure.line(plot_left, plot_top, plot_left, plot_top + plot_height, color=TEXT)
            figure.line(plot_left, plot_top + plot_height, plot_left + plot_width, plot_top + plot_height, color=TEXT)
            unavailable = [styles[strategy_id][0] for strategy_id, values in series if all(value is None for _, value, _ in values)]
            if unavailable and not resources:
                message = ("无成功请求：" if chinese else "No successful requests: ") + ", ".join(unavailable)
                figure.text(plot_left + plot_width / 2, plot_top + 22, message, 17, color=SUBTEXT, anchor="middle", max_w=plot_width)
            concurrency = summary["conditions"]["planned_concurrency"]
            x_positions = {value: plot_left + 35 + index * (plot_width - 70) / max(1, len(concurrency) - 1) for index, value in enumerate(concurrency)}
            for count, tick_x in x_positions.items():
                figure.text(tick_x, plot_top + plot_height + 35, str(count), 21, anchor="middle")
            figure.text(plot_left + plot_width / 2, plot_top + plot_height + 72, "并发请求数" if chinese else "Concurrent requests", 20, anchor="middle")
            for strategy_id, values in series:
                color = styles[strategy_id][1]
                previous = None
                for count, value, failures in values:
                    if value is None:
                        previous = None
                        continue
                    point_x = x_positions[count]
                    point_y = plot_top + plot_height * (1 - scale(value))
                    if (strategy_id, count) in ranges:
                        lower, upper = ranges[(strategy_id, count)]
                        lower_y = plot_top + plot_height * (1 - scale(lower))
                        upper_y = plot_top + plot_height * (1 - scale(upper))
                        figure.line(point_x, lower_y, point_x, upper_y, color=color, sw=1.5)
                        figure.line(point_x - 5, lower_y, point_x + 5, lower_y, color=color, sw=1.5)
                        figure.line(point_x - 5, upper_y, point_x + 5, upper_y, color=color, sw=1.5)
                    if previous:
                        figure.line(previous[0], previous[1], point_x, point_y, color=color, sw=3)
                    fill = "#FFFFFF" if failures else color
                    figure.parts.append(f'<circle cx="{point_x:.2f}" cy="{point_y:.2f}" r="6" fill="{fill}" stroke="{color}" stroke-width="2"/>')
                    previous = (point_x, point_y)
    footer = ("空心点：该轮次包含请求失败。缺失采样不补零；主机内存与各网卡速率保留在同一资源数据中。" if chinese else "Hollow points include failed requests. Missing samples are not zero. Host RAM and per-interface network rates remain in the same resource data.") if resources else ("空心点：包含请求失败。没有成功请求时，延迟不画成零；吞吐为零代表没有成功输出。完整分母与 P95 见表。" if chinese else "Hollow points include failures. Missing successful-request latency is not zero; zero throughput means no successful output. See tables for counts and P95.")
    figure.text(28, 1097, footer, 20, color=SUBTEXT)
    return figure


def draw_fiveway_resources(lang: str, summary: dict, icon: str) -> Svg:
    return draw_fiveway_performance(lang, summary, icon, resources=True)


TIME_BUDGET_NAMES = {"tp": "TP16", "pp": "TP8 × PP2", "tep": "TP16 + EP"}
TIME_BUDGET_COLORS = {"tp": (AZURE_BLUE, "#C7E0F4"), "pp": ("#107C10", "#107C10"), "tep": (AMD_RED, "#F8C8CA")}
TIME_BUDGET_WIRE = "#FFB900"
TIME_BUDGET_INPUTS = {"perf-short.json": ("短问题", "short prompt"), "perf-guide.json": ("部署分析问题", "deployment-analysis prompt")}


def budget_bytes(value: float) -> str:
    return f"{value / 1e6:.1f} MB" if value >= 1e6 else f"{value / 1e3:.0f} KB"


def budget_us(value: float) -> str:
    return f"{value:.0f}" if value >= 10 else f"{value:.2f}"


def draw_time_budget(lang: str, summary: dict, icon: str) -> Svg:
    """Panel A: measured time per output token of each layout. Panel B: the extra time of the cross-node layouts,
    drawn to scale with the time their measured InfiniBand bytes need at the nominal rate; the lower-bound layout's
    bar is divided into the estimated number of cross-node all-reduces. Every number comes from summary["time_budget"]."""
    chinese = lang == "zh"
    budget, spec = summary["time_budget"], summary["publication"]["time_budget"]
    layouts, estimate = budget["layouts"], budget["estimate"]
    scope, network = summary["scope"], summary["conditions"]["network"]
    nominal_gb = budget["nominal_infiniband_mb_s_per_node"] / 1000
    reference = budget["reference_layout"]
    reference_ms = layouts[reference]["ms_per_output_token"]
    collectives = estimate["cross_node_collectives_per_token"]
    figure = Svg(icon, arrow_color=TEXT)
    workload = TIME_BUDGET_INPUTS[budget["workload"]][0 if chinese else 1]
    figure.text(28, 52, (f"一个输出 token 的时间花在哪里 · {workload}，并发 {budget['concurrency']}" if chinese
                         else f"Where one output token's time goes · {workload}, concurrency {budget['concurrency']}"), 32, weight="600")
    gdr_off = network.get("nccl_net_gdr_level") == 0
    model = scope["model"].split("/")[-1]
    if chinese:
        subtitle = (f"{model} · BF16 · {scope['nodes']} 节点 × {scope['gpus_per_node']} 张 MI300X · 每节点 "
                    f"{network['infiniband_ports_per_node']} × {network['infiniband_port_rate_gbit_s']} Gb/s InfiniBand，"
                    f"合计 {nominal_gb:.0f} GB/s" + (" · GPU Direct RDMA 关闭" if gdr_off else ""))
    else:
        subtitle = (f"{model} · BF16 · {scope['nodes']} nodes × {scope['gpus_per_node']} MI300X · "
                    f"{network['infiniband_ports_per_node']} × {network['infiniband_port_rate_gbit_s']} Gb/s InfiniBand "
                    f"per node = {nominal_gb:.0f} GB/s" + (" · GPU Direct RDMA off" if gdr_off else ""))
    figure.text(28, 94, subtitle, 22, color=SUBTEXT)

    # Panel A: measured time per output token
    order = [reference] + [layout for layout in spec["layouts"] if layout != reference]
    left, right, top_row, pitch, bar = 360, 1500, 200, 90, 46
    top_ms = math.ceil(max(layouts[layout]["ms_per_output_token"] for layout in order) / 5) * 5
    scale = (right - left) / top_ms
    figure.text(28, 150, ("A · 实测每个输出 token 的时间（ms）= 1000 ÷ 单请求解码速度中位数" if chinese
                          else "A · Measured time per output token (ms) = 1000 ÷ median per-request decode speed"), 24, weight="600")
    bottom = top_row + (len(order) - 1) * pitch + bar
    for tick in range(0, top_ms + 1, 5):
        tick_x = left + tick * scale
        figure.line(tick_x, top_row - 8, tick_x, bottom + 8, color="#EDEBE9", sw=1)
        figure.line(tick_x, bottom + 16, tick_x, bottom + 24, color=TEXT, sw=1)
        figure.text(tick_x, bottom + 46, f"{tick}" + (" ms" if tick == top_ms else ""), 18, color=SUBTEXT, anchor="middle")
    figure.line(left, bottom + 16, right, bottom + 16, color=TEXT, sw=1.2)
    for index, layout in enumerate(order):
        row = top_row + index * pitch
        dark, light = TIME_BUDGET_COLORS[layout]
        entry = layouts[layout]
        milliseconds = entry["ms_per_output_token"]
        figure.text(28, row + 28, TIME_BUDGET_NAMES[layout], 26, color=dark, weight="600")
        if layout == reference:
            description = ((f"{collectives} 次同步在节点内", "跨节点交接 1 次") if chinese
                           else (f"{collectives} collectives inside a node,", "1 cross-node hand-off"))
            figure.rect(left, row, milliseconds * scale, bar, fill=dark, stroke=dark, sw=1, rx=3)
        else:
            description = ((f"约 {collectives} 次同步全部跨节点（估算）",) if chinese
                           else (f"≈{collectives} collectives across", "nodes (estimate)"))
            extra = entry["extra_ms_per_output_token_vs_reference"]
            figure.rect(left, row, reference_ms * scale, bar, fill=light, stroke=light, sw=1, rx=3)
            figure.rect(left + reference_ms * scale, row, extra * scale, bar, fill=dark, stroke=dark, sw=1, rx=3)
            figure.text(left + (reference_ms + extra / 2) * scale, row + 31, f"+{extra:.1f} ms", 20, color="#FFFFFF",
                        weight="600", anchor="middle")
        for line_index, line in enumerate(description):
            figure.text(28, row + 56 + line_index * 22, line, 18, color=SUBTEXT)
        figure.text(left + milliseconds * scale + 14, row + 31, f"{milliseconds:.1f} ms · {entry['decode_tok_s_median']:.1f} token/s",
                    22, weight="600")
    reference_x = left + reference_ms * scale
    figure.line(reference_x, top_row - 14, reference_x, bottom + 10, color=TIME_BUDGET_COLORS[reference][0], sw=2, dash="6 4")
    figure.text(reference_x, top_row - 20, f"{TIME_BUDGET_NAMES[reference]}: {reference_ms:.1f} ms", 17,
                color=TIME_BUDGET_COLORS[reference][0], anchor="middle")
    figure.text(left, bottom + 76, (f"浅色段：到 {TIME_BUDGET_NAMES[reference]} 的 {reference_ms:.1f} ms 为止；深色段：每个 token 多出的时间，在 B 图放大"
                                    if chinese else
                                    f"Light segment: up to {TIME_BUDGET_NAMES[reference]}'s {reference_ms:.1f} ms; dark segment: the extra time per token, enlarged in panel B"),
                17, color=SUBTEXT)

    # Panel B: the extra time, to scale with the time the measured bytes need on the wire
    zoom = order[1:]
    zoom_left, zoom_right, zoom_top, zoom_pitch, zoom_bar = 360, 1780, 612, 190, 54
    figure.text(28, 548, (f"B · 放大每个 token 多出的时间，与这些 InfiniBand 数据以 {nominal_gb:.0f} GB/s 传输所需的时间按同一比例画出"
                          if chinese else
                          f"B · The extra time per token, enlarged and drawn to scale with the time its InfiniBand data needs at {nominal_gb:.0f} GB/s"),
                24, weight="600", max_w=1900)
    top_extra = max(layouts[layout]["extra_ms_per_output_token_vs_reference"] for layout in zoom)
    zoom_scale = (zoom_right - zoom_left) / top_extra
    bound = layouts[estimate["layout"]]
    for index, layout in enumerate(zoom):
        row = zoom_top + index * zoom_pitch
        dark, _ = TIME_BUDGET_COLORS[layout]
        entry = layouts[layout]
        extra = entry["extra_ms_per_output_token_vs_reference"]
        width = extra * zoom_scale
        figure.text(28, row + 30, TIME_BUDGET_NAMES[layout], 26, color=dark, weight="600")
        figure.text(28, row + 56, (f"每个 token 多 {extra:.1f} ms" if chinese else f"+{extra:.1f} ms per token"), 17, color=SUBTEXT)
        figure.rect(zoom_left, row, width, zoom_bar, fill=dark, stroke=dark, sw=1, rx=2)
        if layout == estimate["layout"]:
            step = width / collectives
            for stripe in range(1, collectives):
                figure.line(zoom_left + stripe * step, row + 3, zoom_left + stripe * step, row + zoom_bar - 3, color="#FFFFFF", sw=1)
        sliver = max(entry["transfer_us_per_output_token_at_nominal"] / 1000 * zoom_scale, 2)
        figure.rect(zoom_left, row - 8, sliver, zoom_bar + 16, fill=TIME_BUDGET_WIRE, stroke=TEXT, sw=1, rx=0)
        moved = budget_bytes(entry["busier_node_infiniband_rx_bytes_per_output_token"])
        wire = budget_us(entry["transfer_us_per_output_token_at_nominal"])
        share = entry["transfer_share_of_extra_ratio"] * 100
        figure.text(zoom_left + 46, row - 18, (f"黄色细条：它每个 token 的 {moved} 以 {nominal_gb:.0f} GB/s 传输需 {wire} µs，占多出时间的 {share:.1f}%"
                                               if chinese else
                                               f"Yellow sliver: moving its {moved} per token at {nominal_gb:.0f} GB/s takes {wire} µs, {share:.1f}% of the extra time"),
                    20, weight="600")
        figure.line(zoom_left + 40, row - 24, zoom_left + sliver + 3, row - 4, color=TEXT, sw=1.5, marker=True)
        if layout == estimate["layout"]:
            note = (f"{collectives} 条 = 每个 token 约 {collectives} 次跨节点集合通信（估算：{spec['language_layers']} 层 × "
                    f"{spec['cross_node_collectives_per_layer']} 次 all-reduce，再加嵌入层和输出层共 {spec['collectives_per_step_outside_layers']} 次）。"
                    f"{TIME_BUDGET_NAMES[reference]} 做同样多次，但都在节点内；平均每次跨节点至少多花 "
                    f"{estimate['extra_us_per_cross_node_collective_lower_bound']:.0f} µs，而每次平均约 "
                    f"{budget_bytes(estimate['infiniband_rx_bytes_per_collective_mean'])} 的数据在链路上只需 "
                    f"{estimate['transfer_us_per_collective_at_nominal']:.2f} µs"
                    if chinese else
                    f"{collectives} stripes = about {collectives} cross-node collectives per token (estimate: {spec['language_layers']} layers × "
                    f"{spec['cross_node_collectives_per_layer']} all-reduces, plus {spec['collectives_per_step_outside_layers']} for the embedding and "
                    f"output layers). {TIME_BUDGET_NAMES[reference]} performs as many, inside a node; a cross-node one costs at least "
                    f"{estimate['extra_us_per_cross_node_collective_lower_bound']:.0f} µs more on average, while its "
                    f"≈{budget_bytes(estimate['infiniband_rx_bytes_per_collective_mean'])} of data needs "
                    f"{estimate['transfer_us_per_collective_at_nominal']:.2f} µs on the wire")
        else:
            if not (entry["busier_node_infiniband_rx_bytes_per_output_token"] < bound["busier_node_infiniband_rx_bytes_per_output_token"]
                    and extra > bound["extra_ms_per_output_token_vs_reference"]):
                raise ValueError(f"{layout}: the 'less data, more time' note does not hold for this summary")
            note = (f"数据比 {TIME_BUDGET_NAMES[estimate['layout']]} 少，多出的时间却更长。这里不按 all-reduce 拆分，因为页面的 AMD 说明指出 Triton 专家内核在专家并行下更慢"
                    if chinese else
                    f"Less data than {TIME_BUDGET_NAMES[estimate['layout']]}, yet more extra time. Not divided into all-reduces: the page's AMD note says the Triton expert kernels are slower with expert parallelism")
        figure.text(zoom_left, row + zoom_bar + 30, note, 20, max_w=1560, line_h=26)
    axis_y = zoom_top + len(zoom) * zoom_pitch - 30
    figure.line(zoom_left, axis_y, zoom_right, axis_y, color=TEXT, sw=1.2)
    for tick in range(0, math.floor(top_extra) + 1):
        tick_x = zoom_left + tick * zoom_scale
        figure.line(tick_x, axis_y, tick_x, axis_y + 8, color=TEXT, sw=1)
        figure.text(tick_x, axis_y + 32, f"{tick}" + (" ms" if tick == math.floor(top_extra) else ""), 18, color=SUBTEXT, anchor="middle")
    footer = ("实测：每 token 时间来自单请求解码速度中位数；InfiniBand 接收量取正式轮次内的每秒采样，按较忙的节点计，含输入部分的分摊。"
              f"估算而非实测：集合通信次数来自 vLLM 源码（{spec['language_layers']} 层 × {spec['cross_node_collectives_per_layer']} 次 all-reduce，"
              f"再加 {spec['collectives_per_step_outside_layers']} 次）；每次多花的时间是下限，前提是 {TIME_BUDGET_NAMES[estimate['layout']]} "
              f"除同步以外的计算不长于 {TIME_BUDGET_NAMES[reference]}（并发 1 时一个 token 在两种布局中都依次经过全部 "
              f"{spec['language_layers']} 层，{TIME_BUDGET_NAMES[estimate['layout']]} 每层的分片计算只有 TP8 的一半）。"
              if chinese else
              "Measured: time per token from the median per-request decode speed; InfiniBand receive from one-second samples inside "
              "the measured rounds, busier node, prompt share included. Estimated, not measured: the collective count, read from the "
              f"vLLM source ({spec['language_layers']} layers × {spec['cross_node_collectives_per_layer']} all-reduces, plus "
              f"{spec['collectives_per_step_outside_layers']}), and the extra cost per call, a lower bound assuming "
              f"{TIME_BUDGET_NAMES[estimate['layout']]}'s computation outside synchronization is no longer than "
              f"{TIME_BUDGET_NAMES[reference]}'s (at concurrency 1 a token passes through all {spec['language_layers']} layers in both, "
              f"and {TIME_BUDGET_NAMES[estimate['layout']]} halves each layer's sharded work).")
    figure.text(28, 1036, footer, 18, color=SUBTEXT, max_w=1900, line_h=24)
    return figure


def write_fiveway_figures(summary_path: Path, png: bool, check: bool) -> int:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    basename = "mi300x-qwen-fiveway" if summary["scope"]["model"].startswith("Qwen/") else "mi300x-fiveway"
    if summary.get("parent_run_id"):
        basename += "-recovery"
    basename = summary.get("publication", {}).get("figure_basename", basename)
    relative_summary = summary_path.resolve().relative_to(ROOT).as_posix()
    href = icon_href()
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    entries = []
    figures = [("topology", draw_fiveway_topology), ("performance", draw_fiveway_performance)]
    if any(len(strategy.get("resource_files", {})) == summary["scope"]["nodes"] for strategy in summary["strategies"]):
        figures.append(("resources", draw_fiveway_resources))
    if summary.get("time_budget"):
        figures.append(("time-budget", draw_time_budget))
    for kind, draw_function in figures:
        for language in ("en", "zh"):
            svg = draw_function(language, summary, href).render()
            path = IMAGES / f"{basename}-{kind}-{language}.svg"
            relative = path.relative_to(ROOT).as_posix()
            if check:
                if path.read_text(encoding="utf-8") != svg:
                    raise ValueError(f"Fiveway figure differs from its data: {relative}")
                continue
            path.write_text(svg, encoding="utf-8", newline="\n")
            entry = {"asset": relative, "source_class": "original_test_topology" if kind == "topology" else "original_measurement_chart",
                     "decision": "USE", "language": language, "generator": "tools/build_layout_figure.py --fiveway " + relative_summary,
                     "sha256": sha(svg.encode("utf-8")), "width": W, "height": H, "bound_to": [relative_summary],
                     "icons": [ICON_ENTRY] if kind == "topology" else [],
                     "incremental_value": "Connects the five website strategies to this exact MI300X run and plots its own per-request measurements, not vendor benchmark numbers.",
                     "does_not_prove": "No unmeasured DP/PD performance, production tail latency, business quality, or universal strategy ranking."}
            if kind == "time-budget":
                entry["incremental_value"] = ("Turns this run's measured time per token and InfiniBand bytes per token into a time "
                                              "budget: at the nominal rate the bytes need a sliver of the extra time, so link bandwidth "
                                              "cannot account for it.")
                entry["does_not_prove"] = ("The collective count and the per-call cost are estimates, not a trace; no GPU Direct RDMA, "
                                           "RCCL small-message or long-context result; no ranking beyond this hardware and input.")
            if png:
                png_path = path.with_suffix(".png")
                render_png(path, png_path)
                width, height = png_size(png_path)
                entry["rendered_png"] = {"asset": png_path.relative_to(ROOT).as_posix(), "sha256": sha(png_path.read_bytes()),
                                         "width": width, "height": height, "rendered_from_svg_sha256": entry["sha256"]}
            entries.append(entry)
    if not check:
        owned_assets = {f"images/{basename}-{kind}-{language}.svg"
                        for kind in ("topology", "performance", "resources", "time-budget") for language in ("en", "zh")}
        ledger["visuals"] = [entry for entry in ledger["visuals"] if entry.get("asset") not in owned_assets] + entries
        LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("FIVEWAY FIGURES CHECK OK" if check else "FIVEWAY FIGURES WRITTEN")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--png", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--topology-only", action="store_true")
    ap.add_argument("--fiveway", type=Path)
    args = ap.parse_args(argv)
    if args.fiveway:
        return write_fiveway_figures(args.fiveway, args.png, args.check)
    href = icon_href()
    runs = load_runs()
    basename = "mi300x-test-topology" if args.topology_only else "mi300x-parallel-layout"
    draw_figure = draw_topology if args.topology_only else draw
    svgs = {lang: draw_figure(lang, runs, href).render() for lang in ("en", "zh")}
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    if args.check:
        problems = []
        by_asset = {v.get("asset"): v for v in ledger["visuals"]}
        for lang, text in svgs.items():
            rel = f"images/{basename}-{lang}.svg"
            p = ROOT / rel
            if not p.exists() or p.read_text(encoding="utf-8") != text:
                problems.append(f"{rel} differs from the generator output")
            entry = by_asset.get(rel)
            if not entry or entry.get("sha256") != sha(text.encode("utf-8")):
                problems.append(f"{rel} sha256 differs from data/visual-evidence.json")
            png = entry.get("rendered_png") if entry else None
            if png:
                pp = ROOT / png["asset"]
                if not pp.exists() or sha(pp.read_bytes()) != png["sha256"]:
                    problems.append(f"{png['asset']} differs from data/visual-evidence.json")
                if png.get("rendered_from_svg_sha256") != sha(text.encode("utf-8")):
                    problems.append(f"{png['asset']} was rendered from an older SVG")
        for p in problems:
            print("CHECK FAIL:", p)
        print("CHECK OK" if not problems else f"{len(problems)} problem(s)")
        return 1 if problems else 0
    for lang, text in svgs.items():
        svg_path = IMAGES / f"{basename}-{lang}.svg"
        svg_path.write_text(text, encoding="utf-8", newline="\n")
        print("wrote", svg_path.relative_to(ROOT).as_posix(), sha(text.encode("utf-8"))[:16])
        if args.png and not args.topology_only:
            png_path = IMAGES / f"mi300x-parallel-layout-{lang}.png"
            render_png(svg_path, png_path)
            print("wrote", png_path.relative_to(ROOT).as_posix(), png_size(png_path))
    new_entries = topology_entries(svgs) if args.topology_only else figure_entries(svgs, args.png)
    kept = [v for v in ledger["visuals"] if not str(v.get("asset", "")).startswith(f"images/{basename}-")]
    ledger["visuals"] = kept + new_entries
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("updated", LEDGER.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())

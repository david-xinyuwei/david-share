#!/usr/bin/env python3
"""Draw the MI300X parallel-layout figure (TP / EP / PP per model) from data/mi300x-run/summary.json.

    python tools/build_layout_figure.py           # write images/mi300x-parallel-layout-{en,zh}.svg and update data/visual-evidence.json
    python tools/build_layout_figure.py --png     # also render the PNGs with headless Microsoft Edge (Windows)
    python tools/build_layout_figure.py --check   # fail if an SVG, PNG or icon differs from data/visual-evidence.json

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
import struct
import subprocess
import sys
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
    def __init__(self, icon_href: str) -> None:
        self.parts: list[str] = []
        self.icon_href = icon_href

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
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">\n'
                f'<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">'
                f'<path d="M0,0 L8,4 L0,8 z" fill="{PP_COLOR}"/></marker></defs>\n'
                f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>\n{body}\n</svg>\n')


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
        cmd = [edge_path(), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
               f"--force-device-scale-factor={scale}", f"--window-size={W},{H}", f"--screenshot={png_path}",
               "--virtual-time-budget=4000", html.as_uri()]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode or not png_path.exists():
            raise RuntimeError(f"Edge screenshot failed ({result.returncode}): {(result.stderr or result.stdout).strip()[:400]}")
        size = png_size(png_path)
        if size != (W * scale, H * scale):
            raise RuntimeError(f"unexpected PNG size {size} for {png_path.name}")
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--png", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    href = icon_href()
    runs = load_runs()
    svgs = {lang: draw(lang, runs, href).render() for lang in ("en", "zh")}
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    if args.check:
        problems = []
        by_asset = {v.get("asset"): v for v in ledger["visuals"]}
        for lang, text in svgs.items():
            rel = f"images/mi300x-parallel-layout-{lang}.svg"
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
        svg_path = IMAGES / f"mi300x-parallel-layout-{lang}.svg"
        svg_path.write_text(text, encoding="utf-8", newline="\n")
        print("wrote", svg_path.relative_to(ROOT).as_posix(), sha(text.encode("utf-8"))[:16])
        if args.png:
            png_path = IMAGES / f"mi300x-parallel-layout-{lang}.png"
            render_png(svg_path, png_path)
            print("wrote", png_path.relative_to(ROOT).as_posix(), png_size(png_path))
    new_entries = figure_entries(svgs, args.png)
    kept = [v for v in ledger["visuals"] if not str(v.get("asset", "")).startswith("images/mi300x-parallel-layout-")]
    ledger["visuals"] = kept + new_entries
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("updated", LEDGER.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())

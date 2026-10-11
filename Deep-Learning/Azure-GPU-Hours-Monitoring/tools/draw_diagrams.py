#!/usr/bin/env python3
"""Draw the README and VALIDATION figures in English and Chinese and keep their hashes in images/SOURCES.json.

    python tools/draw_diagrams.py            # redraw all figures (needs matplotlib and, for Chinese, a CJK font)
    python tools/draw_diagrams.py --check    # verify committed PNGs and chart data against the ledger (no drawing)

Every label is checked against the box it belongs to; a label that would overflow its box stops the build.
Charts are drawn from the committed evidence rows, never from hand-typed values.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "images"
LEDGER = IMAGES / "SOURCES.json"
# Azure portal screenshots of the deployed workbook: not drawn here, registered by hash with what they show.
SCREENSHOTS = {
    "workbook-summary.png": "Azure portal: workbook header and the summary view",
    "workbook-per-hour-day.png": "Azure portal: per_hour chart and per_day view",
    "workbook-trend-user.png": "Azure portal: per-minute SM Active chart and per_user view",
}
SCREENSHOT_NOTE = ("VM and Linux user names replaced with gpu-vm-1 and user-N; the screenshot predates the "
                   "operational panels, which tools/build_workbook.py added afterwards")
RUNS = ROOT / "evidence" / "runs"
CJK_FONTS = ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Zen Hei")
BLUE, DARK, GREEN, GREY, PURPLE, ORANGE, PINK, TEAL = ("#0078D4", "#1F3B5C", "#5E8C00", "#6B7280", "#6D5BD0",
                                                       "#B45309", "#DB2777", "#0F766E")

T = {
    "en": {
        "arch_title": "GPU-hours monitoring on Azure: data path",
        "vm": "GPU VM (each VM)", "azmon": "Azure Monitor (managed service)", "platform": "Your platform",
        "dcgm": ("NVIDIA DCGM host engine", "nvidia-dcgm.service", "SM, tensor, graphics, DRAM active;", "GPU util, memory, power, temperature"),
        "gpumon": ("gpumon collector", "vm/gpu_collector.py (systemd)", "dcgmi dmon every 10 s -> 1-minute", "average + process owners + AML run IDs"),
        "file": ("JSON lines on local disk", "/var/log/gpumon/gpu_metrics_<day>.json", "one line per GPU per minute"),
        "ama": ("Azure Monitor Agent", "VM extension, managed identity", "Custom JSON Logs data source", "sends Heartbeat every minute"),
        "dce": ("Data collection endpoint", "dce-gpu-hours-<workspace hash>"),
        "dcr": ("Data collection rule", "dcr-gpu-hours-<workspace hash>", "azure/dcr-rule.json -> GpuMetrics_CL"),
        "law": ("Log Analytics workspace", "GpuMetrics_CL + Heartbeat", "AzureActivity + AML job status"),
        "kql": ("Eight views in kql/", "VM / time / user,", "AML job / submitter / live"),
        "api": ("Log Analytics Query API", "REST or SDK, timespan = window", "identity: Log Analytics Reader"),
        "cli": ("Operators", "az monitor log-analytics query", "--analytics-query @kql/<view>.kql"),
        "a_dmon": "dcgmi dmon", "a_write": "append", "a_tail": "tail", "a_https": "HTTPS", "a_ingest": "ingest",
        "a_query": "query",
        "topo_title": "Test setup: what ran where",
        "t_vm": ("Measured VM (Spain Central)", "Standard_NC40ads_H100_v5, 1x NVIDIA H100 NVL", "Ubuntu 24.04.5, driver 615.71.09",
                 "DCGM 3.3.9, Azure Monitor Agent 1.45"),
        "t_load": ("Known load: tests/load/gpu_load.py", "validation-1: one user; replay-1: two users", "jobs-1: three AML jobs, one Linux user"),
        "t_gpumon": ("gpumon + Azure Monitor Agent", "10 s samples -> 1-minute rows"),
        "t_ws": ("Same region: DCE, DCR, workspace", "created by scripts/setup-workspace.sh"),
        "t_ops": ("Operator workstation", "Azure CLI: setup-workspace.sh,", "onboard-vm.sh (Run Command, no SSH)",
                  "az monitor log-analytics query", "examples/gpu_hours_client.py"),
        "t_m": ("Measurement points", "M1  GPU rows + Heartbeat minutes", "M2  AML submitter and status events",
                "M3  classic/job views vs. Python recomputation"),
        "a_setup": "ARM + Run Command", "a_rows": "rows", "a_q": "query API",
        "chart_title": "validation-1: how each GPU-minute of a known load is classified",
        "chart_x": "minute since the start of the window", "chart_y": "SM active (%)",
        "full": "full", "held": "held (process, no kernels)", "partial": "partial", "idle": "idle (VM on, no work)",
        "chart_note": "busy = held + partial + full; effective = sum of SM active; idle = allocated - busy",
        "owner_title": "replay-1: two owners on one GPU, each shared minute split 1/2",
        "owner_x": "minute since the start of the window", "owner_y": "GPU-minute share",
        "owner_a": "user-1 only", "owner_b": "user-2 only", "owner_ab": "shared (1/2 each)",
    },
    "cn": {
        "arch_title": "Azure 上的 GPU 卡时监控：数据链路",
        "vm": "GPU VM（每台）", "azmon": "Azure Monitor（托管服务）", "platform": "客户平台",
        "dcgm": ("NVIDIA DCGM host engine", "nvidia-dcgm.service", "SM、Tensor、图形引擎、显存带宽活跃度", "GPU Util、显存、功耗、温度"),
        "gpumon": ("gpumon 采集器", "vm/gpu_collector.py（systemd）", "dcgmi dmon 每 10 秒采样", "每分钟求平均，记录属主和 AML 作业 ID"),
        "file": ("本地磁盘上的 JSON 行", "/var/log/gpumon/gpu_metrics_<day>.json", "每张卡每分钟一行"),
        "ama": ("Azure Monitor Agent", "VM 扩展，托管身份", "Custom JSON Logs 数据源", "每分钟发送 Heartbeat"),
        "dce": ("数据收集终结点（DCE）", "dce-gpu-hours-<工作区 hash>"),
        "dcr": ("数据收集规则（DCR）", "dcr-gpu-hours-<工作区 hash>", "azure/dcr-rule.json -> GpuMetrics_CL"),
        "law": ("Log Analytics 工作区", "GpuMetrics_CL + Heartbeat", "AzureActivity + AML 作业状态"),
        "kql": ("kql/ 下的八个查询", "VM / 时间 / 用户", "AML 作业 / 提交人 / 实时"),
        "api": ("Log Analytics 查询 API", "REST 或 SDK，timespan = 统计时段", "身份：Log Analytics Reader"),
        "cli": ("运维人员", "az monitor log-analytics query", "--analytics-query @kql/<view>.kql"),
        "a_dmon": "dcgmi dmon", "a_write": "追加写", "a_tail": "读取", "a_https": "HTTPS", "a_ingest": "入库",
        "a_query": "查询",
        "topo_title": "测试环境：什么跑在哪里",
        "t_vm": ("被测 VM（Spain Central）", "Standard_NC40ads_H100_v5，1 张 NVIDIA H100 NVL", "Ubuntu 24.04.5，驱动 615.71.09",
                 "DCGM 3.3.9，Azure Monitor Agent 1.45"),
        "t_load": ("已知负载：tests/load/gpu_load.py", "validation-1：一个用户；replay-1：两个用户", "jobs-1：三个 AML 作业，一个 Linux 用户"),
        "t_gpumon": ("gpumon + Azure Monitor Agent", "10 秒采样 -> 每分钟一行"),
        "t_ws": ("同区域：DCE、DCR、工作区", "由 scripts/setup-workspace.sh 新建"),
        "t_ops": ("运维工作站", "Azure CLI：setup-workspace.sh、", "onboard-vm.sh（Run Command，无需 SSH）",
                  "az monitor log-analytics query", "examples/gpu_hours_client.py"),
        "t_m": ("测量点", "M1  GPU 数据 + Heartbeat 分钟数", "M2  AML 提交人与状态事件",
                "M3  经典/作业查询与 Python 重算"),
        "a_setup": "ARM + Run Command", "a_rows": "数据", "a_q": "查询 API",
        "chart_title": "validation-1：已知负载下每个 GPU·分钟怎么分类",
        "chart_x": "统计窗口内的第几分钟", "chart_y": "SM Active（%）",
        "full": "满载", "held": "占用（进程在，无计算）", "partial": "半载", "idle": "空闲（VM 开着，没人用）",
        "chart_note": "占用 = 占用 + 半载 + 满载；有效计算 = Σ SM Active；空闲 = 分配 − 占用",
        "owner_title": "replay-1：两个属主共用一张卡，重叠的分钟各记 1/2",
        "owner_x": "统计窗口内的第几分钟", "owner_y": "GPU·分钟份额",
        "owner_a": "仅 user-1", "owner_b": "仅 user-2", "owner_ab": "共用（各 1/2）",
    },
}


def _setup(lang: str):
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import font_manager, pyplot as plt
    if lang == "cn":
        names = {f.name for f in font_manager.fontManager.ttflist}
        chosen = next((f for f in CJK_FONTS if f in names), None)
        if chosen is None:
            raise SystemExit("NO_CJK_FONT: install one of " + ", ".join(CJK_FONTS))
        matplotlib.rcParams["font.family"] = [chosen, "DejaVu Sans"]
    else:
        matplotlib.rcParams["font.family"] = ["DejaVu Sans"]
    matplotlib.rcParams["svg.hashsalt"] = "fixed"
    return plt


class Board:
    """Boxes with fitted labels; `verify` fails when a label leaves its box."""

    def __init__(self, plt, w: float, h: float):
        self.fig, self.ax = plt.subplots(figsize=(w, h), dpi=150)
        self.ax.set_xlim(0, w)
        self.ax.set_ylim(0, h)
        self.ax.axis("off")
        self.fig.patch.set_facecolor("white")
        self.pairs = []

    def zone(self, x, y, w, h, title, fc, ec):
        from matplotlib.patches import FancyBboxPatch
        self.ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                         fc=fc, ec=ec, lw=1.1, ls="--"))
        t = self.ax.text(x + w / 2, y + h - 0.12, title, ha="center", va="top", fontsize=11, fontweight="bold", color=DARK)
        self.pairs.append(((x, y, w, h), t))

    def box(self, x, y, w, h, lines, ec, size=8.6):
        from matplotlib.patches import FancyBboxPatch
        self.ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                         fc="white", ec=ec, lw=1.5))
        title, *rest = lines
        t = self.ax.text(x + w / 2, y + h - 0.1, title, ha="center", va="top", fontsize=size + 1.4,
                         fontweight="bold", color=ec)
        self.pairs.append(((x, y, w, h), t))
        for i, line in enumerate(rest):
            t = self.ax.text(x + 0.12, y + h - 0.44 - i * 0.26, line, ha="left", va="top", fontsize=size, color="#111827")
            self.pairs.append(((x, y, w, h), t))
        return (x, y, w, h)

    def arrow(self, p, q, label="", color=GREY, dy=0.08):
        from matplotlib.patches import FancyArrowPatch
        self.ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=13, color=color, lw=1.5,
                                          shrinkA=1, shrinkB=1))
        if label:
            self.ax.text((p[0] + q[0]) / 2, (p[1] + q[1]) / 2 + dy, label, ha="center", va="bottom", fontsize=8,
                         color=color, bbox=dict(fc="white", ec="none", pad=0.6))

    def verify(self, name: str):
        self.fig.canvas.draw()
        renderer = self.fig.canvas.get_renderer()
        inv = self.ax.transData.inverted()
        bad = []
        for (x, y, w, h), t in self.pairs:
            bb = t.get_window_extent(renderer)
            (x0, y0), (x1, y1) = inv.transform((bb.x0, bb.y0)), inv.transform((bb.x1, bb.y1))
            if x0 < x - 0.01 or x1 > x + w + 0.01 or y0 < y - 0.01 or y1 > y + h + 0.01:
                bad.append(t.get_text())
        if bad:
            raise SystemExit(f"LABEL_OVERFLOW {name}: {bad}")

    def save(self, out: Path):
        self.fig.savefig(out, bbox_inches="tight", facecolor="white", metadata={"Software": None})


ARCH = {
    "en": {
        "title": "How GPU hours flow from each VM to where you read them",
        "lanes": ("On each GPU VM", "Azure Monitor (managed)", "Where you read them"),
        "dcgm": ("NVIDIA DCGM", "per-GPU SM, memory and power counters"),
        "gpumon": ("gpumon collector", "one row per GPU per minute,", "with process owner and AML job ID"),
        "ama": ("Azure Monitor Agent", "reads the local file and uploads it,", "sends a Heartbeat every minute"),
        "dce": ("Data collection endpoint", "receives the upload"),
        "dcr": ("Data collection rule", "writes the GpuMetrics_CL table"),
        "law": ("Log Analytics workspace", "GPU rows and Heartbeat,", "AML submitter and job status"),
        "wb": ("Workbook in the Azure portal", "GPU-hour tables and trends"),
        "api": ("Your platform", "Log Analytics query API", "with the eight views in kql/"),
        "cli": ("Operators", "az monitor log-analytics query"),
        "a1": "every 10 s", "a2": "local JSON file", "a3": "HTTPS", "a4": "ingest", "a5": "read-only query",
        "note": "Nothing custom runs outside the VMs: no database, no service and no UI to host.",
    },
    "cn": {
        "title": "GPU 卡时从每台 VM 到查看端的路径",
        "lanes": ("每台 GPU VM 上", "Azure Monitor（托管服务）", "在哪里看"),
        "dcgm": ("NVIDIA DCGM", "每张卡的 SM、显存、功耗计数器"),
        "gpumon": ("gpumon 采集器", "每张卡每分钟一行，", "带进程属主和 AML 作业 ID"),
        "ama": ("Azure Monitor Agent", "读取本地文件并上传，", "每分钟发送 Heartbeat"),
        "dce": ("数据收集终结点（DCE）", "接收上传的数据"),
        "dcr": ("数据收集规则（DCR）", "写入 GpuMetrics_CL 表"),
        "law": ("Log Analytics 工作区", "GPU 数据和 Heartbeat，", "AML 提交人和作业状态"),
        "wb": ("Azure 门户中的 Workbook", "卡时表格和趋势"),
        "api": ("客户平台", "Log Analytics 查询 API", "调用 kql/ 下的八个查询"),
        "cli": ("运维人员", "az monitor log-analytics query"),
        "a1": "每 10 秒采样", "a2": "本地 JSON 文件", "a3": "HTTPS", "a4": "入库", "a5": "只读查询",
        "note": "VM 之外不需要自建任何东西：没有数据库、没有服务、没有要托管的界面。",
    },
}


def architecture(lang: str, out: Path) -> None:
    """Data path as a U: down the VM, across to Azure Monitor, up to the workspace, across to the readers."""
    from matplotlib.lines import Line2D
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
    plt = _setup(lang)
    a = ARCH[lang]
    W, H = 15.6, 6.5
    b = Board(plt, W, H)
    ax = b.ax
    ax.text(W / 2, H - 0.28, a["title"], ha="center", va="center", fontsize=15, fontweight="bold", color=DARK)
    lane_x, lane_w, lane_y, lane_h = (0.2, 5.4, 10.6), 4.8, 0.8, 4.95
    styles = (("#EEF5FC", BLUE), ("#F3F1FC", PURPLE), ("#EEF8F1", TEAL))
    for x, (fc, ec), title in zip(lane_x, styles, a["lanes"]):
        ax.add_patch(FancyBboxPatch((x, lane_y), lane_w, lane_h, boxstyle="round,pad=0.02,rounding_size=0.2",
                                    fc=fc, ec="none"))
        tt = ax.text(x + lane_w / 2, lane_y + lane_h - 0.28, title, ha="center", va="center", fontsize=12,
                     fontweight="bold", color=ec)
        b.pairs.append(((x, lane_y, lane_w, lane_h), tt))

    cw, ch = 4.0, 1.12
    rows = (4.05, 2.55, 1.05)  # bottom of row 1 (top), 2, 3

    def card(lane, row, lines, ec):
        x, y = lane_x[lane] + (lane_w - cw) / 2, rows[row]
        ax.add_patch(FancyBboxPatch((x, y), cw, ch, boxstyle="round,pad=0.02,rounding_size=0.12", fc="white", ec=ec,
                                    lw=1.7))
        title, *rest = lines
        mid = y + ch / 2
        top = mid + 0.16 * len(rest)
        tt = ax.text(x + cw / 2, top, title, ha="center", va="center", fontsize=11, fontweight="bold", color=ec)
        b.pairs.append(((x, y, cw, ch), tt))
        for k, line in enumerate(rest):
            tt = ax.text(x + cw / 2, top - 0.31 * (k + 1), line, ha="center", va="center", fontsize=9, color="#374151")
            b.pairs.append(((x, y, cw, ch), tt))
        return x, y

    def arrow(p, q, color, label="", dx=0.0, dy=0.0):
        ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=15, color=color, lw=1.8, shrinkA=1, shrinkB=1))
        if label:
            ax.text((p[0] + q[0]) / 2 + dx, (p[1] + q[1]) / 2 + dy, label, ha="left" if dx else "center", va="center",
                    fontsize=8.6, color=color, bbox=dict(fc="white", ec="none", pad=1.0))

    dcgm = card(0, 0, a["dcgm"], GREEN)
    gpumon = card(0, 1, a["gpumon"], DARK)
    ama = card(0, 2, a["ama"], BLUE)
    dce = card(1, 2, a["dce"], PURPLE)
    dcr = card(1, 1, a["dcr"], PURPLE)
    law = card(1, 0, a["law"], BLUE)
    wb = card(2, 0, a["wb"], TEAL)
    api = card(2, 1, a["api"], GREEN)
    cli = card(2, 2, a["cli"], GREY)
    lx, mx = dcgm[0] + cw / 2, dce[0] + cw / 2
    arrow((lx, rows[0]), (lx, rows[1] + ch), DARK, a["a1"], dx=0.14)
    arrow((lx, rows[1]), (lx, rows[2] + ch), DARK, a["a2"], dx=0.14)
    arrow((ama[0] + cw, rows[2] + ch / 2), (dce[0], rows[2] + ch / 2), BLUE, a["a3"], dy=0.2)
    arrow((mx, rows[2] + ch), (mx, rows[1]), PURPLE)
    arrow((mx, rows[1] + ch), (mx, rows[0]), PURPLE, a["a4"], dx=0.14)
    # one read path from the workspace, fanned out to the three readers
    bus = wb[0] - 0.3
    y0, y2 = rows[0] + ch / 2, rows[2] + ch / 2
    ax.add_line(Line2D([law[0] + cw, bus], [y0, y0], color=TEAL, lw=1.8))
    ax.add_line(Line2D([bus, bus], [y0, y2], color=TEAL, lw=1.8))
    for r in range(3):
        y = rows[r] + ch / 2
        ax.add_patch(FancyArrowPatch((bus, y), (wb[0], y), arrowstyle="-|>", mutation_scale=15, color=TEAL, lw=1.8,
                                     shrinkA=0, shrinkB=1))
    ax.text((law[0] + cw + bus) / 2, y0 + 0.22, a["a5"], ha="center", va="center", fontsize=8.6, color=TEAL,
            bbox=dict(fc="white", ec="none", pad=1.0))
    tt = ax.text(W / 2, 0.38, a["note"], ha="center", va="center", fontsize=9.6, color="#4B5563")
    b.pairs.append(((0, 0, W, H), tt))
    b.verify(out.name)
    b.save(out)
    plt.close(b.fig)


def topology(lang: str, out: Path) -> None:
    plt = _setup(lang)
    t = T[lang]
    b = Board(plt, 15.6, 6.6)
    b.ax.text(7.8, 6.4, t["topo_title"], ha="center", va="center", fontsize=14, fontweight="bold", color=DARK)
    b.zone(0.15, 0.2, 7.0, 5.9, t["t_vm"][0], "#F3F8FD", "#9CC3E6")
    for i, line in enumerate(t["t_vm"][1:]):
        tt = b.ax.text(0.4, 5.55 - i * 0.28, line, ha="left", va="top", fontsize=9, color="#111827")
        b.pairs.append(((0.15, 0.2, 7.0, 5.9), tt))
    b.box(0.4, 2.55, 6.5, 1.35, t["t_load"], ORANGE)
    b.box(0.4, 0.5, 6.5, 1.05, t["t_gpumon"], BLUE)
    ws = b.box(7.6, 3.9, 3.6, 1.25, t["t_ws"], PURPLE, size=8.2)
    ops = b.box(12.0, 3.75, 3.45, 1.65, t["t_ops"], GREEN, size=8.2)
    b.box(7.9, 0.4, 7.55, 1.85, t["t_m"], DARK)
    b.arrow((3.65, 2.55), (3.65, 1.55), "", color=ORANGE)
    b.arrow((6.9, 1.2), (ws[0], 4.2), t["a_rows"], color=BLUE)
    # routed below the workspace box so neither the line nor its label crosses it
    b.arrow((ops[0], 3.85), (6.9, 3.1), t["a_setup"], color=GREY, dy=0.05)
    b.arrow((ops[0], 4.55), (ws[0] + ws[2], 4.55), t["a_q"], color=GREEN)
    b.verify(out.name)
    b.save(out)
    plt.close(b.fig)


def _rows(run: str) -> list[dict]:
    path = RUNS / run / "gpu-metrics.jsonl"
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _data_sha(*runs: str) -> str:
    h = hashlib.sha256()
    for run in runs:
        h.update((RUNS / run / "gpu-metrics.jsonl").read_bytes())
    return h.hexdigest()


def minutes_chart(lang: str, out: Path) -> None:
    sys.path.insert(0, str(ROOT / "tools"))
    from build_evidence import classify

    plt = _setup(lang)
    t = T[lang]
    rows = [r for r in _rows("validation-1") if 8 <= r["Minute"] <= 40]
    colors = {"full": TEAL, "held": PINK, "partial": "#F59E0B", "idle": "#CBD5E1"}
    fig, ax = plt.subplots(figsize=(11, 4.2), dpi=150)
    fig.patch.set_facecolor("white")
    seen = set()
    for r in rows:
        c = classify(r)
        ax.bar(r["Minute"], 100 * (r["SmActive"] or 0) if c != "idle" else 3, width=0.85, color=colors[c],
               label=t[c] if c not in seen else None)
        if c in ("held",):
            ax.bar(r["Minute"], 3, width=0.85, color=colors[c])
        seen.add(c)
    ax.set_xlabel(t["chart_x"])
    ax.set_ylabel(t["chart_y"])
    ax.set_ylim(0, 110)
    ax.set_title(t["chart_title"], fontsize=12, fontweight="bold", color=DARK)
    ax.legend(loc="upper right", fontsize=8.5, frameon=False)
    ax.text(0.01, -0.28, t["chart_note"], transform=ax.transAxes, fontsize=8.5, color=GREY)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.savefig(out, bbox_inches="tight", facecolor="white", metadata={"Software": None})
    plt.close(fig)


def owners_chart(lang: str, out: Path) -> None:
    plt = _setup(lang)
    t = T[lang]
    rows = [r for r in _rows("replay-1") if r["Users"]]
    fig, ax = plt.subplots(figsize=(11, 3.6), dpi=150)
    fig.patch.set_facecolor("white")
    seen = set()
    for r in rows:
        owners = r["Users"].split(",")
        if len(owners) == 1:
            key, color = ("owner_a", BLUE) if owners[0] == "user-1" else ("owner_b", ORANGE)
            ax.bar(r["Minute"], 1.0, width=0.85, color=color, label=t[key] if key not in seen else None)
        else:
            key = "owner_ab"
            ax.bar(r["Minute"], 0.5, width=0.85, color=BLUE, label=None)
            ax.bar(r["Minute"], 0.5, bottom=0.5, width=0.85, color=ORANGE, hatch="//", edgecolor="white",
                   label=t[key] if key not in seen else None)
        seen.add(key)
    ax.set_xlabel(t["owner_x"])
    ax.set_ylabel(t["owner_y"])
    ax.set_ylim(0, 1.25)
    ax.set_title(t["owner_title"], fontsize=12, fontweight="bold", color=DARK)
    ax.legend(loc="upper right", fontsize=8.5, frameon=False, ncol=3)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.savefig(out, bbox_inches="tight", facecolor="white", metadata={"Software": None})
    plt.close(fig)


FIGURES = {
    "architecture-en.png": (architecture, "en", None, "components and data path of the monitoring pipeline"),
    "architecture-cn.png": (architecture, "cn", None, "components and data path of the monitoring pipeline"),
    "test-topology-en.png": (topology, "en", None, "where the measured VM, the workspace and the operator ran"),
    "test-topology-cn.png": (topology, "cn", None, "where the measured VM, the workspace and the operator ran"),
    "gpu-minutes-en.png": (minutes_chart, "en", ("validation-1",), "per-minute class and SM active of validation-1"),
    "gpu-minutes-cn.png": (minutes_chart, "cn", ("validation-1",), "per-minute class and SM active of validation-1"),
    "owners-en.png": (owners_chart, "en", ("replay-1",), "per-minute owner shares of replay-1"),
    "owners-cn.png": (owners_chart, "cn", ("replay-1",), "per-minute owner shares of replay-1"),
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    if args.check:
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        bad = [i["file"] for i in ledger["images"]
               if not (IMAGES / i["file"]).is_file() or hashlib.sha256((IMAGES / i["file"]).read_bytes()).hexdigest() != i["sha256"]]
        if {i["file"] for i in ledger["images"]} != set(FIGURES) | set(SCREENSHOTS):
            bad.append("ledger/figure list mismatch")
        for i in ledger["images"]:
            runs = FIGURES.get(i["file"], (None, None, None))[2]
            if runs and i.get("data_sha256") != _data_sha(*runs):
                bad.append(f"{i['file']} (evidence rows changed; rerun tools/draw_diagrams.py)")
        if bad:
            print("IMAGE_LEDGER_MISMATCH " + ", ".join(bad))
            return 1
        print(f"PASS {len(ledger['images'])} images match images/SOURCES.json")
        return 0
    IMAGES.mkdir(exist_ok=True)
    items = []
    for name, (fn, lang, runs, shows) in FIGURES.items():
        out = IMAGES / name
        fn(lang, out)
        item = {"file": name, "language": lang, "generator": "tools/draw_diagrams.py", "shows": shows,
                "sha256": hashlib.sha256(out.read_bytes()).hexdigest()}
        if runs:
            item["data_sha256"] = _data_sha(*runs)
            item["does_not_show"] = "any run other than " + ", ".join(runs)
        else:
            item["does_not_show"] = "measured traffic, latency or production readiness"
        items.append(item)
    for name, shows in SCREENSHOTS.items():
        items.append({"file": name, "language": "cn", "generator": "Azure portal screenshot", "shows": shows,
                      "sha256": hashlib.sha256((IMAGES / name).read_bytes()).hexdigest(),
                      "does_not_show": SCREENSHOT_NOTE})
    LEDGER.write_text(json.dumps({"schema": 1, "images": items}, indent=1, ensure_ascii=False) + "\n",
                      encoding="utf-8", newline="\n")
    print(f"wrote {len(items)} images and images/SOURCES.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())

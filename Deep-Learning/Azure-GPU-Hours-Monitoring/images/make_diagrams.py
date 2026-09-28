"""Render architecture.png and metrics.png (run: python make_diagrams.py)."""
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

HERE = pathlib.Path(__file__).parent
plt.rcParams["font.family"] = ["Segoe UI", "Microsoft YaHei", "DejaVu Sans"]

AZ_BLUE, AZ_DARK, NV_GREEN, GREY, PURPLE, ORANGE = "#0078D4", "#1F3B5C", "#76B900", "#6B7280", "#6366F1", "#F59E0B"


def box(ax, x, y, w, h, title, lines=(), fc="#FFFFFF", ec=AZ_BLUE, title_fc=None, lw=1.6):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                fc=fc, ec=ec, lw=lw))
    ax.text(x + w / 2, y + h - 0.22, title, ha="center", va="top", fontsize=11, fontweight="bold",
            color=title_fc or ec)
    for i, ln in enumerate(lines):
        ax.text(x + 0.14, y + h - 0.56 - i * 0.3, ln, ha="left", va="top", fontsize=8.6, color="#111827")


def arrow(ax, x1, y1, x2, y2, label="", color=GREY, ls="-", lw=1.6, label_dy=0.12):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=14,
                                 color=color, lw=lw, linestyle=ls, shrinkA=2, shrinkB=2))
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + label_dy, label, ha="center", va="bottom", fontsize=8,
                color=color, bbox=dict(fc="white", ec="none", pad=1))


def architecture():
    fig, ax = plt.subplots(figsize=(15, 8.2), dpi=160)
    ax.set_xlim(0, 15); ax.set_ylim(0, 8.2); ax.axis("off")
    fig.patch.set_facecolor("white")

    ax.text(7.5, 7.85, "Azure GPU-Hours Monitoring — architecture", ha="center", va="center",
            fontsize=15, fontweight="bold", color=AZ_DARK)
    ax.text(7.5, 7.45, "All managed Azure services; the only custom code is a 200-line collector and an optional dashboard",
            ha="center", va="center", fontsize=9.5, color=GREY)

    # ---- GPU VM zone
    ax.add_patch(FancyBboxPatch((0.3, 1.0), 4.6, 6.0, boxstyle="round,pad=0.02,rounding_size=0.15",
                                fc="#F3F8FD", ec="#B6D3EE", lw=1.2, ls="--"))
    ax.text(2.6, 6.75, "GPU VM  (ND H100 v5 / NC H100 v5 …)  ×N", ha="center", fontsize=10.5,
            fontweight="bold", color=AZ_DARK)
    box(ax, 0.6, 5.0, 4.0, 1.35, "NVIDIA DCGM  (nv-hostengine)",
        ["DCGM_FI_PROF_SM_ACTIVE · GR_ENGINE_ACTIVE · TENSOR",
         "GPU_UTIL · FB_USED · POWER · TEMP  (1 s samples)"], ec=NV_GREEN, title_fc="#4E7A00")
    box(ax, 0.6, 3.0, 4.0, 1.6, "gpumon.service  (vm/gpu_collector.py)",
        ["dcgmi dmon every 10 s → per-GPU 1-minute average",
         "+ process owner via nvidia-smi / proc  (Users column)",
         "→ /var/log/gpumon/gpu_metrics_YYYYMMDD.json  (JSONL)"], ec=AZ_DARK)
    box(ax, 0.6, 1.25, 4.0, 1.35, "Azure Monitor Agent  (AMA)",
        ["Custom JSON Logs data source (DCR)  ·  Heartbeat 1/min",
         "Managed identity → HTTPS → Data Collection Endpoint"], ec=AZ_BLUE)
    arrow(ax, 2.6, 5.0, 2.6, 4.6, "")
    arrow(ax, 2.6, 3.0, 2.6, 2.6, "tail JSONL")

    # ---- Azure Monitor zone
    ax.add_patch(FancyBboxPatch((5.5, 1.0), 4.4, 6.0, boxstyle="round,pad=0.02,rounding_size=0.15",
                                fc="#F7F7FB", ec="#C9CBE3", lw=1.2, ls="--"))
    ax.text(7.7, 6.75, "Azure Monitor  (fully managed)", ha="center", fontsize=10.5, fontweight="bold", color=AZ_DARK)
    box(ax, 5.8, 5.0, 3.8, 1.35, "DCE + DCR  (azure/dcr.json)",
        ["stream Custom-Json-GpuMetrics → Custom-GpuMetrics_CL",
         "transform: source  (schema declared in DCR)"], ec=PURPLE)
    box(ax, 5.8, 2.75, 3.8, 1.85, "Log Analytics workspace",
        ["GpuMetrics_CL   1 row / GPU / minute",
         "Heartbeat       1 row / VM / minute  → allocated hours",
         "retention 90 d+  ·  KQL  ·  RBAC (table-level)"], ec=AZ_BLUE)
    box(ax, 5.8, 1.25, 3.8, 1.1, "Alert rule  (scheduledQueryRules)",
        ["GPU powered on but idle ≥ 50 of last 60 min"], ec=ORANGE, title_fc="#B45309")
    arrow(ax, 7.7, 5.0, 7.7, 4.6)
    arrow(ax, 7.7, 2.75, 7.7, 2.35)
    arrow(ax, 4.6, 1.9, 5.8, 5.6, "ingest", color=AZ_BLUE)

    # ---- Consumers zone
    ax.add_patch(FancyBboxPatch((10.5, 1.0), 4.2, 6.0, boxstyle="round,pad=0.02,rounding_size=0.15",
                                fc="#F4FBF6", ec="#BFE3C9", lw=1.2, ls="--"))
    ax.text(12.6, 6.75, "Consumers", ha="center", fontsize=10.5, fontweight="bold", color=AZ_DARK)
    box(ax, 10.8, 5.15, 3.6, 1.2, "Azure Workbook  (azure/workbook.json)",
        ["Portal dashboard, no code · Entra RBAC"], ec=AZ_BLUE)
    box(ax, 10.8, 3.55, 3.6, 1.3, "Web UI + JSON API  (webui/)",
        ["App Service · managed identity · access code",
         "GET /api/data?range=24h&idle=5"], ec=AZ_DARK)
    box(ax, 10.8, 1.95, 3.6, 1.3, "Customer platform",
        ["Log Analytics Query REST API  (KQL)",
         "or the Web UI JSON API above"], ec="#059669", title_fc="#047857")
    box(ax, 10.8, 1.2, 3.6, 0.55, "Cost Management API  → billed hours cross-check", ec=GREY, lw=1.0)
    for y in (5.75, 4.2, 2.6):
        arrow(ax, 9.6, 3.7, 10.8, y, color=AZ_BLUE)

    # footer formulas
    ax.text(7.5, 0.55, "allocated GPU-h = Heartbeat minutes × GPUs ÷ 60      busy GPU-h = minutes with process or util ≥ 5% ÷ 60      "
            "effective GPU-h = Σ SM Active ÷ 60      utilisation = effective ÷ allocated",
            ha="center", va="center", fontsize=8.6, color=AZ_DARK,
            bbox=dict(fc="#FFFBEB", ec="#FCD34D", pad=6))
    fig.savefig(HERE / "architecture.png", bbox_inches="tight")
    plt.close(fig)


def metrics():
    """Stacked-bar illustration of the four GPU-hour buckets using the real demo run."""
    fig, ax = plt.subplots(figsize=(11, 4.6), dpi=160)
    fig.patch.set_facecolor("white")
    # minutes 0..21 of the validation run: SM active fraction per minute
    sm = [0, 0, 0.94, 0.97, 0.97, 0.97, 0.97, 0.97, 0.97, 0.97, 0.005, 0, 0, 0.35, 0.35, 0.35, 0.35, 0.35, 0, 0, 0, 0]
    proc = [0, 1] + [1] * 16 + [0, 0, 0, 0]
    x = range(len(sm))
    ax.bar(x, [1] * len(sm), color="#E5E7EB", width=0.9, label="allocated (VM running)")
    ax.bar(x, [1 if (p or s >= 0.05) else 0 for p, s in zip(proc, sm)], color="#F9A8D4", width=0.9,
           label="busy (process present or util ≥ 5 %)")
    ax.bar(x, sm, color="#14B8A6", width=0.9, label="effective (SM Active)")
    ax.set_xticks(list(x)); ax.set_xticklabels([f"{m}" for m in x], fontsize=8)
    ax.set_xlabel("minute of validation run (1× H100 NVL)"); ax.set_ylabel("GPU-minute fraction")
    ax.set_ylim(0, 1.15)
    ax.set_title("How one GPU-minute is classified: allocated ⊇ busy ⊇ effective", fontsize=12, fontweight="bold", color=AZ_DARK)
    ax.legend(loc="upper right", fontsize=8.5, ncol=3, frameon=False)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.annotate("full load\n~97 % SM", (5, 1.02), ha="center", fontsize=8.5, color="#0F766E")
    ax.annotate("holding 21 GB VRAM,\n0 % SM → busy, not effective", (11.5, 1.02), ha="center", fontsize=8.5, color="#BE185D")
    ax.annotate("50 % duty cycle\n~35 % SM", (15.5, 1.02), ha="center", fontsize=8.5, color="#0F766E")
    ax.annotate("idle GPU-minutes\n(cost, no work)", (19.5, 1.02), ha="center", fontsize=8.5, color=GREY)
    fig.savefig(HERE / "metrics.png", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    architecture()
    metrics()
    print("written architecture.png, metrics.png")

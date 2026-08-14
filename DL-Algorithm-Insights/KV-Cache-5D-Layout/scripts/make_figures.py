"""Generate figures for the 5D KV Cache article.

Figures are shared by README.md and README-CN.md, so all labels are in English.

Usage:
    python scripts/make_figures.py
"""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle

OUT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "images"))

TOKEN_COLORS = ["#4472c4", "#ed7d31", "#70ad47", "#a5389a"]
BG = "#ffffff"

T, D, X = 4, 4, 2  # minimal example: 4 tokens, head_dim=4, vector width 2


def save(fig, name):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    fig.savefig(path, dpi=110, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"  {name}  {os.path.getsize(path)/1024:.0f} KB")


def fig1_layers():
    fig, ax = plt.subplots(figsize=(11, 4.8))
    layers = [
        ("Compute kernel", "AITER / FlyDSL / FA3", "Who reads and computes the data", "#548235"),
        ("Physical layout", "NHD / vectorized_5d", "In what order one page is arranged", "#c55a11"),
        ("Memory paging", "PagedAttention", "How pages are allocated and mapped", "#2e75b6"),
        ("Numeric precision", "FP8 E4M3 / BF16", "How many bytes each value takes", "#1f4e79"),
    ]
    for i, (name, example, question, color) in enumerate(layers):
        y = i * 1.12
        ax.add_patch(Rectangle((0, y), 10.6, 1.0, facecolor=color, edgecolor="white", lw=2))
        ax.text(0.3, y + 0.5, name, color="white", fontsize=13, fontweight="bold", va="center")
        ax.text(3.1, y + 0.5, example, color="white", fontsize=11.5, va="center")
        ax.text(10.3, y + 0.5, question, color="white", fontsize=11, va="center", ha="right")

    ax.text(5.3, 4.75, "Four terms, four different questions",
            fontsize=15, fontweight="bold", ha="center")
    ax.set_xlim(-0.2, 10.8)
    ax.set_ylim(-0.2, 5.1)
    ax.axis("off")
    save(fig, "fig1-four-layers.png")


def _draw_strip(ax, seq, y, title):
    """Draw a (token, dim) sequence as one strip in memory address order."""
    ax.text(0, y + 1.3, title, fontsize=12.5, fontweight="bold", va="center")
    for addr, (t, d) in enumerate(seq):
        ax.add_patch(
            Rectangle((addr, y), 0.94, 0.94, facecolor=TOKEN_COLORS[t], edgecolor="white", lw=1.5)
        )
        ax.text(addr + 0.47, y + 0.47, f"t{t}\nd{d}", color="white", fontsize=9,
                ha="center", va="center", fontweight="bold")
        ax.text(addr + 0.47, y - 0.28, str(addr), fontsize=8, color="#666666", ha="center")


def fig2_nhd_vs_5d():
    nhd = [(t, d) for t in range(T) for d in range(D)]
    five = [(t, db * X + x) for db in range(D // X) for t in range(T) for x in range(X)]

    fig, ax = plt.subplots(figsize=(12, 4.8))
    _draw_strip(ax, nhd, 2.3, "NHD: write every dimension of one token, then move to the next")
    _draw_strip(ax, five, 0.0, "5D: write d0,d1 of all tokens first, then d2,d3")

    ax.text(8.0, 1.62, "Same 16 elements, not one more or fewer - only the addresses changed",
            fontsize=11, color="#c00000", ha="center", fontweight="bold")
    ax.text(0, 4.0, "Minimal example: 4 tokens, head_dim=4, vector width X=2 (color = token)",
            fontsize=12, fontweight="bold")
    ax.set_xlim(-0.3, 16.3)
    ax.set_ylim(-0.6, 4.4)
    ax.axis("off")
    save(fig, "fig2-nhd-vs-5d.png")


def fig3_vector_width():
    fig, ax = plt.subplots(figsize=(10.5, 3.9))
    ax.text(0, 3.35, "X = 16 bytes / bytes per element: same pallet width, smaller boxes fit more",
            fontsize=12.5, fontweight="bold")

    for row, (label, n, color) in enumerate([("BF16: 2 bytes -> 8 per load", 8, "#2e75b6"),
                                             ("FP8: 1 byte -> 16 per load", 16, "#c55a11")]):
        y = row * 1.35
        ax.add_patch(Rectangle((3.6, y - 0.12), 8.0, 1.04, facecolor="#f2f2f2",
                               edgecolor="#999999", lw=1.5))
        w = 8.0 / n
        for i in range(n):
            ax.add_patch(Rectangle((3.6 + i * w + 0.04, y), w - 0.08, 0.8,
                                   facecolor=color, edgecolor="white", lw=1))
        ax.text(3.4, y + 0.4, label, fontsize=11.5, ha="right", va="center")

    ax.annotate("", xy=(3.6, 2.95), xytext=(11.6, 2.95),
                arrowprops=dict(arrowstyle="<->", color="#c00000", lw=2))
    ax.text(7.6, 3.05, "fixed 16 bytes", fontsize=11, color="#c00000",
            ha="center", fontweight="bold")

    ax.set_xlim(-0.3, 12.0)
    ax.set_ylim(-0.4, 3.7)
    ax.axis("off")
    save(fig, "fig3-vector-width.png")


def fig4_k_vs_v():
    fig, ax = plt.subplots(figsize=(11, 4.3))
    ax.text(0, 3.8, "K and V are sliced along different axes because they are read differently",
            fontsize=12.5, fontweight="bold")

    # K: sliced along head_dim
    ax.add_patch(Rectangle((0.9, 0.5), 3.8, 2.6, facecolor="#dae3f3", edgecolor="#2e75b6", lw=2))
    for i in range(1, 3):
        ax.plot([0.9 + i * 3.8 / 3] * 2, [0.5, 3.1], color="#2e75b6", lw=2, ls="--")
    ax.text(2.8, 3.3, "K Cache", fontsize=12, fontweight="bold", ha="center", color="#2e75b6")
    ax.text(2.8, 0.15, "sliced into D/X blocks along head_dim", fontsize=10.5, ha="center")
    ax.text(2.8, 1.9, "Q x K-transpose reads\na full head vector", fontsize=10.5,
            ha="center", va="center")
    ax.text(0.75, 1.8, "token", fontsize=10, color="#666666", ha="right", va="center", rotation=90)
    ax.text(2.8, 0.62, "head_dim ->", fontsize=10, color="#666666", ha="center")

    # V: sliced along token position
    ax.add_patch(Rectangle((6.6, 0.5), 3.8, 2.6, facecolor="#fbe5d6", edgecolor="#c55a11", lw=2))
    for i in range(1, 3):
        ax.plot([6.6, 10.4], [0.5 + i * 2.6 / 3] * 2, color="#c55a11", lw=2, ls="--")
    ax.text(8.5, 3.3, "V Cache", fontsize=12, fontweight="bold", ha="center", color="#c55a11")
    ax.text(8.5, 0.15, "sliced into P/X blocks along token position", fontsize=10.5, ha="center")
    ax.text(8.5, 1.9, "weighted sum\naccumulates over tokens", fontsize=10.5,
            ha="center", va="center")
    ax.text(6.45, 1.8, "token", fontsize=10, color="#666666", ha="right", va="center", rotation=90)
    ax.text(8.5, 0.62, "head_dim ->", fontsize=10, color="#666666", ha="center")

    ax.set_xlim(-0.2, 10.8)
    ax.set_ylim(-0.2, 4.05)
    ax.axis("off")
    save(fig, "fig4-k-vs-v.png")


def fig5_wrong_layout():
    five = [(t, db * X + x) for db in range(D // X) for t in range(T) for x in range(X)]
    fig, ax = plt.subplots(figsize=(12, 4.0))
    ax.text(0, 3.3, "A wrong layout raises no error - it silently returns wrong data",
            fontsize=12.5, fontweight="bold")

    for addr, (t, d) in enumerate(five):
        hot = addr < 4
        ax.add_patch(Rectangle((addr, 1.1), 0.94, 0.94, facecolor=TOKEN_COLORS[t],
                               edgecolor="#c00000" if hot else "white", lw=3 if hot else 1.5))
        ax.text(addr + 0.47, 1.57, f"t{t}\nd{d}", color="white", fontsize=9,
                ha="center", va="center", fontweight="bold")

    ax.text(0, 0.62, "physically stored in 5D order", fontsize=10.5, color="#666666")
    ax.add_patch(FancyArrowPatch((2.0, 2.62), (2.0, 2.12), arrowstyle="-|>",
                                 mutation_scale=18, color="#c00000", lw=2))
    ax.text(2.3, 2.72, "Draft reads addresses 0-3 as NHD, expecting d0~d3 of token0",
            fontsize=11, color="#c00000", va="center")
    ax.text(5.6, 0.62, "actually gets t0d0, t0d1, t1d0, t1d1 - token1 leaked in; "
                       "not slower, just wrong",
            fontsize=11, color="#c00000", fontweight="bold")

    ax.set_xlim(-0.3, 16.3)
    ax.set_ylim(0.2, 3.5)
    ax.axis("off")
    save(fig, "fig5-wrong-layout.png")


if __name__ == "__main__":
    print("generating figures ->", OUT)
    fig1_layers()
    fig2_nhd_vs_5d()
    fig3_vector_width()
    fig4_k_vs_v()
    fig5_wrong_layout()
    print("done")

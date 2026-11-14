"""Draw a schematic 2-view engineering drawing of an EXV valve body (sample input for the 2D→3D scenario)."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle

OUT = Path(__file__).resolve().parent.parent / "static" / "samples" / "exv_body_drawing.png"
OUT.parent.mkdir(parents=True, exist_ok=True)

plt.rcParams["font.family"] = ["Segoe UI", "Microsoft YaHei", "DejaVu Sans"]
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 7.2), dpi=130, gridspec_kw={"width_ratios": [1.15, 1]})
fig.patch.set_facecolor("white")
LW = 1.6
K = dict(color="#111", lw=LW)
DIM = dict(color="#1d4ed8", lw=0.9)


def dim_h(ax, x0, x1, y, text, off=6):
    ax.annotate("", (x0, y), (x1, y), arrowprops=dict(arrowstyle="<->", **DIM))
    ax.plot([x0, x0], [y - off, y + off], **DIM); ax.plot([x1, x1], [y - off, y + off], **DIM)
    ax.text((x0 + x1) / 2, y + 2.5, text, ha="center", va="bottom", fontsize=10, color="#1d4ed8")


def dim_v(ax, x, y0, y1, text, off=6):
    ax.annotate("", (x, y0), (x, y1), arrowprops=dict(arrowstyle="<->", **DIM))
    ax.plot([x - off, x + off], [y0, y0], **DIM); ax.plot([x - off, x + off], [y1, y1], **DIM)
    ax.text(x + 2.5, (y0 + y1) / 2, text, ha="left", va="center", fontsize=10, color="#1d4ed8", rotation=90)


# ---------------- front view (elevation) ----------------
ax = ax1
ax.set_aspect("equal"); ax.axis("off")
ax.set_xlim(-70, 95); ax.set_ylim(-45, 125)
# brass body Ø32 x 60 (x: -16..16, y: 0..60)
ax.add_patch(Rectangle((-16, 0), 32, 60, fill=False, **K))
# coil housing Ø28 x 35 on top (y: 60..95)
ax.add_patch(Rectangle((-14, 60), 28, 35, fill=False, **K))
ax.add_patch(Rectangle((-10, 95), 20, 6, fill=False, **K))  # connector cap
# side inlet tube Ø9.52, length 40, centre at y=22
ax.add_patch(Rectangle((16, 22 - 4.76), 40, 9.52, fill=False, **K))
ax.plot([16, 56], [22, 22], color="#111", lw=0.7, ls="-.")
# bottom outlet tube Ø9.52 length 35
ax.add_patch(Rectangle((-4.76, -35), 9.52, 35, fill=False, **K))
ax.plot([0, 0], [-35, 101], color="#111", lw=0.7, ls="-.")
# hidden lines: internal bore Ø14 and needle seat Ø1.6
ax.plot([-7, -7], [4, 56], color="#555", lw=0.9, ls="--"); ax.plot([7, 7], [4, 56], color="#555", lw=0.9, ls="--")
ax.plot([-0.8, -0.8], [4, 12], color="#555", lw=0.9, ls="--"); ax.plot([0.8, 0.8], [4, 12], color="#555", lw=0.9, ls="--")
# dimensions
dim_h(ax, -16, 16, 110, "Ø32")
dim_h(ax, -14, 14, 103, "Ø28")
dim_v(ax, -30, 0, 60, "60")
dim_v(ax, -46, 60, 95, "35")
dim_v(ax, 62, 22 - 4.76, 22 + 4.76, "Ø9.52")
dim_h(ax, 16, 56, 38, "40")
dim_v(ax, 22, 0, 22, "22")
dim_h(ax, -4.76, 4.76, -41, "Ø9.52")
dim_v(ax, -30, -35, 0, "35")
ax.text(0, 118, "主视图  FRONT VIEW", ha="center", fontsize=11, weight="bold")
ax.text(-66, 8, "内孔 Ø14 (虚线)\n节流孔 Ø1.6", fontsize=8.5, color="#555", va="center")

# ---------------- top view ----------------
ax = ax2
ax.set_aspect("equal"); ax.axis("off")
ax.set_xlim(-45, 80); ax.set_ylim(-45, 60)
ax.add_patch(Circle((0, 0), 16, fill=False, **K))
ax.add_patch(Circle((0, 0), 14, fill=False, color="#111", lw=0.9, ls="--"))
ax.add_patch(Circle((0, 0), 4.76, fill=False, **K))       # outlet tube (bottom) seen through
ax.add_patch(Circle((0, 0), 0.8, fill=False, **K))        # orifice
ax.add_patch(Rectangle((16, -4.76), 40, 9.52, fill=False, **K))  # side inlet tube
ax.plot([-22, 62], [0, 0], color="#111", lw=0.7, ls="-."); ax.plot([0, 0], [-24, 24], color="#111", lw=0.7, ls="-.")
dim_h(ax, 16, 56, 12, "40")
dim_v(ax, -26, -16, 16, "Ø32")
dim_h(ax, -4.76, 4.76, -30, "Ø9.52")
ax.text(15, 52, "俯视图  TOP VIEW", ha="center", fontsize=11, weight="bold")

# title block
fig.text(0.5, 0.045, "电子膨胀阀 阀体组件  ·  材料：阀体 H62 黄铜 / 接管 TP2 紫铜 / 线圈座 PA66  ·  单位 mm  ·  比例 1:1  ·  EXV-DEMO-01",
         ha="center", fontsize=10.5, color="#242424",
         bbox=dict(boxstyle="square,pad=0.6", fc="#f7f4ef", ec="#919191", lw=1))
fig.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.12, wspace=0.05)
fig.savefig(OUT, facecolor="white")
print("saved", OUT, OUT.stat().st_size, "bytes")

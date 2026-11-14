import cadquery as cq
import math

# AIDC GPU 液冷冷板 —— 轨 B 参考脚本（场景需求：基板 110×90×3，微通道翅片 0.3 宽 / 3 高 / 0.6 间距，上盖 2 mm，进出口 φ8 在短边两端）
P = {
    "baseL": 110.0, "baseW": 90.0, "baseT": 3.0, "coverT": 2.0, "cornerR": 4.0, "edgeChamfer": 0.5,
    "finW": 0.3, "finH": 3.0, "finPitch": 0.6, "finFieldL": 70.0, "finFieldW": 60.0, "finEquiv": 50,   # 实际 100 片 → 等效 50 片（间距 ×2，面积按比例换算）
    "manifoldW": 10.0, "manifoldDepth": 2.5,                                                             # 翅片区两侧集流槽
    "portD": 8.0, "portWall": 1.0, "portLen": 18.0, "portBeadD": 10.0, "portInsert": 3.0,
    "lugW": 12.0, "lugL": 10.0, "holeD": 3.4, "cboreD": 6.0, "cboreDepth": 2.0,                         # 4×M3 沉孔安装耳
    "oringW": 1.5, "oringDepth": 1.0, "oringInset": 4.0,
    "seatPad": 60.0, "seatPadDepth": 0.2,                                                                # 底面 GPU 接触凸台（抛光区）
    "copperDensity": 8.96, "aluminumDensity": 2.70,
}
DENSITY = P["copperDensity"]
L, W, T, Tc = P["baseL"], P["baseW"], P["baseT"], P["coverT"]
fin_n = int(P["finEquiv"])
fin_pitch = P["finFieldW"] / fin_n            # 等效间距（1.2 mm）
fin_w = P["finW"] * (fin_pitch / P["finPitch"])  # 等效翅片宽（0.6 mm），保持翅片占空比
H_total = T + P["finH"] + Tc

# ---- 基板：圆角矩形 + 翅片场 + 两侧集流槽 + 四角沉孔安装耳 + O 圈槽 + 底面接触凸台
base = cq.Workplane("XY").box(L, W, T).translate((0, 0, T / 2)).edges("|Z").fillet(P["cornerR"])
lug_pts = [(sx * (L / 2 + P["lugL"] / 2 - 2), sy * (W / 2 - P["lugW"] / 2)) for sx in (-1, 1) for sy in (-1, 1)]
lugs = cq.Workplane("XY").pushPoints(lug_pts).rect(P["lugL"] + 4, P["lugW"]).extrude(T)
lugs = lugs.edges("|Z").fillet(3.0)
base = base.union(lugs)
hole_pts = [(sx * (L / 2 + P["lugL"] / 2), sy * (W / 2 - P["lugW"] / 2)) for sx in (-1, 1) for sy in (-1, 1)]
base = base.faces(">Z").workplane().pushPoints(hole_pts).cboreHole(P["holeD"], P["cboreD"], P["cboreDepth"])
# 翅片场（等效 50 片，沿 X 排布，流向沿 Y）
fins = (cq.Workplane("XY").workplane(offset=T).rarray(fin_pitch, 1, fin_n, 1).rect(fin_w, P["finFieldL"]).extrude(P["finH"]))
fins = fins.translate((0, 0, 0))
# 集流槽：翅片场两端（±Y）下沉 manifoldDepth 进基板，让冷却液横向分配
for sy in (-1, 1):
    base = base.cut(cq.Workplane("XY").workplane(offset=T - P["manifoldDepth"]).center(0, sy * (P["finFieldL"] / 2 + P["manifoldW"] / 2)).rect(P["finFieldW"] + 2, P["manifoldW"]).extrude(P["manifoldDepth"] + 0.1))
# O 圈槽（顶面一圈）
og_w, og_d, inset = P["oringW"], P["oringDepth"], P["oringInset"]
oring = cq.Workplane("XY").workplane(offset=T - og_d).rect(L - 2 * inset, W - 2 * inset).rect(L - 2 * inset - 2 * og_w, W - 2 * inset - 2 * og_w).extrude(og_d + 0.1)
try:
    oring = oring.edges("|Z").fillet(og_w)
except Exception:  # noqa: BLE001
    pass
base = base.cut(oring)
# 底面 GPU 接触凸台：外周下沉 0.2 mm，中央 60×60 保留为抛光接触面
pad_cut = cq.Workplane("XY").rect(L + 2, W + 2).rect(P["seatPad"], P["seatPad"]).extrude(P["seatPadDepth"]).translate((0, 0, -0.0))
base = base.cut(pad_cut)
# 进出口：短边两端，水平进入集流槽
port_z = T - P["manifoldDepth"] / 2 + P["finH"] / 2
ports = []
for sx in (-1, 1):
    x0 = sx * (L / 2 + P["portLen"] - P["portInsert"])
    direction = cq.Vector(-sx, 0, 0)
    body = cq.Solid.makeCylinder(P["portD"] / 2 + P["portWall"], P["portLen"], cq.Vector(x0, 0, port_z), direction)
    bead = cq.Solid.makeCylinder(P["portBeadD"] / 2, 2.5, cq.Vector(x0 - sx * 4, 0, port_z), direction)
    port = cq.Workplane("XY").newObject([body]).union(bead)
    port = port.cut(cq.Solid.makeCylinder(P["portD"] / 2, P["portLen"] + 2, cq.Vector(x0 + sx, 0, port_z), direction))
    try:
        port = port.faces(">X" if sx > 0 else "<X").chamfer(0.5)
    except Exception:  # noqa: BLE001
        pass
    ports.append(port)
    base = base.cut(cq.Solid.makeCylinder(P["portD"] / 2 + P["portWall"] + 0.05, P["portInsert"] + 0.1, cq.Vector(sx * (L / 2 + 0.1), 0, port_z), direction))
inlet, outlet = ports

# ---- 上盖：同轮廓，中央下沉减重区，顶部铭牌凹区，边缘倒角；盖板内腔容纳翅片
cover = cq.Workplane("XY").box(L, W, Tc).translate((0, 0, T + P["finH"] + Tc / 2)).edges("|Z").fillet(P["cornerR"])
cavity = cq.Workplane("XY").workplane(offset=T).rect(P["finFieldW"] + 2 * P["manifoldW"] + 6, P["finFieldL"] + 2 * P["manifoldW"]).extrude(P["finH"])
cover_skirt = cq.Workplane("XY").workplane(offset=T).rect(L - 2 * inset + og_w, W - 2 * inset + og_w).extrude(P["finH"]).edges("|Z").fillet(2.0)
cover = cover.union(cover_skirt).cut(cavity)
cover = cover.faces(">Z").workplane().rect(40, 14).cutBlind(-0.3)                                         # 铭牌凹区
cover = cover.faces(">Z").workplane().pushPoints([(-30, 0), (30, 0)]).slot2D(18, 4).cutBlind(-0.4)         # 两条减重槽
try:
    cover = cover.faces(">Z").edges("not %CIRCLE").chamfer(P["edgeChamfer"])
except Exception:  # noqa: BLE001
    pass

result = base.union(fins).union(cover).union(inlet).union(outlet)

PARTS = {"铜基板": base, "微通道翅片（等效 50 片）": fins, "上盖板": cover, "进口接头": inlet, "出口接头": outlet}
MATERIALS = {"铜基板": "copper", "微通道翅片（等效 50 片）": "copper", "上盖板": "anodized", "进口接头": "steel", "出口接头": "steel"}
DENSITIES = {"上盖板": P["aluminumDensity"], "进口接头": 7.90, "出口接头": 7.90}
NAME = "GPU 液冷冷板"

real_fin_n = int(P["finFieldW"] / P["finPitch"])
real_area = real_fin_n * 2 * P["finH"] * P["finFieldL"] / 100  # cm²
METRICS = [
    {"label": "翅片等效关系", "value": f"{fin_n} 片 ≙ {real_fin_n} 片", "unit": "", "note": f"等效间距 {fin_pitch:.1f} mm / 宽 {fin_w:.1f} mm，占空比不变"},
    {"label": "真实翅片换热面积", "value": round(real_area, 1), "unit": "cm²", "note": f"{real_fin_n} 片 × 2 面 × {P['finH']} × {P['finFieldL']} mm"},
    {"label": "基板一维热阻（铜）", "value": round(P["baseT"] / 1000 / (400 * P["seatPad"] * P["seatPad"] / 1e6) * 1000, 3), "unit": "mK/W", "note": "t/(kA)，A = 60×60 接触区，k = 400 W/m·K"},
    {"label": "安装孔", "value": "4 × M3 沉孔", "unit": "", "note": f"φ{P['holeD']} / φ{P['cboreD']}×{P['cboreDepth']}"},
]

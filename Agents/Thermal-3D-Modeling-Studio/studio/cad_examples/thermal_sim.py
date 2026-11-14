import cadquery as cq
import math

# AI 辅助仿真估算 —— 轨 B 参考脚本：被估算的电池水冷板实体 + 流道内冷却液实体（按 6 个流程拆分，部件名带一维模型给出的进出口温度）。
# 几何与工况取自场景示例 P：320×180×12、6 道 S 形串联流道 10×6、受热面壁厚 1.5、程距 28、进出口 Ø12 同在短边；
# 50% 乙二醇 8 L/min、进口 25 °C、上表面均布 2 kW。METRICS 逐式移植示例 calculate()（集总参数 / 一维模型，不是 CFD）。
P = {
    "L": 320.0, "W": 180.0, "H": 12.0, "n": 6, "cw": 10.0, "ch": 6.0, "wall": 1.5, "pitch": 28.0, "endX": 130.0,
    "portD": 12.0, "portOuterD": 16.0, "portLength": 18.0,
    "corner": 6.0, "bossL": 24.0, "bossW": 26.0, "bossH": 20.0, "beadD": 17.5,   # 假设：圆角与钎焊接头座尺寸
    "flow": 8.0, "Tin": 25.0, "heat": 2000.0,
    "rho": 1069.0, "cp": 3280.0, "mu": 0.0034, "k": 0.38, "Pr": 29.0,
    "alK": 200.0, "criticalRe": 2300.0, "laminarNu": 4.0, "dbC": 0.023, "dbRe": 0.8, "dbPr": 0.4,
    "laminarF": 64.0, "blasiusC": 0.316, "blasiusE": -0.25, "bendK": 1.5, "portK": 1.5,
    "alDensity": 2.70, "coolantDensity": 1.069,
}
n = int(P["n"])
L, W, H, cw, ch = P["L"], P["W"], P["H"], P["cw"], P["ch"]
r = P["pitch"] / 2
tx = P["endX"]
lead = L / 2 - tx

# ---- 一维热-流估算（与示例页面 calculate() 同式）
path_mm = n * 2 * tx + (n - 1) * math.pi * r + 2 * lead
Q = P["flow"] / 60000
A = cw * ch * 1e-6
per = 2 * (cw + ch) / 1000
Dh = 4 * A / per
Lm = path_mm / 1000
rise = P["heat"] / (P["rho"] * Q * P["cp"])
v = Q / A
Re = P["rho"] * v * Dh / P["mu"]
Nu = P["laminarNu"] if Re < P["criticalRe"] else P["dbC"] * Re ** P["dbRe"] * P["Pr"] ** P["dbPr"]
h = Nu * P["k"] / Dh
flux = P["heat"] / (per * Lm)
wall_rise = flux / h + flux * (P["wall"] / 1000) / P["alK"]
fric = P["laminarF"] / Re if Re < P["criticalRe"] else P["blasiusC"] * Re ** P["blasiusE"]
dyn = P["rho"] * v * v / 2
v_port = Q / (math.pi * (P["portD"] / 1000) ** 2 / 4)
dp = (fric * Lm / Dh * dyn + (n - 1) * P["bendK"] * dyn + P["portK"] * P["rho"] * v_port ** 2 / 2) / 1000
T_out = P["Tin"] + rise
T_max = T_out + wall_rise

# ---- 流道几何：盖板 1.5 在上，流道 6 深铣在基板顶面；z = 0 为冷板底面
base_t = H - P["wall"]
zc = base_t - ch / 2
ys = [(i - (n - 1) / 2) * P["pitch"] for i in range(n)]
half_turn = (cq.Workplane("XZ").polyline([(r - cw / 2, -ch / 2), (r + cw / 2, -ch / 2), (r + cw / 2, ch / 2), (r - cw / 2, ch / 2)]).close()
             .revolve(180, (0, 0), (0, 1)))
x_edge = -L / 2
port_x0 = x_edge - P["bossL"]
fluid, seg_len = [], []
for i, y in enumerate(ys):
    xmin = x_edge if i in (0, n - 1) else -tx
    f = cq.Workplane("XY").newObject([cq.Solid.makeBox(tx - xmin, cw, ch, cq.Vector(xmin, y - cw / 2, zc - ch / 2))])
    length = tx - xmin
    if i < n - 1:
        right = i % 2 == 0
        f = f.union(half_turn.rotate((0, 0, 0), (0, 0, 1), -90 if right else 90).translate((tx if right else -tx, (y + ys[i + 1]) / 2, zc)))
        length += math.pi * r
    if i in (0, n - 1):   # 接头座内的 10×6 过渡槽 + Ø12 孔 + 接管内腔
        f = f.union(cq.Solid.makeBox(6.0, cw, ch, cq.Vector(x_edge - 6.0, y - cw / 2, zc - ch / 2)))
        f = f.union(cq.Solid.makeCylinder(P["portD"] / 2, P["bossL"] - 6.0 + P["portLength"], cq.Vector(port_x0 - P["portLength"], y, zc), cq.Vector(1, 0, 0)))
    fluid.append(f)
    seg_len.append(length)

# ---- 冷板基板（铝，流道铣削）与盖板（受热面）
base = cq.Workplane("XY").rect(L, W).extrude(base_t).edges("|Z").fillet(P["corner"])
for f in fluid:
    base = base.cut(f)
lid = cq.Workplane("XY").workplane(offset=base_t).rect(L, W).extrude(P["wall"]).edges("|Z").fillet(P["corner"])

# ---- 进 / 出口接头座（钎焊于短边）与 Ø16/Ø12 接管（带防脱凸环）
bosses, tubes = [], []
for y in (ys[0], ys[-1]):
    b = cq.Workplane("XY").newObject([cq.Solid.makeBox(P["bossL"], P["bossW"], P["bossH"], cq.Vector(port_x0, y - P["bossW"] / 2, zc - P["bossH"] / 2))])
    try:
        b = b.edges("|X").fillet(3.0)
    except Exception:  # noqa: BLE001
        pass
    b = b.cut(cq.Solid.makeBox(6.2, cw, ch, cq.Vector(x_edge - 6.0, y - cw / 2, zc - ch / 2)))
    b = b.cut(cq.Solid.makeCylinder(P["portD"] / 2, P["bossL"] - 5.9, cq.Vector(port_x0 - 0.1, y, zc), cq.Vector(1, 0, 0)))
    bosses.append(b)
    t = cq.Workplane("XY").newObject([cq.Solid.makeCylinder(P["portOuterD"] / 2, P["portLength"], cq.Vector(port_x0 - P["portLength"], y, zc), cq.Vector(1, 0, 0))])
    t = t.union(cq.Solid.makeCylinder(P["beadD"] / 2, 2.5, cq.Vector(port_x0 - P["portLength"] + 4.0, y, zc), cq.Vector(1, 0, 0)))
    t = t.cut(cq.Solid.makeCylinder(P["portD"] / 2, P["portLength"] + 1, cq.Vector(port_x0 - P["portLength"] - 0.5, y, zc), cq.Vector(1, 0, 0)))
    tubes.append(t)

PARTS = {"冷板基板（流道铣削）": base, "盖板（受热面 1.5 mm）": lid, "进口接头座": bosses[0], "出口接头座": bosses[1],
         "进口接管 Ø16/Ø12": tubes[0], "出口接管 Ø16/Ø12": tubes[1]}
MATERIALS = {k: "aluminum" for k in PARTS}
s0 = 0.0
for i, f in enumerate(fluid):
    t0, t1 = P["Tin"] + rise * s0 / path_mm, P["Tin"] + rise * (s0 + seg_len[i]) / path_mm
    name = f"冷却液 · 第 {i + 1} 程 {t0:.1f}→{t1:.1f} °C"
    PARTS[name] = f
    MATERIALS[name] = "coolant"
    s0 += seg_len[i]
DENSITIES = {k: (P["coolantDensity"] if MATERIALS[k] == "coolant" else P["alDensity"]) for k in PARTS}
NAME = "电池水冷板热-流估算模型"
vols = {k: w.val().Volume() for k, w in PARTS.items()}
DENSITY = sum(vols[k] * DENSITIES[k] for k in PARTS) / sum(vols.values())   # 体积加权，使总质量 = 各部件质量之和
result = cq.Workplane("XY").newObject([cq.Compound.makeCompound([w.val() for w in PARTS.values()])])

note = "一维模型，与示例页面 calculate() 同式（默认工况）"
METRICS = [
    {"label": "出口温度", "value": f"{T_out:.2f}", "unit": "°C", "note": note},
    {"label": "最高壁面温度", "value": f"{T_max:.2f}", "unit": "°C", "note": note},
    {"label": "总压降", "value": f"{dp:.2f}", "unit": "kPa", "note": note},
    {"label": "雷诺数", "value": f"{Re:.0f}", "unit": "", "note": note},
    {"label": "对流换热系数", "value": f"{h:.1f}", "unit": "W/(m²·K)", "note": note},
    {"label": "流路总长", "value": f"{Lm:.3f}", "unit": "m", "note": note},
]

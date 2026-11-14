import cadquery as cq
import math

# 镁合金压铸 A 壳（屏幕顶盖）—— 轨 B 参考脚本（场景需求：312×217、R8、主壁 0.8、翻边高 6.5 厚 1.0、加强筋 0.8×2.0 间距 45、
# 两转轴区各 3 个 φ4.5×3.5 螺柱、顶部 10 mm 天线净空区 PC+GF 镶件、胶槽宽 3）。模具两半按概念给出外形，供爆炸/合模查看。
P = {
    "L": 312.0, "W": 217.0, "R": 8.0, "wall": 0.8, "flangeH": 6.5, "flangeT": 1.0, "draft": 1.0,
    "ribW": 0.8, "ribH": 2.0, "ribPitch": 45.0,
    "bossD": 4.5, "bossH": 3.5, "bossHoleD": 1.6, "bossN": 3, "bossPitch": 14.0, "hingeInset": 28.0,
    "antennaW": 10.0, "glueW": 3.0, "glueDepth": 0.3,
    "moldClear": 40.0, "coreH": 30.0, "cavityH": 36.0, "gateW": 60.0, "gateT": 1.2, "overflowN": 4, "overflowD": 8.0,
    "mgDensity": 1.81, "pcDensity": 1.35, "steelDensity": 7.85,
}
DENSITY = P["mgDensity"]
L, W, R, t = P["L"], P["W"], P["R"], P["wall"]
fh, ft = P["flangeH"], P["flangeT"]

# ---- A 壳主体：顶板 + 四周翻边（真实壁厚），由外轮廓拉伸后 shell 得到
outer = cq.Workplane("XY").rect(L, W).extrude(fh + t).edges("|Z").fillet(R)
shell = outer.faces("<Z").shell(-t)                       # 开口朝下的壳：顶板厚 t，四周翻边厚 t（翻边厚 1.0 由后续加厚）
# 翻边加厚到 1.0（内侧贴一圈 0.2 mm）
inner_ring = (cq.Workplane("XY").rect(L - 2 * t, W - 2 * t).rect(L - 2 * ft, W - 2 * ft).extrude(fh))
try:
    inner_ring = inner_ring.edges("|Z").fillet(R - t)
except Exception:  # noqa: BLE001
    pass
cover = shell.union(inner_ring)
# 顶面外缘圆角（A 面观感）
try:
    cover = cover.faces(">Z").edges().fillet(1.2)
except Exception:  # noqa: BLE001
    pass
# 内侧网格加强筋：X / Y 向各若干条，高 2.0，宽 0.8，从顶板内表面向下
nx = int((L - 40) // P["ribPitch"]); ny = int((W - 40) // P["ribPitch"])
xs = [(i - (nx - 1) / 2) * P["ribPitch"] for i in range(nx)]
ys = [(j - (ny - 1) / 2) * P["ribPitch"] for j in range(ny)]
ribs = cq.Workplane("XY").workplane(offset=fh - P["ribH"]).pushPoints([(x, 0) for x in xs]).rect(P["ribW"], W - 2 * ft - 4).extrude(P["ribH"] + 0.05)
ribs = ribs.union(cq.Workplane("XY").workplane(offset=fh - P["ribH"]).pushPoints([(0, y) for y in ys]).rect(L - 2 * ft - 4, P["ribW"]).extrude(P["ribH"] + 0.05))
cover = cover.union(ribs)
# 两个转轴安装区：各 3 个 φ4.5×3.5 螺柱（带 φ1.6 盲孔），位于转轴侧长边（-Y）
boss_pts = [(sx * (L / 2 - P["hingeInset"]) + (k - 1) * P["bossPitch"] * sx, -W / 2 + 14) for sx in (-1, 1) for k in range(P["bossN"])]
bosses = cq.Workplane("XY").workplane(offset=fh - P["bossH"]).pushPoints(boss_pts).circle(P["bossD"] / 2).extrude(P["bossH"] + 0.05)
bosses = bosses.cut(cq.Workplane("XY").workplane(offset=fh - P["bossH"] - 0.1).pushPoints(boss_pts).circle(P["bossHoleD"] / 2).extrude(P["bossH"] - 0.6))
cover = cover.union(bosses)
# 天线净空区：顶部 10 mm 宽条带去掉镁合金，由 PC+GF 镶件填充（屏幕侧对面长边 +Y）
antenna_cut = cq.Workplane("XY").workplane(offset=fh - 0.05).center(0, W / 2 - P["antennaW"] / 2 - 2).rect(L - 2 * R - 10, P["antennaW"]).extrude(t + 1)
cover = cover.cut(antenna_cut)
insert = cq.Workplane("XY").workplane(offset=fh).center(0, W / 2 - P["antennaW"] / 2 - 2).rect(L - 2 * R - 10, P["antennaW"]).extrude(t)
try:
    insert = insert.edges("|Z").fillet(1.0)
except Exception:  # noqa: BLE001
    pass
# 屏幕面胶槽：翻边顶端（壳口）一圈 3 mm 宽、0.3 深（在翻边端面上开槽，实际为翻边内侧台阶）
glue = cq.Workplane("XY").rect(L - 2 * ft, W - 2 * ft).rect(L - 2 * ft - 2 * P["glueW"], W - 2 * ft - 2 * P["glueW"]).extrude(P["glueDepth"])
cover = cover.cut(glue)

# ---- 模具概念：动模（型芯，壳的内腔形状在动模上）与定模（型腔）。合模状态：定模在上，动模在下，分型面在翻边顶端 z=0 平面。
mL, mW = L + 2 * P["moldClear"], W + 2 * P["moldClear"]
core = cq.Workplane("XY").rect(mL, mW).extrude(-P["coreH"]).edges("|Z").fillet(6)
core = core.union(cq.Workplane("XY").rect(L - 2 * ft, W - 2 * ft).extrude(fh - t).edges("|Z").fillet(R - ft))   # 型芯凸台 = 壳内腔
core = core.faces("<Z").workplane().pushPoints([(sx * (mL / 2 - 18), sy * (mW / 2 - 18)) for sx in (-1, 1) for sy in (-1, 1)]).hole(12.0)   # 导柱孔
cavity = cq.Workplane("XY").workplane(offset=fh + t).rect(mL, mW).extrude(P["cavityH"]).edges("|Z").fillet(6)
cavity = cavity.cut(cq.Workplane("XY").rect(L, W).extrude(fh + t + 0.01).edges("|Z").fillet(R))                   # 型腔 = 壳外形
cavity = cavity.union(cq.Workplane("XY").workplane(offset=fh + t).pushPoints([(sx * (mL / 2 - 18), sy * (mW / 2 - 18)) for sx in (-1, 1) for sy in (-1, 1)]).circle(5.9).extrude(-P["coreH"] * 0.6))  # 导柱
# 扇形浇口（转轴侧长边 -Y）与对侧 4 个溢流槽：刻在定模分型面上
gate = cq.Workplane("XY").workplane(offset=fh + t - P["gateT"]).center(0, -W / 2 - 14).rect(P["gateW"], 28).extrude(P["gateT"] + 0.05)
cavity = cavity.cut(gate)
cavity = cavity.cut(cq.Workplane("XY").workplane(offset=fh + t - 3).pushPoints([((k - 1.5) * 70, W / 2 + 10) for k in range(P["overflowN"])]).circle(P["overflowD"] / 2).extrude(3.05))
try:
    cavity = cavity.faces(">Z").edges("not %CIRCLE").chamfer(2.0)
    core = core.faces("<Z").edges("not %CIRCLE").chamfer(2.0)
except Exception:  # noqa: BLE001
    pass

result = cover.union(insert).union(core).union(cavity)

PARTS = {"镁合金 A 壳": cover, "天线区 PC+GF 镶件": insert, "动模（型芯）": core, "定模（型腔）": cavity}
MATERIALS = {"镁合金 A 壳": "aluminumCast", "天线区 PC+GF 镶件": "polymerLight", "动模（型芯）": "steelDark", "定模（型腔）": "steelDark"}
DENSITIES = {"天线区 PC+GF 镶件": P["pcDensity"], "动模（型芯）": P["steelDensity"], "定模（型腔）": P["steelDensity"]}
NAME = "镁合金 A 壳与压铸模具"

proj_area_cm2 = L * W / 100
clamp_kN = 60.0 * (L * W) / 1000 * 1.2
METRICS = [
    {"label": "投影面积", "value": round(proj_area_cm2, 1), "unit": "cm²", "note": "外形 312 × 217"},
    {"label": "锁模力估算", "value": round(clamp_kN / 9.80665, 0), "unit": "t", "note": "比压 60 MPa × 投影面积 × 安全系数 1.2"},
    {"label": "加强筋", "value": f"{nx} 纵 + {ny} 横", "unit": "条", "note": f"{P['ribW']} × {P['ribH']} mm，间距 {P['ribPitch']:g}"},
    {"label": "螺柱凸台", "value": f"{2 * P['bossN']} × φ{P['bossD']}×{P['bossH']}", "unit": "mm", "note": "两转轴区各 3 个，M2 盲孔"},
    {"label": "模具外形", "value": f"{mL:g} × {mW:g} × {P['coreH'] + P['cavityH'] + fh + t:g}", "unit": "mm", "note": "动模 + 定模合模高度（概念）"},
]

import cadquery as cq
import math

# 微通道换热器芯体 —— 轨 B 参考脚本（场景需求：24 根 16×1.3 扁管 × 300 长，管间距 8；两端 φ20 集流管；进出口 φ12 同侧；翅片简化为平直翅片）
P = {
    "tubeN": 24, "tubeW": 16.0, "tubeT": 1.3, "tubeLen": 300.0, "tubePitch": 8.0, "tubeWall": 0.35, "tubeChannels": 8,   # 扁管：真实壁厚 + 8 个微通道
    "headerD": 20.0, "headerWall": 1.2, "headerExtra": 12.0,                                                             # 集流管两端各超出扁管束 12 mm
    "portD": 12.0, "portWall": 1.0, "portLen": 30.0, "portInsert": 3.0,
    "finPerGap": 12, "finT": 0.4, "finEquivNote": "真实翅片间距 1.2 mm → 每个管间隙约 240 片，等效 12 片（厚 0.4 mm），面积按比例换算",
    "bracketT": 2.0, "bracketW": 25.0, "bracketH": 30.0, "bracketHoleD": 6.6,                                            # 两端安装支架 + M6 孔
    "aluminumDensity": 2.70,
}
DENSITY = P["aluminumDensity"]
n, w, t, L, pitch = int(P["tubeN"]), P["tubeW"], P["tubeT"], P["tubeLen"], P["tubePitch"]
stack = (n - 1) * pitch                    # 扁管束高度（Z 方向排布）
zs = [(i - (n - 1) / 2) * pitch for i in range(n)]
hd, hw = P["headerD"], P["headerWall"]
header_len = stack + t + 2 * P["headerExtra"]

# ---- 扁管（24 根，沿 X 长 300，截面 16×1.3 带 8 个微通道孔）：一根做好再 rarray
ch_w = (w - 2 * P["tubeWall"] - (P["tubeChannels"] - 1) * P["tubeWall"]) / P["tubeChannels"]
ch_h = t - 2 * P["tubeWall"]
one_tube = cq.Workplane("YZ").rect(w, t).extrude(L).translate((-L / 2, 0, 0))
try:
    one_tube = one_tube.edges("|X").fillet(t / 2 - 0.05)                                   # 扁管圆边
except Exception:  # noqa: BLE001
    pass
channels = (cq.Workplane("YZ").rarray(ch_w + P["tubeWall"], 1, P["tubeChannels"], 1).rect(ch_w, ch_h).extrude(L + 2).translate((-L / 2 - 1, 0, 0)))
one_tube = one_tube.cut(channels)
tubes = cq.Workplane("XY").newObject([one_tube.val().moved(cq.Location(cq.Vector(0, 0, z))) for z in zs])

# ---- 翅片：每个管间隙放 12 片等效平直翅片（厚 0.4，宽 16，高 = 间隙 pitch - t），沿 X 等距
gap = pitch - t
fin_list = []
fin_pitch_x = L / P["finPerGap"]
for i in range(n - 1):
    zc = (zs[i] + zs[i + 1]) / 2
    for k in range(P["finPerGap"]):
        x = -L / 2 + fin_pitch_x * (k + 0.5)
        fin_list.append(cq.Solid.makeBox(P["finT"], w, gap, cq.Vector(x - P["finT"] / 2, -w / 2, zc - gap / 2)))
fins = cq.Workplane("XY").newObject([cq.Compound.makeCompound(fin_list)])

# ---- 集流管（两端，沿 Z），真实壁厚，端盖，扁管插入孔
def header(x_center: float, with_ports: bool) -> cq.Workplane:
    h = cq.Workplane("XY").workplane(offset=-header_len / 2).center(x_center, 0).circle(hd / 2).circle(hd / 2 - hw).extrude(header_len)
    cap_bot = cq.Workplane("XY").workplane(offset=-header_len / 2 - 1.5).center(x_center, 0).circle(hd / 2).extrude(1.5)
    cap_top = cq.Workplane("XY").workplane(offset=header_len / 2).center(x_center, 0).circle(hd / 2).extrude(1.5)
    h = h.union(cap_bot).union(cap_top)
    try:
        h = h.faces(">Z").edges().fillet(1.2)
        h = h.faces("<Z").edges().fillet(1.2)
    except Exception:  # noqa: BLE001
        pass
    # 扁管插槽：穿过朝向管束一侧的管壁
    sign = -1 if x_center > 0 else 1
    for z in zs:
        h = h.cut(cq.Solid.makeBox(hw + 1, w + 0.1, t + 0.1, cq.Vector(x_center + sign * (hd / 2) - (hw + 1) / 2 - sign * 0.5, -(w + 0.1) / 2, z - (t + 0.1) / 2)))
    # 内部隔板：把集流管分成两程（典型 2-pass 布置）
    h = h.union(cq.Workplane("XY").workplane(offset=zs[n // 2] - pitch / 2 - 0.5).center(x_center, 0).circle(hd / 2 - hw + 0.05).extrude(1.0))
    if with_ports:
        for z, direction in ((zs[2], 1), (zs[-3], 1)):
            h = h.cut(cq.Solid.makeCylinder(P["portD"] / 2 + P["portWall"] + 0.05, hd / 2 + 1, cq.Vector(x_center, 0, z), cq.Vector(0, 1, 0)))
    return h
header_in = header(-L / 2 - hd / 2 + 0.5, True)     # 进出口都在这一侧（同侧）
header_out = header(L / 2 + hd / 2 - 0.5, False)

# ---- 进出口接头：φ12 铝管，真实壁厚，端面倒角，插入集流管 3 mm
ports = []
for z in (zs[2], zs[-3]):
    y0 = hd / 2 - P["portInsert"]
    port = cq.Workplane("XZ").workplane(offset=-y0).center(-L / 2 - hd / 2 + 0.5, z).circle(P["portD"] / 2 + P["portWall"]).circle(P["portD"] / 2).extrude(-P["portLen"])
    try:
        port = port.faces(">Y").chamfer(0.5)
    except Exception:  # noqa: BLE001
        pass
    ports.append(port)
port_in, port_out = ports

# ---- 两端安装支架（钣金 L 形，M6 孔），焊在集流管外侧
brackets = []
for x_center in (-L / 2 - hd / 2 + 0.5, L / 2 + hd / 2 - 0.5):
    sign = -1 if x_center < 0 else 1
    br = cq.Workplane("XY").workplane(offset=header_len / 2 - P["bracketH"]).center(x_center + sign * (hd / 2 + P["bracketT"] / 2), 0).rect(P["bracketT"], P["bracketW"]).extrude(P["bracketH"] + 6)
    foot = cq.Workplane("XY").workplane(offset=header_len / 2 + 6 - P["bracketT"]).center(x_center + sign * (hd / 2 + 8), 0).rect(16, P["bracketW"]).extrude(P["bracketT"])
    br = br.union(foot)
    br = br.faces(">Z").workplane().center(x_center + sign * (hd / 2 + 10), 0).hole(P["bracketHoleD"])
    try:
        br = br.edges("|Z").fillet(1.5)
    except Exception:  # noqa: BLE001
        pass
    brackets.append(br)
bracket_l, bracket_r = brackets

# `.val()` would take only the first of the 24 tubes: collect every solid on each stack so result == union of PARTS (rule 9).
def _solids(wp):
    return [v for v in wp.vals() if isinstance(v, cq.Shape)]
result = cq.Workplane("XY").newObject([cq.Compound.makeCompound(
    _solids(tubes) + _solids(fins) + _solids(header_in) + _solids(header_out) + _solids(port_in) + _solids(port_out) + _solids(bracket_l) + _solids(bracket_r))])

PARTS = {"铝扁管 × 24": tubes, "平直翅片（等效）": fins, "进口侧集流管": header_in, "出口侧集流管": header_out,
         "进口接头": port_in, "出口接头": port_out, "安装支架（左）": bracket_l, "安装支架（右）": bracket_r}
MATERIALS = {"铝扁管 × 24": "aluminum", "平直翅片（等效）": "aluminumCast", "进口侧集流管": "aluminum", "出口侧集流管": "aluminum",
             "进口接头": "aluminum", "出口接头": "aluminum", "安装支架（左）": "powderCoat", "安装支架（右）": "powderCoat"}
DENSITIES = {"安装支架（左）": 7.90, "安装支架（右）": 7.90}
NAME = "微通道换热器芯体"

tube_area = n * 2 * (w + t) * L / 100
real_fins = (n - 1) * int(L / 1.2)
fin_area = real_fins * 2 * w * gap / 100
METRICS = [
    {"label": "扁管外表面积", "value": round(tube_area, 1), "unit": "cm²", "note": f"{n} 根 × 周长 × {L} mm"},
    {"label": "翅片面积（真实）", "value": round(fin_area, 1), "unit": "cm²", "note": f"{real_fins} 片 × 2 面（间距 1.2 mm）"},
    {"label": "总换热面积", "value": round(tube_area + fin_area, 1), "unit": "cm²", "note": "扁管 + 翅片"},
    {"label": "翅片等效关系", "value": f"{P['finPerGap']} ≙ {int(L / 1.2)} 片/间隙", "unit": "", "note": P["finEquivNote"]},
]

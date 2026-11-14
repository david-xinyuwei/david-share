import cadquery as cq
import math

# 四通换向阀 —— 轨 B 参考脚本（场景需求：铜筒 φ34×110 壁厚 3；D 管在上，E/S/C 三管在下间距 22；先导电磁阀 φ14×45 + 两根 φ3 毛细管）
P = {
    "bodyOD": 34.0, "bodyLen": 110.0, "wall": 3.0,
    "tubeOD": 12.7, "tubeWall": 0.9, "tubeLen": 32.0, "tubeInsert": 3.0, "lowerPitch": 22.0,
    "capT": 3.0, "capFillet": 2.5,                                            # 两端封头（带圆角）
    "slideLen": 54.0, "slideOD": 26.0, "slideBore": 10.0,                    # 内部滑块（主阀芯），剖切可见
    "pistonOD": 27.6, "pistonT": 4.0,                                         # 两端活塞
    "pilotD": 14.0, "pilotLen": 45.0, "pilotOffsetY": 24.0, "pilotZ": 6.0,   # 先导电磁阀
    "capD": 3.0, "capWall": 0.5,                                              # 毛细管
    "bracketT": 1.5, "bracketW": 14.0, "bracketH": 20.0, "bracketHoleD": 4.5,  # 安装支架 + M4 孔
    "chamfer": 0.5, "copperDensity": 8.96, "steelDensity": 7.90, "brassDensity": 8.50,
}
DENSITY = P["copperDensity"]
R, L, t = P["bodyOD"] / 2, P["bodyLen"], P["wall"]

# ---- 主阀体：沿 X 的铜筒，两端封头，真实壁厚
shell = cq.Workplane("YZ").circle(R).circle(R - t).extrude(L).translate((-L / 2, 0, 0))
cap_l = cq.Workplane("YZ").circle(R).extrude(P["capT"]).translate((-L / 2 - P["capT"], 0, 0))
cap_r = cq.Workplane("YZ").circle(R).extrude(P["capT"]).translate((L / 2, 0, 0))
body = shell.union(cap_l).union(cap_r)
try:
    body = body.faces("<X").edges().fillet(P["capFillet"])
    body = body.faces(">X").edges().fillet(P["capFillet"])
except Exception:  # noqa: BLE001 — cosmetic
    pass
# 四个接管座孔：D 在顶部中央，E/S/C 在底部等距
ports = [(0.0, 1), (-P["lowerPitch"], -1), (0.0, -1), (P["lowerPitch"], -1)]
for x, s in ports:
    body = body.cut(cq.Solid.makeCylinder(P["tubeOD"] / 2 + 0.05, R + 1, cq.Vector(x, 0, 0), cq.Vector(0, 0, s)))

# ---- 四根接管（真实壁厚，端口倒角）：插入阀体 tubeInsert
tubes = []
for x, s in ports:
    z0 = s * (R - P["tubeInsert"])
    tube = cq.Workplane("XY").workplane(offset=z0 if s > 0 else z0 - P["tubeLen"]).center(x, 0).circle(P["tubeOD"] / 2).circle(P["tubeOD"] / 2 - P["tubeWall"]).extrude(P["tubeLen"])
    try:
        tube = tube.faces(">Z" if s > 0 else "<Z").chamfer(0.4)
    except Exception:  # noqa: BLE001
        pass
    tubes.append(tube)
tube_d, tube_e, tube_s, tube_c = tubes

# ---- 内部滑块（主阀芯，塑料/黄铜）与两端活塞：剖切时可见换向结构
slide = cq.Workplane("YZ").circle(P["slideOD"] / 2).extrude(P["slideLen"]).translate((-P["slideLen"] / 2 + 8, 0, 0))
slide = slide.cut(cq.Workplane("YZ").circle(P["slideBore"] / 2).extrude(P["slideLen"] + 2).translate((-P["slideLen"] / 2 + 7, 0, 0)))
slide = slide.cut(cq.Solid.makeBox(P["lowerPitch"] * 1.6, P["slideOD"], P["slideOD"] / 2, cq.Vector(-P["lowerPitch"] * 0.8 + 8, -P["slideOD"] / 2, -P["slideOD"] / 2)))  # 底部 U 形连通槽（连通 E-S 或 S-C）
piston_l = cq.Workplane("YZ").circle(P["pistonOD"] / 2).extrude(P["pistonT"]).translate((-L / 2 + 6, 0, 0))
piston_r = cq.Workplane("YZ").circle(P["pistonOD"] / 2).extrude(P["pistonT"]).translate((L / 2 - 6 - P["pistonT"], 0, 0))
rod = cq.Workplane("YZ").circle(2.0).extrude(L - 12 - 2 * P["pistonT"]).translate((-L / 2 + 6 + P["pistonT"], 0, 0))
piston_assy = piston_l.union(piston_r).union(rod)

# ---- 先导电磁阀：φ14×45 圆柱 + 顶部线圈段差 + 接线凸台，坐在阀体侧面的支座上
py_, pz = P["pilotOffsetY"], P["pilotZ"]
pilot = cq.Workplane("YZ").center(py_, pz).circle(P["pilotD"] / 2).extrude(P["pilotLen"]).translate((-P["pilotLen"] / 2, 0, 0))
pilot_coil = cq.Workplane("YZ").center(py_, pz).circle(P["pilotD"] / 2 + 2.0).extrude(18).translate((-9, 0, 0))
pilot_conn = cq.Workplane("XY").workplane(offset=pz + P["pilotD"] / 2 - 1).center(0, py_).rect(8, 6).extrude(6)
pilot = pilot.union(pilot_coil).union(pilot_conn)
try:
    pilot = pilot.faces("<X").chamfer(P["chamfer"])
    pilot = pilot.faces(">X").chamfer(P["chamfer"])
except Exception:  # noqa: BLE001
    pass
pilot_seat = cq.Workplane("XY").workplane(offset=pz - 3).center(0, (py_ + R - 4) / 2).rect(16, py_ - R + 6).extrude(6)  # 支座，连接阀体与先导阀

# ---- 两根 φ3 毛细管：从先导阀两端引到主阀体两端封头。三段直管 + 两个球形弯头（sweep 折线在 OCCT 里会得到空形体，
# 直管 + makeSphere 弯头是稳定写法；毛细管是实心表达，φ3 管壁 0.5 mm 在 STEP 中无意义）
def seg(p0, p1):
    v = cq.Vector(*p1) - cq.Vector(*p0)
    return cq.Solid.makeCylinder(P["capD"] / 2, v.Length, cq.Vector(*p0), v.normalized())
def capillary(x_end: float) -> cq.Workplane:
    sign = 1 if x_end > 0 else -1
    a = (sign * (P["pilotLen"] / 2 - 2), py_, pz)
    b = (sign * (P["pilotLen"] / 2 + 10), py_, pz)
    c = (sign * (P["pilotLen"] / 2 + 10), R * 0.55, R * 0.55)
    d = (x_end, R * 0.55, R * 0.55)
    wp = cq.Workplane("XY").newObject([seg(a, b)]).union(seg(b, c)).union(seg(c, d))
    for corner in (b, c):
        wp = wp.union(cq.Solid.makeSphere(P["capD"] / 2, cq.Vector(*corner)))
    return wp
cap_left = capillary(-L / 2 - P["capT"] + 1)
cap_right = capillary(L / 2 + P["capT"] - 1)

# ---- 安装支架：钣金 L 形带 2×M4 孔，焊在阀体下方
bracket = cq.Workplane("XY").workplane(offset=-R - P["bracketH"]).rect(P["bracketW"] * 3, P["bracketT"]).extrude(P["bracketH"] + 2).translate((0, R * 0.0, 0))
foot = cq.Workplane("XY").workplane(offset=-R - P["bracketH"]).center(0, -P["bracketW"] / 2 + P["bracketT"] / 2).rect(P["bracketW"] * 3, P["bracketW"]).extrude(P["bracketT"])
bracket = bracket.union(foot)
bracket = bracket.faces("<Z").workplane().pushPoints([(-P["bracketW"], 0), (P["bracketW"], 0)]).hole(P["bracketHoleD"])
try:
    bracket = bracket.edges("|Z").fillet(1.0)
except Exception:  # noqa: BLE001
    pass

result = body.union(tube_d).union(tube_e).union(tube_s).union(tube_c).union(slide).union(piston_assy).union(pilot).union(pilot_seat).union(cap_left).union(cap_right).union(bracket)

PARTS = {"主阀体（铜筒 + 封头）": body, "高压进气管 D": tube_d, "接管 E": tube_e, "接管 S": tube_s, "接管 C": tube_c,
         "主滑块阀芯": slide, "活塞组件": piston_assy, "先导电磁阀": pilot, "先导阀支座": pilot_seat, "毛细管（左）": cap_left, "毛细管（右）": cap_right, "安装支架": bracket}
MATERIALS = {"主阀体（铜筒 + 封头）": "copper", "高压进气管 D": "copper", "接管 E": "copper", "接管 S": "copper", "接管 C": "copper",
             "主滑块阀芯": "polymerLight", "活塞组件": "steel", "先导电磁阀": "powderCoat", "先导阀支座": "steelDark", "毛细管（左）": "copper", "毛细管（右）": "copper", "安装支架": "powderCoat"}
DENSITIES = {"主滑块阀芯": 1.40, "活塞组件": P["steelDensity"], "先导电磁阀": P["steelDensity"], "先导阀支座": P["steelDensity"], "安装支架": P["steelDensity"]}
NAME = "四通换向阀"

shell_vol = math.pi * (R ** 2 - (R - t) ** 2) * L + 2 * math.pi * R ** 2 * P["capT"]
METRICS = [
    {"label": "主阀体铜用量（壁厚 3.0）", "value": round(shell_vol * P["copperDensity"] / 1e6, 3), "unit": "kg", "note": "筒体 + 两端封头"},
    {"label": "壁厚优化到 2.2 mm", "value": round((math.pi * (R ** 2 - (R - 2.2) ** 2) * L + 2 * math.pi * R ** 2 * P["capT"]) * P["copperDensity"] / 1e6, 3), "unit": "kg", "note": "同外径，减铜 " + f"{(1 - (R ** 2 - (R - 2.2) ** 2) / (R ** 2 - (R - t) ** 2)) * 100:.0f}%"},
    {"label": "改不锈钢 2.0 mm", "value": round((math.pi * (R ** 2 - (R - 2.0) ** 2) * L + 2 * math.pi * R ** 2 * P["capT"]) * P["steelDensity"] / 1e6, 3), "unit": "kg", "note": "材料成本 20,000 元/吨 vs 铜 75,000 元/吨"},
    {"label": "接管", "value": "4 × φ12.7", "unit": "mm", "note": "D 上 / E·S·C 下，间距 22"},
]

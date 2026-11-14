import cadquery as cq
import math

# 电子膨胀阀阀体 —— 轨 B 参考脚本（尺寸取自场景需求：黄铜阀体 φ32×60、φ9.52 铜管、φ28×35 线圈组件、φ1.6 节流孔）
P = {
    "bodyOD": 32.0, "bodyH": 60.0, "boreD": 14.0, "boreDepth": 44.0,          # 阀体与主内腔
    "seatD": 1.6, "seatLen": 4.0,                                               # 节流孔
    "tubeOD": 9.52, "tubeWall": 0.8, "inletLen": 40.0, "inletZ": 22.0, "outletLen": 35.0, "tubeInsert": 6.0,
    "coilD": 28.0, "coilH": 35.0, "coilWall": 1.6, "coilNeckD": 20.0, "coilNeckH": 4.0,   # 步进电机线圈组件（塑料外壳）
    "needleD": 6.0, "needleLen": 46.0, "needleTipLen": 5.0,                    # 针阀阀芯
    "flangeD": 36.0, "flangeT": 3.0, "boltD": 3.4, "boltPitchR": 15.0, "boltN": 4,  # 阀体顶部法兰 + 4×M3 安装孔
    "oringW": 1.8, "oringDepth": 1.2, "oringD": 24.0,                           # 顶部密封槽
    "hexW": 27.0, "hexH": 8.0,                                                  # 阀体下部六角拧紧面
    "chamfer": 0.6, "fillet": 1.5,
    "brassDensity": 8.50, "copperDensity": 8.96, "steelDensity": 7.90, "polymerDensity": 1.40,
}
DENSITY = P["brassDensity"]
D, H, bore = P["bodyOD"], P["bodyH"], P["boreD"]

# ---- 阀体：圆柱 + 顶部法兰 + 底部六角面；内腔、节流孔、侧向进口孔、顶部 O 圈槽、4 个 M3 孔
body = cq.Workplane("XY").circle(D / 2).extrude(H)
flange = cq.Workplane("XY").workplane(offset=H - P["flangeT"]).circle(P["flangeD"] / 2).extrude(P["flangeT"])
hexpart = cq.Workplane("XY").workplane(offset=10.0).polygon(6, P["hexW"] / math.cos(math.pi / 6)).extrude(P["hexH"])
body = body.union(flange).union(hexpart)
body = body.faces(">Z").workplane().hole(bore, P["boreDepth"])                               # 主内腔（从顶向下）
seat = cq.Solid.makeCylinder(P["seatD"] / 2, P["seatLen"] + 0.2, cq.Vector(0, 0, H - P["boreDepth"] - P["seatLen"] - 0.1), cq.Vector(0, 0, 1))
body = body.cut(seat)                                                                      # 节流孔连通内腔与底部出口
outlet_bore = cq.Solid.makeCylinder(P["tubeOD"] / 2 - P["tubeWall"], H - P["boreDepth"] - P["seatLen"] + 0.1, cq.Vector(0, 0, -0.1), cq.Vector(0, 0, 1))
body = body.cut(outlet_bore)
# 侧向进口：接管插入孔（φ 管外径）+ 通到内腔的孔
inlet_socket = cq.Solid.makeCylinder(P["tubeOD"] / 2 + 0.05, P["tubeInsert"] + 0.1, cq.Vector(D / 2 - P["tubeInsert"], 0, P["inletZ"]), cq.Vector(1, 0, 0))
inlet_pass = cq.Solid.makeCylinder(P["tubeOD"] / 2 - P["tubeWall"], D / 2, cq.Vector(0, 0, P["inletZ"]), cq.Vector(1, 0, 0))
body = body.cut(inlet_socket).cut(inlet_pass)
# 底部出口接管插入孔
outlet_socket = cq.Solid.makeCylinder(P["tubeOD"] / 2 + 0.05, P["tubeInsert"] + 0.1, cq.Vector(0, 0, -0.1), cq.Vector(0, 0, 1))
body = body.cut(outlet_socket)
# 顶部 O 圈槽 + 4×M3 安装孔（法兰上）
oring = (cq.Workplane("XY").workplane(offset=H - P["oringDepth"]).circle(P["oringD"] / 2 + P["oringW"] / 2).circle(P["oringD"] / 2 - P["oringW"] / 2).extrude(P["oringDepth"] + 0.1))
body = body.cut(oring)
body = body.faces(">Z").workplane().polarArray(P["boltPitchR"], 0, 360, P["boltN"]).hole(P["boltD"])
try:
    body = body.faces(">Z").edges("%CIRCLE").edges(cq.selectors.RadiusNthSelector(-1)).chamfer(P["chamfer"])   # 法兰外缘倒角
except Exception:  # noqa: BLE001 — chamfer is cosmetic; the solid stays valid without it
    pass
try:
    body = body.faces("<Z").chamfer(P["chamfer"])
except Exception:  # noqa: BLE001
    pass

# ---- 铜接管：真实壁厚、端口倒角
inlet = cq.Workplane("YZ").workplane(offset=D / 2 - P["tubeInsert"]).center(0, P["inletZ"]).circle(P["tubeOD"] / 2).circle(P["tubeOD"] / 2 - P["tubeWall"]).extrude(P["inletLen"])
outlet = cq.Workplane("XY").workplane(offset=-P["outletLen"] + P["tubeInsert"]).circle(P["tubeOD"] / 2).circle(P["tubeOD"] / 2 - P["tubeWall"]).extrude(P["outletLen"])
try:
    inlet = inlet.faces(">X").chamfer(0.4)
    outlet = outlet.faces("<Z").chamfer(0.4)
except Exception:  # noqa: BLE001
    pass

# ---- 线圈组件外壳：φ28×35 塑料壳，颈部缩径坐进法兰，顶部圆角，侧面接线凸台
coil = cq.Workplane("XY").workplane(offset=H).circle(P["coilD"] / 2).extrude(P["coilH"])
coil = coil.faces(">Z").edges().fillet(P["fillet"] * 2)
connector = cq.Workplane("XY").workplane(offset=H + 8).center(P["coilD"] / 2 + 3, 0).rect(10, 8).extrude(10)
coil = coil.union(connector)
coil_cavity = cq.Workplane("XY").workplane(offset=H + P["coilWall"]).circle(P["coilD"] / 2 - P["coilWall"]).extrude(P["coilH"] - 2 * P["coilWall"])
coil = coil.cut(coil_cavity)                                                               # 真实壁厚，剖切可见线圈腔
neck = cq.Workplane("XY").workplane(offset=H - P["coilNeckH"]).circle(P["coilNeckD"] / 2).circle(P["coilNeckD"] / 2 - 1.2).extrude(P["coilNeckH"])
coil = coil.union(neck)

# ---- 线圈（铜）：壳内环形线圈
winding = (cq.Workplane("XY").workplane(offset=H + P["coilWall"] + 2).circle(P["coilD"] / 2 - P["coilWall"] - 0.5).circle(P["needleD"] / 2 + 2.5).extrude(P["coilH"] - 2 * P["coilWall"] - 6))

# ---- 针阀阀芯（不锈钢）：杆 + 圆锥尖，位于内腔中心
needle_rod = cq.Solid.makeCylinder(P["needleD"] / 2, P["needleLen"], cq.Vector(0, 0, H - P["boreDepth"] + P["needleTipLen"]), cq.Vector(0, 0, 1))
needle_tip = cq.Solid.makeCone(0.6, P["needleD"] / 2, P["needleTipLen"], cq.Vector(0, 0, H - P["boreDepth"]), cq.Vector(0, 0, 1))
needle = cq.Workplane("XY").newObject([needle_rod]).union(needle_tip)

result = body.union(inlet).union(outlet).union(coil).union(winding).union(needle)

PARTS = {"黄铜阀体": body, "进口铜管": inlet, "出口铜管": outlet, "线圈组件外壳": coil, "定子线圈": winding, "针阀阀芯": needle}
MATERIALS = {"黄铜阀体": "brass", "进口铜管": "copper", "出口铜管": "copper", "线圈组件外壳": "polymer", "定子线圈": "copperWire", "针阀阀芯": "steel"}
DENSITIES = {"进口铜管": P["copperDensity"], "出口铜管": P["copperDensity"], "线圈组件外壳": P["polymerDensity"], "定子线圈": P["copperDensity"], "针阀阀芯": P["steelDensity"]}
NAME = "电子膨胀阀"

tube_len = P["inletLen"] + P["outletLen"]
METRICS = [
    {"label": "整阀高度", "value": round(H + P["coilH"] + P["outletLen"] - P["tubeInsert"], 1), "unit": "mm", "note": "出口管端到线圈顶"},
    {"label": "铜管总长", "value": round(tube_len, 1), "unit": "mm", "note": "进口 + 出口"},
    {"label": "节流孔", "value": f"φ{P['seatD']}", "unit": "mm", "note": "针阀锥面 + 节流孔，剖切可见"},
    {"label": "安装孔", "value": f"{P['boltN']} × M3", "unit": "", "note": f"法兰 φ{P['flangeD']}，孔径 φ{P['boltD']}"},
]

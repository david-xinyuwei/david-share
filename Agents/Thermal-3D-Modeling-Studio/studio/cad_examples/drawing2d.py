import cadquery as cq
import math

# 2D 图纸 / 照片 → 3D —— 轨 B 参考脚本：按场景示例图纸 EXV-DEMO-01（电子膨胀阀阀体组件）逐项还原。
# 图纸标注：阀体 Ø32×60（H62 黄铜）、线圈座 Ø28×35（PA66）、侧接管 Ø9.52 伸出 40、轴线距阀体底 22，
# 下接管 Ø9.52 伸出 35（TP2 紫铜）、内孔 Ø14（虚线）、节流孔 Ø1.6。图上未标注的尺寸在 P 中注明「假设」。
P = {
    "bodyD": 32.0, "bodyH": 60.0, "upperD": 28.0, "upperH": 35.0,
    "capD": 20.0, "capH": 6.0,            # 假设：顶盖图上无尺寸，按图形比例取 Ø20×6（与轨 A 示例一致）
    "pipeD": 9.52, "pipeWall": 0.8, "sideL": 40.0, "sideZ": 22.0, "bottomL": 35.0,
    "boreD": 14.0, "boreBottom": 4.0, "boreTop": 56.0, "orificeD": 1.6,
    "sideSocket": 6.0,                    # 假设：侧接管插入阀体承插孔 6 mm 钎焊
    "bottomSocket": 2.5,                  # 假设：下接管承插 2.5 mm，其上为 1.5 mm 长节流孔
    "clearance": 0.03, "bodyChamfer": 0.8, "seatChamfer": 1.0,
    "brassDensity": 8.5, "copperDensity": 8.96, "plasticDensity": 1.4,
}
R = P["bodyD"] / 2
pr = P["pipeD"] / 2
pin = pr - P["pipeWall"]
x_sock = R - P["sideSocket"]

# ---- 阀体（H62 黄铜）：Ø32×60 回转体，上下外缘倒角；Ø14 内孔（z 4–56）；侧向承插孔 + 进液孔通内孔；底部承插孔 + Ø1.6 节流孔
body = cq.Workplane("XY").circle(R).extrude(P["bodyH"])
body = body.faces(">Z").edges().chamfer(P["bodyChamfer"]).faces("<Z").edges().chamfer(P["bodyChamfer"])
body = body.cut(cq.Solid.makeCylinder(P["boreD"] / 2, P["boreTop"] - P["boreBottom"], cq.Vector(0, 0, P["boreBottom"])))
body = body.cut(cq.Solid.makeCylinder(pr + P["clearance"], P["sideSocket"] + 2, cq.Vector(x_sock, 0, P["sideZ"]), cq.Vector(1, 0, 0)))
body = body.cut(cq.Solid.makeCylinder(pin, x_sock - P["boreD"] / 2 + 1.0, cq.Vector(P["boreD"] / 2 - 0.5, 0, P["sideZ"]), cq.Vector(1, 0, 0)))
body = body.cut(cq.Solid.makeCylinder(pr + P["clearance"], P["bottomSocket"] + 1, cq.Vector(0, 0, -1)))
body = body.cut(cq.Solid.makeCylinder(P["orificeD"] / 2, P["boreBottom"] - P["bottomSocket"] + 1, cq.Vector(0, 0, P["bottomSocket"] - 0.5)))

# ---- 线圈座（PA66）Ø28×35 + 顶盖 Ø20×6，顶缘倒角
seat = cq.Workplane("XY").workplane(offset=P["bodyH"]).circle(P["upperD"] / 2).extrude(P["upperH"])
seat = seat.faces(">Z").edges().chamfer(P["seatChamfer"])
seat = seat.union(cq.Workplane("XY").workplane(offset=P["bodyH"] + P["upperH"]).circle(P["capD"] / 2).extrude(P["capH"]))

# ---- 接管（TP2 紫铜 Ø9.52×0.8）：侧接管从承插孔底伸出到阀体外 40；下接管从承插孔底向下伸出 35
side = cq.Workplane("YZ").workplane(offset=x_sock).center(0, P["sideZ"]).circle(pr).circle(pin).extrude(R + P["sideL"] - x_sock)
bottom = cq.Workplane("XY").workplane(offset=-P["bottomL"]).circle(pr).circle(pin).extrude(P["bottomL"] + P["bottomSocket"])

PARTS = {"阀体（H62 黄铜）": body, "线圈座与顶盖（PA66）": seat, "侧接管（TP2 紫铜）": side, "下接管（TP2 紫铜）": bottom}
MATERIALS = {"阀体（H62 黄铜）": "brass", "线圈座与顶盖（PA66）": "polymer", "侧接管（TP2 紫铜）": "copper", "下接管（TP2 紫铜）": "copper"}
DENSITIES = {"阀体（H62 黄铜）": P["brassDensity"], "线圈座与顶盖（PA66）": P["plasticDensity"],
             "侧接管（TP2 紫铜）": P["copperDensity"], "下接管（TP2 紫铜）": P["copperDensity"]}
NAME = "电子膨胀阀阀体组件（图纸 EXV-DEMO-01）"
vols = {k: w.val().Volume() for k, w in PARTS.items()}
DENSITY = sum(vols[k] * DENSITIES[k] for k in PARTS) / sum(vols.values())   # 体积加权，使总质量 = 各部件质量之和
result = cq.Workplane("XY").newObject([cq.Compound.makeCompound([w.val() for w in PARTS.values()])])

METRICS = [
    {"label": "图纸识别尺寸", "value": 10, "unit": "处", "note": "Ø32 / Ø28 / Ø9.52 / Ø14 / Ø1.6 / 60 / 35 / 35 / 40 / 22"},
    {"label": "装配总高", "value": P["bottomL"] + P["bodyH"] + P["upperH"] + P["capH"], "unit": "mm", "note": "下接管端面至顶盖：35 + 60 + 35 + 6"},
    {"label": "阀腔容积", "value": round(math.pi * (P["boreD"] / 2) ** 2 * (P["boreTop"] - P["boreBottom"]) / 1000, 2), "unit": "cm³", "note": "Ø14 × 52 内孔"},
    {"label": "节流孔流通面积", "value": round(math.pi * (P["orificeD"] / 2) ** 2, 2), "unit": "mm²", "note": "Ø1.6"},
    {"label": "接管内径", "value": round(2 * pin, 2), "unit": "mm", "note": "Ø9.52 × 0.8 紫铜管"},
    {"label": "侧承插孔底壁厚", "value": round(x_sock - P["boreD"] / 2, 2), "unit": "mm", "note": "承插深 6（假设）后到 Ø14 内孔的余量"},
]

import cadquery as cq
import math

# 电池水冷板 —— 轨 B 参考脚本（按 CAD_PROMPT 规则 9–15 编写，供 tests/test_cad.py 与提示词 few-shot 使用）
P = {
    "plateLength": 320, "plateWidth": 180, "plateThickness": 12, "minimumWall": 1.5,
    "channelRuns": 6, "channelWidth": 10, "channelDepth": 6, "channelPitch": 25, "channelTurnX": 135,
    "coverThickness": 3.0,            # 上盖板厚（流道深 6 + 上下盖各 3 = 12）
    "cornerRadius": 6.0, "edgeChamfer": 0.8,
    "lugWidth": 22, "lugLength": 18, "lugHoleDia": 6.6, "cboreDia": 11.0, "cboreDepth": 6.0,   # M6 沉孔安装耳
    "oringWidth": 2.4, "oringDepth": 1.8, "oringInset": 6.0,
    "portOD": 12.0, "portID": 8.0, "portLength": 26.0, "portBeadOD": 13.5, "portInsert": 4.0,
    "slotLength": 60, "slotWidth": 8, "slotDepth": 0.6,
    "aluminumDensity": 2.70,
}
DENSITY = P["aluminumDensity"]
L, W, T = P["plateLength"], P["plateWidth"], P["plateThickness"]
n, w, d, pitch, tx = int(P["channelRuns"]), P["channelWidth"], P["channelDepth"], P["channelPitch"], P["channelTurnX"]
cover = P["coverThickness"]
r = pitch / 2
ys = [(i - (n - 1) / 2) * pitch for i in range(n)]
assert cover >= P["minimumWall"] and pitch - w >= P["minimumWall"]

# ---- 流道工具体（6 直段 + 5 个半圆弯 + 2 段入口引道），一次 union 后一次 cut
tools = []
for i, y in enumerate(ys):
    xmin = -L / 2 if i in (0, n - 1) else -tx
    tools.append(cq.Solid.makeBox(tx - xmin, w, d, cq.Vector(xmin, y - w / 2, -d / 2)))
half_turn = (cq.Workplane("XZ").polyline([(r - w / 2, -d / 2), (r + w / 2, -d / 2), (r + w / 2, d / 2), (r - w / 2, d / 2)]).close()
             .revolve(180, (0, 0), (0, 1)))
for i in range(n - 1):
    right = i % 2 == 0
    turn = half_turn.rotate((0, 0, 0), (0, 0, 1), -90 if right else 90).translate((tx if right else -tx, (ys[i] + ys[i + 1]) / 2, 0))
    tools.append(turn.val())
channel_tool = cq.Workplane("XY").newObject([tools[0]])
for tl in tools[1:]:
    channel_tool = channel_tool.union(tl)

# ---- 流道基板（下 2/3）：真实圆角外形 + 流道空腔 + 四角安装耳（沉孔）+ O 圈密封槽
base_t = T - cover
base = cq.Workplane("XY").box(L, W, base_t).translate((0, 0, -cover / 2))
base = base.edges("|Z").fillet(P["cornerRadius"])
# 四角安装耳（与基板同厚，向外伸出），M6 沉孔
lug_pts = [(sx * (L / 2 + P["lugLength"] / 2 - 4), sy * (W / 2 - P["lugWidth"] / 2)) for sx in (-1, 1) for sy in (-1, 1)]
lugs = (cq.Workplane("XY").pushPoints(lug_pts).rect(P["lugLength"] + 8, P["lugWidth"]).extrude(base_t).translate((0, 0, -base_t / 2 - cover / 2)))
lugs = lugs.edges("|Z").fillet(min(4.0, P["lugWidth"] / 2 - 0.5))
base = base.union(lugs)
hole_pts = [(sx * (L / 2 + P["lugLength"] / 2), sy * (W / 2 - P["lugWidth"] / 2)) for sx in (-1, 1) for sy in (-1, 1)]
base = base.faces(">Z").workplane().pushPoints(hole_pts).cboreHole(P["lugHoleDia"], P["cboreDia"], P["cboreDepth"])
# 流道空腔：从基板顶面向下 d（流道全深在基板里，盖板是平的）
channel_cavity = channel_tool.translate((0, 0, (T / 2 - cover) - d / 2 + 0.0))  # cavity top flush with base top
base = base.cut(channel_cavity)
# O 圈槽：沿基板顶面、流道区外一圈
og_w, og_d, inset = P["oringWidth"], P["oringDepth"], P["oringInset"]
ring_outer = cq.Workplane("XY").rect(L - 2 * inset, W - 2 * inset).extrude(og_d)
ring_inner = cq.Workplane("XY").rect(L - 2 * inset - 2 * og_w, W - 2 * inset - 2 * og_w).extrude(og_d)
oring_groove = ring_outer.cut(ring_inner).edges("|Z").fillet(og_w).translate((0, 0, T / 2 - cover - og_d))
base = base.cut(oring_groove)


def soft_chamfer(wp, selector, size):
    """Chamfer the straight outer edges of one face; OCCT refuses chamfers that run into fillet tangencies, so fall back
    to a smaller size and finally to no chamfer rather than failing the whole part (prompt rule 11)."""
    for s in (size, size / 2, size / 4):
        try:
            return wp.faces(selector).edges("not %CIRCLE").chamfer(s)
        except Exception:  # noqa: BLE001 — geometric failure only; the solid itself is already valid
            continue
    return wp


base = soft_chamfer(base, "<Z", P["edgeChamfer"])

# ---- 上盖板：同轮廓、减重槽（腰形）、铭牌凹区、边缘倒角
lid = cq.Workplane("XY").box(L, W, cover).translate((0, 0, T / 2 - cover / 2))
lid = lid.edges("|Z").fillet(P["cornerRadius"])
lid = (lid.faces(">Z").workplane().pushPoints([(-L / 4, W / 2 - 18), (L / 4, W / 2 - 18), (-L / 4, -W / 2 + 18), (L / 4, -W / 2 + 18)])
       .slot2D(P["slotLength"], P["slotWidth"]).cutBlind(-P["slotDepth"]))
lid = lid.faces(">Z").workplane().center(0, 0).rect(70, 24).cutBlind(-0.3)          # 铭牌凹区
lid = soft_chamfer(lid, ">Z", P["edgeChamfer"])

# ---- 进出口接头：两段直径（主体 + 密封凸环）+ 端面倒角 + 真实通孔，插入基板 portInsert mm
ports = []
for y in (ys[0], ys[-1]):
    x0 = -L / 2 - P["portLength"] + P["portInsert"]
    body = cq.Solid.makeCylinder(P["portOD"] / 2, P["portLength"], cq.Vector(x0, y, 0), cq.Vector(1, 0, 0))
    bead = cq.Solid.makeCylinder(P["portBeadOD"] / 2, 3.0, cq.Vector(x0 + 6, y, 0), cq.Vector(1, 0, 0))
    port = cq.Workplane("XY").newObject([body]).union(bead)
    try:
        port = port.faces("<X").chamfer(0.6)
    except Exception:  # noqa: BLE001
        pass
    bore = cq.Solid.makeCylinder(P["portID"] / 2, P["portLength"] + 2, cq.Vector(x0 - 1, y, 0), cq.Vector(1, 0, 0))
    ports.append(port.cut(bore))
    base = base.cut(cq.Solid.makeCylinder(P["portOD"] / 2 + 0.05, P["portInsert"] + 0.1, cq.Vector(-L / 2 - 0.1, y, 0), cq.Vector(1, 0, 0)))

inlet, outlet = ports
result = base.union(lid).union(inlet).union(outlet)

PARTS = {"流道基板": base, "上盖板": lid, "进口接头": inlet, "出口接头": outlet}
MATERIALS = {"流道基板": "aluminum", "上盖板": "anodized", "进口接头": "steel", "出口接头": "steel"}
DENSITIES = {"进口接头": 7.90, "出口接头": 7.90}
NAME = "电池水冷板"

channel_len = n * (tx + L / 2) + (n - 1) * math.pi * r
METRICS = [
    {"label": "流道中心线总长", "value": round(channel_len, 1), "unit": "mm", "note": "6 直段 + 5 半圆弯 + 入口引道"},
    {"label": "流道湿润面积", "value": round(2 * (w + d) * channel_len / 100, 1), "unit": "cm²", "note": "矩形截面周长 × 中心线长"},
    {"label": "安装孔", "value": "4 × M6 沉孔", "unit": "", "note": f"φ{P['lugHoleDia']} 通孔 / φ{P['cboreDia']}×{P['cboreDepth']} 沉孔"},
]

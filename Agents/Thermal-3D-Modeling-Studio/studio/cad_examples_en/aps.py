import cadquery as cq
import math

# APS scheduling reasoning — Track B reference script: turns the schedule into a solid scheduling sand table (3D Gantt chart), with the AI schedule and the veteran planner method on two boards side by side.
# The scheduler is ported line by line from the scenario example (workSegments / addWorkHours / option / best / simulate / schedule); METRICS use the same formulas as the page.
# X = time (10 mm/h, Monday 08:00 = 0); each board has 3 rows = lines L1–L3 (row pitch 70, row width 40). Order bars are 14 high, changeover blocks 6 high,
# late orders get a 3 mm red cap, due dates are Ø2×24 pins, breaks and line stops are light strips on the board; the board carries 8 h tick grooves and the line numbers. Colours by product family.
P = {
    "lines": [("L1", "ABC"), ("L2", "ABC"), ("L3", "C")],
    "orders": [("O01", "A", 8, 56), ("O02", "B", 7, 60), ("O03", "C", 9, 64), ("O04", "A", 6, 48), ("O05", "B", 5, 52),
               ("O06", "C", 6, 44), ("O07", "B", 4, 22), ("O08", "A", 5, 26), ("O09", "C", 6, 30), ("O10", "A", 4, 12),
               ("O11", "B", 3, 14), ("O12", "A", 5, 20)],
    "sameFamily": 0.5, "crossFamily": 2.0, "windows": [(0, 4), (4.5, 12), (12.5, 16)], "day": 24.0,
    "timeScale": 10.0, "rowPitch": 70.0, "rowWidth": 40.0, "barHeight": 14.0, "setupHeight": 6.0, "cap": 3.0,
    "dueRadius": 1.0, "dueHeight": 24.0, "tick": 8, "board": 8.0, "labelWidth": 65.0, "boardGap": 110.0, "breakHeight": 1.5,
    "eps": 1e-8, "alDensity": 2.70, "stripeDensity": 1.40, "brassDensity": 8.50,
}
EPS, WIN = P["eps"], P["windows"]


def segs(t, h):
    out, left, cur = [], h, t
    while left > EPS:
        day = math.floor(cur / P["day"])
        adv = False
        for a, b in WIN:
            s, lim = max(cur, day * 24 + a), day * 24 + b
            if s < lim - EPS:
                take = min(left, lim - s)
                out.append((s, s + take))
                left -= take
                cur = s + take
                adv = True
                if left <= EPS:
                    break
        if left > EPS:
            cur = (day + 1) * 24
        if not adv and left <= EPS:
            break
    return out


def add_h(t, h):
    s = segs(t, h)
    return s[-1][1] if s else t


def avail(t):
    tot, d = 0.0, 0
    while d * 24 < t:
        for a, b in WIN:
            tot += max(0.0, min(t, d * 24 + b) - (d * 24 + a))
        d += 1
    return tot


ORD = [{"id": i, "fam": f, "hours": hrs, "deadline": add_h(0, due)} for i, f, hrs, due in P["orders"]]


def edd(o):
    return (o["deadline"], o["id"])


def option(o, i, st):
    prev = st[i]
    setup = (P["sameFamily"] if prev["last"] == o["fam"] else P["crossFamily"]) if prev["last"] else 0
    ready = add_h(prev["free"], setup)
    end = add_h(ready, o["hours"])
    return {"o": o, "line": i, "setup": setup, "prep": segs(prev["free"], setup), "parts": segs(ready, o["hours"]),
            "end": end, "late": end > o["deadline"] + EPS}


def best(o, st, ai):
    ch = [option(o, i, st) for i, (lid, fams) in enumerate(P["lines"]) if o["fam"] in fams]
    ch.sort(key=(lambda c: (c["end"], c["line"])) if ai else (lambda c: (st[c["line"]]["free"], c["line"])))
    return ch[0]


def commit(j, st):
    st[j["line"]] = {"free": j["end"], "last": j["o"]["fam"]}


def simulate(lst, st0):
    st = [dict(s) for s in st0]
    jobs = []
    for o in sorted(lst, key=edd):
        j = best(o, st, True)
        jobs.append(j)
        commit(j, st)
    return jobs


def schedule(ai):
    pend = sorted(ORD, key=edd if ai else (lambda o: o["id"]))
    st = [{"free": 0.0, "last": None} for _ in P["lines"]]
    jobs = []
    while pend:
        chosen = best(pend[0], st, ai)
        if ai and len(pend) > 1:   # A same-family order may jump the queue only if it saves a changeover and makes no on-time order late
            base = simulate(pend, st)
            bmap = {j["o"]["id"]: j for j in base}
            bset = sum(j["setup"] for j in base)
            cands = []
            for k in range(1, len(pend)):
                c = best(pend[k], st, True)
                if st[c["line"]]["last"] != c["o"]["fam"]:
                    continue
                ts = [dict(s) for s in st]
                commit(c, ts)
                trial = [c] + simulate([o for o in pend if o["id"] != c["o"]["id"]], ts)
                safe = all((not j["late"]) or bmap[j["o"]["id"]]["late"] for j in trial)
                saving = bset - sum(j["setup"] for j in trial)
                if safe and saving > EPS:
                    cands.append((c, saving))
            cands.sort(key=lambda cs: (-cs[1],) + edd(cs[0]["o"]))
            if cands:
                chosen = cands[0][0]
        jobs.append(chosen)
        commit(chosen, st)
        pend = [o for o in pend if o["id"] != chosen["o"]["id"]]
    ms = max(j["end"] for j in jobs)
    cap = avail(ms)
    late = sum(1 for j in jobs if j["late"])
    util = [100 * sum(j["o"]["hours"] for j in jobs if j["line"] == i) / cap for i in range(len(P["lines"]))]
    return {"jobs": jobs, "ms": ms, "late": late, "setup": sum(j["setup"] for j in jobs),
            "rate": 100 * (len(jobs) - late) / len(jobs), "util": util, "avg": sum(util) / len(util)}


AI, BASE = schedule(True), schedule(False)

# ---- Solids: two scheduling sand tables
TS, RP, RW = P["timeScale"], P["rowPitch"], P["rowWidth"]
span = max(AI["ms"], BASE["ms"], max(o["deadline"] for o in ORD)) + 2   # The board reaches the latest due date so every due-date pin stands on it
FAM = {"A": "anodizedBlue", "B": "anodizedGreen", "C": "anodizedOrange"}
gaps = []
d = 0
while d * 24 < span:   # Non-working time: two 30 min breaks + night shutdown
    bounds = [0.0] + [v for w in WIN for v in w] + [24.0]
    for a, b in zip(bounds[0::2], bounds[1::2]):
        a, b = d * 24 + a, min(d * 24 + b, span)
        if b - a > EPS and b > 0:
            gaps.append((a, b))
    d += 1


def bar(t0, t1, y, z0, z1):
    return cq.Solid.makeBox((t1 - t0) * TS, RW, z1 - z0, cq.Vector(t0 * TS, y - RW / 2, z0))


def comp(solids):
    return cq.Workplane("XY").newObject([cq.Compound.makeCompound(solids)])


PARTS, MATERIALS, DENSITIES = {}, {}, {}


def add(name, wp, mat, dens):
    PARTS[name] = wp
    MATERIALS[name] = mat
    DENSITIES[name] = dens


for title, res, y0 in (("AI schedule", AI, 0.0), ("Veteran method", BASE, -(3 * RP + P["boardGap"]))):
    rows = [y0 - i * RP for i in range(3)]
    x0, x1 = -P["labelWidth"], span * TS + 20
    board = cq.Workplane("XY").newObject([cq.Solid.makeBox(x1 - x0, 3 * RP, P["board"], cq.Vector(x0, rows[2] - RP / 2, -P["board"]))])
    board = board.edges("|Z").fillet(6.0)
    for k in range(int(span // P["tick"]) + 1):   # 8 h tick grooves
        board = board.cut(cq.Solid.makeBox(1.2, 3 * RP - 12, 0.8, cq.Vector(k * P["tick"] * TS - 0.6, rows[2] - RP / 2 + 6, -0.8)))
    for i, y in enumerate(rows):
        try:
            board = board.cut(cq.Workplane("XY").center(x0 / 2, y).text(P["lines"][i][0], 16, -0.8, cut=False, combine=False,
                                                                        halign="center", valign="center"))
        except Exception:  # noqa: BLE001 — without a usable font the engraving is simply skipped
            pass
    add(f"{title} · board", board, "powderCoat", P["alDensity"])
    for fam in "ABC":
        solids = [bar(s, e, rows[j["line"]], 0, P["barHeight"]) for j in res["jobs"] if j["o"]["fam"] == fam for s, e in j["parts"]]
        add(f"{title} · {fam} family orders ×{sum(1 for j in res['jobs'] if j['o']['fam'] == fam)}", comp(solids), FAM[fam], P["alDensity"])
    setups = [bar(s, e, rows[j["line"]], 0, P["setupHeight"]) for j in res["jobs"] for s, e in j["prep"]]
    add(f"{title} · changeover {res['setup']:.1f} h", comp(setups), "aluminumCast", P["alDensity"])
    caps = [bar(s, e, rows[j["line"]], P["barHeight"], P["barHeight"] + P["cap"]) for j in res["jobs"] if j["late"] for s, e in j["parts"]]
    if caps:
        add(f"{title} · late caps ×{res['late']}", comp(caps), "anodizedRed", P["alDensity"])
    pins = [cq.Solid.makeCylinder(P["dueRadius"], P["dueHeight"], cq.Vector(j["o"]["deadline"] * TS, rows[j["line"]], 0)) for j in res["jobs"]]
    add(f"{title} · due-date pins ×{len(pins)}", comp(pins), "brass", P["brassDensity"])
    panes = [cq.Solid.makeBox((b - a) * TS, 3 * RP - 10, P["breakHeight"], cq.Vector(a * TS, rows[2] - RP / 2 + 5, 0)) for a, b in gaps]
    add(f"{title} · breaks / line stops", comp(panes), "polymerLight", P["stripeDensity"])

NAME = "APS scheduling sand table (AI schedule vs veteran method)"
vols = {k: w.val().Volume() for k, w in PARTS.items()}
DENSITY = sum(vols[k] * DENSITIES[k] for k in PARTS) / sum(vols.values())
result = cq.Workplane("XY").newObject([cq.Compound.makeCompound([w.val() for w in PARTS.values()])])

note = "Same formula as schedule() on the example page"
METRICS = [
    {"label": "Total makespan AI/veteran", "value": f"{AI['ms']:.1f} / {BASE['ms']:.1f}", "unit": "h", "note": note},
    {"label": "On-time rate AI/veteran", "value": f"{AI['rate']:.1f} / {BASE['rate']:.1f}", "unit": "%", "note": note},
    {"label": "Late orders AI/veteran", "value": f"{AI['late']} / {BASE['late']}", "unit": "orders", "note": note},
    {"label": "Changeover time AI/veteran", "value": f"{AI['setup']:.1f} / {BASE['setup']:.1f}", "unit": "h", "note": note},
    {"label": "Average utilisation AI/veteran", "value": f"{AI['avg']:.1f} / {BASE['avg']:.1f}", "unit": "%", "note": note},
    {"label": "Utilisation per line AI", "value": " / ".join(f"{P['lines'][i][0]} {u:.1f}" for i, u in enumerate(AI["util"])), "unit": "%", "note": note},
]

"""轨 B — CadQuery (OCCT B-rep) runner for GPT-6-authored CAD scripts.

The studio's main path (轨 A) has GPT-6 write a three.js *visualisation* mesh. This module is the
engineering-solid path: GPT-6 writes a CadQuery script for the same part, the script is screened
(AST allow-list), executed in an isolated child interpreter (timeout, no inherited secrets) and the
result is exported as a real STEP solid + an STL preview with B-rep metrics (volume, mass, bounding
box, surface area, solid/face count).

Script contract (see CAD_PROMPT in app.py):
    import cadquery as cq
    P = {...}                          # parameters, mm
    result = <cq.Workplane | cq.Shape | cq.Assembly>
    PARTS = {"下盖板": solid_or_workplane, ...}   # optional but preferred: named parts → glTF nodes / outliner rows
    MATERIALS = {"下盖板": "aluminum", ...}        # optional: studio-kit preset per part (default from DENSITY)
    DENSITY = 2.70                     # g/cm³, optional (default aluminium); DENSITIES = {part: g/cm³} overrides per part
    METRICS = [{"label","value","unit","note"}, ...]   # optional, computed by the script

Outputs per job: model.step (assembly with part names), model.stl (fused preview), model.glb (named nodes, mm, Y-up),
parts.json (per-part volume / mass / faces / material preset).

CLI:  python cad_runner.py <script.py> <out_dir> [--timeout 120]   → prints one JSON object.
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

# Modules the generated script may import. Anything else (os, subprocess, socket, ...) is rejected before execution.
ALLOWED_MODULES = {"cadquery", "math", "cmath", "itertools", "functools", "operator", "typing", "dataclasses",
                   "collections", "statistics", "random", "json", "re"}
# Names that must never be called/referenced: dynamic execution, file/OS access, exporting from inside the script.
FORBIDDEN_NAMES = {"__import__", "exec", "eval", "compile", "open", "input", "breakpoint", "globals", "locals", "vars",
                   "getattr", "setattr", "delattr", "exit", "quit", "help", "memoryview", "__builtins__", "__loader__",
                   "__spec__", "__file__"}
FORBIDDEN_ATTRS = {"exporters", "export", "save", "exportStep", "exportStl", "exportBrep", "exportSvg", "importers",
                   "__dict__", "__class__", "__subclasses__", "__globals__", "__code__", "__builtins__", "system", "popen"}
MAX_SCRIPT_CHARS = 20000
DEFAULT_TIMEOUT = 120


def extract_code(text: str) -> str:
    """Pull the Python source out of a model reply (sentinel block, fenced block, or raw)."""
    text = text.strip()
    if "<<<CAD>>>" in text:
        text = text.split("<<<CAD>>>", 1)[1].split("<<<END>>>", 1)[0].strip()
    m = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, re.S)
    if m:
        text = m.group(1).strip()
    return text + "\n"


def validate_code(code: str) -> str | None:
    """Static screening of the generated script; returns an error message or None when it may run."""
    if len(code) > MAX_SCRIPT_CHARS:
        return f"脚本过长（{len(code)} 字符 > {MAX_SCRIPT_CHARS}）"
    try:
        tree = ast.parse(code, "<cad_script>")
    except SyntaxError as e:
        return f"语法错误：{e.msg}（第 {e.lineno} 行）"
    has_cq = False
    has_result = False
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for name in names:
                root = name.split(".")[0]
                if root not in ALLOWED_MODULES:
                    return f"不允许导入模块：{name}"
                if root == "cadquery":
                    has_cq = True
        elif isinstance(node, ast.Name):
            if node.id in FORBIDDEN_NAMES:
                return f"脚本使用了不允许的名称：{node.id}"
            if isinstance(node.ctx, ast.Store) and node.id == "result":
                has_result = True
        elif isinstance(node, ast.Attribute):
            if node.attr in FORBIDDEN_ATTRS or (node.attr.startswith("__") and node.attr.endswith("__")):
                return f"脚本使用了不允许的属性：.{node.attr}"
        elif isinstance(node, (ast.AsyncFunctionDef, ast.Await, ast.AsyncFor, ast.AsyncWith, ast.Global, ast.Nonlocal)):
            return f"脚本包含不允许的语法：{type(node).__name__}"
    if not has_cq:
        return "脚本未导入 cadquery"
    if not has_result:
        return "脚本未给 result 变量赋值"
    return None


# ------------------------------------------------------------------ executed inside the child process
_CHILD_TEMPLATE = r'''
import json, os, sys, time
# `python -I` ignores PYTHONIOENCODING, and a GBK console would choke on "mm²" in a metric label.
for _s in (sys.stdout, sys.stderr):
    _s.reconfigure(encoding="utf-8", errors="replace")
_t0 = time.time()
_out, _script = sys.argv[1], sys.argv[2]
with open(_script, encoding="utf-8") as _f:
    _src = _f.read()
_ns = {"__name__": "__cad__"}
exec(compile(_src, "<cad_script>", "exec"), _ns)
import cadquery as cq
from cadquery import exporters
def _to_shape(obj, what):
    if isinstance(obj, cq.Assembly):
        return obj.toCompound()
    if isinstance(obj, cq.Workplane):
        vals = [v for v in obj.vals() if isinstance(v, cq.Shape)]
        if not vals:
            raise ValueError(f"{what} Workplane 栈上没有形体（请以 .extrude/.union 等生成实体的调用结束）")
        return vals[0] if len(vals) == 1 else cq.Compound.makeCompound(vals)
    if isinstance(obj, cq.Shape):
        return obj
    raise TypeError(f"{what} 类型不支持：{type(obj).__name__}（需为 Workplane / Shape / Assembly）")
res = _ns.get("result")
if res is None:
    raise ValueError("脚本执行完毕但 result 为 None")
shape = _to_shape(res, "result")
solids = shape.Solids()
if not solids:
    raise ValueError("result 不包含任何 Solid —— 请检查拉伸方向或布尔运算")
vol = float(shape.Volume()); area = float(shape.Area()); bb = shape.BoundingBox()
density = float(_ns.get("DENSITY", 2.70))
densities = _ns.get("DENSITIES") if isinstance(_ns.get("DENSITIES"), dict) else {}
materials = _ns.get("MATERIALS") if isinstance(_ns.get("MATERIALS"), dict) else {}
_PRESETS = ("aluminum", "aluminumCast", "anodized", "copper", "brass", "steel", "steelDark", "powderCoat", "polymer",
            "polymerLight", "rubber", "coolant", "refrigerant", "glass", "copperWire", "pcb", "cardboard", "wood",
            "anodizedBlue", "anodizedGreen", "anodizedOrange", "anodizedRed")
_DENSITY_PRESET = {2.70: "aluminum", 8.96: "copper", 8.50: "brass", 7.90: "steel", 1.40: "polymer"}
# Named parts: the glTF nodes the viewer's outliner lists. Fall back to one node per solid of `result`.
parts_in = _ns.get("PARTS")
parts = []
_part_keys = []   # MATERIALS / DENSITIES are keyed by the full name; only the display name is cut to 60 characters
if isinstance(parts_in, dict) and parts_in:
    for name, obj in list(parts_in.items())[:40]:
        sh = _to_shape(obj, f"PARTS[{name!r}]")
        if sh.Solids():
            parts.append((str(name)[:60], sh))
            _part_keys.append(name)
if not parts:
    parts = [(f"实体 {i + 1}" if len(solids) > 1 else "实体", s) for i, s in enumerate(solids[:40])]

# ---- Edge break (锐边倒钝): real B-rep fillets on the sharp edges the script left. A sharp edge has no width, so neither
# a studio MatCap nor reflections can put a highlight on it and the part reads as a block; machined parts carry a general
# edge break anyway. Radius from the part size (R0.3–1.2 mm), limited per edge by the effective width (2·area/perimeter) of
# both adjacent faces; tangent edges are left alone. All candidates are tried in one OCCT fillet; if that fails, they are
# added in chunks of 12 with bisection, every result checked (one valid solid, volume within 5 %). Bounded by a time budget.
# Script control: EDGE_FINISH = 0 / False keeps every edge as written; EDGE_FINISH = <mm> sets the radius.
def _edge_finish(so, target, rmin, deadline):
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
    bb = so.BoundingBox()
    dims = sorted((bb.xlen, bb.ylen, bb.zlen))
    r_part = min(target, 0.06 * dims[1])
    if r_part < rmin:
        return so, 0, 0
    width = {}
    def eff(f):
        v = width.get(f)
        if v is None:
            per = sum(e.Length() for e in f.Edges())
            v = 2.0 * f.Area() / per if per > 1e-9 else 0.0
            width[f] = v
        return v
    cands = []
    for e, fs in so._entitiesFrom("Edge", "Face").items():
        uniq = []
        for f in fs:
            if not any(f.isSame(u) for u in uniq):
                uniq.append(f)
        if len(uniq) != 2:
            continue                                   # seam or free edge
        length = e.Length()
        r = min(r_part, 0.4 * eff(uniq[0]), 0.4 * eff(uniq[1]), 0.35 * length)
        if r < rmin:
            continue
        p = e.positionAt(0.5)
        n1, n2 = uniq[0].normalAt(p), uniq[1].normalAt(p)
        if n1.dot(n2) > 0.94:
            continue                                   # < 20°: already smooth (fillet boundary, tangent faces)
        # Outside face 1, inside face 2: inside the solid only for a concave edge (union vs intersection of half-spaces).
        convex = not so.isInside(p + (n1 - n2) * min(0.02, 0.1 * r))
        cands.append((0 if convex else 1, -length, round(r, 3), e))
    if not cands:
        return so, 0, 0
    cands.sort(key=lambda c: (c[0], c[1]))           # convex (highlight-carrying) and long edges first
    cands = cands[: int(os.environ.get("CAD_EDGE_FINISH_MAX_EDGES", "220"))]   # bounds STEP size and OCCT time per solid
    v0 = so.Volume()
    def attempt(items):
        if time.time() > deadline:
            return None
        mk = BRepFilletAPI_MakeFillet(so.wrapped)
        try:
            for c in items:   # OCCT can reject an edge already in Add ("ChFi3d_Builder:only 2 faces"), not only in Build
                mk.Add(c[2], c[3].wrapped)
            mk.Build()
            if not mk.IsDone():
                return None
            sols = cq.Shape.cast(mk.Shape()).Solids()
        except Exception:
            return None
        if len(sols) != 1 or not sols[0].isValid() or abs(sols[0].Volume() - v0) > 0.05 * v0:
            return None
        return sols[0]
    best = attempt(cands)
    if best is not None:
        return best, len(cands), len(cands)
    state = {"best": so, "ok": []}
    def grow(chunk):
        if not chunk or time.time() > deadline:
            return
        res = attempt(state["ok"] + chunk)
        if res is not None:
            state["best"], state["ok"] = res, state["ok"] + chunk
        elif len(chunk) > 1:
            grow(chunk[: len(chunk) // 2])
            grow(chunk[len(chunk) // 2:])
    for i in range(0, len(cands), 12):
        grow(cands[i:i + 12])
    return state["best"], len(state["ok"]), len(cands)

finish = {"radius_mm": 0, "edges": 0, "candidates": 0, "elapsed_s": 0.0, "skipped": []}
_ef = _ns.get("EDGE_FINISH", os.environ.get("CAD_EDGE_FINISH", "auto"))
if isinstance(_ef, bool):
    _ef = "auto" if _ef else 0
if isinstance(_ef, str) and _ef.strip().lower() in ("0", "off", "false", "none", ""):
    _ef = 0
_diag = (bb.xlen ** 2 + bb.ylen ** 2 + bb.zlen ** 2) ** 0.5
try:
    _target = min(max(0.004 * _diag, 0.3), 1.2) if _ef == "auto" else max(0.0, min(float(_ef), 5.0))
except (TypeError, ValueError):
    _target = 0.0
_stl_shape = shape
if _target > 0:
    _t1 = time.time()
    _deadline = _t1 + float(os.environ.get("CAD_EDGE_FINISH_BUDGET_S", "40"))
    _rmin = max(0.15, 0.25 * _target)
    _new = []
    # Fair share of the time budget per solid (unused time rolls over), so the first complex part cannot starve the rest.
    _queue = sum(len(_sh.Solids()) for _, _sh in parts if len(_sh.Solids()) <= 12)
    for _name, _sh in parts:
        _sols = _sh.Solids()
        if len(_sols) > 12:
            finish["skipped"].append(f"{_name}（{len(_sols)} 个实体的阵列）")
            _new.append((_name, _sh))
            continue
        _done = []
        for _so in _sols:
            _share = max(0.0, _deadline - time.time()) / max(_queue, 1)
            _queue -= 1
            _fs, _n_ok, _n_c = _edge_finish(_so, _target, _rmin, time.time() + _share)
            _done.append(_fs)
            finish["edges"] += _n_ok
            finish["candidates"] += _n_c
        _new.append((_name, _done[0] if len(_done) == 1 else cq.Compound.makeCompound(_done)))
    if finish["edges"]:
        # result is the script's (possibly fused) solid: correct its exact volume / area by what the fillets changed per part.
        vol += sum(float(n.Volume()) for _, n in _new) - sum(float(o.Volume()) for _, o in parts)
        area += sum(float(n.Area()) for _, n in _new) - sum(float(o.Area()) for _, o in parts)
        parts = _new
        _stl_shape = cq.Compound.makeCompound([s for _, n in parts for s in n.Solids()])
    finish.update(radius_mm=round(_target, 2), elapsed_s=round(time.time() - _t1, 1))
t_model = time.time() - _t0
# Two assemblies: STEP carries the real (possibly Chinese) part names for SolidWorks / NX; the glTF writer in OCCT
# mangles non-ASCII node names (observed: '实体' → Latin-1 bytes), so glTF nodes get ASCII ids and parts.json maps
# id → display name → material preset for the viewer's outliner.
assy_step = cq.Assembly(name=str(_ns.get("NAME") or "model")[:60])
assy_glb = cq.Assembly(name="model")
part_rows = []
for i, (name, sh) in enumerate(parts, 1):
    key = _part_keys[i - 1] if _part_keys else name
    d = float(densities.get(key, density))
    preset = materials.get(key) if materials.get(key) in _PRESETS else _DENSITY_PRESET.get(round(d, 2), "aluminum")
    v = float(sh.Volume())
    node_id = f"part_{i}"
    part_rows.append({"id": node_id, "name": name, "volume_mm3": v, "mass_kg": v * d / 1e6, "density_g_cm3": d,
                      "faces": len(sh.Faces()), "solids": len(sh.Solids()), "material": preset})
    assy_step.add(sh, name=name)
    assy_glb.add(sh, name=node_id)
assy_step.export(_out + "/model.step", exportType="STEP")
exporters.export(cq.Workplane("XY").newObject([_stl_shape]), _out + "/model.stl", tolerance=0.08, angularTolerance=0.3)
# glTF: mm units, OCCT rotates the root to Y-up. 0.05 mm chord keeps large bores' silhouettes round; 0.3 rad gives a
# small edge-break fillet ~6 segments per 90° (exact normals from OCCT make it shade smooth). At 0.08 rad every R0.6
# fillet became ~20 strips and a valve body's glb grew from 0.8 MB to 16 MB.
assy_glb.export(_out + "/model.glb", exportType="GLTF", tolerance=0.05, angularTolerance=0.3)
with open(_out + "/parts.json", "w", encoding="utf-8") as _pf:
    json.dump(part_rows, _pf, ensure_ascii=False)
t_export = time.time() - _t0 - t_model
def _fmt(v):
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, (int, float)):  # scripts tend to leave raw floats (1866.349540849362 mm) in METRICS
        return f"{v:g}" if abs(v) < 1e-3 or abs(v) >= 1e6 else f"{v:.2f}".rstrip("0").rstrip(".")
    return str(v)[:120]
extra = [m for m in (_ns.get("METRICS") or []) if isinstance(m, dict) and m.get("label")][:6]
P = _ns.get("P") if isinstance(_ns.get("P"), dict) else {}
# The marker is only known to this child template: a generated script printing its own JSON cannot impersonate the result.
print("__CADQUERY_RESULT__ " + json.dumps({
    "ok": True,
    "volume_mm3": vol, "area_mm2": area, "density_g_cm3": density, "mass_kg": vol * density / 1e6,
    "bbox_mm": [bb.xlen, bb.ylen, bb.zlen], "solids": len(solids),
    "faces": sum(r["faces"] for r in part_rows) if finish["edges"] else len(shape.Faces()),   # after the edge break
    "parts": part_rows,
    "edge_finish": finish,
    "extra_metrics": [{k: _fmt(m.get(k, "")) for k in ("label", "value", "unit", "note")} for m in extra],
    "params": {str(k)[:40]: v for k, v in P.items() if isinstance(v, (int, float, str, bool))},
    "t_model_s": round(t_model, 1), "t_export_s": round(t_export, 1),
}, ensure_ascii=False))
'''


RESULT_MARKER = "__CADQUERY_RESULT__ "


def kill(proc: subprocess.Popen) -> None:
    """Terminate a running child started by run_script and mark it so the result reads 'cancelled', not 'exit code N'
    (Windows reports exit code 1 after TerminateProcess, POSIX a negative signal — the marker is platform-independent)."""
    proc._cad_killed = True  # type: ignore[attr-defined]
    if proc.poll() is None:
        proc.kill()


def run_script(code: str, out_dir: Path, timeout: int = DEFAULT_TIMEOUT, python: str | None = None,
               on_start: Callable[[subprocess.Popen], None] | None = None) -> dict[str, Any]:
    """Execute an already-validated CadQuery script in a child interpreter. Returns metrics JSON or {"ok": False, "error"}.

    `on_start` receives the Popen handle so a caller whose client went away can kill() the child instead of
    leaving an orphaned OCCT process running to the timeout."""
    out_dir.mkdir(parents=True, exist_ok=True)
    script = out_dir / "model.py"
    script.write_text(code, encoding="utf-8")
    child = out_dir / "_child.py"
    child.write_text(_CHILD_TEMPLATE, encoding="utf-8")
    # The child never needs the app's secrets or Azure config.
    env = {k: v for k, v in os.environ.items()
           if not k.upper().startswith(("AOAI_", "PORTAL_", "AZURE_", "MSI_", "IDENTITY_"))}
    env.update({"PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1", "OMP_NUM_THREADS": "2"})
    t0 = time.time()
    proc = subprocess.Popen([python or sys.executable, "-I", str(child), str(out_dir), str(script)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                            cwd=str(out_dir), env=env)
    if on_start:
        on_start(proc)
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        return {"ok": False, "elapsed_s": round(time.time() - t0, 1),
                "error": f"CadQuery 脚本执行超过 {timeout} s —— 通常是对大量重复件逐个 union；请改用 Compound 或减少重复件数量"}
    elapsed = round(time.time() - t0, 1)
    if getattr(proc, "_cad_killed", False):
        return {"ok": False, "error": "CadQuery 子进程被终止（任务已取消）", "elapsed_s": elapsed}
    last = next((line[len(RESULT_MARKER):] for line in reversed((stdout or "").strip().splitlines()) if line.startswith(RESULT_MARKER)), "")
    # The result line is printed after the exports succeed; a non-zero exit after that is the known
    # OCP/VTK teardown crash on Windows (0xC0000374), not a modelling failure — trust the JSON + files.
    if last:
        try:
            data = json.loads(last)
        except json.JSONDecodeError:
            data = None
        if data and data.get("ok") and all((out_dir / n).exists() for n in ("model.step", "model.stl", "model.glb", "parts.json")):
            data["elapsed_s"] = elapsed
            for key, name in (("step_bytes", "model.step"), ("stl_bytes", "model.stl"), ("glb_bytes", "model.glb")):
                p = out_dir / name
                data[key] = p.stat().st_size if p.exists() else 0
            return data
    err = (stderr or stdout or "").strip()
    # The last traceback lines are what the model needs to repair the script on retry.
    tail = "\n".join(err.splitlines()[-12:])
    return {"ok": False, "error": tail or f"exit code {proc.returncode}", "elapsed_s": elapsed}


def main() -> int:
    import argparse

    for stream in (sys.stdout, sys.stderr):   # a GBK console cannot print "mm²" or replacement characters from the child
        stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Validate and run a CadQuery script, exporting STEP/STL/GLB + metrics")
    ap.add_argument("script")
    ap.add_argument("out_dir")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    a = ap.parse_args()
    code = Path(a.script).read_text(encoding="utf-8")
    problem = validate_code(code)
    if problem:
        print(json.dumps({"ok": False, "error": problem}, ensure_ascii=False))
        return 2
    result = run_script(code, Path(a.out_dir), a.timeout)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())

"""Pre-generate the 轨 B (CadQuery → STEP) result for each scenario that has a reference script in cad_examples/.

No model call: the scripts are hand-written, OCCT-verified CadQuery sources that follow the same CAD_PROMPT contract GPT-6
is asked to follow (PARTS / MATERIALS / DENSITIES / NAME, real fillets, bores, grooves). They run through the very same
cad_runner.run_script that serves live requests, so cad_cache/<id>/ holds exactly what a live job would hold:
model.step, model.stl, model.glb, model.py, parts.json — plus meta.json with the metrics and provenance.

Usage (inside the app venv):
    python pregen_cad.py                 # every cad_examples/<id>.py whose cad_cache/<id>/ is missing or built from a different script
    python pregen_cad.py --force         # rebuild all
    python pregen_cad.py coldplate exv   # specific scenarios
    python pregen_cad.py --timeout 300   # OCCT budget per script (default 300 s; a cold OCCT import alone is ~25 s on Windows)
    python pregen_cad.py --lang en       # English UI: cad_cache_en/<id>/ = the solids of cad_cache/<id>/ under the names of
                                         # cad_examples_en/<id>.py (made by cad_i18n.py); see derive()
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import cad_runner
from scenarios import SCENARIOS

BASE = Path(__file__).resolve().parent
EXAMPLES = BASE / "cad_examples"
CACHE = BASE / "cad_cache"
DIRS = {"zh": (EXAMPLES, CACHE), "en": (BASE / "cad_examples_en", BASE / "cad_cache_en")}
GEOMETRY_KEYS = ("volume_mm3", "mass_kg", "area_mm2", "faces", "solids", "bbox_mm")
ARTEFACTS = ("model.step", "model.stl", "model.glb", "model.py", "parts.json")
STEP_STR = re.compile(r"'(?:[^']|'')*'")                              # ISO 10303-21 string literal ('' = quote)
HAN = re.compile(r"[\u3000-\u303f\u3400-\u9fff\uf900-\ufaff\uff00-\uffef]")   # CJK ideographs and full-width punctuation
ARRAY_NOTE = re.compile(r"^(.*)（(\d+) 个实体的阵列）$")                    # cad_runner's edge_finish.skipped entry
NUM = re.compile(r"\d+(?:\.\d+)?")


def unwrap(lit: str) -> str:
    """A STEP writer may break a long line inside a string; line ends carry no meaning in ISO 10303-21."""
    return lit.replace("\r", "").replace("\n", "")


def metric_numbers(rows: list[dict]) -> list[list[str]]:
    return [NUM.findall(str(m.get("value", ""))) for m in rows]


def replace_dir(staging: Path, dest: Path) -> None:
    """Swap the finished staging directory in. OneDrive (or an AV scanner) can hold a handle on the old directory, which
    makes rmtree fail with WinError 5 although its files are gone: retry, then update the files in place, meta.json last
    (the app only serves a directory whose six artefacts all exist)."""
    for _ in range(4):
        try:
            if dest.exists():
                shutil.rmtree(dest)
            staging.rename(dest)
            return
        except PermissionError:
            time.sleep(1.5)
    dest.mkdir(parents=True, exist_ok=True)
    for name in ARTEFACTS:
        shutil.copyfile(staging / name, dest / name)
    shutil.copyfile(staging / "meta.json", dest / "meta.json")
    for extra in dest.iterdir():
        if extra.name not in ARTEFACTS + ("meta.json",):
            extra.unlink()
    shutil.rmtree(staging, ignore_errors=True)


def cadquery_version() -> str:
    """Recorded in meta.json for provenance; read from package metadata so the (slow) kernel is never imported here."""
    if importlib.util.find_spec("cadquery") is None:
        return "missing"
    try:
        from importlib.metadata import version
        return version("cadquery")
    except Exception:  # noqa: BLE001
        return "unknown"


def summary_for(scenario: dict, result: dict, lang: str = "zh") -> str:
    names = " / ".join(p["name"] for p in result["parts"][:6])
    if lang == "en":
        n = len(result["parts"])
        return (f"Reference B-rep solid of the {scenario.get('title_en') or scenario['title']} (pre-generated with CadQuery / OCCT, "
                f"not this GPT-6 response): {names}{' and more' if n > 6 else ''}, {n} parts; {result['faces']} faces, mass "
                f"{result['mass_kg']:.3f} kg. Real fillets, holes, slots and wall thickness, identical to the STEP; click Generate STEP "
                f"to have GPT-6 rebuild it live.")
    more = f" 等 {len(result['parts'])} 个部件" if len(result["parts"]) > 6 else f"，共 {len(result['parts'])} 个部件"
    return (f"{scenario['title']}的参考 B-rep 实体（CadQuery / OCCT 预生成，非本次 GPT-6 输出）：{names}{more}；"
            f"{result['faces']} 个面，质量 {result['mass_kg']:.3f} kg。真实圆角、孔、槽与壁厚，与 STEP 一致；点「生成 STEP」可由 GPT-6 现场重建。")


def same(a, b) -> bool:
    if isinstance(a, list) or isinstance(b, list):
        return isinstance(a, list) and isinstance(b, list) and len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, float) or isinstance(b, float):
        return isinstance(a, (int, float)) and isinstance(b, (int, float)) and abs(a - b) <= 1e-9 * max(1.0, abs(b))
    return a == b


def plain_runs(jobs: list[tuple[str, Path]], timeout: int) -> list[dict]:
    """Run scripts in parallel with the edge break off: the solids are then exactly what each script builds, independent
    of machine load, so equivalent scripts agree to the last digit. The child inherits CAD_EDGE_FINISH; a script's own
    EDGE_FINISH would win, so derive() also checks that no edge was broken."""
    old = os.environ.get("CAD_EDGE_FINISH")
    os.environ["CAD_EDGE_FINISH"] = "0"
    try:
        with ThreadPoolExecutor(len(jobs)) as ex:
            return list(ex.map(lambda j: cad_runner.run_script(j[0], j[1], timeout=timeout), jobs))
    finally:
        if old is None:
            os.environ.pop("CAD_EDGE_FINISH")
        else:
            os.environ["CAD_EDGE_FINISH"] = old


def glb_json_ascii(path: Path) -> bool:
    b = path.read_bytes()
    return b[16:20] == b"JSON" and b[20:20 + int.from_bytes(b[12:16], "little")].isascii()


def derive(scenario: dict, timeout: int, lang: str) -> bool:
    """English cache = the Chinese cache's solids under the English script's names. The edge break is time-budgeted, so
    two full builds of one script can differ by a few fillets (faces, area, mass), and the English page would then show
    other numbers than the Chinese page and its narration. So: run the Chinese and the English script with the edge
    break off and require identical solids, parts and metrics; then take model.glb / model.stl byte for byte from
    cad_cache/<id>/ (glTF nodes carry ASCII ids only), translate the names in its model.step, parts.json and meta.json,
    and store the English script as model.py. The STEP is handled as bytes (latin-1 round-trips every byte): each
    non-ASCII string literal of the Chinese run is replaced by the literal at the same position in the English run, counting
    only non-empty literals: unnamed geometry ('') can differ in number between two runs of one script."""
    sid = scenario["id"]
    examples, cache = DIRS[lang]
    src, script = CACHE / sid, examples / f"{sid}.py"
    zh_code, code = (EXAMPLES / f"{sid}.py").read_text(encoding="utf-8"), script.read_text(encoding="utf-8")
    problem = cad_runner.validate_code(code)
    if problem:
        print(f"[{sid}] {lang} script fails the static gate GPT-6 output must pass: {problem}")
        return False
    if (src / "model.py").read_text(encoding="utf-8").replace("\r\n", "\n") != zh_code.replace("\r\n", "\n"):
        print(f"[{sid}] cad_cache/{sid} was not built from cad_examples/{sid}.py: run pregen_cad.py {sid} first")
        return False
    zh_meta = json.loads((src / "meta.json").read_text(encoding="utf-8"))
    zh_parts = json.loads((src / "parts.json").read_text(encoding="utf-8"))
    t0 = time.time()
    if not glb_json_ascii(src / "model.glb"):
        print(f"[{sid}] cad_cache/{sid}/model.glb has non-ASCII names: it cannot be shared with the {lang} cache")
        return False
    with tempfile.TemporaryDirectory(prefix=f"cadpre-{sid}-zh-") as tz, tempfile.TemporaryDirectory(prefix=f"cadpre-{sid}-{lang}-") as te:
        a, b = plain_runs([(zh_code, Path(tz)), (code, Path(te))], timeout)
        for tag, r in (("zh", a), (lang, b)):
            if not r.get("ok"):
                print(f"[{sid}] {tag} script failed with the edge break off: {str(r.get('error', ''))[-400:]}")
                return False
            if r.get("edge_finish", {}).get("edges"):
                print(f"[{sid}] {tag} script broke {r['edge_finish']['edges']} edges although the edge break was off")
                return False
        part_keys = ("volume_mm3", "mass_kg", "density_g_cm3", "faces", "solids", "material")
        bad = [f"{k}: {a.get(k)} vs {b.get(k)}" for k in GEOMETRY_KEYS if not same(a.get(k), b.get(k))]
        bad += [f"parts: {len(a['parts'])} vs {len(b['parts'])}"] if len(a["parts"]) != len(b["parts"]) else \
            [f"part {i} {k}" for i, (p, q) in enumerate(zip(a["parts"], b["parts"]), 1) for k in part_keys if not same(p[k], q[k])]
        bad += [] if metric_numbers(a["extra_metrics"]) == metric_numbers(b["extra_metrics"]) else ["METRICS values"]
        # ... and the cache really holds this script's solids (its faces / area / mass include the fillets, the rest not)
        bad += [f"cache {k}" for k in ("bbox_mm", "solids", "density_g_cm3") if not same(zh_meta[k], a[k])]
        bad += [] if [p["name"] for p in zh_parts] == [p["name"] for p in a["parts"]] == [p["name"] for p in zh_meta["parts"]] \
            else ["cache part names"]
        bad += [] if metric_numbers(zh_meta["extra_metrics"]) == metric_numbers(a["extra_metrics"]) else ["cache METRICS"]
        if bad:
            print(f"[{sid}] {lang} script does not build the solids of cad_examples/{sid}.py: {bad[:8]}")
            return False
        names, lits = {}, {}
        for p, q in zip(a["parts"], b["parts"]):
            if names.setdefault(p["name"], q["name"]) != q["name"]:
                print(f"[{sid}] part {p['name']} has two {lang} names: {names[p['name']]} / {q['name']}")
                return False
        # Skip unnamed geometry (''): with both builds running at once, OCCT wrote some parameter curves as circles in one
        # STEP and as B-splines in the other (cold plate: 14,538 vs 14,522 literals, all of the difference ''), which
        # shifted every name after it. Names, units and contexts keep their order.
        zs, es = ([s for s in STEP_STR.findall((Path(d) / "model.step").read_bytes().decode("latin-1")) if unwrap(s) != "''"]
                  for d in (tz, te))
        if len(zs) != len(es):
            print(f"[{sid}] named STEP string count differs: {len(zs)} vs {len(es)}")
            return False
        for z, e in zip(map(unwrap, zs), map(unwrap, es)):
            if z != e and not z.isascii() and lits.setdefault(z, e) != e:
                print(f"[{sid}] a STEP string has two {lang} forms: {lits[z]} / {e}")
                return False
        en_strings = Counter(unwrap(s) for s in es if not s.isascii())
        extra = b["extra_metrics"]
    step = STEP_STR.sub(lambda m: lits.get(unwrap(m.group(0)), m.group(0)), (src / "model.step").read_bytes().decode("latin-1"))
    if Counter(unwrap(s) for s in STEP_STR.findall(step) if not s.isascii()) != en_strings:
        print(f"[{sid}] the translated STEP does not carry the names of the {lang} build")
        return False
    parts = [{**p, "name": names[p["name"]]} for p in zh_parts]
    skipped = [(f"{names.get(m[1], m[1])} ({m[2]}-solid array)" if (m := ARRAY_NOTE.match(s)) else s)
               for s in zh_meta.get("edge_finish", {}).get("skipped", [])]
    meta = {**zh_meta, "parts": parts, "extra_metrics": extra, "edge_finish": {**zh_meta.get("edge_finish", {}), "skipped": skipped},
            "step_bytes": len(step.encode("latin-1")), "script": f"{examples.name}/{sid}.py", "lang": lang,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "geometry_from": {"cache": f"{CACHE.name}/{sid}", "created_at": zh_meta.get("created_at"),
                              "check": "both scripts build identical solids, parts and METRICS with the edge break off"}}
    meta["summary"] = summary_for(scenario, meta, lang)
    step_text = step.encode("latin-1").decode("utf-8", errors="replace")
    left = [s for s in (step_text, json.dumps(parts, ensure_ascii=False), json.dumps(meta, ensure_ascii=False), code) if HAN.search(s)]
    if left:
        print(f"[{sid}] Chinese text left in the {lang} cache: {[HAN.search(s).group(0) + '…' for s in left]}")
        return False
    dest, staging = cache / sid, cache / f".{sid}.building"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    for name in ("model.glb", "model.stl"):
        shutil.copyfile(src / name, staging / name)
    shutil.copyfile(script, staging / "model.py")
    (staging / "model.step").write_bytes(step.encode("latin-1"))
    (staging / "parts.json").write_text(json.dumps(parts, ensure_ascii=False), encoding="utf-8")
    (staging / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    replace_dir(staging, dest)
    print(f"[{sid}] OK  {time.time() - t0:.1f}s  parts={len(parts)} faces={meta['faces']} mass={meta['mass_kg']:.3f} kg  "
          f"names {len(names)} / STEP strings {len(lits)}  → {cache.name}/{sid}/ (solids of {CACHE.name}/{sid})")
    return True


def build(scenario: dict, timeout: int, lang: str = "zh") -> bool:
    if lang != "zh":
        return derive(scenario, timeout, lang)
    # Offline build: give the edge-break pass more time than a live request gets (the child inherits the environment).
    os.environ.setdefault("CAD_EDGE_FINISH_BUDGET_S", "200")
    sid = scenario["id"]
    examples, cache = DIRS[lang]
    script = examples / f"{sid}.py"
    code = script.read_text(encoding="utf-8")
    problem = cad_runner.validate_code(code)
    if problem:
        print(f"[{sid}] reference script fails the static gate GPT-6 output must pass: {problem}")
        return False
    with tempfile.TemporaryDirectory(prefix=f"cadpre-{sid}-") as tmp:
        t0 = time.time()
        result = cad_runner.run_script(code, Path(tmp), timeout=timeout)
        if not result.get("ok"):
            print(f"[{sid}] OCCT failed after {result.get('elapsed_s')}s: {str(result.get('error', ''))[-400:]}")
            return False
        dest = cache / sid
        staging = cache / f".{sid}.building"
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        for name in ARTEFACTS:
            shutil.copyfile(Path(tmp) / name, staging / name)
        meta = {k: v for k, v in result.items() if k != "params"}
        meta.update({"scenario_id": sid, "summary": summary_for(scenario, result, lang), "model": "reference-script",
                     "source": "pre_generated", "script": f"{examples.name}/{sid}.py", "lang": lang,
                     "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     "cadquery": cadquery_version()})
        (staging / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        replace_dir(staging, dest)   # the directory is served only once all artefacts are in place
        print(f"[{sid}] OK  {time.time() - t0:.1f}s  parts={len(result['parts'])} faces={result['faces']} "
              f"step={result['step_bytes'] // 1024}KB glb={result['glb_bytes'] // 1024}KB  → {cache.name}/{sid}/")
        return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--lang", choices=sorted(DIRS), default="zh")
    args = ap.parse_args()
    examples, cache = DIRS[args.lang]
    by_id = {s["id"]: s for s in SCENARIOS}
    todo = []
    for script in sorted(examples.glob("*.py")):
        sid = script.stem
        if sid not in by_id:
            print(f"[{sid}] skipped: no such scenario")
            continue
        if args.ids and sid not in args.ids:
            continue
        built = cache / sid / "model.py"   # the exact script the cache was built from (cad_runner writes it)
        fresh = (all((cache / sid / n).exists() for n in ARTEFACTS) and (cache / sid / "meta.json").exists()
                 and built.read_text(encoding="utf-8").replace("\r\n", "\n") == script.read_text(encoding="utf-8").replace("\r\n", "\n"))
        if fresh and args.lang != "zh":   # derived from cad_cache/<id>: stale once the Chinese cache is rebuilt
            fresh = (json.loads((cache / sid / "meta.json").read_text(encoding="utf-8")).get("geometry_from", {}).get("created_at")
                     == json.loads((CACHE / sid / "meta.json").read_text(encoding="utf-8")).get("created_at"))
        if fresh and not args.force:
            continue
        todo.append(by_id[sid])
    if not todo:
        print("nothing to do")
        return 0
    failed = [s["id"] for s in todo if not build(s, args.timeout, args.lang)]
    print("done. failed:", failed or "none")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())

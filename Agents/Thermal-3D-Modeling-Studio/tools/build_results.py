"""Collect the measured results that the README and docs/RESULTS*.md quote into data/results.json.

    python tools/build_results.py                  # rebuild data/results.json from studio/cache and evidence/
    python tools/build_results.py --check          # exit 1 if data/results.json no longer matches those inputs
    python tools/build_results.py --compare-local  # compare your own `python pregen_cad.py` build with the recorded run

Inputs, all committed:
  Track A  studio/cache/<scenario>.json and <scenario>.en.json: 30 GPT-6 responses saved by pregen.py
  Track B  evidence/<run>/cad/<scenario>.meta.json: what `python pregen_cad.py` wrote for each reference script
  Track C  evidence/<run>/engineering/<scenario>_check.json: what `python pregen_engineering.py --out` measured
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / "studio"
EVIDENCE = ROOT / "evidence"
OUT = ROOT / "data" / "results.json"
# Fields of a reference solid that do not depend on the machine: the edge-break pass has a time budget, so faces, area and
# mass can differ by a few fillets on a slower machine; timings always differ.
STABLE_B = ("parts", "solids", "bbox_mm", "density_g_cm3")


def load_scenarios() -> list[dict]:
    spec = importlib.util.spec_from_file_location("scenarios", STUDIO / "scenarios.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SCENARIOS


def spread(values: list[float], digits: int = 1) -> dict:
    values = [v for v in values if v is not None]
    if not values:
        return {"n": 0}
    return {"n": len(values), "median": round(statistics.median(values), digits), "min": round(min(values), digits),
            "max": round(max(values), digits)}


def track_a(scenarios: list[dict]) -> dict:
    runs = []
    for s in scenarios:
        for lang, name in (("zh", f"{s['id']}.json"), ("en", f"{s['id']}.en.json")):
            path = STUDIO / "cache" / name
            if not path.is_file():
                raise SystemExit(f"missing recorded response: {path.relative_to(ROOT)}")
            r = json.loads(path.read_text(encoding="utf-8"))
            usage = r.get("usage") or {}
            reasoning = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
            completion = usage.get("completion_tokens")
            visible = completion - reasoning if completion is not None else None
            stream_s = r["latency_s"] - r["ttft_s"] if r.get("ttft_s") is not None else None
            effort = "not recorded" if "reasoning_effort" not in r else (r["reasoning_effort"] or "not sent")
            runs.append({
                "scenario": s["id"], "lang": lang, "title_zh": s["title"], "title_en": s.get("title_en") or s["title"],
                "date": str(r.get("created_at"))[:10], "model": r.get("actual_model") or r.get("model"),
                "reasoning_effort": effort, "latency_s": r["latency_s"], "ttft_s": r.get("ttft_s"),
                "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": completion, "reasoning_tokens": reasoning,
                "visible_output_tokens": visible,
                "visible_tokens_per_s_after_first_token": round(visible / stream_s, 1) if visible and stream_s else None,
                "html_lines": r["html"].count("\n") + 1, "metrics_count": len(r.get("metrics") or []),
            })
    summary = {}
    for lang in ("zh", "en", "all"):
        sel = [r for r in runs if lang == "all" or r["lang"] == lang]
        summary[lang] = {
            "runs": len(sel), "first_date": min(r["date"] for r in sel), "last_date": max(r["date"] for r in sel),
            "latency_s": spread([r["latency_s"] for r in sel]), "ttft_s": spread([r["ttft_s"] for r in sel]),
            "completion_tokens": spread([r["completion_tokens"] for r in sel], 0),
            "visible_tokens_per_s_after_first_token": spread([r["visible_tokens_per_s_after_first_token"] for r in sel]),
            "html_lines": spread([r["html_lines"] for r in sel], 0),
            "runs_with_reasoning_tokens": sum(1 for r in sel if r["reasoning_tokens"]),
            "reasoning_effort": {e: sum(1 for r in sel if r["reasoning_effort"] == e) for e in sorted({r["reasoning_effort"] for r in sel})},
        }
    return {"source": "studio/cache/<scenario>.json (zh) and <scenario>.en.json (en)",
            "clock": "pregen.py process: request sent -> response parsed (latency_s); request sent -> first visible token (ttft_s)",
            "runs": runs, "summary": summary}


def latest_run() -> Path:
    runs = sorted(p for p in EVIDENCE.glob("run-*") if p.is_dir())
    if not runs:
        raise SystemExit("no evidence/run-*/ directory")
    return runs[-1]


def solid_row(s: dict, m: dict) -> dict:
    ef = m.get("edge_finish") or {}
    return {"scenario": s["id"], "title_zh": s["title"], "title_en": s.get("title_en") or s["title"],
            "parts": len(m["parts"]), "solids": m["solids"], "faces": m["faces"], "mass_kg": round(m["mass_kg"], 3),
            "volume_cm3": round(m["volume_mm3"] / 1000, 2), "bbox_mm": [round(x, 1) for x in m["bbox_mm"]],
            "density_g_cm3": m["density_g_cm3"], "edges_broken": ef.get("edges", 0), "edge_candidates": ef.get("candidates", 0),
            "edge_radius_mm": ef.get("radius_mm", 0), "edge_break_s": ef.get("elapsed_s", 0), "occt_total_s": m["elapsed_s"],
            "step_bytes": m["step_bytes"], "glb_bytes": m["glb_bytes"]}


def track_b(scenarios: list[dict], run: Path) -> dict:
    solids = []
    for s in scenarios:
        path = run / "cad" / f"{s['id']}.meta.json"
        if not path.is_file():
            raise SystemExit(f"missing {path.relative_to(ROOT)}")
        solids.append(solid_row(s, json.loads(path.read_text(encoding="utf-8"))))
    total = lambda k: sum(x[k] for x in solids)
    summary = {"scenarios": len(solids), "parts": total("parts"), "faces": total("faces"), "edges_broken": total("edges_broken"),
               "edge_candidates": total("edge_candidates"), "occt_total_s_sum": round(total("occt_total_s"), 1),
               "occt_total_s": spread([x["occt_total_s"] for x in solids]), "step_bytes_sum": total("step_bytes"),
               "parts_spread": spread([x["parts"] for x in solids], 0)}
    return {"source": f"{run.relative_to(ROOT).as_posix()}/cad/<scenario>.meta.json (studio/cad_cache/<scenario>/meta.json of that run)",
            "clock": "pregen_cad.py: OCCT child process start -> STEP, STL and GLB written (occt_total_s); no model call",
            "solids": solids, "summary": summary}


def track_c(scenarios: list[dict], run: Path) -> dict:
    rows = []
    for s in scenarios:
        path = run / "engineering" / f"{s['id']}_check.json"
        if not path.is_file():
            raise SystemExit(f"missing {path.relative_to(ROOT)}")
        c = json.loads(path.read_text(encoding="utf-8"))
        rows.append({"scenario": s["id"], "title_zh": s["title"], "title_en": s.get("title_en") or s["title"],
                     "iou_pct": c["iou_pct"], "outline_median_px": c["outline_median_px"], "outline_p90_px": c["outline_p90_px"],
                     "render_s": c["render_s"], "spp": c["spp"], "unmatched_meshes": c["unmatched_meshes"]})
    return {"source": f"{run.relative_to(ROOT).as_posix()}/engineering/<scenario>_check.json",
            "method": "pregen_engineering.py renders model.glb (the STEP's mesh) at 2048x1152 and compares the part area segmented "
                      "from that picture with the STEP silhouette from the same camera; no scaling or shifting",
            "rows": rows,
            "summary": {"scenarios": len(rows), "iou_pct": spread([r["iou_pct"] for r in rows]),
                        "outline_median_px": spread([r["outline_median_px"] for r in rows]),
                        "render_s": spread([r["render_s"] for r in rows]), "render_s_sum": round(sum(r["render_s"] for r in rows), 1),
                        "unmatched_meshes": sum(r["unmatched_meshes"] for r in rows)}}


def build() -> dict:
    scenarios = load_scenarios()
    run = latest_run()
    machine = json.loads((run / "machine.json").read_text(encoding="utf-8"))
    return {"generated_by": "tools/build_results.py", "run": run.name, "machine": machine,
            "track_a": track_a(scenarios), "track_b": track_b(scenarios, run), "track_c": track_c(scenarios, run)}


def compare_local() -> int:
    run = latest_run()
    problems, notes = [], []
    for s in load_scenarios():
        mine = STUDIO / "cad_cache" / s["id"] / "meta.json"
        if not mine.is_file():
            problems.append(f"{s['id']}: no local build (run `python pregen_cad.py` in studio/)")
            continue
        a = solid_row(s, json.loads((run / "cad" / f"{s['id']}.meta.json").read_text(encoding="utf-8")))
        b = solid_row(s, json.loads(mine.read_text(encoding="utf-8")))
        problems += [f"{s['id']} {k}: recorded {a[k]} vs yours {b[k]}" for k in STABLE_B if a[k] != b[k]]
        notes.append(f"{s['id']:<17} faces {a['faces']:>5} vs {b['faces']:>5} | mass {a['mass_kg']:>10} vs {b['mass_kg']:>10} kg"
                     f" | OCCT {a['occt_total_s']:>6} vs {b['occt_total_s']:>6} s")
    print("\n".join(notes))
    print("\n".join(problems) or f"parts, solids, bounding boxes and densities match {run.name}")
    return 1 if problems else 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--compare-local", action="store_true")
    a = ap.parse_args()
    if a.compare_local:
        return compare_local()
    fresh = build()
    if a.check:
        saved = json.loads(OUT.read_text(encoding="utf-8"))
        bad = [k for k in fresh if fresh[k] != saved.get(k)]
        print(f"data/results.json differs in {bad}: run python tools/build_results.py" if bad else "data/results.json matches its inputs")
        return 1 if bad else 0
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(fresh, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"track_a {fresh['track_a']['summary']['all']['runs']} runs, track_b {fresh['track_b']['summary']['scenarios']} solids, "
          f"track_c {fresh['track_c']['summary']['scenarios']} renders -> {OUT.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Evidence pipeline for the validation runs.

    python tools/build_evidence.py capture --workspace <guid> --start <ISO-UTC> --minutes <n> --out <private-dir>
    python tools/build_evidence.py project --private <private-dir> --run <run-id>
    python tools/build_evidence.py            # rebuild evidence/measurements.json from evidence/runs/*/
    python tools/build_evidence.py --check    # fail if measurements.json is stale or KQL disagrees with Python

`capture` runs the raw exports and the five views in kql/ through examples/gpu_hours_client.py with
the window as the query timespan, and writes identifiable data to a private directory outside the repo.
`project` maps VM and user names to neutral labels, drops resource IDs and GPU UUIDs, and replaces
timestamps with minutes since the start of the window. The default build needs only committed files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))
from gpu_hours_client import VIEWS, GpuHoursClient  # noqa: E402

EVIDENCE = ROOT / "evidence"
RUNS = EVIDENCE / "runs"
MEASUREMENTS = EVIDENCE / "measurements.json"
IDLE_PCT = 5
DROP_GPU_FIELDS = {"VmResourceId", "GpuUuid", "Tags", "TenantId", "_ResourceId", "Type", "_BilledSize",
                   "TimeGenerated", "IngestionTime"}
RAW_QUERIES = {
    "gpu_metrics": "GpuMetrics_CL | extend IngestionTime = ingestion_time(), BilledSize = _BilledSize "
                   "| order by TimeGenerated asc, GpuId asc",
    "heartbeat": "Heartbeat | where Computer in ((GpuMetrics_CL | distinct Computer)) "
                 "| extend IngestionTime = ingestion_time(), BilledSize = _BilledSize "
                 "| project TimeGenerated, IngestionTime, BilledSize, Computer, Category, Version, OSType "
                 "| order by TimeGenerated asc",
}
METRICS = ("AllocatedGpuHours", "BusyGpuHours", "EffectiveGpuHours", "IdleGpuHours", "UtilizationPct")


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8", newline="\n")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


# ------------------------------------------------------------------ capture (private, needs Azure)
def capture(workspace: str, start: str, minutes: int, out: Path) -> None:
    t0 = _ts(start)
    t1 = t0 + timedelta(minutes=minutes)
    client = GpuHoursClient(workspace)
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"window_start_utc": start, "window_minutes": minutes, "files": {}}
    for name, kql in RAW_QUERIES.items():
        rows = client.run_kql(kql, t0, t1)
        (out / f"{name}.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
        manifest["files"][name] = len(rows)
    results = {view: client.query_view(view, t0, t1) for view in VIEWS}
    (out / "kql-results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    (out / "export-manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"captured {manifest['files']} and {len(results)} views into {out}")


# ------------------------------------------------------------------ project (private -> public)
class Labels:
    """Stable neutral labels in order of first appearance."""

    def __init__(self, prefix: str):
        self.prefix, self.map = prefix, {}

    def __call__(self, value: str) -> str:
        if value and value not in self.map:
            self.map[value] = f"{self.prefix}-{len(self.map) + 1}"
        return self.map.get(value, value)


def project(private: Path, run_id: str) -> None:
    manifest = json.loads((private / "export-manifest.json").read_text(encoding="utf-8"))
    t0 = _ts(manifest["window_start_utc"])
    minute = lambda s: int((_ts(s) - t0).total_seconds() // 60)  # noqa: E731
    delay = lambda r: round((_ts(r["IngestionTime"]) - _ts(r["TimeGenerated"])).total_seconds())  # noqa: E731
    vm, user = Labels("gpu-vm"), Labels("user")

    gpu_rows = []
    for r in json.loads((private / "gpu_metrics.json").read_text(encoding="utf-8")):
        row = {"Minute": minute(r["TimeGenerated"])}
        for k, v in r.items():
            if k in DROP_GPU_FIELDS:
                continue
            if k in ("Computer", "VmName"):
                v = vm(v)
            elif k == "Users":
                v = ",".join(user(u) for u in v.split(",")) if v else ""
            elif k == "FilePath":
                v = "/var/log/gpumon/gpu_metrics_<day>.json"
            row[k] = v
        row["IngestionDelaySeconds"] = delay(r)
        gpu_rows.append(row)
    hb_rows = [{"Minute": minute(r["TimeGenerated"]), "Computer": vm(r["Computer"]), "Category": r["Category"],
                "Version": r["Version"], "OSType": r["OSType"], "BilledSize": r["BilledSize"],
                "IngestionDelaySeconds": delay(r)}
               for r in json.loads((private / "heartbeat.json").read_text(encoding="utf-8"))]

    results = json.loads((private / "kql-results.json").read_text(encoding="utf-8"))
    pub = {}
    for view, rows in results.items():
        out_rows = []
        for i, r in enumerate(rows):
            r = dict(r)
            if "Computer" in r:
                r["Computer"] = vm(r["Computer"])
            if "User" in r:
                r["User"] = user(r["User"])
            for bucket in ("Hour", "Day"):
                if bucket in r:
                    r[bucket] = f"{bucket.lower()} {i + 1}"
            out_rows.append(r)
        pub[view] = out_rows

    run_dir = RUNS / run_id
    _write_jsonl(run_dir / "gpu-metrics.jsonl", gpu_rows)
    _write_jsonl(run_dir / "heartbeat.jsonl", hb_rows)
    _write_json(run_dir / "kql-results.json", pub)
    sources = {p.name: _sha(p) for p in sorted(private.glob("*.json")) if p.name != "export-manifest.json"}
    public = {p.name: _sha(p) for p in sorted(run_dir.iterdir()) if p.name != "raw-manifest.json"}
    _write_json(run_dir / "raw-manifest.json", {
        "window_minutes": manifest["window_minutes"],
        "private_sources_sha256": sources,
        "public_projection_sha256": public,
        "projection": "Computer/VmName -> gpu-vm-N; Users -> user-N; TimeGenerated -> Minute since window start; "
                      "IngestionTime -> IngestionDelaySeconds; dropped VmResourceId, GpuUuid, Tags, TenantId, _ResourceId; "
                      "Hour/Day labels -> ordinal",
    })
    print(f"projected {len(gpu_rows)} GPU rows and {len(hb_rows)} heartbeats into {run_dir.relative_to(ROOT)}")


# ------------------------------------------------------------------ build (committed files only)
def is_busy(r: dict) -> bool:
    return r["ProcCount"] > 0 or (r["GpuUtil"] or 0) >= IDLE_PCT


def classify(r: dict) -> str:
    """Taxonomy of one GPU-minute: idle, held (process, no kernels), partial or full."""
    sm = r["SmActive"] or 0.0
    if not is_busy(r):
        return "idle"
    if sm >= 0.8:
        return "full"
    if sm < 0.05 and (r["GpuUtil"] or 0) < IDLE_PCT:
        return "held"
    return "partial"


def segments(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for r in rows:
        c = classify(r)
        if out and out[-1]["phase"] == c and out[-1]["last"] == r["Minute"] - 1:
            out[-1]["last"] = r["Minute"]
            out[-1]["rows"].append(r)
        else:
            out.append({"phase": c, "first": r["Minute"], "last": r["Minute"], "rows": [r]})
    return out


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.fmean(xs) if xs else 0.0


def recompute(gpu: list[dict], hb: list[dict]) -> dict:
    """Pure-Python implementation of kql/per_vm.kql, kql/summary.kql and kql/per_user.kql."""
    gpus: dict[str, set] = {}
    for r in gpu:
        gpus.setdefault(r["Computer"], set()).add(r["GpuId"])
    per_vm = []
    for comp in sorted(gpus):
        running = len({h["Minute"] for h in hb if h["Computer"] == comp})
        rows = [r for r in gpu if r["Computer"] == comp]
        alloc = running * len(gpus[comp]) / 60
        busy = sum(1 for r in rows if is_busy(r)) / 60
        eff = sum(r["SmActive"] or 0.0 for r in rows) / 60
        per_vm.append({"Computer": comp, "Gpus": len(gpus[comp]), "RunningHours": running / 60,
                       "AllocatedGpuHours": alloc, "BusyGpuHours": busy, "EffectiveGpuHours": eff,
                       "IdleGpuHours": max(alloc - busy, 0.0), "UtilizationPct": 100 * eff / alloc if alloc else 0.0})
    summary = {k: sum(v[k] for v in per_vm) for k in METRICS[:4] + ("Gpus",)}
    summary["Vms"] = len(per_vm)
    summary["UtilizationPct"] = 100 * summary["EffectiveGpuHours"] / summary["AllocatedGpuHours"] if summary["AllocatedGpuHours"] else 0.0
    users: dict[tuple, dict] = {}
    for r in gpu:
        if not r["Users"]:
            continue
        owners = r["Users"].split(",")
        for u in owners:
            d = users.setdefault((u, r["Computer"]), {"User": u, "Computer": r["Computer"],
                                                      "BusyGpuHours": 0.0, "EffectiveGpuHours": 0.0})
            d["BusyGpuHours"] += 1 / len(owners) / 60
            d["EffectiveGpuHours"] += (r["SmActive"] or 0.0) / len(owners) / 60
    ordered = sorted(users.values(), key=lambda d: (-round(d["BusyGpuHours"], 9), d["User"]))
    return {"summary": summary, "per_vm": per_vm, "per_user": ordered}


def _agreement(python: dict, kql: dict) -> dict:
    diffs = []
    for view, keys in (("summary", METRICS), ("per_vm", METRICS + ("RunningHours",)),
                       ("per_user", ("BusyGpuHours", "EffectiveGpuHours"))):
        py_rows = [python[view]] if view == "summary" else python[view]
        if len(py_rows) != len(kql[view]):
            raise SystemExit(f"KQL_PYTHON_ROWCOUNT {view}: python {len(py_rows)} kql {len(kql[view])}")
        for a, b in zip(py_rows, kql[view]):
            if view == "per_user" and a["User"] != b["User"]:
                raise SystemExit(f"KQL_PYTHON_ORDER per_user: {a['User']} vs {b['User']}")
            diffs += [abs(a[k] - b[k]) for k in keys]
    worst = max(diffs) if diffs else 0.0
    if worst > 1e-6:
        raise SystemExit(f"KQL_PYTHON_MISMATCH max abs diff {worst}")
    return {"compared_values": len(diffs), "max_abs_diff": round(worst, 12)}


def _pct(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    return xs[max(0, min(len(xs) - 1, round(q * (len(xs) - 1))))]


def _r(obj):
    if isinstance(obj, float):
        return round(obj, 3)
    if isinstance(obj, dict):
        return {k: _r(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_r(v) for v in obj]
    return obj


def build_run(run_dir: Path, contract: dict) -> dict:
    gpu = _read_jsonl(run_dir / "gpu-metrics.jsonl")
    hb = _read_jsonl(run_dir / "heartbeat.jsonl")
    kql = json.loads((run_dir / "kql-results.json").read_text(encoding="utf-8"))
    python = recompute(gpu, hb)
    busy = [r for r in gpu if is_busy(r)]
    phases = [{
        "phase": s["phase"], "first_minute": s["first"], "minutes": s["last"] - s["first"] + 1,
        "mean_sm_active_pct": round(100 * _mean([r["SmActive"] for r in s["rows"]]), 1),
        "mean_gpu_util_pct": round(_mean([r["GpuUtil"] for r in s["rows"]]), 1),
        "mean_power_w": round(_mean([r["PowerW"] for r in s["rows"]]), 1),
        "max_memory_gib": round(max((r["FbUsedMiB"] or 0) for r in s["rows"]) / 1024, 1),
        "owner_minutes": sum(1 for r in s["rows"] if r["Users"]),
        "shared_minutes": sum(1 for r in s["rows"] if "," in r["Users"]),
    } for s in segments(gpu) if s["phase"] != "idle"]
    gpu_bytes = statistics.median(r["BilledSize"] for r in gpu)
    hb_bytes = statistics.median(h["BilledSize"] for h in hb)
    return _r({
        "run": run_dir.name,
        "hardware": contract["hardware"],
        "window_minutes": json.loads((run_dir / "raw-manifest.json").read_text(encoding="utf-8"))["window_minutes"],
        "heartbeat_minutes": len({h["Minute"] for h in hb}),
        "first_heartbeat_minute": min(h["Minute"] for h in hb),
        "first_gpu_minute": min(r["Minute"] for r in gpu),
        "gpu_rows": len(gpu),
        "summary": python["summary"],
        "busy_minutes": len(busy),
        "owner_minutes": sum(1 for r in busy if r["Users"]),
        "unattributed_busy_minutes": sum(1 for r in busy if not r["Users"]),
        "per_user": python["per_user"],
        "phases": phases,
        "kql_vs_python": _agreement(python, kql),
        "ingestion_delay_seconds": {"median": round(statistics.median(r["IngestionDelaySeconds"] for r in gpu)),
                                    "p95": round(_pct([r["IngestionDelaySeconds"] for r in gpu], 0.95)),
                                    "max": max(r["IngestionDelaySeconds"] for r in gpu)},
        "billed_bytes_per_row": {"gpu_median": gpu_bytes, "gpu_max": max(r["BilledSize"] for r in gpu),
                                 "heartbeat_median": hb_bytes},
        "derived_mb_per_vm_day": {"1_gpu": round((gpu_bytes + hb_bytes) * 1440 / 1e6, 2),
                                  "8_gpu": round((8 * gpu_bytes + hb_bytes) * 1440 / 1e6, 2)},
    })


def build() -> dict:
    contracts = json.loads((EVIDENCE / "runs.json").read_text(encoding="utf-8"))
    runs = {}
    for run_id, contract in contracts["runs"].items():
        run_dir = RUNS / run_id
        manifest = json.loads((run_dir / "raw-manifest.json").read_text(encoding="utf-8"))
        for name, digest in manifest["public_projection_sha256"].items():
            if _sha(run_dir / name) != digest:
                raise SystemExit(f"HASH_MISMATCH {run_id}/{name}: evidence changed after projection")
        runs[run_id] = build_run(run_dir, contract)
    return {"schema": 1, "idle_pct": IDLE_PCT, "runs": runs}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("capture")
    c.add_argument("--workspace", required=True)
    c.add_argument("--start", required=True, help="window start, ISO-8601 UTC")
    c.add_argument("--minutes", type=int, required=True)
    c.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("project")
    p.add_argument("--private", type=Path, required=True)
    p.add_argument("--run", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "capture":
        capture(args.workspace, args.start, args.minutes, args.out)
        return 0
    if args.cmd == "project":
        project(args.private, args.run)
        return 0
    text = json.dumps(build(), indent=1, ensure_ascii=False) + "\n"
    if args.check:
        if not MEASUREMENTS.exists() or MEASUREMENTS.read_text(encoding="utf-8") != text:
            print("EVIDENCE_STALE evidence/measurements.json differs from a fresh build")
            return 1
        data = json.loads(text)
        n = sum(r["kql_vs_python"]["compared_values"] for r in data["runs"].values())
        print(f"PASS measurements.json is current; {n} KQL values equal the Python recomputation")
        return 0
    MEASUREMENTS.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {MEASUREMENTS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

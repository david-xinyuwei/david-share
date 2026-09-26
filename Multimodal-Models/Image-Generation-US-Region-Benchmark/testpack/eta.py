"""ETA for the running matrix: pace since resume + per-group median-weighted projection."""
import json, statistics, sys, time
from datetime import datetime, timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
run = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "runs" / "us-matrix-9g-20260926"
d = json.loads((run / "5way_v2_results.json").read_text(encoding="utf-8"))
raw = d["raw_data"]
ok = [r for r in raw if r["ok"]]
now = datetime.now()
print(f"now={now:%H:%M:%S} state={d['state']} formal ok={len(ok)}/306 failed={len(raw)-len(ok)}")

from datetime import timezone
TS_KEY = "ended_at_utc"
INTER_WAIT = 5.0

def parse(v):
    dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().replace(tzinfo=None)  # local wall clock

resume_at = datetime(2026, 9, 26, 10, 0, 43)
recent = [r for r in ok if parse(r[TS_KEY]) >= resume_at]
if len(recent) >= 2:
    span = (parse(recent[-1][TS_KEY]) - resume_at).total_seconds()
    pace = span / len(recent)
    remaining = 306 - len(ok)
    print(f"since resume 10:00:43: {len(recent)} samples in {span/60:.1f} min -> {pace:.1f} s/sample")
    print(f"  linear ETA: {remaining} left x {pace:.0f}s = {remaining*pace/3600:.1f} h -> finish ~{(now + timedelta(seconds=remaining*pace)):%H:%M}")

# Median-weighted projection: what remains per group, times that group's own median (+ inter-call wait).
groups = {}
for r in ok:
    groups.setdefault(r["group"], []).append(float(r["time"]))
need = {g: 34 - len(v) for g, v in groups.items()}
proj = sum(need[g] * (statistics.median(v) + INTER_WAIT) for g, v in groups.items())
proj_mean = sum(need[g] * (statistics.fmean(v) + INTER_WAIT) for g, v in groups.items())
print(f"\nmedian-weighted remaining: {proj/3600:.1f} h -> ~{(now + timedelta(seconds=proj)):%H:%M}")
print(f"mean-weighted remaining:   {proj_mean/3600:.1f} h -> ~{(now + timedelta(seconds=proj_mean)):%H:%M}")
print("\ngroup                         done  left  median_s  mean_s  left_min")
for g, v in groups.items():
    print(f"{g:<30}{len(v):>4}{need[g]:>6}{statistics.median(v):>10.1f}{statistics.fmean(v):>8.1f}{need[g]*(statistics.fmean(v)+INTER_WAIT)/60:>9.1f}")

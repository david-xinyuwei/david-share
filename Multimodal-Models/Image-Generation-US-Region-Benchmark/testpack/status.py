"""One-shot progress snapshot of a run directory (no network). Usage: python status.py runs/<tag>"""
import json, statistics, sys, time
from datetime import datetime, timezone
from pathlib import Path

run = Path(sys.argv[1] if len(sys.argv) > 1 else "runs/us-matrix-9g-20260926").resolve()
res = run / "5way_v2_results.json"
if not res.exists():
    raise SystemExit(f"no results yet at {res}")
d = json.loads(res.read_text(encoding="utf-8"))
cfg, raw = d["config"], d.get("raw_data", [])
planned = cfg["formal_sample_count"]
ok = [r for r in raw if r["ok"]]
bad = [r for r in raw if not r["ok"]]
age = time.time() - res.stat().st_mtime
print(f"run={run.name} state={d.get('state')} last_write={age:.0f}s ago")
print(f"warmup={sum(1 for w in d.get('warmup', []) if w['ok'])}/{len(cfg['groups'])} ok")
print(f"formal={len(raw)}/{planned} ({len(raw)/planned:.0%})  ok={len(ok)} failed={len(bad)}")
if d.get("current_sample"):
    cs = d["current_sample"]
    print(f"current={cs.get('sample_id')}")
if raw:
    t0 = datetime.fromisoformat(raw[0]["started_at_utc"])
    t1 = datetime.fromisoformat(raw[-1]["ended_at_utc"])
    per = (t1 - t0).total_seconds() / len(raw)
    eta = (planned - len(raw)) * per
    print(f"pace={per:.0f}s/sample  eta~{eta/3600:.1f}h  (finish ~{datetime.now().astimezone() + __import__('datetime').timedelta(seconds=eta):%H:%M})")
    print("\ngroup                          n   median s   auto-echo")
    for g in cfg["groups"]:
        rs = [r for r in ok if r["group"] == g]
        if not rs:
            continue
        echo = ""
        if rs[0].get("quality") == "auto":
            c = {}
            for r in rs:
                q = (r.get("token_info") or {}).get("service_quality") or "?"
                c[q] = c.get(q, 0) + 1
            echo = ", ".join(f"{k}×{v}" for k, v in c.items())
        print(f"{g:<30} {len(rs):>3}   {statistics.median(r['time'] for r in rs):>7.1f}   {echo}")

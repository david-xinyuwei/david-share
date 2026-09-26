"""Re-freeze a run onto a revised runner, keeping an audit trail inside the run record.

The runner's --resume refuses to continue when its own SHA-256 differs from the one frozen in 5way_v2_results.json.
That is the right default: silent method drift must not be resumable. When the change is deliberate (here: v2.2,
token refresh on JWT expiry + 401 retry; request payloads, pacing, prompts and measurement definition untouched),
record old and new hashes plus the reason in the run, copy the new source beside the results, then resume.

    python refreeze_runner.py runs/<tag> "reason text"
"""
import hashlib, json, shutil, sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "source" / "benchmark_5way_v2.py"
run = Path(sys.argv[1]).resolve()
reason = sys.argv[2] if len(sys.argv) > 2 else "runner revised"
results = run / "5way_v2_results.json"
doc = json.loads(results.read_text(encoding="utf-8"))
old = doc["script_sha256"]
new = hashlib.sha256(RUNNER.read_bytes()).hexdigest()
if old == new:
    print("runner unchanged; nothing to do"); raise SystemExit(0)
doc.setdefault("runner_revisions", []).append({
    "at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "from_sha256": old, "to_sha256": new, "reason": reason,
    "samples_before": len(doc.get("raw_data", [])),
    "ok_before": sum(1 for r in doc.get("raw_data", []) if r["ok"]),
    "failed_before": sum(1 for r in doc.get("raw_data", []) if not r["ok"]),
})
doc["script_sha256"] = new
# atomic write, same as the runner's checkpoint()
tmp = results.with_suffix(".json.tmp")
tmp.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
tmp.replace(results)
src_dir = run / "source"
(src_dir / f"benchmark_5way_v2.pre-revision-{old[:12]}.py").write_bytes((src_dir / "benchmark_5way_v2.py").read_bytes())
shutil.copyfile(RUNNER, src_dir / "benchmark_5way_v2.py")
info = run / "RUN-INFO.txt"
info.write_text(info.read_text(encoding="utf-8") + f"runner_revised_at={datetime.now().isoformat(timespec='seconds')} from={old} to={new} reason={reason}\n", encoding="utf-8")
print(f"REFROZEN {run.name}: {old[:12]} -> {new[:12]}; previous source kept as source/benchmark_5way_v2.pre-revision-{old[:12]}.py")

"""Hold ES_SYSTEM_REQUIRED|ES_CONTINUOUS while a benchmark run is in progress, then release it and exit.

    python keep_awake_while_running.py <run_dir>

Polls <run_dir>/5way_v2_results.json every 60 s; exits when state is COMPLETED / COMPLETED_WITH_FAILURES /
INTERRUPTED / WARMUP_FAILED, or when the file has not been updated for 30 minutes (runner dead). Run-scoped:
nothing is left behind after exit. Windows only; no-op elsewhere.
"""
import ctypes, json, sys, time
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1]).resolve()
results = run_dir / "5way_v2_results.json"
TERMINAL = {"COMPLETED", "COMPLETED_WITH_FAILURES", "INTERRUPTED", "WARMUP_FAILED"}
ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
k32 = ctypes.windll.kernel32 if sys.platform == "win32" else None
if k32:
    k32.SetThreadExecutionState.restype = ctypes.c_uint32
    prev = k32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    print(f"{datetime.now():%H:%M:%S} SLEEP_BLOCKED={'yes' if prev else 'FAILED'} watching {results}", flush=True)
try:
    while True:
        time.sleep(60)
        if not results.exists():
            print(f"{datetime.now():%H:%M:%S} results.json not yet written", flush=True)
            continue
        state = json.loads(results.read_text(encoding="utf-8")).get("state")
        age_min = (time.time() - results.stat().st_mtime) / 60
        done = len(json.loads(results.read_text(encoding="utf-8")).get("raw_data", []))
        print(f"{datetime.now():%H:%M:%S} state={state} samples={done} last_write={age_min:.0f}min ago", flush=True)
        if state in TERMINAL or age_min > 30:
            print(f"EXIT reason={'terminal state' if state in TERMINAL else 'runner stale >30min'}", flush=True)
            break
finally:
    if k32:
        k32.SetThreadExecutionState(ES_CONTINUOUS)
        print("SLEEP_BLOCK_RELEASED", flush=True)

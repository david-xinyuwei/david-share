"""
Hyperlight Sandbox — Stress Test
Tests rapid sequential sandbox creation + execution to measure throughput.
NOT a live monitor — runs N iterations and exits with summary.

Usage: python hyperlight_stress_test.py [iterations]
Default: 20 iterations
"""
import time
import sys
import os
import statistics

ITERATIONS = int(sys.argv[1]) if len(sys.argv) > 1 else 20

print("=" * 62)
print(f"  HYPERLIGHT STRESS TEST — {ITERATIONS} iterations")
print(f"  Host Python: {sys.version.split()[0]}  PID: {os.getpid()}")
print("=" * 62)

from hyperlight_sandbox import Sandbox

create_times = []
exec_times = []
total_times = []
errors = 0

for i in range(1, ITERATIONS + 1):
    t_total = time.time()

    try:
        # Create
        t0 = time.time()
        sandbox = Sandbox(backend="wasm")
        ct = round((time.time() - t0) * 1000, 1)
        create_times.append(ct)

        # Register tool
        sandbox.register_tool("add", lambda a=0, b=0: a + b)

        # Execute
        code = f"""
result = call_tool('add', a={i}, b=1000)
print(f"{{result}}")
"""
        t1 = time.time()
        result = sandbox.run(code)
        et = round((time.time() - t1) * 1000, 1)
        exec_times.append(et)

        # Verify
        stdout = (result.stdout or "").strip()
        expected = str(i + 1000)
        ok = stdout == expected

        # Release
        close_fn = getattr(sandbox, "close", None)
        if callable(close_fn):
            close_fn()
        del sandbox

        tt = round((time.time() - t_total) * 1000, 1)
        total_times.append(tt)

        status = "OK" if ok else f"WRONG (got {stdout}, expected {expected})"
        if not ok:
            errors += 1

        print(f"  [{i:3d}/{ITERATIONS}] create={ct:7.1f}ms  exec={et:7.1f}ms  total={tt:7.1f}ms  result={stdout:>6s}  {status}")

    except Exception as e:
        errors += 1
        print(f"  [{i:3d}/{ITERATIONS}] ERROR: {e}")

# Summary
print("\n" + "=" * 62)
print(f"  RESULTS — {ITERATIONS} iterations, {errors} errors")
print(f"  {'':20s} {'P50':>10s} {'P95':>10s} {'P99':>10s} {'Mean':>10s}")

def pct(data, p):
    s = sorted(data)
    idx = int(len(s) * p / 100)
    return s[min(idx, len(s)-1)]

if create_times:
    print(f"  {'Sandbox create (ms)':20s} {pct(create_times,50):10.1f} {pct(create_times,95):10.1f} {pct(create_times,99):10.1f} {statistics.mean(create_times):10.1f}")
if exec_times:
    print(f"  {'Code execute (ms)':20s} {pct(exec_times,50):10.1f} {pct(exec_times,95):10.1f} {pct(exec_times,99):10.1f} {statistics.mean(exec_times):10.1f}")
if total_times:
    print(f"  {'Total per iter (ms)':20s} {pct(total_times,50):10.1f} {pct(total_times,95):10.1f} {pct(total_times,99):10.1f} {statistics.mean(total_times):10.1f}")
    throughput = 1000.0 / statistics.mean(total_times)
    print(f"\n  Throughput: {throughput:.2f} sandboxes/sec")
    print(f"  Correctness: {ITERATIONS - errors}/{ITERATIONS} passed")
print("=" * 62)

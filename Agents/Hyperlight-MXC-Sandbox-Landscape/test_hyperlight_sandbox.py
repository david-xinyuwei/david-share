"""Hyperlight Sandbox - Windows WHP direct test.

Tests the Hyperlight Sandbox Python SDK with the Wasm backend
running on Windows Hypervisor Platform (WHP).
"""
import sys
import time
import traceback

LOG = []

def log(msg):
    print(msg, flush=True)
    LOG.append(msg)

log(f"Python {sys.version}")
log(f"Platform: {sys.platform}")

# --- Test 1: Basic import and sandbox creation ---
log("\n=== TEST 1: Import & Create Sandbox ===")
try:
    from hyperlight_sandbox import Sandbox, ExecutionResult
    log("Import OK")

    t0 = time.perf_counter()
    sandbox = Sandbox(backend="wasm")
    t1 = time.perf_counter()
    log(f"Sandbox created in {(t1-t0)*1000:.1f} ms")
except Exception as e:
    log(f"FAIL: {e}")
    traceback.print_exc()
    sys.exit(1)

# --- Test 2: Simple print ---
log("\n=== TEST 2: Simple print ===")
try:
    t0 = time.perf_counter()
    result = sandbox.run("print('HYPERLIGHT_SANDBOX_HELLO_OK')")
    t1 = time.perf_counter()
    log(f"stdout: {result.stdout.strip()}")
    log(f"stderr: {result.stderr.strip()}")
    log(f"exit_code: {result.exit_code}")
    log(f"Execution time: {(t1-t0)*1000:.1f} ms")
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}"
    assert "HYPERLIGHT_SANDBOX_HELLO_OK" in result.stdout, "Missing expected output"
    log("PASS")
except Exception as e:
    log(f"FAIL: {e}")
    traceback.print_exc()

# --- Test 3: Math computation ---
log("\n=== TEST 3: Math computation ===")
try:
    result = sandbox.run("""
import math
pi = math.pi
result = sum(1/math.factorial(k) for k in range(20))
print(f'e ≈ {result:.15f}')
print(f'π ≈ {pi:.15f}')
print(f'√2 ≈ {math.sqrt(2):.15f}')
""")
    log(f"stdout: {result.stdout.strip()}")
    log(f"exit_code: {result.exit_code}")
    assert result.exit_code == 0
    log("PASS")
except Exception as e:
    log(f"FAIL: {e}")
    traceback.print_exc()

# --- Test 4: Tool dispatch (host function call) ---
log("\n=== TEST 4: Tool dispatch ===")
try:
    sandbox2 = Sandbox(backend="wasm")
    sandbox2.register_tool("add", lambda a=0, b=0: a + b)
    sandbox2.register_tool("greet", lambda name="World": f"Hello, {name}!")

    result = sandbox2.run("""
sum_result = call_tool('add', a=17, b=25)
greeting = call_tool('greet', name='Hyperlight')
print(f'add(17,25) = {sum_result}')
print(f'greet = {greeting}')
""")
    log(f"stdout: {result.stdout.strip()}")
    log(f"exit_code: {result.exit_code}")
    assert result.exit_code == 0
    assert "42" in result.stdout
    assert "Hello, Hyperlight" in result.stdout
    log("PASS")
except Exception as e:
    log(f"FAIL: {e}")
    traceback.print_exc()

# --- Test 5: Snapshot and restore ---
log("\n=== TEST 5: Snapshot & Restore ===")
try:
    sandbox3 = Sandbox(backend="wasm")
    sandbox3.run("x = 100")
    snap = sandbox3.snapshot()
    log(f"Snapshot taken: {type(snap)}")

    sandbox3.run("x = 999")
    result_before = sandbox3.run("print(f'x before restore = {x}')")
    log(f"Before restore: {result_before.stdout.strip()}")

    sandbox3.restore(snap)
    result_after = sandbox3.run("print(f'x after restore = {x}')")
    log(f"After restore: {result_after.stdout.strip()}")
    assert "100" in result_after.stdout, "Snapshot restore failed"
    log("PASS")
except Exception as e:
    log(f"FAIL: {e}")
    traceback.print_exc()

# --- Test 6: Network allow-listing ---
log("\n=== TEST 6: Network (blocked by default) ===")
try:
    sandbox4 = Sandbox(backend="wasm")
    result = sandbox4.run("""
try:
    resp = http_get('https://httpbin.org/get')
    print(f'UNEXPECTED: got response {resp}')
except Exception as e:
    print(f'BLOCKED: {type(e).__name__}: {e}')
""")
    log(f"stdout: {result.stdout.strip()}")
    log(f"exit_code: {result.exit_code}")
    log("PASS (network blocked as expected)" if "BLOCKED" in result.stdout else "CHECK: unexpected result")
except Exception as e:
    log(f"FAIL: {e}")
    traceback.print_exc()

# --- Summary ---
log("\n=== SUMMARY ===")
log(f"All tests completed on {sys.platform}")

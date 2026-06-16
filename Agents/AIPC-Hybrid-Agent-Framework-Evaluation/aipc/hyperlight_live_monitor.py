"""
Hyperlight Sandbox — Live Task Monitor
Each cycle runs a REAL data processing task inside Hyperlight micro-VM.
Shows: fast startup + real computation + isolation proof.
Ctrl+C to exit.

Usage: python hyperlight_live_monitor.py
"""
import time
import sys
import os
import random

INTERVAL = 10

# Real tasks that demonstrate actual data processing inside sandbox
TASKS = [
    {
        "name": "JSON Data Processing",
        "desc": "Parse sales data -> filter by amount -> calculate total revenue",
        "code": """
import json

data = [
    {"product": "Laptop", "price": 5999, "qty": 3, "region": "Beijing"},
    {"product": "Phone", "price": 3999, "qty": 8, "region": "Shanghai"},
    {"product": "Tablet", "price": 2999, "qty": 5, "region": "Shenzhen"},
    {"product": "Monitor", "price": 1899, "qty": 12, "region": "Beijing"},
    {"product": "Keyboard", "price": 399, "qty": 25, "region": "Shanghai"},
]

total_revenue = sum(item["price"] * item["qty"] for item in data)
top_items = sorted(data, key=lambda x: x["price"] * x["qty"], reverse=True)[:3]
bj_revenue = sum(item["price"] * item["qty"] for item in data if item["region"] == "Beijing")

print(f"Total revenue: {total_revenue}")
print(f"Beijing revenue: {bj_revenue}")
for item in top_items:
    print(f"  Top: {item['product']} = {item['price'] * item['qty']}")
print(f"Items processed: {len(data)}")
"""
    },
    {
        "name": "Text Analysis",
        "desc": "Word frequency analysis on English text",
        "code": """
text = '''Hyperlight creates micro virtual machines in milliseconds.
Each VM is isolated by the hypervisor. Guest code cannot access
the host filesystem or network. Host tools are the only bridge
between the guest and the host. This makes Hyperlight ideal for
running untrusted code safely at scale.'''

words = text.lower().replace('.', '').replace(',', '').split()
freq = {}
for w in words:
    freq[w] = freq.get(w, 0) + 1

top5 = sorted(freq.items(), key=lambda x: -x[1])[:5]
print(f"Total words: {len(words)}")
print(f"Unique words: {len(freq)}")
for word, count in top5:
    print(f"  '{word}': {count}x")
print(f"Avg word length: {sum(len(w) for w in words) / len(words):.1f}")
"""
    },
    {
        "name": "Prime Number Sieve",
        "desc": "Sieve of Eratosthenes -> find primes up to 1000",
        "code": """
def sieve(n):
    is_prime = [True] * (n + 1)
    is_prime[0] = is_prime[1] = False
    for i in range(2, int(n**0.5) + 1):
        if is_prime[i]:
            for j in range(i*i, n + 1, i):
                is_prime[j] = False
    return [i for i in range(2, n + 1) if is_prime[i]]

primes = sieve(1000)
print(f"Primes up to 1000: {len(primes)}")
print(f"First 10: {primes[:10]}")
print(f"Last 10: {primes[-10:]}")
print(f"Sum of all primes: {sum(primes)}")
print(f"Largest gap: {max(primes[i+1]-primes[i] for i in range(len(primes)-1))}")
"""
    },
    {
        "name": "CSV Data Pipeline",
        "desc": "Parse CSV -> aggregate by category -> rank",
        "code": """
csv_data = '''name,category,score
Alice,Engineering,92
Bob,Marketing,85
Carol,Engineering,88
Dave,Marketing,91
Eve,Engineering,95
Frank,Sales,78
Grace,Sales,82
Heidi,Marketing,89'''

rows = []
lines = csv_data.strip().split('\\n')
headers = lines[0].split(',')
for line in lines[1:]:
    vals = line.split(',')
    rows.append(dict(zip(headers, vals)))

cat_scores = {}
for r in rows:
    cat = r['category']
    cat_scores.setdefault(cat, []).append(int(r['score']))

print(f"Records: {len(rows)}")
for cat, scores in sorted(cat_scores.items()):
    avg = sum(scores) / len(scores)
    print(f"  {cat}: avg={avg:.1f}, count={len(scores)}, max={max(scores)}")
top = max(rows, key=lambda r: int(r['score']))
print(f"Top scorer: {top['name']} ({top['score']})")
"""
    },
    {
        "name": "Matrix Operations",
        "desc": "3x3 matrix multiply + determinant calculation",
        "code": """
A = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
B = [[9, 8, 7], [6, 5, 4], [3, 2, 1]]

C = [[sum(A[i][k]*B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

det = (A[0][0]*(A[1][1]*A[2][2]-A[1][2]*A[2][1])
      -A[0][1]*(A[1][0]*A[2][2]-A[1][2]*A[2][0])
      +A[0][2]*(A[1][0]*A[2][1]-A[1][1]*A[2][0]))

print("A x B =")
for row in C:
    print(f"  {row}")
print(f"det(A) = {det}")
print(f"Trace(A) = {A[0][0]+A[1][1]+A[2][2]}")
print(f"Trace(C) = {C[0][0]+C[1][1]+C[2][2]}")
"""
    },
]

cycle = 0
while True:
    cycle += 1
    os.system('cls' if os.name == 'nt' else 'clear')

    task = TASKS[(cycle - 1) % len(TASKS)]
    now = time.strftime("%H:%M:%S")

    print("=" * 62)
    print(f"  HYPERLIGHT LIVE TASK MONITOR                 {now}")
    print(f"  Cycle #{cycle}  |  Refresh: {INTERVAL}s  |  Ctrl+C to exit")
    print("=" * 62)

    print(f"\n  -- HOST --")
    print(f"     Python: {sys.version.split()[0]}  PID: {os.getpid()}  OS: {os.name}")

    print(f"\n  -- TASK: {task['name']} --")
    print(f"     {task['desc']}")

    try:
        from hyperlight_sandbox import Sandbox

        t0 = time.time()
        sandbox = Sandbox(backend="wasm")
        create_ms = round((time.time() - t0) * 1000, 1)

        # Proof: runtime info at START and END of task, business results in between
        # Same sandbox.run() stdout = same execution context = proof that task ran in VM
        proof_start = """
import sys, os
u = os.uname()
print(f"--- Runtime: Python {sys.version.split()[0]} on {u.sysname}/{u.machine} (PID {os.getpid()}) ---")
"""
        proof_end = """
print(f"--- Verified: kernel={os.uname().sysname} env_vars={len(os.environ)} ---")
"""
        full_code = proof_start + task["code"] + proof_end

        t1 = time.time()
        result = sandbox.run(full_code)
        exec_ms = round((time.time() - t1) * 1000, 1)

        close_fn = getattr(sandbox, "close", None)
        if callable(close_fn):
            close_fn()
        del sandbox

        print(f"\n  -- EXECUTION (create={create_ms}ms, exec={exec_ms}ms) --")
        vm_runtime = ""
        vm_verified = ""
        if result.stdout:
            for line in result.stdout.strip().split("\n"):
                print(f"     {line}")
                if line.startswith("--- Runtime:"):
                    vm_runtime = line.strip("- ").strip()
                elif line.startswith("--- Verified:"):
                    vm_verified = line.strip("- ").strip()
        if result.stderr:
            print(f"     STDERR: {result.stderr[:200]}")

    except Exception as e:
        print(f"\n  -- ERROR --")
        print(f"     {e}")
        vm_runtime = ""
        vm_verified = ""

    import platform
    host_arch = platform.machine()
    host_kernel = platform.system()
    print(f"\n  -- ISOLATION PROOF --")
    print(f"     Host: kernel={host_kernel} arch={host_arch} Python={sys.version.split()[0]}")
    if vm_runtime:  
        print(f"     VM:   {vm_runtime}")
    if vm_verified:
        print(f"     VM:   {vm_verified}")
    if vm_runtime:
        print(f"     -> Task results sandwiched between VM runtime probes = executed in Hyperlight")
    else:
        print(f"     -> (no VM proof data — sandbox may have failed)")
    print("=" * 62)

    time.sleep(INTERVAL)

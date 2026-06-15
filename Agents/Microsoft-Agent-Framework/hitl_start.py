import subprocess
import sys
import time
import webbrowser

print("="*80)
print("Starting HITL Workflow Demo")
print("="*80)

# 1. Start DevUI in background
print("\n[1/3] Starting DevUI...")
devui = subprocess.Popen(
    [sys.executable, "hitl_devui.py"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL
)
print(f"DevUI started (PID: {devui.pid})")

# 2. Wait for server
print("[2/3] Waiting 5 seconds...")
time.sleep(5)

# 3. Open browser
print("[3/3] Opening browser...")
webbrowser.open("http://localhost:8080")

print("\n" + "="*80)
print("DevUI: http://localhost:8080")
print("="*80)

# 4. Run agent in foreground (inherits stdin/stdout)
try:
    subprocess.run([sys.executable, "hitl_agent.py"], stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr, check=False)
finally:
    print("\nShutting down DevUI...")
    devui.terminate()
    devui.wait()
    print("Done!")




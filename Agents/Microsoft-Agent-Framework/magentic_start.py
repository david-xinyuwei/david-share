import subprocess
import sys
import time
import webbrowser

print("="*80)
print("Starting Workflow 1: Magentic Dynamic Agent Routing")
print("="*80)
print()
print("[1/3] Starting DevUI server...")

# Redirect DevUI output to null to keep terminal clean
devui = subprocess.Popen(
    [sys.executable, "magentic_devui.py"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL
)
print(f"DevUI started (PID: {devui.pid})")

print("[2/3] Waiting for server initialization...")
time.sleep(5)

print("[3/3] Opening browser...")
webbrowser.open("http://localhost:8080")

print()
print("="*80)
print("DevUI: http://localhost:8080")
print("Terminal: Ready for interaction")
print("="*80)
print()

try:
    # Run agent in current terminal (inherits stdin/stdout)
    subprocess.run([sys.executable, "magentic_agent.py"], stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr, check=False)
finally:
    print("\nShutting down DevUI...")
    devui.terminate()
    devui.wait()
    print("Done!")




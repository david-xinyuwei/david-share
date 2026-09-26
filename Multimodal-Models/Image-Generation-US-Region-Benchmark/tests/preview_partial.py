"""Dev aid: render the in-progress run into a scratch folder to exercise render.py before the run completes.
Copies render.py + pricing.json to a temp dir, relaxes ONLY the COMPLETED gate, renders, and prints the Results
and Cost sections. Never writes to the repo README. Usage: python tests/preview_partial.py runs/<tag>"""
import re, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
run_dir = Path(sys.argv[1]).resolve()
tmp = Path(tempfile.mkdtemp(prefix="usb-preview-"))
src = (ROOT / "render.py").read_text(encoding="utf-8")
patched = src.replace('if results.get("state") != "COMPLETED":', 'if False:')
assert patched != src, "COMPLETED gate not found; render.py changed"
(tmp / "render.py").write_text(patched, encoding="utf-8")
for sibling in ("pricing.json", "robustness.py", "references.json"):
    shutil.copy(ROOT / sibling, tmp / sibling)
env = {**__import__("os").environ, "USB_REFERENCE_ROOT": str(ROOT.parent)}  # MAI-Image-2.6 Test, where runs/ lives
proc = subprocess.run([sys.executable, str(tmp / "render.py"), str(run_dir)], capture_output=True, text=True, cwd=tmp, env=env)
print(proc.stdout.strip()); print(proc.stderr.strip())
if proc.returncode:
    raise SystemExit(proc.returncode)
text = (tmp / "README.md").read_text(encoding="utf-8")
head = text.split("## Images", 1)[0]
print("\n" + head)
imgs = len(list((tmp / "images").glob("*.png")))
print(f"[preview] {len(text):,} chars, {imgs} images copied -> {tmp}")

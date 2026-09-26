"""Scrub local-machine details from the publish tree and report anything that still looks private.

Rewrites (idempotent):
  runs/<run>/RUN-INFO.txt   local absolute paths -> repo-relative; az profile dir -> '<isolated az profile>'
Deletes planning-only helper scripts that hard-code local paths.
Then scans every text file (excluding runs/*/images, images/, .pytest_cache) for:
  C:\\Users, /home/, .azure-, GUIDs, api-key, subscription ids, public IPv4.
Exit 1 if anything remains.
"""
import re, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs" / "us-matrix-9g-20260926"

# 1. RUN-INFO.txt
info = RUN / "RUN-INFO.txt"
if info.is_file():
    t = info.read_text(encoding="utf-8")
    t2 = t.replace(str(ROOT) + "\\", "").replace(str(ROOT), ".")
    t2 = re.sub(r"az_profile=.*", "az_profile=<isolated Azure CLI profile dir; tenant/subscription not recorded here>", t2)
    t2 = t2.replace("testpack\\runs\\us-matrix-9g-20260926", "runs\\us-matrix-9g-20260926")
    if t2 != t:
        info.write_text(t2, encoding="utf-8")
        print("SCRUBBED RUN-INFO.txt")

# 2. planning helpers that only made sense on this laptop, and the aborted first attempt (superseded by the 9g run)
import shutil
for name in ("david_share_state.py", "david_share_dirty.py", "publish_size.py", "which_repos.py", "grep_repo_refs.py",
             "where_is_it_running.py", "check_runner_sha.py", "restore_runner_source.py", "fetch_keys_to_env.py",
             "PUBLISH-PLAN.md"):
    p = ROOT / "testpack" / name
    if p.exists():
        p.unlink()
        print("DELETED testpack/" + name)
for name in ("probe_reference_runs.py", "show_config.py", "move_run_to_canonical.py"):
    p = ROOT / "tests" / name
    if p.exists():
        p.unlink()
        print("DELETED tests/" + name)
stale = ROOT / "testpack" / "runs"
archive = ROOT.parent / "_local-archive" / "us-image-benchmark-testpack-runs"  # outside the publish tree, nothing deleted
if stale.is_dir():
    archive.mkdir(parents=True, exist_ok=True)
    for p in list(stale.iterdir()):
        if p.name.startswith("us-matrix-20260926"):  # smoke-only attempt from 08:41, never a formal run
            shutil.move(str(p), str(archive / p.name))
            print(f"MOVED testpack/runs/{p.name} -> {archive.relative_to(ROOT.parent)}/")
    if not any(stale.iterdir()):
        try:
            stale.rmdir()
            print("REMOVED empty testpack/runs/")
        except PermissionError:
            print("NOTE testpack/runs/ is empty but a handle still holds it (OneDrive/explorer); git ignores empty dirs")

# 3. scan
PAT = {
    "local path": re.compile(r"[A-Z]:\\Users\\|/home/\w+|/Users/\w+"),
    "az profile": re.compile(r"\.azure-[0-9a-f]{4}"),
    "guid": re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I),
    "api key": re.compile(r"api[-_]?key\s*[:=]\s*[A-Za-z0-9]{16,}", re.I),
    "ipv4": re.compile(r"\b(?!10\.|127\.|192\.168\.|0\.0\.0\.0)\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
}
SKIP_DIRS = {"images", ".pytest_cache", "__pycache__", ".venv"}
TEXT = {".md", ".py", ".json", ".jsonl", ".txt", ".csv", ".ps1", ".example", ".toml", ".cfg", ".ini", ".yaml", ".yml"}
hits = 0
for p in sorted(ROOT.rglob("*")):
    if not p.is_file() or any(s in p.parts for s in SKIP_DIRS) or (p.suffix.lower() not in TEXT and p.name != ".env.example"):
        continue
    if p.name in ("scrub_publish_tree.py",):
        continue
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"UNREADABLE {p.relative_to(ROOT)}: {e}")
        continue
    for kind, rx in PAT.items():
        for m in rx.finditer(text):
            # per-request trace ids (apim-request-id / x-request-id) in attempts.jsonl are not identities or secrets
            if kind == "guid" and p.name == "attempts.jsonl" and re.search(r"(apim-request-id|x-request-id)\"?: ?\"?$", text[max(0, m.start()-40):m.start()]):
                continue
            if kind == "local path" and p.name == ".env.example" and "<you>" in text.splitlines()[text.count("\n", 0, m.start())]:
                continue  # documented placeholder, not a real path
            line_no = text.count("\n", 0, m.start()) + 1
            print(f"HIT {kind:<10} {p.relative_to(ROOT)}:{line_no}: {text.splitlines()[line_no-1].strip()[:140]}")
            hits += 1
            break  # one hit per kind per file is enough to flag it
print(f"\nSCRUB_HITS={hits}")
sys.exit(1 if hits else 0)

#!/bin/bash
# 03_download.sh <model_id> <revision> — download one pinned snapshot into $HF_CACHE/hub with the host Python.
#   bash scripts/mi300x/03_download.sh "$NEMOTRON_ID" "$NEMOTRON_REV"      # node 0 only, 1.12 TB
#   bash scripts/mi300x/03_download.sh "$INKLING_ID"  "$INKLING_REV"       # BOTH nodes, 1.90 TB each
# Runs in the background; follow with:  tail -f $MOE_ROOT/logs/04_download_<model>.log
# Expected final line: DL_DONE path=... bytes=<total> secs=<n>. Observed 2026-11-02: Nemotron 1,121,078,235,607 bytes
# in 728 s; Inkling 1,904,787,107,666 bytes per node (1.5-3 GB/s per node from Hugging Face on this VM size).
# Gated repositories (Muse) need HF_TOKEN in the environment and prior approval on the model page; this script
# never requests access and never prints the token.
set -u
. "$(dirname "$0")/00_env.sh"
MID="$1"; REV="$2"; TAG="$(echo "$MID" | tr '/' '_')"
LOG="$MOE_ROOT/logs/04_download_$TAG.log"
if [ ! -x "$MOE_ROOT/venv/bin/python" ]; then
  python3 -m venv "$MOE_ROOT/venv" && "$MOE_ROOT/venv/bin/pip" install -q 'huggingface_hub[hf_transfer]' hf_transfer >> "$LOG" 2>&1
fi
mkdir -p "$HF_CACHE/hub"
echo "DL_START=$(date -u +%FT%TZ) MID=$MID REV=$REV" | tee -a "$LOG"
cat > "$MOE_ROOT/dl_$TAG.py" <<PY
import os, time
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"; os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "60"
from huggingface_hub import snapshot_download
t = time.time()
p = snapshot_download("$MID", revision="$REV", cache_dir="$HF_CACHE/hub", max_workers=32,
    allow_patterns=["*.json", "*.safetensors", "*.py", "*.jinja", "*.txt", "*.model", "*.tiktoken", "*.yaml", "*.yml"])
tot = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(p) for f in fs)
print(f"DL_DONE path={p} bytes={tot} secs={time.time()-t:.0f}", flush=True)
PY
nohup "$MOE_ROOT/venv/bin/python" "$MOE_ROOT/dl_$TAG.py" >> "$LOG" 2>&1 &
echo "DL_PID=$!" | tee -a "$LOG"

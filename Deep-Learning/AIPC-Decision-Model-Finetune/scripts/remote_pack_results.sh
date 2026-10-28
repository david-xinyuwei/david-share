#!/usr/bin/env bash
# Pack everything that must leave the VM before the ephemeral /mnt disk is wiped: reports, per-question rows,
# compare outputs, train/eval logs, GPU traces, status files, the calibrated checkpoints (LoRA adapter + pointer head
# + configs, small) and GGUF export logs and hashes. GGUF weights are excluded (regenerated from the checkpoint).
set -euo pipefail
source "$(dirname "$0")/remote_env.sh"
TS=$(date -u +%Y%m%d-%H%M%S)
OUT="$WORK/results-$TS.tgz"
rm -rf "$WORK/pack-meta"
mkdir -p "$WORK/pack-meta"
cp "$META/state/"* "$META/logs/"* "$META/scripts/"* "$WORK/pack-meta/" 2>/dev/null || true
for s in 0.8b 4b; do
  for f in "$META/state/pipeline-$s.status" "$META/state/pipeline-cf-$s.status"; do
    if [ -f "$f" ]; then cp "$f" "$WORK/runs/$s/"; fi
  done
done
cd "$WORK"
probe=$(ls runs/memory-probe/*.log runs/memory-probe/*.csv runs/memory-probe/*.jsonl 2>/dev/null || true)  # logs only, not its checkpoints
rc=0
tar czf "$OUT" --exclude='*.gguf' --exclude='*.part' runs/0.8b runs/4b gguf pack-meta $probe || rc=$?
[ "$rc" -le 1 ] || { echo "tar failed rc=$rc"; exit "$rc"; }  # 1 = a file changed while being read (jobs still running)
ls -l "$OUT"
sha256sum "$OUT"
echo "PACK_DONE $OUT"

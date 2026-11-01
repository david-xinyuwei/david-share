#!/usr/bin/env bash
# GGUF export (BF16 -> Q8_0, Q4_K_M) of the second-round checkpoints runs/<size>/r2-<arm>, same converter, quantizer
# and Q4_K_M tensor rules as remote_export_gguf_cf.sh, into new directories gguf/<size>-r2<arm>/ with new file names.
# Usage: remote_export_round2.sh 0.8b A B
set -uo pipefail
source "$(dirname "$0")/remote_env.sh"
SIZE="$1"; shift
L="$WORK/llama.cpp"
LV="$WORK/llama-venv"
Q="$L/build/bin/llama-quantize"
FLAGS_Q4_K_M="--pure --tensor-type ^output.weight=q8_0 --tensor-type attn_=q8_0 --tensor-type ssm_=q8_0 --tensor-type cls=q8_0"
case "$SIZE" in 0.8b) PFX=Contoso-Kev-0.8B ;; 4b) PFX=Contoso-Kev-4B ;; *) echo "bad size $SIZE"; exit 2 ;; esac
for ARM in "$@"; do
  NAME="$PFX-FTcf-R2$ARM"
  CK="$WORK/runs/$SIZE/r2-$ARM"
  OUT="$WORK/gguf/$SIZE-r2$ARM"
  STATUS="$META/state/round2-$SIZE-$ARM.status"
  grep -q '^CALIBRATED' "$STATUS" 2>/dev/null || { echo "NOT_CALIBRATED $SIZE $ARM"; continue; }
  mkdir -p "$OUT"
  echo "EXPORT_START $SIZE-r2$ARM $(date -Is)"
  start=$SECONDS
  if [ ! -f "$OUT/$NAME-BF16.gguf" ]; then
    "$LV/bin/python" "$L/convert_hf_to_gguf.py" "$CK" --outtype bf16 --outfile "$OUT/$NAME-BF16.gguf.part" --model-name "$NAME" > "$OUT/convert.log" 2>&1 \
      && mv "$OUT/$NAME-BF16.gguf.part" "$OUT/$NAME-BF16.gguf" || { echo "CONVERT_FAILED $SIZE-r2$ARM"; tail -n 20 "$OUT/convert.log"; continue; }
  fi
  [ -f "$OUT/$NAME-Q8_0.gguf" ] || "$Q" "$OUT/$NAME-BF16.gguf" "$OUT/$NAME-Q8_0.gguf" Q8_0 > "$OUT/quantize-Q8_0.log" 2>&1 || echo "QUANT_FAILED $SIZE-r2$ARM Q8_0"
  [ -f "$OUT/$NAME-Q4_K_M.gguf" ] || "$Q" $FLAGS_Q4_K_M "$OUT/$NAME-BF16.gguf" "$OUT/$NAME-Q4_K_M.gguf" Q4_K_M > "$OUT/quantize-Q4_K_M.log" 2>&1 || echo "QUANT_FAILED $SIZE-r2$ARM Q4_K_M"
  "$LV/bin/python" "$L/gguf-py/gguf/scripts/gguf_dump.py" --no-tensors "$OUT/$NAME-Q8_0.gguf" 2>&1 | grep -E "general.name|decision.temperature" > "$OUT/metadata.txt" || true
  cat "$OUT/metadata.txt"
  (cd "$OUT" && sha256sum ./*.gguf > gguf.sha256 && ls -l ./*.gguf)
  echo "EXPORT_DONE $SIZE-r2$ARM wall_s=$((SECONDS - start)) $(date -Is)"
done

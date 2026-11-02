#!/usr/bin/env bash
# Export the calibrated fine-tuned checkpoints to GGUF with the ggml-org/convert recipe of Kev-4B:
# BF16 (the converter downloads the pinned base and merges the LoRA; the head temperature becomes GGUF metadata),
# then Q8_0 and Q4_K_M with the same llama-quantize flags. Requires completed calibration.
# CPU only. Usage: remote_export_gguf.sh 0.8b 4b
set -euo pipefail
source "$(dirname "$0")/remote_env.sh"
if [ "$#" -eq 0 ]; then echo "usage: remote_export_gguf.sh 0.8b|4b [0.8b|4b ...]" >&2; exit 2; fi
L="$WORK/llama.cpp"
LV="$WORK/llama-venv"
Q="$L/build/bin/llama-quantize"
FLAGS_Q4_K_M="--pure --tensor-type ^output.weight=q8_0 --tensor-type attn_=q8_0 --tensor-type ssm_=q8_0 --tensor-type cls=q8_0"
for SIZE in "$@"; do
  case "$SIZE" in 0.8b) NAME=Contoso-Kev-0.8B-FT ;; 4b) NAME=Contoso-Kev-4B-FT ;; *) echo "bad size $SIZE"; exit 2 ;; esac
  STATUS="$META/state/pipeline-$SIZE.status"
  FT="$WORK/runs/$SIZE/ft"
  OUT="$WORK/gguf/$SIZE"
  grep -q '^CALIBRATED' "$STATUS" 2>/dev/null || { echo "NOT_CALIBRATED $SIZE"; exit 3; }
  mkdir -p "$OUT"
  echo "EXPORT_START $SIZE $(date -Is)"
  start=$SECONDS
  if [ ! -s "$OUT/$NAME-BF16.gguf" ]; then
    "$LV/bin/python" "$L/convert_hf_to_gguf.py" "$FT" --outtype bf16 --outfile "$OUT/$NAME-BF16.gguf.part" --model-name "$NAME" > "$OUT/convert.log" 2>&1 \
      && mv "$OUT/$NAME-BF16.gguf.part" "$OUT/$NAME-BF16.gguf" || { echo "CONVERT_FAILED $SIZE"; tail -n 20 "$OUT/convert.log"; exit 4; }
  fi
  [ -s "$OUT/$NAME-Q8_0.gguf" ] || { "$Q" "$OUT/$NAME-BF16.gguf" "$OUT/$NAME-Q8_0.gguf.part" Q8_0 > "$OUT/quantize-Q8_0.log" 2>&1 && mv "$OUT/$NAME-Q8_0.gguf.part" "$OUT/$NAME-Q8_0.gguf"; } || { echo "QUANT_FAILED $SIZE Q8_0"; exit 5; }
  [ -s "$OUT/$NAME-Q4_K_M.gguf" ] || { "$Q" $FLAGS_Q4_K_M "$OUT/$NAME-BF16.gguf" "$OUT/$NAME-Q4_K_M.gguf.part" Q4_K_M > "$OUT/quantize-Q4_K_M.log" 2>&1 && mv "$OUT/$NAME-Q4_K_M.gguf.part" "$OUT/$NAME-Q4_K_M.gguf"; } || { echo "QUANT_FAILED $SIZE Q4_K_M"; exit 5; }
  for format in BF16 Q8_0 Q4_K_M; do
    [ -s "$OUT/$NAME-$format.gguf" ] || { echo "MISSING_GGUF $SIZE $format"; exit 5; }
  done
  "$LV/bin/python" "$L/gguf-py/gguf/scripts/gguf_dump.py" --no-tensors "$OUT/$NAME-Q8_0.gguf" 2>&1 | grep -E "general.name|decision.temperature" > "$OUT/metadata.txt"
  for kind in choice score noul; do
    grep -q "qwen35.decision.temperature.$kind" "$OUT/metadata.txt" || { echo "MISSING_TEMPERATURE $kind"; exit 6; }
  done
  cat "$OUT/metadata.txt"
  (cd "$OUT" && sha256sum ./*.gguf > gguf.sha256 && ls -l ./*.gguf)
  echo "EXPORT_DONE $SIZE wall_s=$((SECONDS - start)) $(date -Is)"
done

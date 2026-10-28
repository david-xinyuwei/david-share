#!/usr/bin/env bash
# Export the calibrated fine-tuned checkpoints to GGUF with the ggml-org/convert recipe of Kev-4B:
# BF16 (the converter downloads the pinned base and merges the LoRA; the head temperature becomes GGUF metadata),
# then Q8_0 and Q4_K_M with the same llama-quantize flags. Waits for each size's CALIBRATED status line, so it can be
# started while training is still running. CPU only. Usage: remote_export_gguf.sh 0.8b 4b
set -uo pipefail
source "$(dirname "$0")/remote_env.sh"
L="$WORK/llama.cpp"
LV="$WORK/llama-venv"
Q="$L/build/bin/llama-quantize"
FLAGS_Q4_K_M="--pure --tensor-type ^output.weight=q8_0 --tensor-type attn_=q8_0 --tensor-type ssm_=q8_0 --tensor-type cls=q8_0"
for SIZE in "$@"; do
  case "$SIZE" in 0.8b) NAME=Contoso-Kev-0.8B-FT ;; 4b) NAME=Contoso-Kev-4B-FT ;; *) echo "bad size $SIZE"; continue ;; esac
  STATUS="$META/state/pipeline-$SIZE.status"
  FT="$WORK/runs/$SIZE/ft"
  OUT="$WORK/gguf/$SIZE"
  until [ -f "$STATUS" ] && grep -q '^CALIBRATED' "$STATUS"; do sleep 30; done
  mkdir -p "$OUT"
  echo "EXPORT_START $SIZE $(date -Is)"
  start=$SECONDS
  if [ ! -f "$OUT/$NAME-BF16.gguf" ]; then
    "$LV/bin/python" "$L/convert_hf_to_gguf.py" "$FT" --outtype bf16 --outfile "$OUT/$NAME-BF16.gguf.part" --model-name "$NAME" > "$OUT/convert.log" 2>&1 \
      && mv "$OUT/$NAME-BF16.gguf.part" "$OUT/$NAME-BF16.gguf" || { echo "CONVERT_FAILED $SIZE"; tail -n 20 "$OUT/convert.log"; continue; }
  fi
  [ -f "$OUT/$NAME-Q8_0.gguf" ] || "$Q" "$OUT/$NAME-BF16.gguf" "$OUT/$NAME-Q8_0.gguf" Q8_0 > "$OUT/quantize-Q8_0.log" 2>&1 || echo "QUANT_FAILED $SIZE Q8_0"
  [ -f "$OUT/$NAME-Q4_K_M.gguf" ] || "$Q" $FLAGS_Q4_K_M "$OUT/$NAME-BF16.gguf" "$OUT/$NAME-Q4_K_M.gguf" Q4_K_M > "$OUT/quantize-Q4_K_M.log" 2>&1 || echo "QUANT_FAILED $SIZE Q4_K_M"
  grep -E "detected Kev|downloading the base|merged|temperature|Model successfully exported|ERROR|Error" "$OUT/convert.log" | head -20
  (cd "$OUT" && sha256sum ./*.gguf > gguf.sha256 && ls -l ./*.gguf)
  echo "EXPORT_DONE $SIZE wall_s=$((SECONDS - start)) $(date -Is)"
done

#!/bin/bash
# 06_evidence.sh <container> <served_model_name> <tag> — collect the evidence set for one running server.
#   sudo -E bash scripts/mi300x/06_evidence.sh vllm_nemotron nemotron-3-ultra-bf16 nemotron_bf16_8xMI300X
#   sudo -E bash scripts/mi300x/06_evidence.sh vllm_inkling  inkling-bf16          inkling_bf16_16xMI300X_pp2
# Writes $MOE_ROOT/evidence/<tag>/ :
#   00_meta.txt                 image id, container args, wall-clock per smoke request
#   01_models.json              GET /v1/models
#   02_/03_/07_smoke*_request/response.json   the exact requests and raw responses (temperature 0)
#   04_rocm_smi_vram.json, 04_amd_smi_mem.json   per-GPU memory after load
#   05_server_full.log, 05_server_keylines.log   full container log and the backend/kernel/cache lines
#   SHA256SUMS.txt
# Inkling is a reasoning model: with max_tokens 200/256 the first two requests stop inside the reasoning segment
# (finish_reason=length); 07_smoke3 uses max_tokens 1024 and reaches a final answer.
set -u
. "$(dirname "$0")/00_env.sh"
CTR="${1:?container}"; MODEL="${2:?served model name}"; TAG="${3:?evidence tag}"
E="$MOE_ROOT/evidence/$TAG"; mkdir -p "$E"
echo "EVIDENCE_START=$(date -u +%FT%TZ) ctr=$CTR model=$MODEL" | tee "$E/00_meta.txt"
echo "kernel=$(uname -r) rocm_host=$(cat /opt/rocm/.info/version 2>/dev/null)" >> "$E/00_meta.txt"
docker inspect "$CTR" --format 'image={{.Config.Image}} imageid={{.Image}} started={{.State.StartedAt}} args={{join .Args " "}}' >> "$E/00_meta.txt" 2>&1

curl -s --max-time 30 http://127.0.0.1:8000/v1/models > "$E/01_models.json"; echo "models_http=$?" >> "$E/00_meta.txt"

smoke() { # <index> <max_tokens> <prompt>
  local req="$E/$1_request.json" resp="$E/$1_response.json"
  printf '{"model":"%s","messages":[{"role":"user","content":"%s"}],"max_tokens":%s,"temperature":0}\n' "$MODEL" "$3" "$2" > "$req"
  local t0 t1; t0=$(date +%s.%N)
  curl -s --max-time 600 http://127.0.0.1:8000/v1/chat/completions -H 'Content-Type: application/json' -d @"$req" > "$resp"
  t1=$(date +%s.%N); echo "$1_wall_secs=$(echo "$t1 - $t0" | bc)" >> "$E/00_meta.txt"
}
smoke 02_smoke  200  '用一句话说明 BF16 和 FP16 的区别。'
smoke 03_smoke2 256  'List three differences between Mamba-2 state space layers and softmax attention, in English, under 120 words.'
smoke 07_smoke3 1024 '用一句话说明 BF16 和 FP16 的区别。'

rocm-smi --showmeminfo vram --json > "$E/04_rocm_smi_vram.json" 2>/dev/null
amd-smi metric --mem --json > "$E/04_amd_smi_mem.json" 2>/dev/null || true
docker logs "$CTR" > "$E/05_server_full.log" 2>&1
grep -iE 'attention backend|Using .* backend|aiter|triton|moe|quantiz|kv.?cache|dtype|mamba|hip graph|cuda graph|compil|Model loading took|GPU KV cache size|Maximum concurrency|Available KV cache memory|Free memory on device' \
  "$E/05_server_full.log" | head -300 > "$E/05_server_keylines.log"
echo "EVIDENCE_END=$(date -u +%FT%TZ)" >> "$E/00_meta.txt"
( cd "$E" && find . -type f ! -name SHA256SUMS.txt -print0 | xargs -0 sha256sum > SHA256SUMS.txt )
echo "evidence written to $E ($(find "$E" -type f | wc -l) files)"

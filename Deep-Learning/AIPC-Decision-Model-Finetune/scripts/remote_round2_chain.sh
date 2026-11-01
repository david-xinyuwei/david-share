#!/usr/bin/env bash
# Unattended chain for the second round on one size: arm A, then arm B, then llama.cpp prep + GGUF export of both arms,
# then pack. Writes a single progress file the laptop can poll. Never stops or deallocates the VM.
# Usage: nohup bash remote_round2_chain.sh 0.8b > ~/remote-workspaces/aipc-decision/logs/round2-chain.log 2>&1 &
set -uo pipefail
source "$(dirname "$0")/remote_env.sh"
SIZE="${1:-0.8b}"
S="$(dirname "$0")"
P="$META/state/round2-chain.status"
mkdir -p "$META/state" "$META/logs"
echo "CHAIN_START $SIZE $(date -Is)" | tee -a "$P"
bash "$S/remote_round2.sh" "$SIZE" A && echo "ARM_A_OK $(date -Is)" | tee -a "$P" || echo "ARM_A_FAILED rc=$? $(date -Is)" | tee -a "$P"
bash "$S/remote_round2.sh" "$SIZE" B && echo "ARM_B_OK $(date -Is)" | tee -a "$P" || echo "ARM_B_FAILED rc=$? $(date -Is)" | tee -a "$P"
if [ ! -x "$WORK/llama.cpp/build/bin/llama-quantize" ]; then
  bash "$S/remote_llama_prep.sh" > "$META/logs/llama-prep.log" 2>&1 && echo "LLAMA_PREP_OK $(date -Is)" | tee -a "$P" || echo "LLAMA_PREP_FAILED rc=$? $(date -Is)" | tee -a "$P"
fi
bash "$S/remote_export_round2.sh" "$SIZE" A B > "$META/logs/export-round2.log" 2>&1 && echo "EXPORT_OK $(date -Is)" | tee -a "$P" || echo "EXPORT_FAILED rc=$? $(date -Is)" | tee -a "$P"
bash "$S/remote_pack_results.sh" > "$META/logs/pack.log" 2>&1 && echo "PACK_OK $(tail -n 1 "$META/logs/pack.log") $(date -Is)" | tee -a "$P" || echo "PACK_FAILED rc=$? $(date -Is)" | tee -a "$P"
echo "CHAIN_DONE $(date -Is)" | tee -a "$P"

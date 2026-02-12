#!/bin/bash
# Train all 4 domain-specific LoRA adapters for EXAONE
# Usage: bash scripts/train_all.sh [BASE_MODEL_PATH]
#
# Author: Xinyu Wei

set -e
export PYTHONUNBUFFERED=1

BASE_MODEL="${1:-/data/EXAONE-3.5-2.4B-Instruct}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="${SCRIPT_DIR}/../data"
OUTPUT_DIR="/data"

echo "=========================================="
echo "EXAONE Multi-LoRA Training (All 4 Domains)"
echo "Base model: ${BASE_MODEL}"
echo "=========================================="

# Domain → data file → output dir mapping
declare -A DOMAINS=(
    ["medical"]="medical_qa_train.jsonl"
    ["legal"]="legal_korean_train.jsonl"
    ["customer_support"]="customer_support_train.jsonl"
    ["code"]="code_assistant_train.jsonl"
)

for domain in medical legal customer_support code; do
    data_file="${DATA_DIR}/${DOMAINS[$domain]}"
    output_path="${OUTPUT_DIR}/exaone-lora-${domain}"

    echo ""
    echo "=== [$(date +%H:%M:%S)] Training ${domain} adapter ==="
    echo "  Data: ${data_file}"
    echo "  Output: ${output_path}"

    python3 "${SCRIPT_DIR}/train_lora_sft.py" \
        --model "${BASE_MODEL}" \
        --data "${data_file}" \
        --output "${output_path}" \
        --lora_r 32 \
        --lora_alpha 64 \
        --num_epochs 30 \
        --batch_size 4 \
        --gradient_accumulation_steps 8 \
        --learning_rate 2e-4

    echo "  ✅ ${domain} adapter saved to ${output_path}"
done

echo ""
echo "=========================================="
echo "All 4 adapters trained successfully!"
echo "=========================================="
ls -lhd ${OUTPUT_DIR}/exaone-lora-*/

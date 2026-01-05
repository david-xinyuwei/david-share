#!/bin/bash
cd /root/quant_exp
mkdir -p logs results

echo "=== 10B Zone Test (30 samples) ===" | tee logs/test_10b_zone.log
echo "Start: $(date)" | tee -a logs/test_10b_zone.log

TASK="mmlu_abstract_algebra"
LIMIT=30

# 1. Gemma-2-9B-it (9B)
echo "--- google/gemma-2-9b-it (9B) ---" | tee -a logs/test_10b_zone.log
for MODE in "orig" "4bit"; do
    if [ "$MODE" == "orig" ]; then
        ARGS="pretrained=google/gemma-2-9b-it,trust_remote_code=True"
        OUT="results/orig_gemma9b"
    else
        ARGS="pretrained=google/gemma-2-9b-it,trust_remote_code=True,load_in_4bit=True"
        OUT="results/4bit_gemma9b"
    fi
    echo "  $MODE:" | tee -a logs/test_10b_zone.log
    timeout 300 lm_eval --model hf --model_args $ARGS --tasks $TASK --batch_size auto --limit $LIMIT --output_path $OUT 2>&1 | grep -E "abstract_algebra|error|Error" | tee -a logs/test_10b_zone.log
done

# 2. Mistral-Nemo (12B)
echo "--- mistralai/Mistral-Nemo-Instruct-2407 (12B) ---" | tee -a logs/test_10b_zone.log
for MODE in "orig" "4bit"; do
    if [ "$MODE" == "orig" ]; then
        ARGS="pretrained=mistralai/Mistral-Nemo-Instruct-2407,trust_remote_code=True"
        OUT="results/orig_mistral12b"
    else
        ARGS="pretrained=mistralai/Mistral-Nemo-Instruct-2407,trust_remote_code=True,load_in_4bit=True"
        OUT="results/4bit_mistral12b"
    fi
    echo "  $MODE:" | tee -a logs/test_10b_zone.log
    timeout 300 lm_eval --model hf --model_args $ARGS --tasks $TASK --batch_size auto --limit $LIMIT --output_path $OUT 2>&1 | grep -E "abstract_algebra|error|Error" | tee -a logs/test_10b_zone.log
done

echo "=== Completed: $(date) ===" | tee -a logs/test_10b_zone.log

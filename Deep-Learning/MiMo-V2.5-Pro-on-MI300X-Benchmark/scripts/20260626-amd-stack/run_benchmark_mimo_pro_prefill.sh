#!/bin/bash


TOKEN_LIST=(8192 65536 262144)
output_tokens=1
concurrency_list=(4)
LOG_DIR="${LOG_DIR:-/data/xisun/bench_tp8_noep_mooncake}"
mkdir -p "$LOG_DIR"

# Loop execution: run each length multiple times (1 time), each run with a different concurrency
for input_tokens in "${TOKEN_LIST[@]}"; do
  for concurrency in "${concurrency_list[@]}"; do # iterate over the concurrency list
    # Run 1 round of test for each length and concurrency combination
    run=1 # only run one round
    echo -e "\n============================================================"
    echo "Testing: Input Token = ${input_tokens}, Concurrency = ${concurrency} | Run ${run}"
    echo "Log file: benchmark_decode_${input_tokens}_con${concurrency}_${run}.log"
    echo "============================================================"

    # Run benchmark: display in terminal + write to a separate log
    python3 -m sglang.bench_serving \
        --backend sglang \
        --model /data/models/MiMo-V2.5-Pro \
        --host 0.0.0.0 \
        --port 40000 \
        --dataset-name random \
        --random-input-len ${input_tokens} \
        --random-output-len ${output_tokens} \
        --random-range-ratio 1.0 \
	--dataset-path /data/xisun/ShareGPT_V3_unfiltered_cleaned_split.json \
        --flush-cache \
        --seed 12345 \
        --num-prompts 32 \
        --warmup-requests 1 \
        --max-concurrency ${concurrency} \
	--pd-separated \
        2>&1 | tee "$LOG_DIR/benchmark_${input_tokens}_con${concurrency}.log"

    echo -e "============================================================\n"
  done
done

echo "✅ All lengths and concurrency tests completed!"

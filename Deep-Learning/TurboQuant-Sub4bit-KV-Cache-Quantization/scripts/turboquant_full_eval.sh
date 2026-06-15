#!/bin/bash
# TurboQuant Full Accuracy Benchmark with lm-eval
# Runs MMLU (57 subjects) + GSM8K (1319 problems) across 4 KV cache configs
# Expected runtime: ~2 hours per config, ~8 hours total on H100

set -e
# Activate your Python environment with vLLM + lm-eval installed

MODEL="YOUR_MODEL_PATH"
OUTDIR="./results_lm_eval_results"
mkdir -p "$OUTDIR"

# Benchmark tasks: GSM8K (1319 test) + MMLU (57 subjects, ~14k questions)
# Using mmlu as it's faster than mmlu_pro; gsm8k is the standard math test
TASKS="gsm8k,mmlu"

for KV_DTYPE in auto fp8_e4m3 turboquant_4bit_nc turboquant_3bit_nc; do
    echo ""
    echo "============================================================"
    echo "Starting: kv_cache_dtype=${KV_DTYPE} at $(date)"
    echo "============================================================"
    
    OUTFILE="${OUTDIR}/results_${KV_DTYPE}.json"
    
    if [ -f "$OUTFILE" ]; then
        echo "  Results already exist at $OUTFILE, skipping..."
        continue
    fi
    
    lm_eval --model vllm \
        --model_args "pretrained=${MODEL},kv_cache_dtype=${KV_DTYPE},max_model_len=4096,gpu_memory_utilization=0.9,enforce_eager=True,trust_remote_code=True" \
        --tasks "$TASKS" \
        --batch_size auto \
        --output_path "$OUTFILE" \
        --log_samples \
        2>&1 | tee "${OUTDIR}/log_${KV_DTYPE}.txt"
    
    echo "Completed: ${KV_DTYPE} at $(date)"
    echo ""
done

echo ""
echo "============================================================"
echo "ALL BENCHMARKS COMPLETE at $(date)"
echo "============================================================"

# Print summary
echo ""
echo "===== SUMMARY ====="
for KV_DTYPE in auto fp8_e4m3 turboquant_4bit_nc turboquant_3bit_nc; do
    OUTFILE="${OUTDIR}/results_${KV_DTYPE}.json"
    if [ -f "$OUTFILE" ]; then
        echo "--- ${KV_DTYPE} ---"
        python3 -c "
import json, glob
files = glob.glob('${OUTDIR}/results_${KV_DTYPE}/**/results.json', recursive=True)
if not files:
    files = ['${OUTFILE}']
for f in files:
    try:
        d = json.load(open(f))
        results = d.get('results', d)
        for task, metrics in results.items():
            if isinstance(metrics, dict):
                acc = metrics.get('acc,none', metrics.get('acc_norm,none', metrics.get('exact_match,strict-match', 'N/A')))
                print(f'  {task}: {acc}')
    except: pass
" 2>/dev/null
    fi
done
echo "FULL_BENCHMARK_DONE"

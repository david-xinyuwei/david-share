#!/bin/bash
# TurboQuant Comprehensive Benchmark — 4 追加测试
# 1. 长上下文 NIAH (8K/16K/32K tokens)
# 2. HumanEval 代码生成
# 3. 27B 大模型 (Qwen3.5-27B MMLU+GSM8K)
# 4. 多次重复 (8B GSM8K ×3)
set -e
# Activate your Python environment with vLLM + lm-eval installed

OUTDIR="./results_comprehensive"
mkdir -p "$OUTDIR"

echo "============================================================"
echo "TurboQuant Comprehensive Benchmark Started at $(date)"
echo "============================================================"

# ============================================================
# TEST 1: Long-context NIAH (8K/16K/32K tokens)
# ============================================================
echo ""
echo "===== TEST 1: Long-context NIAH ====="
python3 -u -c "
import json, time, gc, torch
from vllm import LLM, SamplingParams

NEEDLE = 'The secret passphrase is: TURBOQUANT-DEEP-VERIFY-2026'

def build_haystack(target_tokens):
    para = 'The field of artificial intelligence continues to advance rapidly with new breakthroughs in language models, computer vision, and reinforcement learning. Researchers around the world are exploring novel architectures and training techniques to push the boundaries of what machines can achieve. '
    chunks = []
    est_tokens = 0
    insert_pos = target_tokens // 2
    inserted = False
    while est_tokens < target_tokens:
        if est_tokens >= insert_pos and not inserted:
            chunks.append(NEEDLE)
            inserted = True
        chunks.append(para)
        est_tokens += len(para.split()) * 1.3
    text = '\n'.join(chunks)
    return f'Read the following document and answer the question.\n\n{text}\n\nQuestion: What is the secret passphrase? Answer with just the passphrase.'

results = []
for kv_dtype in ['auto', 'fp8_e4m3', 'turboquant_4bit_nc', 'turboquant_3bit_nc']:
    for ctx_len in [8192, 16384, 32768]:
        print(f'  NIAH: kv={kv_dtype}, ctx={ctx_len}...', flush=True)
        try:
            llm = LLM(model='YOUR_MODEL_PATH', kv_cache_dtype=kv_dtype,
                       max_model_len=ctx_len, gpu_memory_utilization=0.92,
                       enforce_eager=True, trust_remote_code=True)
            prompt = build_haystack(ctx_len)
            sp = SamplingParams(temperature=0, max_tokens=64)
            t0 = time.time()
            out = llm.generate([prompt], sp)
            gen_time = time.time() - t0
            ans = out[0].outputs[0].text.strip()
            found = 'TURBOQUANT-DEEP-VERIFY-2026' in ans
            itoks = len(out[0].prompt_token_ids)
            r = {'kv_dtype': kv_dtype, 'target_ctx': ctx_len, 'actual_tokens': itoks,
                 'found': found, 'ans': ans[:120], 'time_s': round(gen_time, 2)}
            results.append(r)
            print(f'    tokens={itoks}, found={found}, time={gen_time:.1f}s', flush=True)
            del llm; gc.collect(); torch.cuda.empty_cache(); time.sleep(3)
        except Exception as e:
            print(f'    ERROR: {e}', flush=True)
            results.append({'kv_dtype': kv_dtype, 'target_ctx': ctx_len, 'error': str(e)[:200]})
            gc.collect(); torch.cuda.empty_cache(); time.sleep(3)

with open('$OUTDIR/niah_longctx.json', 'w') as f:
    json.dump(results, f, indent=2)

print('\n===== NIAH Long-Context Summary =====', flush=True)
print(f'{\"Config\":<25} {\"8K\":>6} {\"16K\":>6} {\"32K\":>6}')
for kv in ['auto', 'fp8_e4m3', 'turboquant_4bit_nc', 'turboquant_3bit_nc']:
    row = [kv]
    for ctx in [8192, 16384, 32768]:
        r = [x for x in results if x.get('kv_dtype')==kv and x.get('target_ctx')==ctx]
        if r and 'found' in r[0]:
            row.append('PASS' if r[0]['found'] else 'FAIL')
        else:
            row.append('ERR')
    print(f'{row[0]:<25} {row[1]:>6} {row[2]:>6} {row[3]:>6}')
print('TEST1_DONE', flush=True)
" 2>&1 | tee "$OUTDIR/test1_niah.log"

# ============================================================
# TEST 2: HumanEval (code generation)
# ============================================================
echo ""
echo "===== TEST 2: HumanEval ====="
for KV_DTYPE in auto fp8_e4m3 turboquant_4bit_nc turboquant_3bit_nc; do
    echo "  HumanEval: kv_cache_dtype=${KV_DTYPE}..."
    OUTFILE="${OUTDIR}/humaneval_${KV_DTYPE}.json"
    if [ -f "$OUTFILE" ]; then echo "  Skipping (exists)"; continue; fi
    lm_eval --model vllm \
        --model_args "pretrained=YOUR_MODEL_PATH,kv_cache_dtype=${KV_DTYPE},max_model_len=4096,gpu_memory_utilization=0.9,enforce_eager=True,trust_remote_code=True" \
        --tasks humaneval \
        --batch_size auto \
        --output_path "$OUTFILE" \
        2>&1 | tail -5
    echo "  Completed: ${KV_DTYPE}"
done
echo "TEST2_DONE"

# ============================================================
# TEST 3: 27B Model (Qwen3.5-27B, MMLU+GSM8K)
# ============================================================
echo ""
echo "===== TEST 3: 27B Model ====="
# Download 27B model if not present
if [ ! -f "YOUR_27B_MODEL_PATH/config.json" ]; then
    echo "  Downloading Qwen3.5-27B..."
    hf download Qwen/Qwen3.5-27B --local-dir YOUR_27B_MODEL_PATH 2>&1 | tail -3
fi

for KV_DTYPE in auto turboquant_4bit_nc turboquant_3bit_nc; do
    echo "  27B lm-eval: kv_cache_dtype=${KV_DTYPE}..."
    OUTFILE="${OUTDIR}/27b_${KV_DTYPE}.json"
    if [ -f "$OUTFILE" ]; then echo "  Skipping (exists)"; continue; fi
    lm_eval --model vllm \
        --model_args "pretrained=YOUR_27B_MODEL_PATH,kv_cache_dtype=${KV_DTYPE},max_model_len=4096,gpu_memory_utilization=0.92,enforce_eager=True,trust_remote_code=True" \
        --tasks gsm8k,mmlu \
        --batch_size auto \
        --output_path "$OUTFILE" \
        2>&1 | tail -10
    echo "  Completed 27B: ${KV_DTYPE}"
done
echo "TEST3_DONE"

# ============================================================
# TEST 4: Repeated runs (8B GSM8K ×3)
# ============================================================
echo ""
echo "===== TEST 4: Repeated Runs (GSM8K ×3) ====="
for RUN in 1 2 3; do
    for KV_DTYPE in auto turboquant_4bit_nc turboquant_3bit_nc; do
        echo "  Run ${RUN}, kv=${KV_DTYPE}..."
        OUTFILE="${OUTDIR}/repeat_run${RUN}_${KV_DTYPE}.json"
        if [ -f "$OUTFILE" ]; then echo "  Skipping (exists)"; continue; fi
        lm_eval --model vllm \
            --model_args "pretrained=YOUR_MODEL_PATH,kv_cache_dtype=${KV_DTYPE},max_model_len=4096,gpu_memory_utilization=0.9,enforce_eager=True,trust_remote_code=True" \
            --tasks gsm8k \
            --batch_size auto \
            --output_path "$OUTFILE" \
            2>&1 | tail -3
    done
done
echo "TEST4_DONE"

# ============================================================
# SUMMARY
# ============================================================
echo ""
echo "============================================================"
echo "ALL COMPREHENSIVE TESTS COMPLETE at $(date)"
echo "============================================================"

# Extract all results
python3 -u -c "
import json, glob, os

print('\n===== COMPREHENSIVE RESULTS =====\n')

# Test 1: NIAH
print('--- Test 1: Long-context NIAH ---')
try:
    niah = json.load(open('$OUTDIR/niah_longctx.json'))
    for r in niah:
        status = 'PASS' if r.get('found') else ('FAIL' if 'found' in r else 'ERR')
        print(f\"  {r.get('kv_dtype','?'):<25} ctx={r.get('target_ctx','?'):<6} {status}\")
except: print('  No NIAH results')

# Test 2: HumanEval
print('\n--- Test 2: HumanEval ---')
for cfg in ['auto', 'fp8_e4m3', 'turboquant_4bit_nc', 'turboquant_3bit_nc']:
    files = glob.glob(f'$OUTDIR/humaneval_{cfg}*/**/results.json', recursive=True)
    if not files: files = glob.glob(f'$OUTDIR/humaneval_{cfg}*.json')
    for f in files:
        try:
            d = json.load(open(f))
            r = d.get('results', d)
            for task, metrics in r.items():
                if isinstance(metrics, dict):
                    acc = metrics.get('pass@1,none', metrics.get('acc,none', 'N/A'))
                    print(f'  {cfg:<25} {task}: {acc}')
        except: pass

# Test 3: 27B
print('\n--- Test 3: 27B Model ---')
for cfg in ['auto', 'turboquant_4bit_nc', 'turboquant_3bit_nc']:
    files = glob.glob(f'$OUTDIR/27b_{cfg}*/**/results.json', recursive=True)
    if not files: files = glob.glob(f'$OUTDIR/27b_{cfg}*.json')
    for f in files:
        try:
            d = json.load(open(f))
            r = d.get('results', d)
            mmlu = r.get('mmlu', {}).get('acc,none', 'N/A')
            gsm = r.get('gsm8k', {}).get('exact_match,strict-match', r.get('gsm8k', {}).get('acc,none', 'N/A'))
            print(f'  {cfg:<25} MMLU={mmlu} GSM8K={gsm}')
        except: pass

# Test 4: Repeated
print('\n--- Test 4: Repeated GSM8K ---')
for cfg in ['auto', 'turboquant_4bit_nc', 'turboquant_3bit_nc']:
    scores = []
    for run in [1, 2, 3]:
        files = glob.glob(f'$OUTDIR/repeat_run{run}_{cfg}*/**/results.json', recursive=True)
        if not files: files = glob.glob(f'$OUTDIR/repeat_run{run}_{cfg}*.json')
        for f in files:
            try:
                d = json.load(open(f))
                r = d.get('results', d)
                gsm = r.get('gsm8k', {}).get('exact_match,strict-match', r.get('gsm8k', {}).get('acc,none', None))
                if gsm is not None: scores.append(gsm)
            except: pass
    if scores:
        avg = sum(scores)/len(scores)
        spread = max(scores)-min(scores)
        print(f'  {cfg:<25} runs={[round(s*100,1) for s in scores]}% avg={avg*100:.1f}% spread={spread*100:.1f}%')
    else:
        print(f'  {cfg:<25} no results')

print('\nALL_COMPREHENSIVE_DONE')
" 2>&1 | tee "$OUTDIR/comprehensive_summary.log"

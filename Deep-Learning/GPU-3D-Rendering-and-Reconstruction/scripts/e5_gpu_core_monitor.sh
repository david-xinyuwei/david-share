#!/bin/bash
# E5: GPU Core Utilization Monitor — 对比渲染 vs AI 推理的 GPU 利用率
# Author: 魏新宇 (Xinyu Wei)
#
# 用法: bash e5_gpu_core_monitor.sh [workload]
#   workload: idle / render_eevee / render_cycles / ai_inference
#
# 输出: results/e5_gpu/e5_<workload>_gpu.csv

set -e

WORKLOAD=${1:-idle}
OUTPUT_DIR="/root/rendering-experiments/results/e5_gpu"
mkdir -p "$OUTPUT_DIR"

DURATION=30  # 采集 30 秒
INTERVAL=1   # 每秒采集

echo "============================================================"
echo "E5: GPU Core Utilization Monitor"
echo "  Workload: $WORKLOAD"
echo "  Duration: ${DURATION}s, Interval: ${INTERVAL}s"
echo "============================================================"

OUTPUT_FILE="$OUTPUT_DIR/e5_${WORKLOAD}_gpu.csv"

# 采集 GPU 利用率
echo "timestamp,gpu_util_pct,mem_util_pct,mem_used_mb,mem_total_mb,power_w,temp_c,sm_clock_mhz,gpu_name" > "$OUTPUT_FILE"

for i in $(seq 1 $DURATION); do
    TIMESTAMP=$(date +%Y-%m-%dT%H:%M:%S)
    DATA=$(nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total,power.draw,temperature.gpu,clocks.sm,name --format=csv,noheader,nounits 2>/dev/null)
    echo "$TIMESTAMP,$DATA" >> "$OUTPUT_FILE"
    
    if (( i % 10 == 0 )); then
        echo "  [$i/$DURATION] $DATA"
    fi
    sleep $INTERVAL
done

echo ""
echo "✅ 采集完成: $OUTPUT_FILE"
echo ""

# 统计
echo "=== 统计 ==="
python3 -c "
import csv
with open('$OUTPUT_FILE') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    
gpu_utils = [float(r['gpu_util_pct'].strip()) for r in rows]
mem_utils = [float(r['mem_util_pct'].strip()) for r in rows]
powers = [float(r['power_w'].strip()) for r in rows if r['power_w'].strip() != 'N/A']

print(f'  GPU 利用率: avg={sum(gpu_utils)/len(gpu_utils):.1f}%, max={max(gpu_utils):.0f}%, min={min(gpu_utils):.0f}%')
print(f'  显存利用率: avg={sum(mem_utils)/len(mem_utils):.1f}%, max={max(mem_utils):.0f}%')
if powers:
    print(f'  功耗: avg={sum(powers)/len(powers):.1f}W, max={max(powers):.0f}W')
print(f'  GPU: {rows[0][\"gpu_name\"].strip()}')
print(f'  采样数: {len(rows)}')
"

echo "============================================================"

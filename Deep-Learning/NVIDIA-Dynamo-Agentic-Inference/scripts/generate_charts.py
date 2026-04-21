#!/usr/bin/env python3
"""Generate benchmark comparison charts for NVIDIA Dynamo Agentic Inference Repo.
Author: Xinyu Wei
"""
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
import os

matplotlib.rcParams['font.size'] = 11
matplotlib.rcParams['figure.dpi'] = 150

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'images')
os.makedirs(OUT_DIR, exist_ok=True)

# === Data from benchmark logs ===

# Low concurrency (50 prompts @ 5 req/s)
low_configs = ['Single GPU', 'TP=2', 'Dynamo PD\n1P1D']
low_ttft =    [43.42, 32.47, 49.61]
low_tps =     [541.31, 559.10, 539.70]
low_e2e =     [870.53, 575.51, 827.68]
low_p99_itl = [35.25, 13.17, 12.49]

# High concurrency (200 prompts @ 20 req/s) - fair 2v2
high_configs = ['TP=2', 'Dynamo PD 1P1D']
high_ttft =    [25.29, 53.01]
high_tps =     [2259.35, 2179.46]
high_e2e =     [848.82, 995.12]
high_p99_itl = [24.56, 11.78]
high_p95_itl = [13.82, 8.24]

# Prefix Cache
cache_configs = ['Cold Cache', 'Warm Cache', 'Flush Control']
cache_ttft =    [31.89, 18.65, 31.51]
cache_p99_ttft = [53.24, 26.11, 51.59]
cache_max_itl = [44.02, 17.01, 43.74]

colors_3 = ['#2196F3', '#4CAF50', '#FF9800']
colors_2 = ['#2196F3', '#FF9800']
colors_cache = ['#9E9E9E', '#4CAF50', '#F44336']

def save(fig, name):
    path = os.path.join(OUT_DIR, name)
    fig.savefig(path, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"  Saved: {path}")

# --- Chart 1: Low Concurrency 4-metric comparison ---
fig, axes = plt.subplots(1, 4, figsize=(16, 4))
fig.suptitle('Low Concurrency: 50 prompts @ 5 req/s (Qwen3-8B, H100 NVL)', fontsize=13, fontweight='bold')

for ax, data, title, unit, better in zip(
    axes,
    [low_ttft, low_tps, low_e2e, low_p99_itl],
    ['Mean TTFT', 'Output tok/s', 'Mean E2E', 'P99 ITL'],
    ['ms', 'tok/s', 'ms', 'ms'],
    ['lower', 'higher', 'lower', 'lower']
):
    bars = ax.bar(low_configs, data, color=colors_3, edgecolor='white', linewidth=0.5)
    ax.set_title(title, fontweight='bold')
    ax.set_ylabel(unit)
    for bar, val in zip(bars, data):
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + max(data)*0.02,
                f'{val:.1f}', ha='center', va='bottom', fontsize=9)
    # Highlight best
    best_idx = data.index(min(data)) if better == 'lower' else data.index(max(data))
    bars[best_idx].set_edgecolor('#000000')
    bars[best_idx].set_linewidth(2)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

fig.tight_layout()
save(fig, 'benchmark_low_concurrency.png')

# --- Chart 2: High Concurrency fair 2v2 ---
fig, axes = plt.subplots(1, 4, figsize=(14, 4))
fig.suptitle('High Concurrency: 200 prompts @ 20 req/s — Fair 2-GPU Comparison', fontsize=13, fontweight='bold')

for ax, data, title, unit in zip(
    axes,
    [high_ttft, high_tps, high_e2e, high_p99_itl],
    ['Mean TTFT', 'Output tok/s', 'Mean E2E', 'P99 ITL'],
    ['ms', 'tok/s', 'ms', 'ms']
):
    bars = ax.bar(high_configs, data, color=colors_2, edgecolor='white', width=0.5)
    ax.set_title(title, fontweight='bold')
    ax.set_ylabel(unit)
    for bar, val in zip(bars, data):
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + max(data)*0.02,
                f'{val:.1f}', ha='center', va='bottom', fontsize=10)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

fig.tight_layout()
save(fig, 'benchmark_high_concurrency.png')

# --- Chart 3: Prefix Cache effect ---
fig, axes = plt.subplots(1, 3, figsize=(13, 4))
fig.suptitle('Prefix Cache Effect: Same Seed Repeated (Single GPU)', fontsize=13, fontweight='bold')

for ax, data, title, unit in zip(
    axes,
    [cache_ttft, cache_p99_ttft, cache_max_itl],
    ['Mean TTFT', 'P99 TTFT', 'Max ITL'],
    ['ms', 'ms', 'ms']
):
    bars = ax.bar(cache_configs, data, color=colors_cache, edgecolor='white')
    ax.set_title(title, fontweight='bold')
    ax.set_ylabel(unit)
    for bar, val in zip(bars, data):
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + max(data)*0.02,
                f'{val:.1f}', ha='center', va='bottom', fontsize=10)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

fig.tight_layout()
save(fig, 'benchmark_prefix_cache.png')

# --- Chart 4: PD advantage/disadvantage summary ---
fig, ax = plt.subplots(figsize=(10, 5))
metrics = ['TTFT', 'tok/s', 'E2E', 'P99 ITL', 'P95 ITL']
pct_change = [
    (53.01 - 25.29) / 25.29 * 100,   # TTFT: PD worse
    (2179.46 - 2259.35) / 2259.35 * 100,  # tok/s: PD worse
    (995.12 - 848.82) / 848.82 * 100,  # E2E: PD worse
    (11.78 - 24.56) / 24.56 * 100,    # P99 ITL: PD better
    (8.24 - 13.82) / 13.82 * 100,     # P95 ITL: PD better
]
bar_colors = ['#F44336' if v > 0 else '#4CAF50' for v in pct_change]
bars = ax.barh(metrics, pct_change, color=bar_colors, edgecolor='white', height=0.6)
ax.axvline(x=0, color='black', linewidth=0.8)
ax.set_xlabel('% Change (PD vs TP=2) — Negative = PD Better')
ax.set_title('Dynamo PD vs TP=2: Where PD Wins and Loses\n(200 prompts @ 20 req/s, 2×H100 NVL)', fontweight='bold')
for bar, val in zip(bars, pct_change):
    x_pos = val + (3 if val > 0 else -3)
    ax.text(x_pos, bar.get_y() + bar.get_height()/2.,
            f'{val:+.1f}%', ha='left' if val > 0 else 'right', va='center', fontweight='bold')
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
fig.tight_layout()
save(fig, 'pd_vs_tp2_summary.png')

# ===== NEW: 32B Model Charts =====

# 32B data (C-series, 100 prompts @ 10 req/s, 1024/256 tokens)
configs_32b_3 = ['Baseline\n(1 GPU)', 'TP=2\n(2 GPU)', 'Dynamo PD\n1P1D (2 GPU)']
c32_tps =     [748.83, 965.95, 830.06]
c32_ttft =    [368.60, 129.95, 355.20]
c32_e2e =     [7547.93, 3523.50, 3558.81]
c32_p99_itl = [680.06, 201.42, 31.00]

# --- Chart 5: 32B 3-config comparison ---
fig, axes = plt.subplots(1, 4, figsize=(17, 4.5))
fig.suptitle('32B Model: 100 prompts @ 10 req/s (Qwen2.5-32B, 2×H100 NVL)', fontsize=13, fontweight='bold')

for ax, data, title, unit, better in zip(
    axes,
    [c32_ttft, c32_tps, c32_e2e, c32_p99_itl],
    ['Mean TTFT', 'Output tok/s', 'Mean E2E', 'P99 ITL'],
    ['ms', 'tok/s', 'ms', 'ms'],
    ['lower', 'higher', 'lower', 'lower']
):
    bars = ax.bar(range(len(data)), data, color=colors_3, edgecolor='white', linewidth=0.5)
    ax.set_title(title, fontweight='bold')
    ax.set_ylabel(unit)
    ax.set_xticks(range(len(data)))
    ax.set_xticklabels(configs_32b_3, fontsize=9)
    for bar, val in zip(bars, data):
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + max(data)*0.02,
                f'{val:.0f}', ha='center', va='bottom', fontsize=9)
    best_idx = data.index(min(data)) if better == 'lower' else data.index(max(data))
    bars[best_idx].set_edgecolor('#000000')
    bars[best_idx].set_linewidth(2)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

fig.tight_layout()
save(fig, 'benchmark_32b_tp_vs_pd.png')

# --- Chart 6: Cross-model P99 ITL comparison ---
fig, ax = plt.subplots(figsize=(9, 5))
x = np.arange(2)
w = 0.32
tp_vals  = [24.56, 201.42]
pd_vals  = [11.78, 31.00]
bars1 = ax.bar(x - w/2, tp_vals, w, label='TP=2', color='#2196F3', edgecolor='white')
bars2 = ax.bar(x + w/2, pd_vals, w, label='Dynamo PD', color='#FF9800', edgecolor='white')
ax.set_xticks(x)
ax.set_xticklabels(['Qwen3-8B\n(200@20)', 'Qwen2.5-32B\n(100@10)'], fontsize=11)
ax.set_ylabel('P99 ITL (ms)')
ax.set_title('P99 ITL: PD Advantage Scales with Model Size', fontsize=13, fontweight='bold')
ax.legend()
for bar, val in zip(bars1, tp_vals):
    ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 3,
            f'{val:.1f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
for bar, val in zip(bars2, pd_vals):
    ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 3,
            f'{val:.1f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
# Add advantage annotations
ax.annotate('-52%', xy=(0, 11.78), xytext=(0.35, 50),
            fontsize=12, fontweight='bold', color='#4CAF50',
            arrowprops=dict(arrowstyle='->', color='#4CAF50', lw=1.5))
ax.annotate('-85%', xy=(1, 31.00), xytext=(1.35, 130),
            fontsize=14, fontweight='bold', color='#4CAF50',
            arrowprops=dict(arrowstyle='->', color='#4CAF50', lw=2))
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
fig.tight_layout()
save(fig, 'benchmark_model_size_itl.png')

# --- Chart 7: Chunked Prefill ablation ---
fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
fig.suptitle('Chunked Prefill Ablation: 32B Single GPU (100@10, 1024/256)', fontsize=13, fontweight='bold')

chunk_configs = ['Chunked ON\n(default)', 'Chunked OFF']
chunk_colors = ['#4CAF50', '#F44336']
chunk_data = [
    ([368.60, 1729.08], 'Mean TTFT', 'ms'),
    ([748.83, 617.84], 'Output tok/s', 'tok/s'),
    ([257.79, 154.97], 'P95 ITL', 'ms'),
]
for ax, (data, title, unit) in zip(axes, chunk_data):
    bars = ax.bar(chunk_configs, data, color=chunk_colors, edgecolor='white', width=0.5)
    ax.set_title(title, fontweight='bold')
    ax.set_ylabel(unit)
    for bar, val in zip(bars, data):
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + max(data)*0.02,
                f'{val:.0f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    # Delta annotation between bars
    pct = (data[1] - data[0]) / data[0] * 100
    mid_y = (data[0] + data[1]) / 2
    ax.text(0.5, mid_y, f'{pct:+.0f}%', ha='center', fontsize=13,
            fontweight='bold', color='#F44336' if pct > 0 else '#4CAF50')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

fig.tight_layout()
save(fig, 'benchmark_chunked_ablation.png')

print(f"\nAll charts saved to {OUT_DIR}/")

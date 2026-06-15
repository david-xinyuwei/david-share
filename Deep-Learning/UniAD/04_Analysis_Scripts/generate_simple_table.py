#!/usr/bin/env python3
"""
生成简洁清晰的三方对比表格 - 每隔10个iter采样
只对比 Time, Loss, Grad_Norm
"""

import re
import pandas as pd

def parse_training_log(log_file: str):
    """解析训练日志"""
    data = []
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    pattern = r'Epoch \[(\d+)\]\[(\d+)/(\d+)\].*?time: ([\d.]+),.*?memory: (\d+),.*?loss: ([\d.]+),.*?grad_norm: ([\d.]+)'
    
    for line in lines:
        match = re.search(pattern, line)
        if match:
            data.append({
                'epoch': int(match.group(1)),
                'iter': int(match.group(2)),
                'time': float(match.group(4)),
                'memory': int(match.group(5)),
                'loss': float(match.group(6)),
                'grad_norm': float(match.group(7))
            })
    
    return pd.DataFrame(data)


print("📊 加载训练日志...")
fp32_df = parse_training_log('training_logs/fp32_test.log')
fp16_df = parse_training_log('training_logs/fp16_test.log')
flash_df = parse_training_log('training_logs/flashattn_test_latest.log')

print(f"✅ FP32:     {len(fp32_df)} 数据")
print(f"✅ FP16:     {len(fp16_df)} 数据")
print(f"✅ FP16+FA2: {len(flash_df)} 数据")
print()

# 生成对比表格
comparison_table = []

for epoch in [1, 2, 3]:
    fp32_e = fp32_df[fp32_df['epoch'] == epoch]
    fp16_e = fp16_df[fp16_df['epoch'] == epoch]
    flash_e = flash_df[flash_df['epoch'] == epoch]
    
    if len(fp32_e) == 0 or len(fp16_e) == 0 or len(flash_e) == 0:
        continue
    
    # 每隔10个iter采样
    max_iter = min(fp32_e['iter'].max(), fp16_e['iter'].max(), flash_e['iter'].max())
    sample_iters = list(range(10, max_iter + 1, 10))
    if max_iter not in sample_iters:
        sample_iters.append(max_iter)
    
    for it in sample_iters:
        fp32_row = fp32_e[fp32_e['iter'] == it]
        fp16_row = fp16_e[fp16_e['iter'] == it]
        flash_row = flash_e[flash_e['iter'] == it]
        
        if len(fp32_row) > 0 and len(fp16_row) > 0 and len(flash_row) > 0:
            comparison_table.append({
                'Epoch': epoch,
                'Iter': it,
                'FP32_Time': fp32_row['time'].values[0],
                'FP16_Time': fp16_row['time'].values[0],
                'FA2_Time': flash_row['time'].values[0],
                'FP32_Loss': fp32_row['loss'].values[0],
                'FP16_Loss': fp16_row['loss'].values[0],
                'FA2_Loss': flash_row['loss'].values[0],
                'FP32_Grad': fp32_row['grad_norm'].values[0],
                'FP16_Grad': fp16_row['grad_norm'].values[0],
                'FA2_Grad': flash_row['grad_norm'].values[0]
            })

df = pd.DataFrame(comparison_table)

# 保存CSV
csv_file = 'training_logs/comparison_clean_10iter.csv'
df.to_csv(csv_file, index=False, float_format='%.4f')
print(f"✅ CSV 已保存: {csv_file}")
print()

# 打印表格
print("=" * 140)
print("FP32 vs FP16 vs FP16+FA2 对比表 (每10 iter采样, 3 Epochs)")
print("=" * 140)
print()

print("【训练时间 (秒/iter)】")
print("-" * 140)
print(f"{'Epoch':^6} {'Iter':^6} | {'FP32':^8} {'FP16':^8} {'FA2':^8} | {'FP16加速比':^10} {'FA2加速比':^10} {'FA2 vs FP16':^10}")
print("-" * 140)
for _, row in df.iterrows():
    speedup_fp16 = row['FP32_Time'] / row['FP16_Time']
    speedup_fa2 = row['FP32_Time'] / row['FA2_Time']
    speedup_fa2_fp16 = row['FP16_Time'] / row['FA2_Time']
    print(f"{int(row['Epoch']):^6} {int(row['Iter']):^6} | "
          f"{row['FP32_Time']:>8.4f} {row['FP16_Time']:>8.4f} {row['FA2_Time']:>8.4f} | "
          f"{speedup_fp16:>10.3f}x {speedup_fa2:>10.3f}x {speedup_fa2_fp16:>10.3f}x")
print()

print("【Loss 对比】")
print("-" * 140)
print(f"{'Epoch':^6} {'Iter':^6} | {'FP32':^10} {'FP16':^10} {'FA2':^10} | {'FP16差异':^10} {'FA2差异':^10} {'FA2-FP16':^10}")
print("-" * 140)
for _, row in df.iterrows():
    diff_fp16 = row['FP16_Loss'] - row['FP32_Loss']
    diff_fa2 = row['FA2_Loss'] - row['FP32_Loss']
    diff_fa2_fp16 = row['FA2_Loss'] - row['FP16_Loss']
    print(f"{int(row['Epoch']):^6} {int(row['Iter']):^6} | "
          f"{row['FP32_Loss']:>10.2f} {row['FP16_Loss']:>10.2f} {row['FA2_Loss']:>10.2f} | "
          f"{diff_fp16:>10.2f} {diff_fa2:>10.2f} {diff_fa2_fp16:>10.2f}")
print()

print("【梯度范数对比】")
print("-" * 140)
print(f"{'Epoch':^6} {'Iter':^6} | {'FP32':^10} {'FP16':^10} {'FA2':^10} | {'FP16比值':^10} {'FA2比值':^10} {'FA2/FP16':^10}")
print("-" * 140)
for _, row in df.iterrows():
    ratio_fp16 = row['FP16_Grad'] / row['FP32_Grad'] if row['FP32_Grad'] > 0 else 0
    ratio_fa2 = row['FA2_Grad'] / row['FP32_Grad'] if row['FP32_Grad'] > 0 else 0
    ratio_fa2_fp16 = row['FA2_Grad'] / row['FP16_Grad'] if row['FP16_Grad'] > 0 else 0
    print(f"{int(row['Epoch']):^6} {int(row['Iter']):^6} | "
          f"{row['FP32_Grad']:>10.2f} {row['FP16_Grad']:>10.2f} {row['FA2_Grad']:>10.2f} | "
          f"{ratio_fp16:>10.3f} {ratio_fa2:>10.3f} {ratio_fa2_fp16:>10.3f}")
print()

print("=" * 140)
print("【统计汇总】")
print("=" * 140)
print()
print(f"平均训练时间:  FP32 = {df['FP32_Time'].mean():.4f}s  |  FP16 = {df['FP16_Time'].mean():.4f}s  |  FA2 = {df['FA2_Time'].mean():.4f}s")
print(f"平均 Loss:     FP32 = {df['FP32_Loss'].mean():.2f}     |  FP16 = {df['FP16_Loss'].mean():.2f}     |  FA2 = {df['FA2_Loss'].mean():.2f}")
print(f"平均梯度范数:  FP32 = {df['FP32_Grad'].mean():.2f}     |  FP16 = {df['FP16_Grad'].mean():.2f}    |  FA2 = {df['FA2_Grad'].mean():.2f}")
print()
avg_speedup_fp16 = df['FP32_Time'].mean() / df['FP16_Time'].mean()
avg_speedup_fa2 = df['FP32_Time'].mean() / df['FA2_Time'].mean()
avg_speedup_fa2_fp16 = df['FP16_Time'].mean() / df['FA2_Time'].mean()
print(f"平均加速比:    FP16 vs FP32 = {avg_speedup_fp16:.3f}x  |  FA2 vs FP32 = {avg_speedup_fa2:.3f}x  |  FA2 vs FP16 = {avg_speedup_fa2_fp16:.3f}x")
print()
print("=" * 140)
print("✅ 完成")
print("=" * 140)

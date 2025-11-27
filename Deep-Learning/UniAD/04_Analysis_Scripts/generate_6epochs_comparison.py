#!/usr/bin/env python3
"""
生成完整6 Epochs对比表格 - 每隔15个iter采样
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


print("📊 加载训练日志 (6 Epochs)...")
fp32_df = parse_training_log('training_logs/fp32_test.log')
fp16_df = parse_training_log('training_logs/fp16_test.log')
flash_df = parse_training_log('training_logs/flashattn_test_6epochs.log')

print(f"✅ FP32:     {len(fp32_df)} 数据, {fp32_df['epoch'].max()} epochs")
print(f"✅ FP16:     {len(fp16_df)} 数据, {fp16_df['epoch'].max()} epochs")
print(f"✅ FP16+FA2: {len(flash_df)} 数据, {flash_df['epoch'].max()} epochs")
print()

# 生成对比表格 - 每隔15个iter
comparison_table = []

for epoch in range(1, 7):  # 6 个 epochs
    fp32_e = fp32_df[fp32_df['epoch'] == epoch]
    fp16_e = fp16_df[fp16_df['epoch'] == epoch]
    flash_e = flash_df[flash_df['epoch'] == epoch]
    
    if len(fp32_e) == 0 or len(fp16_e) == 0 or len(flash_e) == 0:
        continue
    
    # 每隔15个iter采样
    max_iter = min(fp32_e['iter'].max(), fp16_e['iter'].max(), flash_e['iter'].max())
    sample_iters = list(range(15, max_iter + 1, 15))
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

# 添加加速比列
df['FP16_Speedup_vs_FP32'] = df['FP32_Time'] / df['FP16_Time']
df['FA2_Speedup_vs_FP32'] = df['FP32_Time'] / df['FA2_Time']
df['FA2_Speedup_vs_FP16'] = df['FP16_Time'] / df['FA2_Time']

# 保存CSV
csv_file = 'training_logs/comparison_6epochs_15iter.csv'
df.to_csv(csv_file, index=False, float_format='%.4f')
print(f"✅ CSV 已保存: {csv_file}")
print(f"   总共 {len(df)} 行数据 (6 Epochs × 每隔15 iter)")
print()

# 打印表格
print("=" * 150)
print("FP32 vs FP16 vs FP16+FA2 完整对比表 (6 Epochs, 每15 iter采样)")
print("=" * 150)
print()

print("【训练时间对比 (秒/iter)】")
print("-" * 150)
print(f"{'Epoch':^6} {'Iter':^6} | {'FP32':^8} {'FP16':^8} {'FA2':^8} | {'FP16 vs FP32':^12} {'FA2 vs FP32':^12} {'FA2 vs FP16':^12}")
print("-" * 150)
for _, row in df.iterrows():
    print(f"{int(row['Epoch']):^6} {int(row['Iter']):^6} | "
          f"{row['FP32_Time']:>8.4f} {row['FP16_Time']:>8.4f} {row['FA2_Time']:>8.4f} | "
          f"{row['FP16_Speedup_vs_FP32']:>12.3f}x {row['FA2_Speedup_vs_FP32']:>12.3f}x {row['FA2_Speedup_vs_FP16']:>12.3f}x")
print()

print("【Loss 对比】")
print("-" * 150)
print(f"{'Epoch':^6} {'Iter':^6} | {'FP32':^10} {'FP16':^10} {'FA2':^10} | {'FP16-FP32':^10} {'FA2-FP32':^10} {'FA2-FP16':^10}")
print("-" * 150)
for _, row in df.iterrows():
    diff_fp16 = row['FP16_Loss'] - row['FP32_Loss']
    diff_fa2 = row['FA2_Loss'] - row['FP32_Loss']
    diff_fa2_fp16 = row['FA2_Loss'] - row['FP16_Loss']
    print(f"{int(row['Epoch']):^6} {int(row['Iter']):^6} | "
          f"{row['FP32_Loss']:>10.2f} {row['FP16_Loss']:>10.2f} {row['FA2_Loss']:>10.2f} | "
          f"{diff_fp16:>10.2f} {diff_fa2:>10.2f} {diff_fa2_fp16:>10.2f}")
print()

print("【梯度范数对比】")
print("-" * 150)
print(f"{'Epoch':^6} {'Iter':^6} | {'FP32':^10} {'FP16':^10} {'FA2':^10} | {'FP16/FP32':^10} {'FA2/FP32':^10} {'FA2/FP16':^10}")
print("-" * 150)
for _, row in df.iterrows():
    ratio_fp16 = row['FP16_Grad'] / row['FP32_Grad'] if row['FP32_Grad'] > 0 else 0
    ratio_fa2 = row['FA2_Grad'] / row['FP32_Grad'] if row['FP32_Grad'] > 0 else 0
    ratio_fa2_fp16 = row['FA2_Grad'] / row['FP16_Grad'] if row['FP16_Grad'] > 0 else 0
    print(f"{int(row['Epoch']):^6} {int(row['Iter']):^6} | "
          f"{row['FP32_Grad']:>10.2f} {row['FP16_Grad']:>10.2f} {row['FA2_Grad']:>10.2f} | "
          f"{ratio_fp16:>10.3f} {ratio_fa2:>10.3f} {ratio_fa2_fp16:>10.3f}")
print()

print("=" * 150)
print("【统计汇总 - 全部6 Epochs】")
print("=" * 150)
print()
print(f"平均训练时间:  FP32 = {df['FP32_Time'].mean():.4f}s  |  FP16 = {df['FP16_Time'].mean():.4f}s  |  FA2 = {df['FA2_Time'].mean():.4f}s")
print(f"平均 Loss:     FP32 = {df['FP32_Loss'].mean():.2f}     |  FP16 = {df['FP16_Loss'].mean():.2f}     |  FA2 = {df['FA2_Loss'].mean():.2f}")
print(f"平均梯度范数:  FP32 = {df['FP32_Grad'].mean():.2f}     |  FP16 = {df['FP16_Grad'].mean():.2f}    |  FA2 = {df['FA2_Grad'].mean():.2f}")
print()
print(f"平均加速比:    FP16 vs FP32 = {df['FP16_Speedup_vs_FP32'].mean():.3f}x  |  FA2 vs FP32 = {df['FA2_Speedup_vs_FP32'].mean():.3f}x  |  FA2 vs FP16 = {df['FA2_Speedup_vs_FP16'].mean():.3f}x")
print()

# 分 Epoch 统计
print("=" * 150)
print("【分 Epoch 统计】")
print("=" * 150)
print()
for epoch in range(1, 7):
    epoch_data = df[df['Epoch'] == epoch]
    if len(epoch_data) > 0:
        print(f"Epoch {epoch}:")
        print(f"  平均时间: FP32={epoch_data['FP32_Time'].mean():.4f}s, FP16={epoch_data['FP16_Time'].mean():.4f}s, FA2={epoch_data['FA2_Time'].mean():.4f}s")
        print(f"  加速比:   FP16={epoch_data['FP16_Speedup_vs_FP32'].mean():.3f}x, FA2={epoch_data['FA2_Speedup_vs_FP32'].mean():.3f}x, FA2 vs FP16={epoch_data['FA2_Speedup_vs_FP16'].mean():.3f}x")
        print()

print("=" * 150)
print("✅ 完成")
print("=" * 150)

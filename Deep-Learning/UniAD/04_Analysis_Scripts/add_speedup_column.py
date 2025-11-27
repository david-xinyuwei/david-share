#!/usr/bin/env python3
"""
生成完整的三方对比表格 - 包含加速比列
"""

import pandas as pd

# 读取现有CSV
df = pd.read_csv('training_logs/comparison_clean_10iter.csv')

# 添加加速比列
df['FP16_Speedup_vs_FP32'] = df['FP32_Time'] / df['FP16_Time']
df['FA2_Speedup_vs_FP32'] = df['FP32_Time'] / df['FA2_Time']
df['FA2_Speedup_vs_FP16'] = df['FP16_Time'] / df['FA2_Time']

# 调整列顺序
columns = [
    'Epoch', 'Iter',
    'FP32_Time', 'FP16_Time', 'FA2_Time',
    'FP16_Speedup_vs_FP32', 'FA2_Speedup_vs_FP32', 'FA2_Speedup_vs_FP16',
    'FP32_Loss', 'FP16_Loss', 'FA2_Loss',
    'FP32_Grad', 'FP16_Grad', 'FA2_Grad'
]

df = df[columns]

# 保存新CSV
csv_file = 'training_logs/comparison_with_speedup.csv'
df.to_csv(csv_file, index=False, float_format='%.4f')
print(f"✅ 完整CSV已保存: {csv_file}")
print(f"   总共 {len(df)} 行数据")
print()

# 打印前10行预览
print("【数据预览 (前10行)】")
print("=" * 160)
print(df.head(10).to_string(index=False))
print()

# 统计汇总
print("=" * 160)
print("【统计汇总】")
print("=" * 160)
print(f"平均训练时间:  FP32={df['FP32_Time'].mean():.4f}s, FP16={df['FP16_Time'].mean():.4f}s, FA2={df['FA2_Time'].mean():.4f}s")
print(f"平均加速比:    FP16 vs FP32={df['FP16_Speedup_vs_FP32'].mean():.3f}x, FA2 vs FP32={df['FA2_Speedup_vs_FP32'].mean():.3f}x, FA2 vs FP16={df['FA2_Speedup_vs_FP16'].mean():.3f}x")
print(f"平均 Loss:     FP32={df['FP32_Loss'].mean():.2f}, FP16={df['FP16_Loss'].mean():.2f}, FA2={df['FA2_Loss'].mean():.2f}")
print(f"平均梯度范数:  FP32={df['FP32_Grad'].mean():.2f}, FP16={df['FP16_Grad'].mean():.2f}, FA2={df['FA2_Grad'].mean():.2f}")
print()
print("✅ 完成")

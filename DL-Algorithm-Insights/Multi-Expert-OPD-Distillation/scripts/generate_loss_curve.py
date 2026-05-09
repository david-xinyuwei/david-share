#!/usr/bin/env python3
"""Generate OPD loss curve chart with PIL beautification (24px white padding + 1px #dcdee2 border)."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw
import os

# Data from experiment logs (6 runs total)
steps_run1 = [5, 10, 15, 20]
loss_run1 = [0.5337, 0.6157, 0.6218, 0.5715]

steps_run3 = [5, 10, 15]
loss_run3 = [0.5246, 0.5961, 0.5573]

steps_run4 = [5, 10, 25, 30, 35]
loss_run4 = [0.5788, 0.5744, 0.6239, 0.6444, 0.4863]

steps_run5 = [5, 10]   # Step 15+ exploded, plot only valid points
loss_run5 = [0.4375, 0.4858]

steps_run6 = [5, 10, 15, 20]   # Step 20 = NaN grad, model collapsed
loss_run6 = [0.5302, 0.6091, 0.5683, 0.5165]

# Eval comparison data — N=100 with bug-fixed extractor (the REAL numbers)
labels = ['Baseline\n(no OPD)', 'Run 5\nckpt-10\n(greedy, 10 steps)', 'Run 6\nckpt-20\n(sampling, 20 steps)']
accuracies = [19.0, 18.0, 0.0]
colors = ['#94a3b8', '#fbbf24', '#dc2626']

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5))

# Loss plot - all runs
ax1.plot(steps_run1, loss_run1, 'o-', color='#2563eb', linewidth=2, markersize=8, label='Run 1 (sampling, killed by VM reboot)')
ax1.plot(steps_run3, loss_run3, 's--', color='#dc2626', linewidth=2, markersize=8, label='Run 3 (sampling, NaN crash)')
ax1.plot(steps_run4, loss_run4, '^-', color='#16a34a', linewidth=2, markersize=8, label='Run 4 (sampling, NaN crash)')
ax1.plot(steps_run5, loss_run5, 'D-', color='#ea580c', linewidth=2.5, markersize=10, label='Run 5 (greedy, ckpt-10 saved)')
ax1.plot(steps_run6, loss_run6, 'v-', color='#7c3aed', linewidth=2.5, markersize=10, label='Run 6 (sampling+fp32hook, COLLAPSED)')
ax1.scatter([20], [0.5165], s=300, facecolors='none', edgecolors='#dc2626', linewidth=3, zorder=5)
ax1.annotate('Loss looks fine\nbut model outputs\n"!!!!!!" x200', xy=(20, 0.5165), xytext=(28, 0.43),
             fontsize=9, ha='center', color='#dc2626',
             arrowprops=dict(arrowstyle='->', color='#dc2626'))
ax1.set_xlabel('Training Step', fontsize=12)
ax1.set_ylabel('Reverse KL Loss', fontsize=12)
ax1.set_title('OPD Training Loss Across 6 Runs (λ=1.0, β=1.0)', fontsize=13, fontweight='bold')
ax1.legend(fontsize=8, loc='upper right')
ax1.set_xlim(0, 40)
ax1.set_ylim(0.40, 0.75)
ax1.grid(True, alpha=0.3)

# Accuracy comparison - HONEST N=100 results
bars = ax2.bar(labels, accuracies, color=colors, edgecolor='black', linewidth=1.5, width=0.55)
ax2.set_ylabel('GSM8K Accuracy (%)', fontsize=12)
ax2.set_title('End-Task Accuracy: GSM8K test[:100], greedy decoding\n(OPD did NOT beat baseline at this scale)', fontsize=12, fontweight='bold')
ax2.set_ylim(0, 25)
ax2.grid(True, alpha=0.3, axis='y')
for bar, acc in zip(bars, accuracies):
    height = bar.get_height()
    ax2.text(bar.get_x() + bar.get_width()/2, height + 0.5, f'{acc:.1f}%',
             ha='center', va='bottom', fontsize=12, fontweight='bold')
ax2.text(2, 8, 'mode collapse:\noutputs "!!!!!!"\non every question',
         ha='center', fontsize=9, color='#dc2626', fontweight='bold',
         bbox=dict(boxstyle='round,pad=0.3', facecolor='#fef2f2', edgecolor='#dc2626'))

plt.tight_layout()

# Save raw chart
raw_path = '/tmp/opd_loss_raw.png'
plt.savefig(raw_path, dpi=150, bbox_inches='tight')
plt.close()

# PIL beautification: 24px white padding + 1px #dcdee2 border
img = Image.open(raw_path)
padding = 24
border = 1
border_color = (0xdc, 0xde, 0xe2)

new_w = img.width + 2 * (padding + border)
new_h = img.height + 2 * (padding + border)
canvas = Image.new('RGB', (new_w, new_h), 'white')

# Draw border
draw = ImageDraw.Draw(canvas)
draw.rectangle(
    [border - 1, border - 1, new_w - border, new_h - border],
    outline=border_color, width=border
)

# Paste image
canvas.paste(img, (padding + border, padding + border))

output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'images')
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, 'opd_loss_curve.png')
canvas.save(output_path, 'PNG')
print(f"Saved to {output_path}")
print(f"Size: {canvas.size}")

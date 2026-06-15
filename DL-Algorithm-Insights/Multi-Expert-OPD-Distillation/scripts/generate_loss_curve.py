#!/usr/bin/env python3
"""Generate OPD loss curve chart with PIL beautification.

Usage:
    python3 scripts/generate_loss_curve.py --output-dir images
"""
import argparse
import os


def build_chart(output_dir, raw_path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image, ImageDraw

    # Data from experiment logs (6 runs total)
    steps_run1 = [5, 10, 15, 20]
    loss_run1 = [0.5337, 0.6157, 0.6218, 0.5715]

    steps_run3 = [5, 10, 15]
    loss_run3 = [0.5246, 0.5961, 0.5573]

    steps_run4 = [5, 10, 25, 30, 35]
    loss_run4 = [0.5788, 0.5744, 0.6239, 0.6444, 0.4863]

    steps_run5 = [5, 10]
    loss_run5 = [0.4375, 0.4858]

    steps_run6 = [5, 10, 15, 20]
    loss_run6 = [0.5302, 0.6091, 0.5683, 0.5165]

    labels = ['Baseline\n(no OPD)', 'Run 5\nckpt-10\n(greedy, 10 steps)', 'Run 6\nckpt-20\n(sampling, 20 steps)']
    accuracies = [19.0, 18.0, 0.0]
    colors = ['#94a3b8', '#fbbf24', '#dc2626']

    fig, (loss_axis, accuracy_axis) = plt.subplots(1, 2, figsize=(15, 5))

    loss_axis.plot(steps_run1, loss_run1, 'o-', color='#2563eb', linewidth=2, markersize=8, label='Run 1 (sampling, killed by VM reboot)')
    loss_axis.plot(steps_run3, loss_run3, 's--', color='#dc2626', linewidth=2, markersize=8, label='Run 3 (sampling, NaN crash)')
    loss_axis.plot(steps_run4, loss_run4, '^-', color='#16a34a', linewidth=2, markersize=8, label='Run 4 (sampling, NaN crash)')
    loss_axis.plot(steps_run5, loss_run5, 'D-', color='#ea580c', linewidth=2.5, markersize=10, label='Run 5 (greedy, ckpt-10 saved)')
    loss_axis.plot(steps_run6, loss_run6, 'v-', color='#7c3aed', linewidth=2.5, markersize=10, label='Run 6 (sampling+fp32hook, COLLAPSED)')
    loss_axis.scatter([20], [0.5165], s=300, facecolors='none', edgecolors='#dc2626', linewidth=3, zorder=5)
    loss_axis.annotate('Loss looks fine\nbut model outputs\n"!!!!!!" x200', xy=(20, 0.5165), xytext=(28, 0.43),
                       fontsize=9, ha='center', color='#dc2626',
                       arrowprops=dict(arrowstyle='->', color='#dc2626'))
    loss_axis.set_xlabel('Training Step', fontsize=12)
    loss_axis.set_ylabel('Reverse KL Loss', fontsize=12)
    loss_axis.set_title('OPD Training Loss Across 6 Runs (λ=1.0, β=1.0)', fontsize=13, fontweight='bold')
    loss_axis.legend(fontsize=8, loc='upper right')
    loss_axis.set_xlim(0, 40)
    loss_axis.set_ylim(0.40, 0.75)
    loss_axis.grid(True, alpha=0.3)

    bars = accuracy_axis.bar(labels, accuracies, color=colors, edgecolor='black', linewidth=1.5, width=0.55)
    accuracy_axis.set_ylabel('GSM8K Accuracy (%)', fontsize=12)
    accuracy_axis.set_title('End-Task Accuracy: GSM8K test[:100], greedy decoding\n(OPD did NOT beat baseline at this scale)', fontsize=12, fontweight='bold')
    accuracy_axis.set_ylim(0, 25)
    accuracy_axis.grid(True, alpha=0.3, axis='y')
    for bar, accuracy in zip(bars, accuracies):
        height = bar.get_height()
        accuracy_axis.text(bar.get_x() + bar.get_width() / 2, height + 0.5, f'{accuracy:.1f}%',
                           ha='center', va='bottom', fontsize=12, fontweight='bold')
    accuracy_axis.text(2, 8, 'mode collapse:\noutputs "!!!!!!"\non every question',
                       ha='center', fontsize=9, color='#dc2626', fontweight='bold',
                       bbox=dict(boxstyle='round,pad=0.3', facecolor='#fef2f2', edgecolor='#dc2626'))

    plt.tight_layout()
    plt.savefig(raw_path, dpi=150, bbox_inches='tight')
    plt.close()

    image = Image.open(raw_path)
    padding = 24
    border = 1
    border_color = (0xdc, 0xde, 0xe2)
    canvas_width = image.width + 2 * (padding + border)
    canvas_height = image.height + 2 * (padding + border)
    canvas = Image.new('RGB', (canvas_width, canvas_height), 'white')

    draw = ImageDraw.Draw(canvas)
    draw.rectangle([border - 1, border - 1, canvas_width - border, canvas_height - border], outline=border_color, width=border)
    canvas.paste(image, (padding + border, padding + border))

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'opd_loss_curve.png')
    canvas.save(output_path, 'PNG')
    print(f"Saved to {output_path}")
    print(f"Size: {canvas.size}")


def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parser = argparse.ArgumentParser(description="Generate the OPD loss curve image used by the README files.")
    parser.add_argument("--output-dir", default=os.path.join(repo_root, "images"), help="Directory for opd_loss_curve.png")
    parser.add_argument("--raw-path", default="/tmp/opd_loss_raw.png", help="Temporary raw matplotlib image path")
    args = parser.parse_args()
    build_chart(args.output_dir, args.raw_path)


if __name__ == "__main__":
    main()

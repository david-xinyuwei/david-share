"""Render README figures from the published inference summary or adaptation histories."""

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch


TOPIC = Path(__file__).resolve().parent.parent
LATEST = TOPIC / "experiments/20260906-qwen38/data/summary.json"
ADAPTATION = TOPIC / "experiments/20260909-drafter-adaptation"
CJK_FONTS = ("Microsoft YaHei", "Noto Sans CJK SC", "Source Han Sans SC", "PingFang SC", "SimHei")
TEXT = "#182529"
MUTED = "#4B555A"


def select_font(font_file=None):
    if font_file is not None:
        font_manager.fontManager.addfont(str(font_file))
        return font_manager.FontProperties(fname=str(font_file)).get_name()
    available = {font.name for font in font_manager.fontManager.ttflist}
    for name in CJK_FONTS:
        if name in available:
            return name
    raise SystemExit("NO_CJK_FONT: install one of " + ", ".join(CJK_FONTS))


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def draw_latest_throughput(summary, path):
    labels = {"baseline": "基线", "mtp7": "MTP7", "dflash2_7": "DFlash 2-7"}
    colors = ("#637078", "#C68118", "#16836F")
    figure, axes = plt.subplots(1, 3, figsize=(15, 7.6), dpi=100)
    for axis, concurrency in zip(axes, summary["coverage"]["matched_concurrency"]):
        rows = [row for row in summary["matched_summary"] if row["concurrency"] == concurrency]
        medians = [row["throughput_tok_s"]["median"] for row in rows]
        errors = [[median - row["throughput_tok_s"]["min"] for median, row in zip(medians, rows)],
                  [row["throughput_tok_s"]["max"] - median for median, row in zip(medians, rows)]]
        bars = axis.bar([labels[row["route"]] for row in rows], medians, color=colors, width=0.62, yerr=errors, capsize=6)
        axis.set_title(f"并发 {concurrency}", fontsize=16, pad=18)
        axis.set_ylim(0, max(row["throughput_tok_s"]["max"] for row in rows) * 1.23)
        axis.set_ylabel("整组输出 token / 秒", fontsize=11)
        axis.tick_params(axis="both", labelsize=11)
        axis.spines[["top", "right"]].set_visible(False)
        axis.set_axisbelow(True)
        axis.grid(axis="y", color="#DCE3E1", linewidth=0.8)
        axis.bar_label(bars, fmt="%.2f", padding=10, fontsize=12)
    figure.suptitle("Qwen3.8-27B：三条路线的输出吞吐", fontsize=23, y=0.95)
    figure.text(0.5, 0.88, "同一批 64 题 | 每条路线 3 个随机种子 | H100 NVL | vLLM 0.28.0 | 含思考过程的 token",
                ha="center", fontsize=13, color=MUTED)
    figure.text(0.5, 0.075, "柱形：三次运行的中位数。误差线：观测到的最小值和最大值，不是置信区间。",
                ha="center", fontsize=11, color=MUTED)
    figure.text(0.5, 0.035, "作者实测：qwen38-quality-20260906 | 来源：data/groups.json | 仅 S 阶段；F 未执行。",
                ha="center", fontsize=11, color=MUTED)
    figure.subplots_adjust(left=0.065, right=0.975, bottom=0.18, top=0.77, wspace=0.34)
    figure.savefig(path, facecolor="white")
    plt.close(figure)


def draw_adaptation_losses(histories, path, chinese):
    figure, axes = plt.subplots(2, 1, figsize=(10, 9), dpi=180)
    colors = ("#287D8E", "#BB812B", "#697885", "#B64C53")
    order = ("english_seed20260908", "english_seed1", "english_seed2", "chinese_seed20260908")
    for name, color in zip(order, colors):
        record = histories[name]
        language = ("中文" if chinese else "Chinese") if name.startswith("chinese") else ("英文" if chinese else "English")
        label = f"{language} seed {record['args']['seed']}"
        for axis, field in zip(axes, ("history", "selector_history")):
            values = record[field]
            ends = [min(start + 50, len(values)) for start in range(0, len(values), 50)]
            means = [sum(values[start:end]) / (end - start)
                     for start, end in zip(range(0, len(values), 50), ends)]
            axis.plot(ends, means, label=label, color=color, linewidth=2.1)
    for axis, title in zip(axes, ("Backbone loss", "Selector loss")):
        axis.set_title(title, loc="left", fontsize=17, pad=12)
        axis.set_ylabel("加权交叉熵" if chinese else "Weighted cross-entropy", fontsize=12)
        axis.set_xlabel("训练步" if chinese else "Training step", fontsize=12)
        axis.grid(color="#E2E7E8", linewidth=0.7)
        axis.spines[["top", "right"]].set_visible(False)
        axis.tick_params(labelsize=11)
    title = "草稿再适配：训练 loss 轨迹" if chinese else "Drafter adaptation: training loss"
    figure.suptitle(title, fontsize=22, y=0.975)
    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.94),
                  ncol=2, frameon=False, fontsize=11)
    note = ("连续 50 步分组均值；尾组按实际步数计算。每条线对应一次训练。\n不同语言与目标的 loss 不作排名；loss 下降不是质量或服务收益证明。" if chinese else
            "Consecutive 50-step means; the final partial group uses its actual length. One run per line.\nLosses across languages/targets are not a ranking or proof of quality or serving gains.")
    figure.text(0.06, 0.035, note, fontsize=10.5, color=MUTED, linespacing=1.5)
    figure.subplots_adjust(left=0.11, right=0.96, top=0.82, bottom=0.17, hspace=0.62)
    figure.savefig(path, facecolor="white")
    plt.close(figure)


def draw_adaptation_flow(flow, path, chinese):
    figure, axis = plt.subplots(figsize=(8, 9), dpi=180)
    axis.set(xlim=(0, 1), ylim=(0, 1))
    axis.axis("off")
    language = "cn" if chinese else "en"
    colors = ("#EDF1F3", "#E5F2F0", "#E5F2F0", "#FFF2D7", "#EDF1F3", "#E5F2F0")
    positions = [0.88 - index * 0.14 for index in range(len(flow["steps"]))]
    for index, (step, position, color) in enumerate(zip(flow["steps"], positions, colors)):
        axis.add_patch(FancyBboxPatch((0.04, position - 0.052), 0.67, 0.104,
                                     boxstyle="round,pad=0.007,rounding_size=0.008",
                                     facecolor=color, edgecolor="#63777B", linewidth=1.2))
        axis.text(0.375, position, step[language], ha="center", va="center", fontsize=16,
                  linespacing=1.45, color=TEXT)
        if index:
            axis.annotate("", xy=(0.375, position + 0.059), xytext=(0.375, positions[index - 1] - 0.059),
                          arrowprops={"arrowstyle": "->", "color": "#63777B", "lw": 1.5})
    axis.add_patch(FancyBboxPatch((0.79, positions[-1] - 0.057), 0.19, 0.114,
                                 boxstyle="round,pad=0.007,rounding_size=0.008",
                                 facecolor="#F5E8EC", edgecolor="#9A596C", linewidth=1.2))
    axis.text(0.885, positions[-1], flow["held_out"][language], ha="center", va="center", fontsize=12)
    axis.annotate("", xy=(0.723, positions[-1]), xytext=(0.782, positions[-1]),
                  arrowprops={"arrowstyle": "->", "color": "#9A596C", "lw": 1.5})
    figure.suptitle("草稿再适配：数据与模型流" if chinese else "Drafter adaptation: data and models",
                   fontsize=20, y=0.985)
    figure.text(0.055, 0.026,
                "单张 GPU 分阶段执行；训练、重载、效果分别验收。" if chinese else
                "One GPU, staged execution. Training, reload and outcomes are separate checks.",
                fontsize=10.5, color=MUTED)
    figure.subplots_adjust(left=0.025, right=0.98, top=0.93, bottom=0.05)
    figure.savefig(path, facecolor="white")
    plt.close(figure)


def render_adaptation(output):
    summary = read_json(ADAPTATION / "data/summary.json")
    histories, sources = {}, {}
    for name, entry in summary["training"].items():
        path = ADAPTATION / entry["history_path"]
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        if checksum != entry["history_sha256"]:
            raise SystemExit("TRAINING_FIGURE_SOURCE_MISMATCH:" + name)
        histories[name] = read_json(path)
        sources[entry["history_path"]] = checksum
    record = {"scope": "Four archived training runs; grouped loss means, not a quality comparison.",
              "aggregation": "Consecutive groups of 50 steps; final partial group retained.",
              "sources": sources, "figures": {}}
    output.mkdir(parents=True, exist_ok=True)
    for chinese, name in ((False, "training-loss-en.png"), (True, "training-loss-cn.png")):
        path = output / name
        draw_adaptation_losses(histories, path, chinese)
        pixels = plt.imread(path)
        record["figures"][name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                   "width": pixels.shape[1], "height": pixels.shape[0]}
    flow_path = ADAPTATION / "images/training-flow.json"
    flow = read_json(flow_path)
    record["diagram_scope"] = flow["scope"]
    for relative in ("images/training-flow.json", *(step["source"] for step in flow["steps"])):
        record["sources"][relative] = hashlib.sha256((ADAPTATION / relative).read_bytes()).hexdigest()
    for chinese, name in ((False, "training-flow-en.png"), (True, "training-flow-cn.png")):
        path = output / name
        draw_adaptation_flow(flow, path, chinese)
        pixels = plt.imread(path)
        record["figures"][name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                   "width": pixels.shape[1], "height": pixels.shape[0]}
    (output / "loss-figures.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--adaptation-only", action="store_true")
    parser.add_argument("--font-file", type=Path, help="Use an existing CJK font without installing it")
    args = parser.parse_args()
    plt.rcParams.update({"font.family": select_font(args.font_file), "axes.unicode_minus": False,
                         "text.color": TEXT, "axes.labelcolor": TEXT})
    if args.adaptation_only:
        render_adaptation(args.output or ADAPTATION / "images")
        return
    args.output = args.output or TOPIC / "images"
    args.output.mkdir(parents=True, exist_ok=True)
    latest = read_json(LATEST)
    outputs = {"throughput-cn.png": (draw_latest_throughput, latest)}
    report = {"font": plt.rcParams["font.family"], "figures": {}}
    for name, (draw, data) in outputs.items():
        path = args.output / name
        draw(data, path)
        report["figures"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
    report["sources"] = {LATEST.relative_to(TOPIC).as_posix(): hashlib.sha256(LATEST.read_bytes()).hexdigest()}
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

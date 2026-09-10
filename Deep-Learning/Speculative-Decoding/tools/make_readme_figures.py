"""Render README figures from published inference summaries or adaptation histories."""

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager


TOPIC = Path(__file__).resolve().parent.parent
LATEST = TOPIC / "experiments/20260906-qwen38/data/summary.json"
PREVIOUS = TOPIC / "experiments/20260905-quality/analysis/summary.json"
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


PREVIOUS_ROUTES = ("baseline", "mtp5", "dflash15")
PREVIOUS_COLORS = {"baseline": "#68747b", "mtp5": "#057d73", "dflash15": "#b12b52"}
PREVIOUS_LABELS = {"baseline": "基线", "mtp5": "MTP / 5", "dflash15": "DFlash / 15"}
DATASETS = (("humaneval_plus", "HumanEval+（需通过全部测试）"), ("math_500", "MATH-500"))


def draw_previous_latency(result, path):
    summaries = {route: result["routes"][route]["primary"]["quality_and_latency"] for route in PREVIOUS_ROUTES}
    figure, axes = plt.subplots(2, 1, figsize=(7.4, 8.8), dpi=180)
    figure.subplots_adjust(left=0.24, right=0.94, top=0.80, bottom=0.22, hspace=0.72)
    figure.text(0.06, 0.95, "完整答案的请求耗时", fontsize=21, weight="bold")
    figure.text(0.06, 0.907, "H100 NVL | Qwen3.6-27B BF16 | 贪心解码", fontsize=13, color=MUTED)
    for axis, (dataset, label) in zip(axes, DATASETS):
        values = [summaries[route][dataset]["median_total_s"] for route in PREVIOUS_ROUTES]
        positions = list(range(len(PREVIOUS_ROUTES)))
        axis.barh(positions, values, color=[PREVIOUS_COLORS[route] for route in PREVIOUS_ROUTES], height=0.58, zorder=3)
        axis.set_yticks(positions, [PREVIOUS_LABELS[route] for route in PREVIOUS_ROUTES], fontsize=14)
        axis.invert_yaxis()
        axis.tick_params(axis="y", length=0, pad=10)
        axis.spines[["top", "right", "left"]].set_visible(False)
        axis.grid(axis="x", color="#e4e8e8", linewidth=0.8, zorder=0)
        axis.set_title(label, loc="left", pad=13, fontsize=17, weight="bold")
        maximum = max(values) * 1.26
        axis.set_xlim(0, maximum)
        axis.set_xlabel("请求耗时中位数（秒）", fontsize=13, labelpad=8)
        for position, value in zip(positions, values):
            axis.text(value + maximum * 0.02, position, f"{value:.2f} 秒", ha="left", va="center", fontsize=13, weight="bold")
    figure.text(0.06, 0.045, "含预填充和同机客户端开销，不含服务启动。\n统计全部答案；各路线的输出长度可能不同。",
                fontsize=11.5, color=MUTED, linespacing=1.55)
    figure.savefig(path, dpi=180, facecolor="white")
    plt.close(figure)


def draw_previous_concurrency(result, path):
    figure, axes = plt.subplots(2, 1, figsize=(7.4, 8.8), dpi=180)
    figure.subplots_adjust(left=0.14, right=0.91, top=0.77, bottom=0.21, hspace=0.65)
    figure.text(0.06, 0.95, "并发下的答对数", fontsize=21, weight="bold")
    figure.text(0.06, 0.907, "每档使用相同的 32 道代码题和 32 道数学题", fontsize=13, color=MUTED)
    for axis, (dataset, label) in zip(axes, (DATASETS[0], ("math_500", "MATH-500 子集"))):
        for route in PREVIOUS_ROUTES:
            values = [result["routes"][route][f"concurrency-{level}"]["quality_and_latency"][dataset]["correct"] for level in (1, 4, 8)]
            axis.plot((1, 4, 8), values, marker="o", linewidth=2.5, markersize=7, color=PREVIOUS_COLORS[route], label=PREVIOUS_LABELS[route])
            if route == "dflash15":
                for level, correct in zip((4, 8), values[1:]):
                    axis.annotate(f"{correct}/32", (level, correct), xytext=(0, 12), textcoords="offset points",
                                  ha="center", fontsize=13, color=PREVIOUS_COLORS[route], weight="bold")
        axis.set_title(label, loc="left", pad=12, fontsize=17, weight="bold")
        axis.set_xlim(0.6, 8.4)
        axis.set_ylim(0, 35)
        axis.set_xticks((1, 4, 8))
        axis.set_yticks((0, 8, 16, 24, 32))
        axis.set_ylabel("答对数 / 32", fontsize=13)
        axis.set_xlabel("并发请求数", fontsize=13, labelpad=6)
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(color="#e4e8e8", linewidth=0.8)
    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.52, 0.885), ncol=3, frameon=False, fontsize=12)
    figure.text(0.06, 0.043, "每档只运行一次，不是对算法整体的结论。\nDFlash15 的回退尚未定位根因，也未修复。",
                fontsize=11.5, color=MUTED, linespacing=1.55)
    figure.savefig(path, dpi=180, facecolor="white")
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
    latest, previous = read_json(LATEST), read_json(PREVIOUS)
    if previous["scope"] != "complete_frozen_matrix":
        raise SystemExit("PREVIOUS_SUMMARY_SCOPE_MISMATCH")
    outputs = {
        "throughput-cn.png": (draw_latest_throughput, latest),
        "previous-latency-cn.png": (draw_previous_latency, previous),
        "previous-concurrency-cn.png": (draw_previous_concurrency, previous),
    }
    report = {"font": plt.rcParams["font.family"], "figures": {}}
    for name, (draw, data) in outputs.items():
        path = args.output / name
        draw(data, path)
        report["figures"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
    report["sources"] = {LATEST.relative_to(TOPIC).as_posix(): hashlib.sha256(LATEST.read_bytes()).hexdigest(),
                         PREVIOUS.relative_to(TOPIC).as_posix(): hashlib.sha256(PREVIOUS.read_bytes()).hexdigest()}
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

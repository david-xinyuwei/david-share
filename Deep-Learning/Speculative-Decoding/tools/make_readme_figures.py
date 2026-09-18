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


ROUTE_LABELS = {"baseline": ("Autoregressive", "自回归"), "mtp7": ("MTP7", "MTP7"), "dflash2_7": ("DFlash 2-7", "DFlash 2-7")}
ROUTE_COLORS = {"baseline": "#637078", "mtp7": "#C68118", "dflash2_7": "#16836F"}
DATASET_LABELS = {"humaneval_plus": ("HumanEval+", "HumanEval+"), "math_500": ("MATH-500 subset", "MATH-500 子集")}


def _label(pair, chinese):
    return pair[1] if chinese else pair[0]


def draw_accuracy_alignment(summary, path, chinese):
    """Figure 2: correct answers per repeat for the three routes, same 32+32 tasks, three seeds."""
    levels = summary["coverage"]["matched_concurrency"]
    rows = {(row["route"], row["concurrency"]): row for row in summary["matched_summary"]}
    figure, axes = plt.subplots(1, 2, figsize=(14, 6.4), dpi=150)
    routes = ("baseline", "mtp7", "dflash2_7")
    width = 0.26
    for axis, dataset in zip(axes, ("humaneval_plus", "math_500")):
        for offset, route in enumerate(routes):
            positions = [index + (offset - 1) * width for index in range(len(levels))]
            values = [rows[(route, level)]["datasets"][dataset]["raw_correct"] for level in levels]
            means = [sum(v) / len(v) for v in values]
            lows = [mean - min(v) for mean, v in zip(means, values)]
            highs = [max(v) - mean for mean, v in zip(means, values)]
            axis.bar(positions, means, width=width, color=ROUTE_COLORS[route], yerr=[lows, highs],
                     capsize=4, label=_label(ROUTE_LABELS[route], chinese), zorder=3)
            for position, mean in zip(positions, means):
                axis.text(position, mean - 1.4, f"{mean:.1f}", ha="center", va="top", fontsize=9.5,
                          color="white", weight="bold", zorder=5)
        denominator = rows[(routes[0], levels[0])]["datasets"][dataset]["denominator_per_repeat"]
        axis.set_title(_label(DATASET_LABELS[dataset], chinese), loc="left", fontsize=15, pad=10)
        axis.set_xticks(range(len(levels)), [f"并发 {l}" if chinese else f"Concurrency {l}" for l in levels], fontsize=11)
        axis.set_ylim(0, denominator + 5)
        axis.axhline(denominator, color="#B8C0C3", linewidth=1, linestyle="--", zorder=1)
        axis.text(-0.45, denominator + 0.35, f"{denominator} = 全对" if chinese else f"{denominator} = all correct",
                  ha="left", va="bottom", fontsize=9, color="#8A969B")
        axis.set_ylabel(f"答对数 / {denominator}" if chinese else f"Correct / {denominator}", fontsize=11)
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(axis="y", color="#E2E7E8", linewidth=0.7, zorder=0)
    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.855), ncol=3, frameon=False, fontsize=11.5)
    figure.suptitle("Qwen3.8-27B：三条路线的答案正确数" if chinese else "Qwen3.8-27B: correct answers by route",
                    fontsize=21, y=0.985)
    figure.text(0.5, 0.895, "同一批 32 道代码题 + 32 道数学题 | 三个随机种子 | 并发 1 / 4 / 8 | H100 NVL | vLLM 0.28.0" if chinese else
                "Same 32 code + 32 math tasks | three seeds | concurrency 1 / 4 / 8 | H100 NVL | vLLM 0.28.0",
                ha="center", fontsize=12, color=MUTED)
    figure.text(0.5, 0.045, ("柱形：三个种子的平均答对数；误差线：最小到最大。基线自身跨并发档也有 1–2 题波动。\n"
                             "长度截断的回答留在分母内。样本量不足以证明\u201c不劣于\u201d，只表明未观察到系统性下降。") if chinese else
                ("Bars: mean correct over three seeds; whiskers: min to max. The baseline itself varies by 1-2 tasks across concurrency.\n"
                 "Length-stopped answers stay in the denominator. The sample cannot prove noninferiority; it shows no systematic drop."),
                ha="center", fontsize=10.5, color=MUTED, linespacing=1.5)
    figure.subplots_adjust(left=0.07, right=0.98, top=0.74, bottom=0.2, wspace=0.22)
    figure.savefig(path, facecolor="white")
    plt.close(figure)


def draw_finetuned_throughput(adaptation, path, chinese):
    """Figure 3: fine-tuned target served three ways; Round 5 four observations per cell."""
    routes = adaptation["round5"]["vllm"]["routes"]
    levels = sorted(routes["baseline"]["levels"], key=int)
    order = ("baseline", "dflash_released", "dflash_ours")
    labels = {"baseline": ("Autoregressive", "自回归"), "dflash_released": ("Released\nDFlash 2", "发布版 DFlash 2"),
              "dflash_ours": ("Re-adapted\nDFlash 2", "再训 DFlash 2")}
    colors = {"baseline": "#637078", "dflash_released": "#5B8FB9", "dflash_ours": "#16836F"}
    figure, axes = plt.subplots(1, len(levels), figsize=(15, 6.6), dpi=150)
    for axis, level in zip(axes, levels):
        cells = [routes[route]["levels"][level] for route in order]
        means = [cell["mean"] for cell in cells]
        errors = [[cell["mean"] - cell["min"] for cell in cells], [cell["max"] - cell["mean"] for cell in cells]]
        bars = axis.bar([_label(labels[route], chinese) for route in order], means, color=[colors[r] for r in order],
                        width=0.62, yerr=errors, capsize=6, zorder=3)
        axis.bar_label(bars, fmt="%.1f", padding=8, fontsize=11)
        for bar, route, cell in zip(bars, order, cells):
            if "speedup_vs_baseline_mean" in cell:
                axis.text(bar.get_x() + bar.get_width() / 2, cell["mean"] * 0.5, f"{cell['speedup_vs_baseline_mean']:.2f}×",
                          ha="center", va="center", fontsize=13, color="white", weight="bold")
        axis.set_title(f"并发 {level}" if chinese else f"Concurrency {level}", fontsize=15, pad=14)
        axis.set_ylim(0, max(cell["max"] for cell in cells) * 1.22)
        axis.set_ylabel("整组输出 token / 秒" if chinese else "Output tokens / s for the group", fontsize=11)
        axis.tick_params(axis="x", labelsize=10.5)
        axis.spines[["top", "right"]].set_visible(False)
        axis.set_axisbelow(True)
        axis.grid(axis="y", color="#E2E7E8", linewidth=0.7)
    figure.suptitle("微调后的目标模型：三种服务方式的吞吐" if chinese else "Fine-tuned target: throughput of three serving routes",
                    fontsize=21, y=0.985)
    figure.text(0.5, 0.895, ("目标 = Qwen3.8-27B + 中文全模块 LoRA | 同一批 40 条中文提示 | greedy, max_tokens 256 | 每格 4 次观测" if chinese else
                             "Target = Qwen3.8-27B + Chinese all-module LoRA | same 40 Chinese prompts | greedy, max_tokens 256 | 4 observations per cell"),
                ha="center", fontsize=12, color=MUTED)
    figure.text(0.5, 0.05, ("柱内数字：相对自回归的加速倍数。误差线：4 次观测的最小到最大，只反映计时抖动。\n"
                            "两个 draft model 在并发 1 的输出 40/40 逐字相同：draft 只改变步数，不改变目标模型的回答。") if chinese else
                ("Numbers inside bars: speedup over autoregressive. Whiskers: min to max of 4 observations, timing jitter only.\n"
                 "Both draft models produce byte-identical outputs on 40/40 prompts at concurrency 1: the draft changes steps, not the answer."),
                ha="center", fontsize=10.5, color=MUTED, linespacing=1.5)
    figure.subplots_adjust(left=0.06, right=0.98, top=0.79, bottom=0.22, wspace=0.3)
    figure.savefig(path, facecolor="white")
    plt.close(figure)


def draw_finetuned_alignment(adaptation, path, chinese):
    """Figure 3b: how well each draft predicts the fine-tuned target, teacher-forced on identical text (Round 4)."""
    agreement = adaptation["round4"]["agreement"]
    paired = adaptation["round4"]["agreement_paired"]["chinese_ours_minus_released_selector"]
    released, ours = agreement["ftzh_released"], agreement["ftzh_ours"]
    offsets = list(range(1, len(released["marginal_hit_rate_by_offset"]) + 1))
    figure, axes = plt.subplots(1, 2, figsize=(14, 6.2), dpi=150, gridspec_kw={"width_ratios": [1.6, 1]})
    axis = axes[0]
    axis.plot(offsets, released["marginal_hit_rate_by_offset"], marker="o", linewidth=2.4, color="#5B8FB9",
              label=_label(("Released DFlash 2", "发布版 DFlash 2"), chinese))
    axis.plot(offsets, ours["marginal_hit_rate_by_offset"], marker="o", linewidth=2.4, color="#16836F",
              label=_label(("Re-adapted DFlash 2", "再训 DFlash 2"), chinese))
    for k, (a, b) in enumerate(zip(released["marginal_hit_rate_by_offset"], ours["marginal_hit_rate_by_offset"]), start=1):
        axis.annotate(f"{b:.3f}", (k, b), xytext=(0, 9), textcoords="offset points", ha="center", fontsize=9, color="#16836F")
        axis.annotate(f"{a:.3f}", (k, a), xytext=(0, -14), textcoords="offset points", ha="center", fontsize=9, color="#5B8FB9")
    axis.set_xticks(offsets)
    axis.set_xlabel("草稿位置 k" if chinese else "Draft position k", fontsize=11.5)
    axis.set_ylabel("命中目标 argmax 的比例" if chinese else "Fraction matching the target argmax", fontsize=11.5)
    axis.set_ylim(0, 0.85)
    axis.set_title("逐位置命中率（教师强制，200 条序列）" if chinese else "Per-position hit rate (teacher-forced, 200 sequences)", loc="left", fontsize=14, pad=10)
    axis.grid(color="#E2E7E8", linewidth=0.7)
    axis.spines[["top", "right"]].set_visible(False)
    axis.legend(frameon=False, fontsize=11, loc="upper right")
    axis = axes[1]
    metrics = [("first_offset_hit_rate", ("k=1 hit rate", "k=1 命中率")), ("joint_prefix_acceptance_length", ("Acceptance length τ", "接受长度 τ"))]
    xs = range(len(metrics))
    rel = [released[m] for m, _ in metrics]
    our = [ours[m] for m, _ in metrics]
    axis.bar([x - 0.18 for x in xs], rel, width=0.36, color="#5B8FB9", zorder=3)
    axis.bar([x + 0.18 for x in xs], our, width=0.36, color="#16836F", zorder=3)
    for x, (m, _) in zip(xs, metrics):
        d = paired[m]
        lo, hi = d["bootstrap_95_percent_interval"]
        axis.text(x, max(rel[x], our[x]) * 1.06, f"+{d['difference']:.3f}\n[{lo:.3f}, {hi:.3f}]", ha="center", fontsize=9.5, color=TEXT)
        axis.text(x - 0.18, rel[x] / 2, f"{rel[x]:.3f}", ha="center", va="center", fontsize=10, color="white", weight="bold")
        axis.text(x + 0.18, our[x] / 2, f"{our[x]:.3f}", ha="center", va="center", fontsize=10, color="white", weight="bold")
    axis.set_xticks(list(xs), [_label(l, chinese) for _, l in metrics], fontsize=11)
    axis.set_ylim(0, max(our) * 1.35)
    axis.set_title("成对差异与 95% bootstrap 区间" if chinese else "Paired difference, 95% bootstrap interval", loc="left", fontsize=14, pad=10)
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="y", color="#E2E7E8", linewidth=0.7, zorder=0)
    figure.suptitle("微调后的目标模型：两个 draft 与目标的对齐程度" if chinese else "Fine-tuned target: how well each draft tracks the target",
                    fontsize=21, y=0.985)
    figure.text(0.5, 0.895, ("同一段目标文本、同一批位置；selector 路径；再训 draft 从发布版权重继续训练" if chinese else
                             "Identical target text and positions; selector path; the re-adapted draft continues from the released weights"),
                ha="center", fontsize=12, color=MUTED)
    figure.text(0.5, 0.04, ("命中率和接受长度描述 draft 猜中目标的能力，不是答案正确率；答案由目标模型验证并保持不变。\n"
                            "中文医学提示集没有可执行判题器，微调后的答案正确率未测量。") if chinese else
                ("Hit rate and acceptance length describe drafting, not answer correctness; the target verifies every token.\n"
                 "No executable grader exists for the Chinese medical prompt set, so post-fine-tuning answer accuracy was not measured."),
                ha="center", fontsize=10.5, color=MUTED, linespacing=1.5)
    figure.subplots_adjust(left=0.07, right=0.98, top=0.8, bottom=0.19, wspace=0.28)
    figure.savefig(path, facecolor="white")
    plt.close(figure)


def draw_readapted_gain(adaptation, path, chinese):
    """Figure 4: re-adapted vs released draft, five disjoint prompt blocks x four concurrency levels (Round 6)."""
    per = adaptation["round6"]["vllm"]["per_concurrency"]
    identity = adaptation["round6"]["text_identity"]
    levels = sorted(per, key=int)
    blocks = len(per[levels[0]]["adapted_over_released_pct_per_block"])
    figure, axes = plt.subplots(1, 2, figsize=(15, 6.4), dpi=150, gridspec_kw={"width_ratios": [1.5, 1]})
    axis = axes[0]
    width = 0.8 / blocks
    palette = ("#0F6E5F", "#16836F", "#3F9E8C", "#6DB8A8", "#9BD0C4")
    for b in range(blocks):
        xs = [i + (b - (blocks - 1) / 2) * width for i in range(len(levels))]
        ys = [per[l]["adapted_over_released_pct_per_block"][b] for l in levels]
        axis.bar(xs, ys, width=width, color=palette[b], label=(f"提示块 {b}" if chinese else f"Prompt block {b}"), zorder=3)
    for i, l in enumerate(levels):
        axis.plot([i - 0.42, i + 0.42], [per[l]["gain_mean"]] * 2, color="#B64C53", linewidth=2, zorder=4)
        axis.text(i + 0.44, per[l]["gain_mean"], f"{per[l]['gain_mean']:.1f}%", va="center", fontsize=10.5, color="#B64C53",
                  zorder=6, bbox={"boxstyle": "round,pad=0.15", "facecolor": "white", "edgecolor": "none", "alpha": 0.9})
    axis.axhline(0, color="#63777B", linewidth=1)
    axis.set_xticks(range(len(levels)), [f"并发 {l}" if chinese else f"Concurrency {l}" for l in levels], fontsize=11)
    axis.set_ylabel("再训 draft 相对发布版的吞吐增益 (%)" if chinese else "Throughput gain of re-adapted over released (%)", fontsize=11.5)
    axis.set_title(f"{blocks} 个不重叠的 40 条提示块，各测一次；红线 = 均值" if chinese else f"{blocks} disjoint 40-prompt blocks, once each; red line = mean",
                   loc="left", fontsize=13.5, pad=10)
    axis.legend(frameon=False, fontsize=10, ncol=blocks, loc="upper left")
    axis.set_ylim(0, max(max(per[l]["adapted_over_released_pct_per_block"]) for l in levels) * 1.25)
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="y", color="#E2E7E8", linewidth=0.7, zorder=0)
    axis = axes[1]
    released = [per[l]["released_speedup_mean"] for l in levels]
    adapted = [per[l]["adapted_speedup_mean"] for l in levels]
    xs = list(range(len(levels)))
    axis.plot(xs, released, marker="o", linewidth=2.4, color="#5B8FB9", label=_label(("Released DFlash 2", "发布版 DFlash 2"), chinese))
    axis.plot(xs, adapted, marker="o", linewidth=2.4, color="#16836F", label=_label(("Re-adapted DFlash 2", "再训 DFlash 2"), chinese))
    for x, r, a in zip(xs, released, adapted):
        axis.annotate(f"{a:.2f}×", (x, a), xytext=(0, 9), textcoords="offset points", ha="center", fontsize=9.5, color="#16836F")
        axis.annotate(f"{r:.2f}×", (x, r), xytext=(0, -14), textcoords="offset points", ha="center", fontsize=9.5, color="#5B8FB9")
    axis.axhline(1.0, color="#63777B", linewidth=1, linestyle="--")
    axis.set_xticks(xs, [f"c{l}" for l in levels], fontsize=11)
    axis.set_ylabel("相对自回归的加速（5 块均值）" if chinese else "Speedup over autoregressive (mean of 5 blocks)", fontsize=11)
    axis.set_ylim(0.9, max(adapted) * 1.15)
    axis.set_title("加速随并发的衰减" if chinese else "Speedup versus concurrency", loc="left", fontsize=13.5, pad=10)
    axis.legend(frameon=False, fontsize=10.5, loc="upper right")
    axis.grid(color="#E2E7E8", linewidth=0.7)
    axis.spines[["top", "right"]].set_visible(False)
    total = sum(all(g > 0 for g in per[l]["adapted_over_released_pct_per_block"]) for l in levels)
    cells = len(levels) * blocks
    positives = sum(sum(g > 0 for g in per[l]["adapted_over_released_pct_per_block"]) for l in levels)
    per_block = identity["1"]["released_vs_adapted_per_block"]
    same_c1 = (f"每块 {per_block[0]}/40" if chinese else f"{per_block[0]}/40 in every block") if len(set(per_block)) == 1 else ", ".join(f"{n}/40" for n in per_block)
    figure.suptitle("微调后再训 DFlash 2：相对发布版的吞吐增益" if chinese else "Re-adapted DFlash 2 after fine-tuning: gain over the released draft",
                    fontsize=21, y=0.985)
    figure.text(0.5, 0.895, ("目标 = Qwen3.8-27B + 中文全模块 LoRA | 200 条中文提示切成 5 块 | greedy, max_tokens 256 | vLLM 0.28.0" if chinese else
                             "Target = Qwen3.8-27B + Chinese all-module LoRA | 200 Chinese prompts in 5 blocks | greedy, max_tokens 256 | vLLM 0.28.0"),
                ha="center", fontsize=12, color=MUTED)
    figure.text(0.5, 0.04, (f"{positives}/{cells} 格为正（{total}/{len(levels)} 个并发档全部为正）。并发 1 下两个 draft 的输出逐字相同：{same_c1}。\n"
                            "每格只测一次；不同块之间的差异是提示集方差，引用时应给均值和范围，不应单取最高的块。") if chinese else
                (f"{positives}/{cells} cells positive ({total}/{len(levels)} concurrency levels all positive). At concurrency 1 both drafts return byte-identical text: {same_c1}.\n"
                 "One run per cell; spread across blocks is prompt-set variance. Quote the mean and range, never the best block alone."),
                ha="center", fontsize=10.5, color=MUTED, linespacing=1.5)
    figure.subplots_adjust(left=0.06, right=0.98, top=0.8, bottom=0.19, wspace=0.26)
    figure.savefig(path, facecolor="white")
    plt.close(figure)


def render_results(output):
    """Figures 2-4 for both languages, hash-bound to the two published summaries."""
    latest = read_json(LATEST)
    adaptation = read_json(ADAPTATION / "data/summary.json")
    if latest["coverage"]["matched_concurrency"] != [1, 4, 8]:
        raise SystemExit("LATEST_SUMMARY_SHAPE_MISMATCH")
    if adaptation["round6"]["blocks"].keys() != {"b0", "b1", "b2", "b3", "b4"}:
        raise SystemExit("ROUND6_BLOCK_SHAPE_MISMATCH")
    record = {"scope": "Rendered from the two published summary.json files only; no new measurement.",
              "sources": {LATEST.relative_to(TOPIC).as_posix(): hashlib.sha256(LATEST.read_bytes()).hexdigest(),
                          (ADAPTATION / "data/summary.json").relative_to(TOPIC).as_posix():
                              hashlib.sha256((ADAPTATION / "data/summary.json").read_bytes()).hexdigest()},
              "figures": {}}
    output.mkdir(parents=True, exist_ok=True)
    plan = (("accuracy-alignment", draw_accuracy_alignment, latest),
            ("finetuned-throughput", draw_finetuned_throughput, adaptation),
            ("finetuned-alignment", draw_finetuned_alignment, adaptation),
            ("readapted-gain", draw_readapted_gain, adaptation))
    for stem, draw, data in plan:
        for chinese, suffix in ((False, "en"), (True, "cn")):
            path = output / f"{stem}-{suffix}.png"
            draw(data, path, chinese)
            pixels = plt.imread(path)
            record["figures"][path.name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                            "width": pixels.shape[1], "height": pixels.shape[0]}
    (output / "result-figures.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))


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
    parser.add_argument("--results-only", action="store_true", help="Figures 2-4 (accuracy alignment, fine-tuned throughput/alignment, re-adapted gain)")
    parser.add_argument("--font-file", type=Path, help="Use an existing CJK font without installing it")
    args = parser.parse_args()
    plt.rcParams.update({"font.family": select_font(args.font_file), "axes.unicode_minus": False,
                         "text.color": TEXT, "axes.labelcolor": TEXT})
    if args.results_only:
        render_results(args.output or TOPIC / "images")
        return
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

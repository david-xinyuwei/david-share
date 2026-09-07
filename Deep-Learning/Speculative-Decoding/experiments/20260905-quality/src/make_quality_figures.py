"""Render measured complete-answer quality and latency from reconciled results."""

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties


ROUTES = ("baseline", "mtp5", "dflash15")
COLORS = {"baseline": "#68747b", "mtp5": "#057d73", "dflash15": "#b12b52"}
LABELS = {"baseline": "Baseline", "mtp5": "MTP / 5", "dflash15": "DFlash / 15"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--font", type=Path)
    args = parser.parse_args()
    result = json.loads(args.summary.read_text(encoding="utf-8"))
    full = result["scope"] == "complete_frozen_matrix"
    if not full and result["scope"] != "canary":
        raise ValueError("Figures require a complete matrix or an explicitly labeled canary")
    routes = [route for route in ROUTES if route in result["routes"]]
    summaries = {route: (result["routes"][route]["primary"] if full else result["routes"][route])["quality_and_latency"] for route in routes}
    font = FontProperties(fname=str(args.font)) if args.font else FontProperties(family="DejaVu Sans")
    plt.rcParams.update({"font.family": font.get_name(), "font.size": 16, "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False, "axes.edgecolor": "#ccd3d4", "text.color": "#182529", "axes.labelcolor": "#182529", "savefig.facecolor": "white"})
    args.output.mkdir(parents=True, exist_ok=True)
    source_hash = hashlib.sha256(args.summary.read_bytes()).hexdigest()
    evidence = {"summary_sha256": source_hash, "scope": result["scope"], "figures": []}
    for quantity in ("quality", "latency"):
        figure, axes = plt.subplots(2, 1, figsize=(7.4, 8.8), dpi=180)
        figure.subplots_adjust(left=0.24, right=0.94, top=0.84, bottom=0.22, hspace=0.72)
        heading = "Complete-answer correctness" if quantity == "quality" else "Time to the complete answer"
        subtitle = "H100 NVL | Qwen3.6-27B BF16 | greedy" if full else "CANARY ONLY | NOT A FULL EVALUATION"
        figure.text(0.06, 0.94, heading, fontsize=21, weight="bold")
        figure.text(0.06, 0.897, subtitle, fontsize=13, color="#526268")
        plotted = []
        for axis, dataset, label in zip(axes, ("humaneval_plus", "math_500"), ("HumanEval+ / full tests", "MATH-500")):
            values = [100 * summaries[route][dataset]["accuracy"] if quantity == "quality" else summaries[route][dataset]["median_total_s"] for route in routes]
            positions = list(range(len(routes)))
            axis.barh(positions, values, color=[COLORS[route] for route in routes], height=0.58, zorder=3)
            axis.set_yticks(positions, [LABELS[route] for route in routes], fontsize=14)
            axis.invert_yaxis()
            axis.tick_params(axis="y", length=0, pad=10)
            axis.grid(axis="x", color="#e4e8e8", linewidth=0.8, zorder=0)
            axis.set_title(label, loc="left", pad=13, fontsize=17, weight="bold")
            maximum = 100 if quantity == "quality" else max(values) * 1.26
            axis.set_xlim(0, maximum)
            axis.set_xlabel("Correct (%)" if quantity == "quality" else "Median request time (s)", fontsize=13, labelpad=8)
            for position, route, value in zip(positions, routes, values):
                metrics = summaries[route][dataset]
                if quantity == "quality":
                    annotation = f"{metrics['correct']}/{metrics['responses']}  ({value:.1f}%)"
                    axis.text(max(value - 2, 0.5), position, annotation, ha="right" if value >= 45 else "left", va="center", color="white" if value >= 45 else "#182529", fontsize=13, weight="bold")
                else:
                    annotation = f"{value:.2f} s"
                    axis.text(value + maximum * 0.02, position, annotation, ha="left", va="center", fontsize=13, weight="bold")
                plotted.append({"route": route, "dataset": dataset, "value": value, "correct": metrics["correct"], "responses": metrics["responses"], "annotation": annotation})
        footer = "One response per task; no best-of selection.\nObserved scores do not prove universal equivalence." if quantity == "quality" else "Includes prefill and client overhead, excludes server startup.\nAll answers counted; output lengths can differ."
        if not full:
            footer = "Canary parser/figure validation only.\nDo not use these small-sample values as benchmark results."
        figure.text(0.06, 0.045, footer, fontsize=11.5, color="#526268", linespacing=1.55)
        path = args.output / ("primary-" + quantity + ".png")
        figure.savefig(path, dpi=180)
        plt.close(figure)
        evidence["figures"].append({"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "pixels": [1332, 1584], "values": plotted})
    if full:
        figure, axes = plt.subplots(2, 1, figsize=(7.4, 8.8), dpi=180)
        figure.subplots_adjust(left=0.14, right=0.91, top=0.77, bottom=0.21, hspace=0.65)
        figure.text(0.06, 0.95, "Correctness under concurrency", fontsize=21, weight="bold")
        figure.text(0.06, 0.907, "Same 32 code + 32 math tasks per setting", fontsize=13, color="#526268")
        plotted = []
        for axis, dataset, label in zip(axes, ("humaneval_plus", "math_500"), ("HumanEval+ / full tests", "MATH-500 subset")):
            for route in routes:
                values = [result["routes"][route][f"concurrency-{level}"]["quality_and_latency"][dataset]["correct"] for level in (1, 4, 8)]
                axis.plot((1, 4, 8), values, marker="o", linewidth=2.5, markersize=7, color=COLORS[route], label=LABELS[route])
                if route == "dflash15":
                    for level, correct in zip((1, 4, 8), values):
                        if level > 1:
                            axis.annotate(f"{correct}/32", (level, correct), xytext=(0, 12), textcoords="offset points", ha="center", fontsize=13, color=COLORS[route], weight="bold")
                plotted.extend({"route": route, "dataset": dataset, "concurrency": level, "correct": correct, "responses": 32} for level, correct in zip((1, 4, 8), values))
            axis.set_title(label, loc="left", pad=12, fontsize=17, weight="bold")
            axis.set_xlim(0.6, 8.4)
            axis.set_ylim(0, 35)
            axis.set_xticks((1, 4, 8))
            axis.set_yticks((0, 8, 16, 24, 32))
            axis.set_ylabel("Correct / 32", fontsize=13)
            axis.set_xlabel("Concurrent requests", fontsize=13, labelpad=6)
            axis.grid(color="#e4e8e8", linewidth=0.8)
        handles, labels = axes[0].get_legend_handles_labels()
        legend = figure.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.52, 0.885), ncol=3, frameon=False, fontsize=12)
        figure.text(0.06, 0.043, "One run per setting; not an algorithm-wide claim.\nThe observed DFlash15 regression is not root-caused or fixed.", fontsize=11.5, color="#526268", linespacing=1.55)
        figure.canvas.draw()
        renderer = figure.canvas.get_renderer()
        if legend.get_window_extent(renderer).overlaps(axes[0]._left_title.get_window_extent(renderer)):
            raise ValueError("Concurrency figure legend overlaps its first panel title")
        path = args.output / "concurrency-quality.png"
        figure.savefig(path, dpi=180)
        plt.close(figure)
        evidence["figures"].append({"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "pixels": [1332, 1584], "values": plotted})
    (args.output / "figure-evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"scope": result["scope"], "figures": len(evidence["figures"]), "summary_sha256": source_hash}))


if __name__ == "__main__":
    main()
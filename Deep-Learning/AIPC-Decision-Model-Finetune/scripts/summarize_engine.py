"""Collect every on-device engine run under 验证结果/端侧引擎_*/<label>/ into one table.

Each run folder holds <workload>/summary.json and rows.jsonl (systemone_client.py), optionally
<workload>/parity_vs_pytorch*.json (parity.py) and run.json (run_engine_eval.ps1) or server_memory.json (first manual runs).
Usage: python summarize_engine.py --root 验证结果/端侧引擎_20261027-124700 [--out engine_summary.md]
Standard library only.
"""
import argparse
import json
import sys
from pathlib import Path


def load(p):
    return json.loads(p.read_text(encoding="utf-8-sig")) if p.is_file() else None


KIND = {"released": "发布版", "ft": "微调 FT", "ftcf": "微调 FT-cf"}
VARIANT = {"": "默认参数", "lean": "-c 2048 -ub 512", "ctx2048": "-c 2048", "policy": "默认参数，提示词含策略全文（B0-policy）"}
BACKEND = {"cpu": "CPU", "opencl": "Adreno GPU（OpenCL）"}


def describe(label):
    """'ft-kev-0.8b-Q8_0-cpu-lean' -> (sort key, model, quant, backend and settings)."""
    kind, _, size, quant, backend, *rest = label.split("-")
    variant = "-".join(rest)
    key = (list(KIND).index(kind), float(size.rstrip("b")), quant, backend, variant)
    return key, f"{KIND[kind]} {size.upper()}", quant, f"{BACKEND[backend]}，{VARIANT.get(variant, variant)}"


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # a piped Windows console defaults to GBK
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    root = Path(a.root)
    rows, incomplete = [], []
    for d in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("pytorch-")):
        if not all((d / w / "summary.json").is_file() for w in ("support", "assistant")):
            done = {w: sum(1 for line in (d / w / "rows.jsonl").read_text(encoding="utf-8").splitlines() if line.strip())
                    for w in ("support", "assistant") if (d / w / "rows.jsonl").is_file()}
            incomplete.append(f"{d.name}（" + ("，".join(f"{w} {n} 条" for w, n in done.items()) or "无结果") + "，无汇总）")
            continue
        run = load(d / "run.json") or {}
        mem = load(d / "server_memory.json") or {}
        r = {"label": d.name, "backend": run.get("backend") or ("opencl" if "opencl" in d.name else "cpu"),
             "gguf_mib": run.get("gguf_mib") or mem.get("gguf_mib"),
             "load_s": run.get("load_seconds"),
             "peak_ws_mib": run.get("peak_working_set_mib") or mem.get("peak_working_set_mib"),
             "private_mib": run.get("private_mib") or mem.get("private_mib"),
             "gpu_shared_mib": run.get("gpu_shared_mib"),
             "args": run.get("server_args") or mem.get("args")}
        for w in ("support", "assistant"):
            s = load(d / w / "summary.json")
            if s:
                r[f"{w}_acc"] = s["accuracy"]
                rows_file = d / w / "rows.jsonl"
                if rows_file.is_file():  # exact accuracy from the per-question results (summary.json rounds to 4 decimals)
                    oks = [q["ok"] for line in rows_file.read_text(encoding="utf-8").splitlines() if line.strip()
                           for q in json.loads(line).get("questions", {}).values()]
                    r[f"{w}_acc"] = sum(oks) / len(oks) if oks else None
                r[f"{w}_p50"] = s["latency_ms"]["p50"]
                r[f"{w}_p90"] = s["latency_ms"]["p90"]
                r[f"{w}_errors"] = s["errors"]
            par = next((load(p) for p in sorted((d / w).glob("parity_vs_pytorch*.json"))), None) if (d / w).is_dir() else None
            if par:
                r[f"{w}_agree"] = par["by_type"]["all"]["agreement"]
                r[f"{w}_tvd"] = par["by_type"]["all"]["mean_tvd"]
                r[f"{w}_torch_acc"] = par["by_type"]["all"]["torch_acc"]
        r["model"] = run.get("model") or mem.get("model")
        rows.append(r)
    sizes = {r["model"]: r["gguf_mib"] for r in rows if r["model"] and r["gguf_mib"]}
    for r in rows:  # runs that loaded a Hugging Face reference (-hf) take the size recorded for the same file elsewhere
        r["gguf_mib"] = r["gguf_mib"] or sizes.get(r["model"])

    f = lambda x, spec: "—" if x is None else format(x, spec)
    pc = lambda x: "—" if x is None else f"{100 * x:.1f}%"
    lines = ["| 运行 | 后端 | GGUF（MiB） | 加载（秒） | 峰值工作集（MiB） | 提交内存（MiB） | 准确率 工单 / 助手 | 同一测试集 PyTorch 准确率 工单 / 助手 | 与 PyTorch 预测一致率 工单 / 助手 | 概率差（平均 TVD）工单 / 助手 | 单次决策时延 p50 / p90（毫秒）工单 | 单次决策时延 p50 / p90（毫秒）助手 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(" | ".join([
            f"| {r['label']}", r["backend"], f(r["gguf_mib"], ".0f"), f(r["load_s"], ".1f"), f(r["peak_ws_mib"], "d"),
            f(r["private_mib"], "d"),
            f"{pc(r.get('support_acc'))} / {pc(r.get('assistant_acc'))}",
            f"{pc(r.get('support_torch_acc'))} / {pc(r.get('assistant_torch_acc'))}",
            f"{pc(r.get('support_agree'))} / {pc(r.get('assistant_agree'))}",
            f"{f(r.get('support_tvd'), '.4f')} / {f(r.get('assistant_tvd'), '.4f')}",
            f"{f(r.get('support_p50'), '.0f')} / {f(r.get('support_p90'), '.0f')}",
            f"{f(r.get('assistant_p50'), '.0f')} / {f(r.get('assistant_p90'), '.0f')} |"]))
    # brief table for the report: readable names, sorted released -> FT -> FT-cf, by size
    brief = ["| 模型 | 量化 | 后端与启动参数 | 模型文件（MiB） | 内存：峰值工作集 / 提交（MiB） | 准确率 工单 / 助手（括号内为 PyTorch） | 与 PyTorch 逐题一致率 工单 / 助手 | 单次决策时延中位数 工单 / 助手（毫秒） |",
             "|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: describe(r["label"])[0]):
        _, model, quant, setting = describe(r["label"])
        brief.append(f"| {model} | {quant} | {setting} | {f(r['gguf_mib'], ',.0f')} | {f(r['peak_ws_mib'], ',d')} / {f(r['private_mib'], ',d')} | "
                     f"{pc(r.get('support_acc'))}（{pc(r.get('support_torch_acc'))}） / {pc(r.get('assistant_acc'))}（{pc(r.get('assistant_torch_acc'))}） | "
                     f"{pc(r.get('support_agree'))} / {pc(r.get('assistant_agree'))} | {f(r.get('support_p50'), ',.0f')} / {f(r.get('assistant_p50'), ',.0f')} |")
    if incomplete:
        brief += ["", "没有跑完、不计入上表的运行：" + "；".join(incomplete) + "。"]
    text = "\n".join(lines) + "\n\n" + "\n".join(brief) + "\n"
    print(text)
    (root / "engine_summary.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    (root / "engine_brief.md").write_text("\n".join(brief) + "\n", encoding="utf-8")
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()

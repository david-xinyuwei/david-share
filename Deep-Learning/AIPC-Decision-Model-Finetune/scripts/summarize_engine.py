"""Collect every on-device engine run under 验证结果/端侧引擎_*/<label>/ into one table.

Each run folder holds <workload>/summary.json and rows.jsonl (systemone_client.py), optionally
<workload>/parity_vs_pytorch*.json (parity.py) and run.json (run_engine_eval.ps1) or server_memory.json (first manual runs).
Usage: python summarize_engine.py --root 验证结果/端侧引擎_20261027-124700 [--out engine_summary.md]
Standard library only.
"""
import argparse
import hashlib
import json
import shlex
import sys
from pathlib import Path


def load(p):
    return json.loads(p.read_text(encoding="utf-8-sig")) if p.is_file() else None


KIND = {"released": "发布版", "ft": "微调 FT", "ftcf": "微调 FT-cf"}
VARIANT = {"": "默认参数", "lean": "-c 2048 -ub 512", "ctx2048": "-c 2048", "policy": "默认参数，提示词含策略全文（B0-policy）",
           "run1": "默认参数，第 1 次运行", "run2": "默认参数，第 2 次运行"}  # repeated runs of one configuration (x86-64 root)
BACKEND = {"cpu": "CPU", "opencl": "Adreno GPU（OpenCL）"}


def describe(label):
    """'ft-kev-0.8b-Q8_0-cpu-lean' -> (sort key, model, quant, backend and settings)."""
    kind, _, size, quant, backend, *rest = label.split("-")
    variant = "-".join(rest)
    key = (list(KIND).index(kind), float(size.rstrip("b")), quant, backend, variant)
    return key, f"{KIND[kind]} {size.upper()}", quant, f"{BACKEND[backend]}，{VARIANT.get(variant, variant)}"


def brief_table(rows, incomplete):
    ordered = sorted(rows, key=lambda row: describe(row["label"])[0])

    def metric(value, specification):
        return "—" if value is None else format(value, specification)

    def percentage(value):
        return "—" if value is None else f"{100 * value:.1f}%"

    sections = []
    for title, headers, fields in (
        ("准确率与引擎一致率", ["工单准确率：端侧（PyTorch）", "助手准确率：端侧（PyTorch）",
                                "工单答案一致率：端侧对 PyTorch", "助手答案一致率：端侧对 PyTorch"], "quality"),
        ("模型文件与进程内存", ["模型文件（MiB）", "峰值工作集（MiB）", "提交内存（MiB）"], "memory"),
        ("单次请求时延", ["工单请求耗时中位数（毫秒）", "助手请求耗时中位数（毫秒）"], "latency"),
    ):
        sections += [f"**{title}**", "", "| 模型、量化与运行参数 | " + " | ".join(headers) + " |",
                     "|" + "---|" * (len(headers) + 1)]
        for row in ordered:
            _, model, quant, setting = describe(row["label"])
            label = f"{model}<br>{quant} · {setting}"
            if fields == "quality":
                values = [f"{percentage(row.get('support_acc'))}（{percentage(row.get('support_torch_acc'))}）",
                          f"{percentage(row.get('assistant_acc'))}（{percentage(row.get('assistant_torch_acc'))}）",
                          percentage(row.get("support_agree")), percentage(row.get("assistant_agree"))]
            elif fields == "memory":
                values = [metric(row.get("gguf_mib"), ",.0f"), metric(row.get("peak_ws_mib"), ",d"),
                          metric(row.get("private_mib"), ",d")]
            else:
                values = [metric(row.get("support_p50"), ",.0f"), metric(row.get("assistant_p50"), ",.0f")]
            sections.append("| " + " | ".join([label, *values]) + " |")
        sections.append("")
    if incomplete:
        sections.append("没有跑完、不计入上表的运行：" + "；".join(incomplete) + "。")
    return "\n".join(sections).rstrip() + "\n"


def before_after_table(rows):
    by_label = {row["label"]: row for row in rows}
    lines = ["| 固定模型配置 | 性能指标（单位） | 微调前测量值：发布版 | 微调后测量值：最终方案 |",
             "|---|---|---|---|"]
    for size, quantization in (("0.8b", "Q8_0"), ("4b", "Q4_K_M")):
        before = by_label.get(f"released-kev-{size}-{quantization}-cpu", {})
        after = by_label.get(f"ftcf-kev-{size}-{quantization}-cpu", {})
        if before and after:
            fields = ("backend", "build", "support_records", "assistant_records",
                      "support_data", "assistant_data", "support_cases_sha256", "assistant_cases_sha256",
                      "support_tokens_sha256", "assistant_tokens_sha256")
            for field in fields:
                if before.get(field) is None or before.get(field) != after.get(field):
                    raise ValueError(f"Before/after performance conditions differ: {size}/{field}")
            settings = []
            for row in (before, after):
                arguments = shlex.split(row.get("args") or "", posix=False)
                settings.append({flag: arguments[arguments.index(flag) + 1] if flag in arguments else None
                                 for flag in ("-c", "-b", "-ub", "--cache-ram", "-ngl", "--parallel", "--threads")})
            if settings[0] != settings[1] or any(settings[0][flag] is None for flag in ("-c", "-b", "-ub", "--cache-ram")):
                raise ValueError(f"Before/after performance settings differ: {size}")
        for field, metric in (("support_p50", "工单请求耗时中位数（毫秒）"),
                              ("assistant_p50", "助手请求耗时中位数（毫秒）"),
                              ("peak_ws_mib", "进程峰值工作集（MiB）")):
            values = ["未跑" if row.get(field) is None else format(row[field], ",.0f") for row in (before, after)]
            lines.append(f"| {size.upper()} / {quantization} / CPU | {metric} | " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n"


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # a piped Windows console defaults to GBK
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--output-dir", type=Path, help="write derived summaries here instead of the run directory")
    a = ap.parse_args()
    root = Path(a.root)
    output_dir = a.output_dir or root
    output_dir.mkdir(parents=True, exist_ok=True)
    rows, incomplete = [], []
    for d in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("pytorch-")):
        if not any((d / name).exists() for name in ("run.json", "server.log", "server_memory.json", "support", "assistant")):
            continue  # not a run folder (e.g. the derived summary/ written by --output-dir)
        if not all((d / w / "summary.json").is_file() for w in ("support", "assistant")):
            done = {w: sum(1 for line in (d / w / "rows.jsonl").read_text(encoding="utf-8").splitlines() if line.strip())
                    for w in ("support", "assistant") if (d / w / "rows.jsonl").is_file()}
            incomplete.append(f"{d.name}（" + ("，".join(f"{w} {n} 条" for w, n in done.items()) or "无结果") + "，无汇总）")
            continue
        run = load(d / "run.json") or {}
        mem = load(d / "server_memory.json") or {}
        r = {"label": d.name, "backend": run.get("backend") or ("opencl" if "opencl" in d.name else "cpu"),
               "build": run.get("build") or mem.get("build"),
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
                r[f"{w}_records"] = s["records"]
                r[f"{w}_data"] = str(s["data"]).replace("\\", "/")
                rows_file = d / w / "rows.jsonl"
                if rows_file.is_file():  # exact accuracy from the per-question results (summary.json rounds to 4 decimals)
                    records = [json.loads(line) for line in rows_file.read_text(encoding="utf-8").splitlines() if line.strip()]
                    oks = [question["ok"] for record in records for question in record.get("questions", {}).values()]
                    r[f"{w}_acc"] = sum(oks) / len(oks) if oks else None
                    cases = [(record["i"], record.get("case"),
                              {name: question["label"] for name, question in record.get("questions", {}).items()})
                             for record in records]
                    tokens = [record.get("input_tokens") for record in records]
                    r[f"{w}_cases_sha256"] = hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest()
                    r[f"{w}_tokens_sha256"] = hashlib.sha256(json.dumps(tokens).encode()).hexdigest()
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
    brief = brief_table(rows, incomplete)
    text = "\n".join(lines) + "\n\n" + brief
    print(text)
    (output_dir / "engine_summary.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    (output_dir / "engine_brief.md").write_text(brief, encoding="utf-8")
    (output_dir / "engine_comparison.md").write_text(before_after_table(rows), encoding="utf-8")
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()

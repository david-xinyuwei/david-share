#!/usr/bin/env python3
"""Fill the generated blocks of README.md and README_CN.md.

    python tools/build_readme.py          # rewrite the generated blocks in place
    python tools/build_readme.py --check  # fail if either README differs from a fresh render

Every number, table and code excerpt between `<!-- BEGIN GENERATED: name -->`
and `<!-- END GENERATED: name -->` comes from evidence/, profiles/ or the
pinned upstream patches. Prose outside the markers is written by hand.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READMES = {"en": ROOT / "README.md", "cn": ROOT / "README_CN.md"}
BLOCK = re.compile(r"(<!-- BEGIN GENERATED: (?P<name>[a-z0-9-]+) -->\n)(?P<body>.*?)(<!-- END GENERATED: (?P=name) -->)", re.S)


def _json(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _n(value: float, digits: int = 2) -> str:
    return f"{value:,.{digits}f}"


def _i(value: float) -> str:
    return f"{value:,.0f}"


def _pct(value: float) -> str:
    return f"{value:+.2f}%"


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def _table(header: list[str], rows: list[list[str]], align: list[str]) -> str:
    sep = ["---:" if a == "r" else "---" for a in align]
    out = ["| " + " | ".join(_cell(h) for h in header) + " |", "|" + "|".join(sep) + "|"]
    for r in rows:
        if len(r) != len(header):
            raise SystemExit(f"TABLE_SHAPE {len(r)} cells for {len(header)} columns: {r}")
        out.append("| " + " | ".join(_cell(c) for c in r) + " |")
    return "\n".join(out) + "\n"


def _lock() -> dict:
    return {e["file"]: e for e in _json("upstream/SOURCES.lock.json")["patches"]}


def excerpt(name: str, lang: str) -> str:
    spec = _json("tools/excerpts.json")["excerpts"][name]
    entry = _lock()[spec["patch"]]
    lines = (ROOT / "upstream" / "patches" / spec["patch"]).read_text(encoding="utf-8").split("\n")
    hits = [i for i, line in enumerate(lines) if line == spec["start"]]
    if len(hits) != 1:
        raise SystemExit(f"EXCERPT_ANCHOR {name}: {len(hits)} matches in {spec['patch']}")
    body = lines[hits[0]: hits[0] + spec["lines"]]
    if len(body) != spec["lines"]:
        raise SystemExit(f"EXCERPT_SHORT {name}")
    short = entry["commit"][:7]
    link = f"[`{entry['repository']}@{short}`]({entry['url']})"
    patch_link = f"[{spec['patch']}](upstream/patches/{spec['patch']})"
    if lang == "en":
        caption = f"Diff excerpt from {link}, file `{spec['path']}` (local copy: {patch_link})."
    else:
        caption = f"摘自 {link} 的 diff，文件 `{spec['path']}`（本地副本：{patch_link}）。"
    return caption + "\n\n```diff\n" + "\n".join(body) + "\n```\n"


def moe_table(lang: str) -> str:
    text = (ROOT / "upstream/patches/sammysun0711__aiter__d725746.patch").read_text(encoding="utf-8")
    section = text.split("b/aiter/configs/model_configs/mimo_v2_5_pro_b16_tuned_fmoe.csv\n", 2)[2]
    section = section.split("diff --git", 1)[0]
    rows_csv = [l[1:] for l in section.split("\n") if l.startswith("+") and not l.startswith("+++")]
    reader = list(csv.DictReader(io.StringIO("\n".join(rows_csv))))
    block_m = {r["block_m"] for r in reader}
    if len(block_m) != 1:
        raise SystemExit(f"MOE_BLOCK_M not constant: {block_m}")
    out = []
    for r in reader:
        kernel = re.sub(r"^_ZN5aiter\d+", "", r["kernelName1"]).rstrip("E")
        out.append([_i(int(r["token"])), f"`{kernel}`", _n(float(r["us"]), 1), _n(float(r["tflops"]), 1)])
    bm = next(iter(block_m))
    if lang == "en":
        head = ["Tokens in the MoE batch", "Selected kernel", "Tuned time (µs)", "TFLOPS"]
        caption = f"Every row uses block_m = {bm}; the columns are the tuner's own measurement at each token count."
    else:
        head = ["MoE batch token 数", "选中的 kernel", "调优实测耗时（µs）", "TFLOPS"]
        caption = f"每一行的 block_m 都是 {bm}；后两列是调优器自己在每个 token 数下测到的值。"
    return _table(head, out, ["r", "l", "r", "r"]) + "\n" + caption + "\n"


def headline(lang: str) -> str:
    m = _json("evidence/measurements.json")
    ab = m["ab_ck_unified_verify_64k"]
    st = m["tuned_moe_stage"]
    pre = {r["input_tokens"]: r for r in st["prefill"]}
    dec = {r["concurrency"]: r for r in st["decode"]}
    ab_val = f"{_n(ab['baseline_mean_tok_s'])} → {_n(ab['optimized_mean_tok_s'])} gen tok/s"
    pre_val = f"{_n(pre[8192]['before_input_tok_s'])} → {_n(pre[8192]['after_input_tok_s'])} input tok/s"
    dec_val = f"{_n(dec[128]['before_output_tok_s'])} → {_n(dec[128]['after_output_tok_s'])} output tok/s"
    if lang == "en":
        head = ["What changed / workload", "Before → after (MI300X)", "Change", "Evidence"]
        rows = [
            ["CK block-scale FP8 GEMM + unified verify (two switches)<br>64K in / 1K out, 16 in flight, single VM", ab_val, f"**{_pct(ab['throughput_delta_pct'])}**", "two-switch A/B, same image, back-to-back, N=2 each"],
            ["Shape-tuned fused-MoE table<br>8K prefill, concurrency 4, 1P1D", pre_val, f"**{_pct(pre[8192]['input_tok_s_delta_pct'])}**", "stage pair, N=1 each"],
            ["Shape-tuned fused-MoE table<br>8K in / 1K out, concurrency 128, 1P1D", dec_val, f"**{_pct(dec[128]['output_tok_s_delta_pct'])}**", "stage pair, N=1 each"],
        ]
    else:
        head = ["改了什么 / 负载", "优化前 → 优化后（MI300X）", "变化", "证据类型"]
        rows = [
            ["CK block-scale FP8 GEMM + unified verify（两个开关）<br>64K 输入 / 1K 输出，16 个请求并发，单机", ab_val, f"**{_pct(ab['throughput_delta_pct'])}**", "两开关 A/B：同一镜像、背靠背，各 2 次"],
            ["按 shape 调优的 fused-MoE 表<br>8K prefill，并发 4，1P1D", pre_val, f"**{_pct(pre[8192]['input_tok_s_delta_pct'])}**", "阶段对比，各 1 次"],
            ["按 shape 调优的 fused-MoE 表<br>8K 输入 / 1K 输出，并发 128，1P1D", dec_val, f"**{_pct(dec[128]['output_tok_s_delta_pct'])}**", "阶段对比，各 1 次"],
        ]
    return _table(head, rows, ["l", "l", "r", "l"])


def _ab_names(lang: str) -> list[str]:
    return ["Baseline", "Optimized", "Change"] if lang == "en" else ["基线", "优化后", "变化"]


def ab_table(lang: str) -> str:
    ab = _json("evidence/measurements.json")["ab_ck_unified_verify_64k"]
    n = _ab_names(lang)
    head = ["Arm", "Run 1 (tok/s)", "Run 2 (tok/s)", "Mean (tok/s)"] if lang == "en" else ["组别", "第 1 次（tok/s）", "第 2 次（tok/s）", "均值（tok/s）"]
    rows = [
        [n[0], _n(ab["baseline_run_means_tok_s"][0]), _n(ab["baseline_run_means_tok_s"][1]), _n(ab["baseline_mean_tok_s"])],
        [n[1], _n(ab["optimized_run_means_tok_s"][0]), _n(ab["optimized_run_means_tok_s"][1]), _n(ab["optimized_mean_tok_s"])],
        [n[2], "", "", f"**{_pct(ab['throughput_delta_pct'])}**"],
    ]
    return _table(head, rows, ["l", "r", "r", "r"])


def ab_tpot(lang: str) -> str:
    ab = _json("evidence/measurements.json")["ab_ck_unified_verify_64k"]
    n = _ab_names(lang)
    head = ["Arm", "Implied TPOT at batch 16 (ms)"] if lang == "en" else ["组别", "batch 16 下折算 TPOT（ms）"]
    rows = [[n[0], _n(ab["baseline_implied_tpot_ms"])], [n[1], _n(ab["optimized_implied_tpot_ms"])],
            [n[2], f"**{_pct(ab['implied_tpot_delta_pct'])}**"]]
    return _table(head, rows, ["l", "r"])


def stage_prefill(lang: str) -> str:
    st = _json("evidence/measurements.json")["tuned_moe_stage"]
    head = (["Input tokens", "Before (input tok/s)", "After (input tok/s)", "Change"]
            if lang == "en" else ["输入 token", "优化前（input tok/s）", "优化后（input tok/s）", "变化"])
    rows = [[_i(r["input_tokens"]), _n(r["before_input_tok_s"]), _n(r["after_input_tok_s"]),
             f"**{_pct(r['input_tok_s_delta_pct'])}**"] for r in st["prefill"]]
    return _table(head, rows, ["r", "r", "r", "r"])


def stage_prefill_ttft(lang: str) -> str:
    st = _json("evidence/measurements.json")["tuned_moe_stage"]
    head = (["Input tokens", "Before (mean TTFT, s)", "After (mean TTFT, s)", "Change"]
            if lang == "en" else ["输入 token", "优化前（平均 TTFT，s）", "优化后（平均 TTFT，s）", "变化"])
    rows = [[_i(r["input_tokens"]), _n(r["before_mean_ttft_ms"] / 1000.0), _n(r["after_mean_ttft_ms"] / 1000.0),
             _pct(r["mean_ttft_delta_pct"])] for r in st["prefill"]]
    return _table(head, rows, ["r", "r", "r", "r"])


def stage_decode(lang: str) -> str:
    st = _json("evidence/measurements.json")["tuned_moe_stage"]
    head = (["Concurrency", "Before (output tok/s)", "After (output tok/s)", "Change"]
            if lang == "en" else ["并发", "优化前（output tok/s）", "优化后（output tok/s）", "变化"])
    rows = [[str(r["concurrency"]), _n(r["before_output_tok_s"]), _n(r["after_output_tok_s"]),
             f"**{_pct(r['output_tok_s_delta_pct'])}**"] for r in st["decode"]]
    return _table(head, rows, ["r", "r", "r", "r"])


def stage_decode_tpot(lang: str) -> str:
    st = _json("evidence/measurements.json")["tuned_moe_stage"]
    head = (["Concurrency", "Before (mean TPOT, ms)", "After (mean TPOT, ms)", "Change"]
            if lang == "en" else ["并发", "优化前（平均 TPOT，ms）", "优化后（平均 TPOT，ms）", "变化"])
    rows = [[str(r["concurrency"]), _n(r["before_mean_tpot_ms"]), _n(r["after_mean_tpot_ms"]),
             _pct(r["mean_tpot_delta_pct"])] for r in st["decode"]]
    return _table(head, rows, ["r", "r", "r", "r"])


def ladder(lang: str) -> str:
    rows_in = _json("evidence/measurements.json")["concurrency_ladder_8k1k"]
    head = (["Configured", "Observed", "Output tok/s", "Mean TPOT (ms)"]
            if lang == "en" else ["配置并发", "实测并发", "Output tok/s", "平均 TPOT（ms）"])
    rows = [[str(r["concurrency"]), _n(r["observed_concurrency"]), _n(r["output_tok_s"]), _n(r["mean_tpot_ms"])] for r in rows_in]
    return _table(head, rows, ["r", "r", "r", "r"])


def ladder_ttft(lang: str) -> str:
    rows_in = _json("evidence/measurements.json")["concurrency_ladder_8k1k"]
    head = (["Configured", "Mean TTFT (s)", "P99 TTFT (s)"] if lang == "en" else ["配置并发", "平均 TTFT（s）", "P99 TTFT（s）"])
    rows = [[str(r["concurrency"]), _n(r["mean_ttft_ms"] / 1000.0, 1), _n(r["p99_ttft_ms"] / 1000.0, 1)] for r in rows_in]
    return _table(head, rows, ["r", "r", "r"])


def snapshot(lang: str) -> str:
    snap = _json("evidence/measurements.json")["stack_snapshot"]
    head = (["Concurrency", "2026-05-09 output tok/s (16K in)", "2026-07-13 output tok/s (8K in)"]
            if lang == "en" else ["并发", "2026-05-09 output tok/s（16K 输入）", "2026-07-13 output tok/s（8K 输入）"])
    rows = [[str(r["concurrency"]), _i(r["early_output_tok_s"]), _n(r["late_output_tok_s"])] for r in snap["decode"]]
    return _table(head, rows, ["r", "r", "r"])


def snapshot_tpot(lang: str) -> str:
    snap = _json("evidence/measurements.json")["stack_snapshot"]
    head = (["Concurrency", "2026-05-09 mean TPOT (ms)", "2026-07-13 mean TPOT (ms)"]
            if lang == "en" else ["并发", "2026-05-09 平均 TPOT（ms）", "2026-07-13 平均 TPOT（ms）"])
    rows = [[str(r["concurrency"]), _n(r["early_mean_tpot_ms"]), _n(r["late_mean_tpot_ms"])] for r in snap["decode"]]
    return _table(head, rows, ["r", "r", "r"])


EVIDENCE_LABEL = {
    "en": {"LOCAL_AB": "measured A/B", "LOCAL_STAGE": "measured stage pair", "LOCAL_LADDER": "measured ladder",
           "ON_IN_MEASURED_RUN": "on in measured runs, not isolated", "PINNED_NOT_MEASURED": "pinned runtime, not throughput-tested here",
           "KERNEL_NOT_ISOLATED": "pinned runtime; kernel not measured in isolation", "NOT_MEASURED": "later commit, not measured"},
    "cn": {"LOCAL_AB": "实测 A/B", "LOCAL_STAGE": "实测阶段对比", "LOCAL_LADDER": "实测并发阶梯",
           "ON_IN_MEASURED_RUN": "实测时已打开，未单独拆分", "PINNED_NOT_MEASURED": "在固定 runtime 中，本仓库未测吞吐",
           "KERNEL_NOT_ISOLATED": "在固定 runtime 中；kernel 未单独测试", "NOT_MEASURED": "后续提交，未实测"},
}


def technique_map(lang: str) -> str:
    cat = _json("profiles/techniques.json")
    lock = _lock()
    head = (["Technique", "Switch: MI300X / NVIDIA", "Code", "Evidence"]
            if lang == "en" else ["技术", "开关：MI300X / NVIDIA", "代码", "证据"])
    out = []
    for layer in ("framework", "operator", "workload"):
        rows = []
        for t in cat["techniques"]:
            if t["layer"] != layer:
                continue
            codes = ", ".join(f"[{lock[p]['commit'][:7]}]({lock[p]['url']})" for p in t["patches"]) or "—"
            label = t["evidence_note"][lang] if "evidence_note" in t else EVIDENCE_LABEL[lang][t["evidence"]]
            rows.append([t[lang], f"MI300X: {t['rocm']}<br>NVIDIA: {t['cuda']}", codes, label])
        out.append(f"**{cat['layers'][layer][lang]}**\n\n" + _table(head, rows, ["l", "l", "l", "l"]))
    return "\n".join(out)


STACK_LABEL = {
    "en": {"measured_run": "in the measured runs", "pinned_runtime_not_throughput_tested": "pinned runtime, not throughput-tested here",
           "later_branch": "later branch, not in any runtime here", "upstreamed_later": "upstream follow-up, not in the pinned runtime"},
    "cn": {"measured_run": "在实测 runtime 中", "pinned_runtime_not_throughput_tested": "在固定 runtime 中，本仓库未测吞吐",
           "later_branch": "后续分支，不在任何 runtime 中", "upstreamed_later": "上游后续提交，不在固定 runtime 中"},
}


def upstream_table(lang: str) -> str:
    lock = _json("upstream/SOURCES.lock.json")
    head = (["Commit", "Subject", "Layer", "Status"] if lang == "en" else ["Commit", "提交标题", "层", "状态"])
    cat = _json("profiles/techniques.json")["layers"]
    rows = [[f"[{e['repository']}@{e['commit'][:7]}]({e['url']})", e["subject"], cat[e["layer"]][lang],
             STACK_LABEL[lang][e["stack_status"]]] for e in lock["patches"]]
    return _table(head, rows, ["l", "l", "l", "l"])


BLOCKS = {
    "headline": headline,
    "ab-table": ab_table,
    "ab-tpot": ab_tpot,
    "stage-prefill": stage_prefill,
    "stage-prefill-ttft": stage_prefill_ttft,
    "stage-decode": stage_decode,
    "stage-decode-tpot": stage_decode_tpot,
    "ladder": ladder,
    "ladder-ttft": ladder_ttft,
    "snapshot": snapshot,
    "snapshot-tpot": snapshot_tpot,
    "technique-map": technique_map,
    "moe-table": moe_table,
    "upstream-table": upstream_table,
}
for _name in _json("tools/excerpts.json")["excerpts"]:
    BLOCKS[f"excerpt-{_name}"] = (lambda n: (lambda lang: excerpt(n, lang)))(_name)


def render(text: str, lang: str) -> str:
    seen = set()

    def fill(m: re.Match) -> str:
        name = m.group("name")
        if name not in BLOCKS:
            raise SystemExit(f"UNKNOWN_BLOCK {name} in {lang} README")
        seen.add(name)
        return m.group(1) + BLOCKS[name](lang) + m.group(4)

    out = BLOCK.sub(fill, text)
    missing = set(BLOCKS) - seen
    if missing:
        raise SystemExit(f"MISSING_BLOCKS in {lang} README: {sorted(missing)}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    stale = []
    for lang, path in READMES.items():
        current = path.read_text(encoding="utf-8")
        fresh = render(current, lang)
        if args.check:
            if fresh != current:
                stale.append(path.name)
        else:
            path.write_text(fresh, encoding="utf-8", newline="\n")
    if args.check:
        if stale:
            print("STALE " + ", ".join(stale) + "; run tools/build_readme.py")
            return 1
        print(f"PASS {len(BLOCKS)} generated blocks are current in README.md and README_CN.md")
        return 0
    print("rendered README.md and README_CN.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())

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


def _c(value: float) -> str:
    """Compact throughput: no decimals, so before/after pairs fit a phone column."""
    return f"{value:,.0f}"


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
    kernels = []
    out = []
    for r in reader:
        kernel = re.sub(r"^_ZN5aiter\d+", "", r["kernelName1"]).rstrip("E")
        if kernel not in kernels:
            kernels.append(kernel)
        out.append([_i(int(r["token"])), chr(ord("A") + kernels.index(kernel)), _n(float(r["us"]), 1), _n(float(r["tflops"]), 1)])
    bm = next(iter(block_m))
    legend = "\n".join(f"- {chr(ord('A') + i)} = `{k}`" for i, k in enumerate(kernels))
    if lang == "en":
        head = ["Tokens", "Kernel", "Time (µs)", "TFLOPS"]
        caption = f"Every row uses block_m = {bm}; time and TFLOPS are the tuner's own measurement at each token count. Kernel letters:"
    else:
        head = ["Token 数", "Kernel", "耗时（µs）", "TFLOPS"]
        caption = f"每一行的 block_m 都是 {bm}；耗时和 TFLOPS 是调优器自己在每个 token 数下测到的值。Kernel 字母含义："
    return _table(head, out, ["r", "l", "r", "r"]) + "\n" + caption + "\n\n" + legend + "\n"


def headline(lang: str) -> str:
    m = _json("evidence/measurements.json")
    ab = m["ab_ck_unified_verify_64k"]
    st = m["tuned_moe_stage"]
    pre = {r["input_tokens"]: r for r in st["prefill"]}
    dec = {r["concurrency"]: r for r in st["decode"]}
    ab_val = f"{_c(ab['baseline_mean_tok_s'])} → {_c(ab['optimized_mean_tok_s'])}"
    pre_val = f"{_c(pre[8192]['before_input_tok_s'])} → {_c(pre[8192]['after_input_tok_s'])}"
    dec_val = f"{_c(dec[128]['before_output_tok_s'])} → {_c(dec[128]['after_output_tok_s'])}"
    if lang == "en":
        head = ["What changed", "Before → after (tok/s)", "Change", "Evidence"]
        rows = [
            ["CK FP8 GEMM + unified verify<br>64K/1K decode, batch 16, one VM", ab_val, f"**{_pct(ab['throughput_delta_pct'])}**", "A/B, two switches, N=2"],
            ["Tuned fused-MoE table<br>8K prefill, concurrency 4, 1P1D", pre_val, f"**{_pct(pre[8192]['input_tok_s_delta_pct'])}**", "stage pair, N=1"],
            ["Tuned fused-MoE table<br>8K/1K decode, concurrency 128, 1P1D", dec_val, f"**{_pct(dec[128]['output_tok_s_delta_pct'])}**", "stage pair, N=1"],
        ]
    else:
        head = ["改了什么", "优化前 → 优化后（tok/s）", "变化", "证据"]
        rows = [
            ["CK FP8 GEMM + unified verify<br>64K/1K decode，batch 16，单机", ab_val, f"**{_pct(ab['throughput_delta_pct'])}**", "两开关 A/B，各 2 次"],
            ["调优 fused-MoE 表<br>8K prefill，并发 4，1P1D", pre_val, f"**{_pct(pre[8192]['input_tok_s_delta_pct'])}**", "阶段对比，各 1 次"],
            ["调优 fused-MoE 表<br>8K/1K decode，并发 128，1P1D", dec_val, f"**{_pct(dec[128]['output_tok_s_delta_pct'])}**", "阶段对比，各 1 次"],
        ]
    return _table(head, rows, ["l", "l", "r", "l"])


def _ab_names(lang: str) -> list[str]:
    return ["Baseline", "Optimized", "Change"] if lang == "en" else ["基线", "优化后", "变化"]


def ab_table(lang: str) -> str:
    ab = _json("evidence/measurements.json")["ab_ck_unified_verify_64k"]
    n = _ab_names(lang)
    head = ["Arm", "Run 1", "Run 2", "Mean"] if lang == "en" else ["组别", "第 1 次", "第 2 次", "均值"]
    rows = [
        [n[0], _n(ab["baseline_run_means_tok_s"][0]), _n(ab["baseline_run_means_tok_s"][1]), _n(ab["baseline_mean_tok_s"])],
        [n[1], _n(ab["optimized_run_means_tok_s"][0]), _n(ab["optimized_run_means_tok_s"][1]), _n(ab["optimized_mean_tok_s"])],
        [n[2], "", "", f"**{_pct(ab['throughput_delta_pct'])}**"],
    ]
    return _table(head, rows, ["l", "r", "r", "r"])


def ab_tpot(lang: str) -> str:
    ab = _json("evidence/measurements.json")["ab_ck_unified_verify_64k"]
    n = _ab_names(lang)
    head = ["Arm", "Implied TPOT (ms)"] if lang == "en" else ["组别", "折算 TPOT（ms）"]
    rows = [[n[0], _n(ab["baseline_implied_tpot_ms"])], [n[1], _n(ab["optimized_implied_tpot_ms"])],
            [n[2], f"**{_pct(ab['implied_tpot_delta_pct'])}**"]]
    return _table(head, rows, ["l", "r"])


def stage_prefill(lang: str) -> str:
    st = _json("evidence/measurements.json")["tuned_moe_stage"]
    head = (["Input tokens", "Before", "After", "Change"] if lang == "en" else ["输入 token", "优化前", "优化后", "变化"])
    rows = [[_i(r["input_tokens"]), _c(r["before_input_tok_s"]), _c(r["after_input_tok_s"]),
             f"**{_pct(r['input_tok_s_delta_pct'])}**"] for r in st["prefill"]]
    return _table(head, rows, ["r", "r", "r", "r"])


def stage_prefill_ttft(lang: str) -> str:
    st = _json("evidence/measurements.json")["tuned_moe_stage"]
    head = (["Input tokens", "Before", "After", "Change"] if lang == "en" else ["输入 token", "优化前", "优化后", "变化"])
    rows = [[_i(r["input_tokens"]), _n(r["before_mean_ttft_ms"] / 1000.0), _n(r["after_mean_ttft_ms"] / 1000.0),
             _pct(r["mean_ttft_delta_pct"])] for r in st["prefill"]]
    return _table(head, rows, ["r", "r", "r", "r"])


def stage_decode(lang: str) -> str:
    st = _json("evidence/measurements.json")["tuned_moe_stage"]
    head = (["Concurrency", "Before", "After", "Change"] if lang == "en" else ["并发", "优化前", "优化后", "变化"])
    rows = [[str(r["concurrency"]), _c(r["before_output_tok_s"]), _c(r["after_output_tok_s"]),
             f"**{_pct(r['output_tok_s_delta_pct'])}**"] for r in st["decode"]]
    return _table(head, rows, ["r", "r", "r", "r"])


def stage_decode_tpot(lang: str) -> str:
    st = _json("evidence/measurements.json")["tuned_moe_stage"]
    head = (["Concurrency", "Before", "After", "Change"] if lang == "en" else ["并发", "优化前", "优化后", "变化"])
    rows = [[str(r["concurrency"]), _n(r["before_mean_tpot_ms"]), _n(r["after_mean_tpot_ms"]),
             _pct(r["mean_tpot_delta_pct"])] for r in st["decode"]]
    return _table(head, rows, ["r", "r", "r", "r"])


def ladder(lang: str) -> str:
    rows_in = _json("evidence/measurements.json")["concurrency_ladder_8k1k"]
    head = (["Configured", "Observed", "Output tok/s", "TPOT (ms)"] if lang == "en" else ["配置并发", "实测并发", "Output tok/s", "TPOT（ms）"])
    rows = [[str(r["concurrency"]), _n(r["observed_concurrency"]), _n(r["output_tok_s"]), _n(r["mean_tpot_ms"])] for r in rows_in]
    return _table(head, rows, ["r", "r", "r", "r"])


def ladder_ttft(lang: str) -> str:
    rows_in = _json("evidence/measurements.json")["concurrency_ladder_8k1k"]
    head = (["Configured", "Mean TTFT (s)", "P99 TTFT (s)"] if lang == "en" else ["配置并发", "平均 TTFT（s）", "P99 TTFT（s）"])
    rows = [[str(r["concurrency"]), _n(r["mean_ttft_ms"] / 1000.0, 1), _n(r["p99_ttft_ms"] / 1000.0, 1)] for r in rows_in]
    return _table(head, rows, ["r", "r", "r"])


def snapshot(lang: str) -> str:
    snap = _json("evidence/measurements.json")["stack_snapshot"]
    head = (["Concurrency", "2026-05-09 (16K in)", "2026-07-13 (8K in)"] if lang == "en" else ["并发", "2026-05-09（16K 输入）", "2026-07-13（8K 输入）"])
    rows = [[str(r["concurrency"]), _i(r["early_output_tok_s"]), _n(r["late_output_tok_s"])] for r in snap["decode"]]
    return _table(head, rows, ["r", "r", "r"])


def snapshot_tpot(lang: str) -> str:
    snap = _json("evidence/measurements.json")["stack_snapshot"]
    head = (["Concurrency", "2026-05-09", "2026-07-13"] if lang == "en" else ["并发", "2026-05-09", "2026-07-13"])
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
    """One heading per layer, one entry per technique; lists instead of tables so long switch names wrap on phones."""
    cat = _json("profiles/techniques.json")
    lock = _lock()
    lab = ({"mi": "MI300X", "nv": "NVIDIA", "code": "Code", "ev": "Evidence", "none": "no code change (configuration only)"}
           if lang == "en" else {"mi": "MI300X", "nv": "NVIDIA", "code": "代码", "ev": "证据", "none": "无代码改动（仅配置）"})
    out = []
    for layer in ("framework", "operator", "workload"):
        out.append(f"**{cat['layers'][layer][lang]}**\n")
        for t in cat["techniques"]:
            if t["layer"] != layer:
                continue
            codes = ", ".join(f"[{lock[p]['commit'][:7]}]({lock[p]['url']})" for p in t["patches"]) or lab["none"]
            label = t["evidence_note"][lang] if "evidence_note" in t else EVIDENCE_LABEL[lang][t["evidence"]]
            rocm = t["rocm"] if lang == "en" else t["rocm_cn"]
            cuda = t["cuda"] if lang == "en" else t["cuda_cn"]
            sep = ": " if lang == "en" else "："
            out.append(f"- **{t[lang]}**  \n  {lab['mi']}{sep}{rocm}  \n  {lab['nv']}{sep}{cuda}  \n  {lab['code']}{sep}{codes}  \n  {lab['ev']}{sep}{label}")
        out.append("")
    return "\n".join(out)


STACK_LABEL = {
    "en": {"measured_run": "in the measured runs", "pinned_runtime_not_throughput_tested": "pinned runtime, not throughput-tested here",
           "later_branch": "later branch, not in any runtime here", "upstreamed_later": "upstream follow-up, not in the pinned runtime"},
    "cn": {"measured_run": "在实测 runtime 中", "pinned_runtime_not_throughput_tested": "在固定 runtime 中，本仓库未测吞吐",
           "later_branch": "后续分支，不在任何 runtime 中", "upstreamed_later": "上游后续提交，不在固定 runtime 中"},
}


def upstream_table(lang: str) -> str:
    lock = _json("upstream/SOURCES.lock.json")
    cat = _json("profiles/techniques.json")["layers"]
    lines = [f"- [`{e['repository']}@{e['commit'][:7]}`]({e['url']}) — {e['subject']}  \n  {cat[e['layer']][lang]} · {STACK_LABEL[lang][e['stack_status']]}"
             for e in lock["patches"]]
    return "\n".join(lines) + "\n"


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

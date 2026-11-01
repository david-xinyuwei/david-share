"""Summarize the second training round against the published FT-cf: arm A (more data: train_cf2, 2 epochs) and arm B
(same data, 4 epochs). For every evaluation set: accuracy, ECE, paired accuracy delta vs FT-cf with a cluster-bootstrap
95% interval (same method as summarize_results.paired), rule-following accuracy by changed field on the counterfactual
sets, public transfer-v4 retention, training wall time and GPU peak. Standard library only.

Usage: python summarize_round2.py --round2 <runs dir with 0.8b/r2-A-*> --baseline <2026-10-27 runs dir with 0.8b/ftcf-*>
                                  --data data/contoso/final --out <dir> [--size 0.8b]
Writes round2_summary.json and round2_summary.md.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from summarize_results import SETS, accuracy_on, clean, load, paired, pct, pp, read_jsonl, status_fields  # noqa: E402

ARMS = {"ftcf": ("FT-cf（已发布）", None), "r2-A": ("A：加数据（train_cf2，2 epoch）", "A"), "r2-B": ("B：同数据 4 epoch", "B"),
        "r2-C": ("C：加数据 + 4 epoch", "C")}
R2 = ("r2-A", "r2-B", "r2-C")


def rows_for(root, size, prefix, s):
    return load(Path(root) / size / f"{prefix}-{s}" / "rows.json"), load(Path(root) / size / f"{prefix}-{s}" / "report.json")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--round2", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", default="0.8b")
    a = ap.parse_args()
    data, out, size = Path(a.data), Path(a.out), a.size
    out.mkdir(parents=True, exist_ok=True)
    summary = {"size": size, "sets": {}, "public": {}, "training": {}}
    for s in SETS:
        f = data / f"{s}.jsonl"
        if not f.is_file():
            continue
        records = read_jsonl(f)
        groups = {i: r["_meta"]["group"] for i, r in enumerate(records)}
        rows, reps = {}, {}
        rows["ftcf"], reps["ftcf"] = rows_for(a.baseline, size, "ftcf", s)
        for arm in R2:
            rows[arm], reps[arm] = rows_for(a.round2, size, arm, s)
        if not any(rows[k] for k in R2):
            continue
        e = {"records": len(records), "questions": {k: clean(v) for k, v in reps.items() if v}}
        e["paired_vs_ftcf"] = {arm: paired(rows[arm], rows["ftcf"], groups) for arm in R2 if rows[arm] and rows["ftcf"]}
        if "_cf_" in s:
            base = {r["_meta"]["case"]: r for r in read_jsonl(data / f"{s.replace('_cf', '')}.jsonl")}
            changed = {(i, q) for i, r in enumerate(records) if r["_meta"]["group"] in base
                       for q, v in r["questions"].items() if v["label"] != base[r["_meta"]["group"]]["questions"][q]["label"]}
            fields = {i: r["_meta"].get("pair_field") for i, r in enumerate(records)}
            e["changed_questions"] = len(changed)
            e["changed_acc"] = {k: accuracy_on(rows[k], lambda i, q, ch=changed: (i, q) in ch) for k in rows if rows[k]}
            e["changed_by_field"] = {k: {fl: accuracy_on(rows[k], lambda i, q, ch=changed, fl=fl: (i, q) in ch and fields[i] == fl)
                                         for fl in sorted(set(fields.values()))} for k in rows if rows[k]}
            keep = lambda i, q, ch=changed: (i, q) in ch
            e["changed_paired_vs_ftcf"] = {arm: paired(rows[arm], rows["ftcf"], groups, keep) for arm in R2 if rows[arm] and rows["ftcf"]}
        summary["sets"][s] = e
    pub_base = load(Path(a.baseline) / size / "ftcf-public-transfer-v4-dev" / "report.json")
    for arm in R2:
        pub = load(Path(a.round2) / size / f"{arm}-public-transfer-v4-dev" / "report.json")
        if pub and pub_base:
            c, b = pub["clean"], pub_base["clean"]
            summary["public"][arm] = {"ftcf_acc": b["acc"], "acc": c["acc"], "n": c["n"], "acc_drop_pp_vs_ftcf": 100 * (b["acc"] - c["acc"]), "brier": c["brier"], "ftcf_brier": b["brier"]}
    for arm, letter in (("r2-A", "A"), ("r2-B", "B"), ("r2-C", "C")):
        candidates = (Path(a.round2) / size / f"round2-{size}-{letter}.status", Path(a.round2).parent / "pack-meta" / f"round2-{size}-{letter}.status")
        st = next((p for p in candidates if p.is_file()), candidates[0])
        summary["training"][arm] = status_fields(st, "TRAIN") if st.is_file() else {}
        m = load(Path(a.round2) / size / arm / "training_metrics.json")
        if m:
            summary["training"][arm]["training_metrics"] = m
    (out / "round2_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    L = [f"# 第二轮训练汇总（{size}，自动生成）", "", "## 1. 准确率 / ECE，以及与已发布 FT-cf 的配对差值（百分点，95% 区间）", "",
         "| 数据集 | 题数 | FT-cf 准确率 | A 准确率 | B 准确率 | C 准确率 | A − FT-cf | B − FT-cf | C − FT-cf | FT-cf ECE | A ECE | B ECE | C ECE |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s, e in summary["sets"].items():
        q = e["questions"]
        n = next((v["n"] for v in q.values() if v), "—")
        P = e.get("paired_vs_ftcf", {})
        ci = lambda d: "—" if not d else f"{pp(d['acc_delta'])}（{pp(d['acc_ci95'][0])} ~ {pp(d['acc_ci95'][1])}）"
        g = lambda k, m: (f"{q[k][m]:.3f}" if m == "ece" else pct(q[k][m])) if q.get(k) else "—"
        L.append(f"| {s} | {n} | {g('ftcf','acc')} | {g('r2-A','acc')} | {g('r2-B','acc')} | {g('r2-C','acc')} | {ci(P.get('r2-A'))} | {ci(P.get('r2-B'))} | {ci(P.get('r2-C'))} | {g('ftcf','ece')} | {g('r2-A','ece')} | {g('r2-B','ece')} | {g('r2-C','ece')} |")
    L += ["", "## 2. 只改一个字段、答案必须跟着变：按字段的准确率（test_cf + ood_cf 合计看各自表）", ""]
    for s, e in summary["sets"].items():
        if "changed_by_field" not in e:
            continue
        fields = sorted({f for d in e["changed_by_field"].values() for f in d})
        L += [f"**{s}**（改变答案的题 {e['changed_questions']} 道）", "", "| 模型 | 全部改变题 | " + " | ".join(str(f) for f in fields) + " |", "|---|---|" + "---|" * len(fields)]
        acc_of = lambda d: d["acc"] if d else None
        for k, name in (("ftcf", "FT-cf"), ("r2-A", "A"), ("r2-B", "B"), ("r2-C", "C")):
            if k in e["changed_acc"]:
                L.append(f"| {name} | {pct(acc_of(e['changed_acc'][k]))} | " + " | ".join(pct(acc_of(e["changed_by_field"][k].get(f))) for f in fields) + " |")
        L.append("")
    L += ["## 3. 公开题（transfer-v4 开发集）：原有本事有没有丢", "", "| 模型 | 题数 | FT-cf 准确率 | 本模型准确率 | 变化（百分点） |", "|---|---|---|---|---|"]
    for arm, v in summary["public"].items():
        L.append(f"| {ARMS[arm][0]} | {v['n']} | {pct(v['ftcf_acc'])} | {pct(v['acc'])} | {-v['acc_drop_pp_vs_ftcf']:+.1f} |")
    L += ["", "## 4. 训练成本", "", "| 模型 | 训练时间 | GPU 显存峰值 | 校准 |", "|---|---|---|---|"]
    for arm, t in summary["training"].items():
        w = t.get("wall_s")
        L.append(f"| {ARMS[arm][0]} | {(int(w) // 60) if w else '—'} 分 {(int(w) % 60) if w else '—'} 秒 | {t.get('peak_gpu_mib', '—')} MiB | {t.get('calibrated', '—')} |")
    (out / "round2_summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(json.dumps({"sets": list(summary["sets"]), "public": summary["public"], "training": {k: {kk: vv for kk, vv in v.items() if kk != 'training_metrics'} for k, v in summary["training"].items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()

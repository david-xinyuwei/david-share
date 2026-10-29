"""Summarize the pulled VM results per size and set: B0, B0-policy, FT (first recipe) and FT-cf (first recipe plus
counterfactual variants), paired differences, rule-following on the variant sets, public transfer-v4, training cost.

Usage: python summarize_results.py --runs <dir containing 0.8b/ and 4b/> --data data/contoso/final --out <dir>
Paired 95% intervals: cluster bootstrap over case groups (a message and all its field variants stay together),
10,000 resamples, seed 1. kev.compare's own interval (clustered per record) is kept in summary.json.
Standard library only. Writes summary.json and summary.md.
"""
import argparse
import json
import random
import re
import sys
from pathlib import Path

MODELS = {"b0": "B0", "b0policy": "B0-policy", "ft": "FT", "ftcf": "FT-cf"}
SETS = ["test_support", "test_assistant", "ood_support", "ood_assistant", "dev_support", "dev_assistant",
        "test_cf_support", "test_cf_assistant", "ood_cf_support", "ood_cf_assistant", "dev_cf_support", "dev_cf_assistant"]
PAIRS = [("ft", "b0"), ("ft", "b0policy"), ("ftcf", "b0"), ("ftcf", "ft")]
# released checkpoints on transfer-v4 dev, reproduced on the same VM before any fine-tuning
PUBLIC_BASELINE = Path(__file__).resolve().parents[1] / "验证结果" / "公开基线复现_20261027-123403" / "runs"


def load(path):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def read_jsonl(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def per_question(rows):
    """record index -> {question: (correct, brier)}."""
    out = {}
    for r in rows:
        i = int(str(r["id"]).rsplit("/", 1)[-1])
        p = [float(x) for x in r["p"]]
        label = int(r["label"])
        pred = max(range(len(p)), key=lambda j: p[j])
        brier = sum((x - (1.0 if j == label else 0.0)) ** 2 for j, x in enumerate(p))
        out.setdefault(i, {})[r["question"]] = (pred == label, brier)
    return out


def paired(cand_rows, ref_rows, groups, keep=None, n_boot=10000, seed=1):
    """Accuracy and Brier difference cand - ref over the same questions; keep(i, q) can restrict the questions."""
    c, r = per_question(cand_rows), per_question(ref_rows)
    by_group = {}
    for i, qs in c.items():
        if i not in r:
            continue
        g = by_group.setdefault(groups[i], [0, 0.0, 0.0])
        for q, (ok, br) in qs.items():
            if q not in r[i] or (keep and not keep(i, q)):
                continue
            ok_ref, br_ref = r[i][q]
            g[0] += 1
            g[1] += ok - ok_ref
            g[2] += br - br_ref
    keys = [k for k, v in by_group.items() if v[0]]
    n = sum(by_group[k][0] for k in keys)
    if not n:
        return None
    rng = random.Random(seed)
    accs, briers = [], []
    for _ in range(n_boot):
        sample = [keys[rng.randrange(len(keys))] for _ in keys]
        nq = sum(by_group[k][0] for k in sample)
        accs.append(sum(by_group[k][1] for k in sample) / nq)
        briers.append(sum(by_group[k][2] for k in sample) / nq)
    accs.sort()
    briers.sort()
    lo, hi = int(0.025 * n_boot), int(0.975 * n_boot) - 1
    return {"questions": n, "groups": len(keys), "acc_delta": sum(by_group[k][1] for k in keys) / n,
            "acc_ci95": [accs[lo], accs[hi]], "brier_delta": sum(by_group[k][2] for k in keys) / n,
            "brier_ci95": [briers[lo], briers[hi]]}


def accuracy_on(rows, keep):
    pq = per_question(rows)
    hits = [ok for i, qs in pq.items() for q, (ok, _) in qs.items() if keep(i, q)]
    return {"n": len(hits), "acc": sum(hits) / len(hits)} if hits else None


def per_question_table(rows, records):
    """question -> accuracy, balanced accuracy (mean recall over the labels present) and the majority-label rate."""
    out = {}
    for q in records[0]["questions"]:
        counts = {}
        for r in records:
            x = json.dumps(r["questions"][q]["label"])
            counts[x] = counts.get(x, 0) + 1
        out[q] = {"n": len(records), "majority_rate": max(counts.values()) / len(records)}
    if not rows:
        return out
    hits, per_label = {}, {}
    for r in rows:
        q = r["question"]
        p = [float(x) for x in r["p"]]
        label = int(r["label"])
        ok = max(range(len(p)), key=lambda j: p[j]) == label
        h = hits.setdefault(q, [0, 0])
        h[0] += ok
        h[1] += 1
        pl = per_label.setdefault(q, {}).setdefault(label, [0, 0])
        pl[0] += ok
        pl[1] += 1
    for q, (k, n) in hits.items():
        out.setdefault(q, {})["acc"] = k / n
        out[q]["balanced_acc"] = sum(a / b for a, b in per_label[q].values()) / len(per_label[q])
    return out


def flip_pairs(rows, records):
    """Field-flip pairs inside a set (same text, one field changed, label changed): share of the changed questions
    answered correctly on both records. A model that ignores the changed field cannot get both right."""
    if not rows:
        return None
    pq = per_question(rows)
    by_group = {}
    for i, r in enumerate(records):
        by_group.setdefault(r["_meta"]["group"], []).append(i)
    items = both = 0
    for idx in by_group.values():
        if len(idx) != 2:
            continue
        a, b = idx
        for q in records[a]["questions"]:
            if records[a]["questions"][q]["label"] == records[b]["questions"][q]["label"]:
                continue
            if a in pq and b in pq and q in pq[a] and q in pq[b]:
                items += 1
                both += pq[a][q][0] and pq[b][q][0]
    return {"changed_questions": items, "both_correct": both, "rate": both / items if items else None}


def clean(report):
    if not report:
        return None
    c = report["clean"]
    return {k: c.get(k) for k in ("n", "acc", "brier", "ece", "nll", "coverage_at_5pct_error", "mean_conf")}


def pct(x, digits=1):
    return "—" if x is None else f"{100 * x:.{digits}f}%"


def pp(x):
    return "—" if x is None else f"{100 * x:+.1f}"


def ci(d):
    return "—" if not d else f"{pp(d['acc_delta'])}（{pp(d['acc_ci95'][0])} ~ {pp(d['acc_ci95'][1])}）"


def status_fields(path, prefix):
    out = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith(prefix + "_DONE") or line.startswith(prefix + "_CF_DONE"):
                out.update(dict(kv.split("=", 1) for kv in line.split()[1:] if "=" in kv))
            if line.startswith("CALIBRATED"):
                t, e = re.search(r"T=([\d.]+)", line), re.search(r"ece ([\d.]+) -> ([\d.]+)", line)
                out["temperature"] = float(t.group(1)) if t else None
                out["calibrated"] = (f"T={t.group(1)}" if t else "") + (f"（校准集 ECE {e.group(1)} → {e.group(2)}）" if e else "")
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # the tables contain "−" and "→"; a piped Windows console defaults to GBK
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    runs, data, out = Path(a.runs), Path(a.data), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    def text_of(r):
        st = r["state"] if isinstance(r["state"], dict) else json.loads(r["state"])
        return st.get("message") or st.get("utterance")

    # short assistant commands repeat: a test record whose exact text is also a first-recipe training text is re-scored
    train_texts = {text_of(r) for r in read_jsonl(data / "train.jsonl")}

    summary = {"sets": {}, "public": {}, "training": {}}
    for size in ("0.8b", "4b"):
        R = runs / size
        if not R.is_dir():
            continue
        for s in SETS:
            f = data / f"{s}.jsonl"
            if not f.is_file():
                continue
            records = read_jsonl(f)
            groups = {i: r["_meta"]["group"] for i, r in enumerate(records)}
            pol = data / f"policy_{s}.jsonl"
            if pol.is_file():  # B0-policy rows must describe the same records in the same order
                pcases = [r["_meta"]["case"] for r in read_jsonl(pol)]
                assert pcases == [r["_meta"]["case"] for r in records], f"policy file order differs for {s}"
            rows = {m: load(R / f"{m}-{s}" / "rows.json") for m in MODELS}
            if not any(rows.values()):
                continue
            e = {"records": len(records), "groups": len(set(groups.values()))}
            for m in MODELS:
                e[m] = clean(load(R / f"{m}-{s}" / "report.json"))
            e["per_question"] = {m: per_question_table(rows[m], records) for m in MODELS}
            e["paired"] = {f"{c}_vs_{r}": paired(rows[c], rows[r], groups) for c, r in PAIRS if rows[c] and rows[r]}
            if "_cf_" in s:
                # rule-following: only the questions whose label differs from the original message's label
                base = {r["_meta"]["case"]: r for r in read_jsonl(data / f"{s.replace('_cf', '')}.jsonl")}
                changed = {(i, q) for i, r in enumerate(records) if r["_meta"]["group"] in base
                           for q, v in r["questions"].items()
                           if v["label"] != base[r["_meta"]["group"]]["questions"][q]["label"]}
                keep = lambda i, q, ch=changed: (i, q) in ch
                e["changed_questions"] = len(changed)
                e["changed_acc"] = {m: accuracy_on(rows[m], keep) for m in MODELS if rows[m]}
                fields = {i: r["_meta"].get("pair_field") for i, r in enumerate(records)}
                e["changed_by_field"] = {m: {f: accuracy_on(rows[m], lambda i, q, ch=changed, f=f: (i, q) in ch and fields[i] == f)
                                             for f in sorted(set(fields.values()))} for m in MODELS if rows[m]}
                e["changed_paired"] = {f"{c}_vs_{r}": paired(rows[c], rows[r], groups, keep) for c, r in PAIRS if rows[c] and rows[r]}
            else:
                e["flip_pairs"] = {m: flip_pairs(rows[m], records) for m in MODELS}
                seen = {i for i, r in enumerate(records) if text_of(r) in train_texts}
                e["records_with_training_text"] = len(seen)
                if seen and rows["ft"] and rows["b0"]:
                    e["ft_vs_b0_unseen_text"] = paired(rows["ft"], rows["b0"], groups, lambda i, q, sn=seen: i not in sn)
            # kev.compare (the comparison named in the frozen protocol): macro average over question types
            for key_, fname in (("ft_vs_b0", f"cmp-{s}"), ("ftcf_vs_b0", f"cmpcf-b0-{s}"), ("ftcf_vs_ft", f"cmpcf-ft-{s}")):
                cmp_ = load(R / fname)
                if cmp_:
                    pa = cmp_["paired"]["acc"]
                    e.setdefault("kev_compare", {})[key_] = {"acc_delta": pa.get("macro_acc_delta"), "acc_ci95": pa.get("ci95"),
                                                             "groups": pa.get("groups")}
            summary["sets"][f"{size}/{s}"] = e
        base = load(PUBLIC_BASELINE / f"public-kev-{size}-transfer-v4-dev" / "report.json")["clean"]
        for m, run in (("ft", "ft-public-transfer-v4-dev"), ("ftcf", "ftcf-public-transfer-v4-dev")):
            pub = load(R / run / "report.json")
            if pub:
                c = pub["clean"]
                assert c["n"] == base["n"], f"{size}/{m}: transfer-v4 question count differs from the baseline"
                summary["public"][f"{size}/{m}"] = {"b0_acc": base["acc"], "acc": c["acc"], "b0_brier": base["brier"],
                                                    "brier": c["brier"], "n": c["n"], "acc_drop_pp": 100 * (base["acc"] - c["acc"])}
        summary["training"][f"{size}/ft"] = status_fields(R / f"pipeline-{size}.status", "TRAIN")
        summary["training"][f"{size}/ftcf"] = status_fields(R / f"pipeline-cf-{size}.status", "TRAIN")
        for m in ("ft", "ft_cf"):
            metrics = load(R / m / "training_metrics.json")
            if metrics:
                summary["training"][f"{size}/{m.replace('_', '')}"]["training_metrics"] = metrics

    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    L = ["# 结果汇总（自动生成，数字来自 report.json / rows.json）", "",
         "## 1. 准确率（问题级）与配对差值", "",
         "| 尺寸 / 数据集 | 题数 | B0 | B0-policy | FT | FT-cf | FT−B0（百分点，95% 区间） | FT−B0-policy | FT-cf−B0 | FT-cf−FT |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for key, e in summary["sets"].items():
        n = next((e[m]["n"] for m in MODELS if e.get(m)), "—")
        P = e.get("paired", {})
        L.append(f"| {key} | {n} | " + " | ".join(pct((e.get(m) or {}).get("acc")) for m in MODELS) + " | "
                 + " | ".join(ci(P.get(k)) for k in ("ft_vs_b0", "ft_vs_b0policy", "ftcf_vs_b0", "ftcf_vs_ft")) + " |")
    L += ["", "上表的配对差值按题目计（每题权重相同），95% 区间按原话分组重抽样。实验协议指定的判定工具 `kev.compare` 按题型先求平均再平均（宏平均），结果如下：", "",
          "| 尺寸 / 数据集 | FT−B0（kev.compare，百分点，95% 区间） | FT-cf−B0 | FT-cf−FT |", "|---|---|---|---|"]
    for key, e in summary["sets"].items():
        kc = e.get("kev_compare") or {}
        if kc:
            L.append(f"| {key} | " + " | ".join(ci(kc.get(k)) for k in ("ft_vs_b0", "ftcf_vs_b0", "ftcf_vs_ft")) + " |")
    L += ["", "## 2. 规则跟随：变体集上\"答案因字段改变而改变\"的那些题", "",
          "变体集 = 开发/测试/分布外原话不变，只改一个策略字段（保修、购买天数、地区、电池循环；网络、企业管理、电量），标签由策略代码重算。只统计标签和原话那条不同的题。", "",
          "| 尺寸 / 变体集 | 题数 | B0 | B0-policy | FT | FT-cf | FT-cf−FT（百分点，95% 区间） |", "|---|---|---|---|---|---|---|"]
    for key, e in summary["sets"].items():
        if "changed_acc" in e:
            ca = e["changed_acc"]
            L.append(f"| {key} | {e['changed_questions']} | " + " | ".join(pct((ca.get(m) or {}).get("acc")) for m in MODELS)
                     + f" | {ci(e['changed_paired'].get('ftcf_vs_ft'))} |")
    L += ["", "原测试集里的配对样本（同一原话、只改一个字段、答案改变）两条都答对的比例：", "",
          "| 尺寸 / 数据集 | 答案改变的题数 | B0 | B0-policy | FT | FT-cf |", "|---|---|---|---|---|---|"]
    for key, e in summary["sets"].items():
        fp = e.get("flip_pairs") or {}
        n = next((v["changed_questions"] for v in fp.values() if v), None)
        if n:
            L.append(f"| {key} | {n} | " + " | ".join(pct((fp.get(m) or {}).get("rate")) for m in MODELS) + " |")
    L += ["", "## 3. 校准与可自动处理比例（Brier 越低越好；ECE 越低越好；5% 错误预算下可自动处理的比例越高越好）", "",
          "| 尺寸 / 数据集 | Brier B0 / FT / FT-cf | ECE B0 / FT / FT-cf | 5% 错误预算可自动处理 B0 / FT / FT-cf |", "|---|---|---|---|"]
    num = lambda x, k: "—" if not x or x.get(k) is None else f"{x[k]:.3f}"
    for key, e in summary["sets"].items():
        if "_cf_" in key:
            continue
        L.append(f"| {key} | " + " / ".join(num(e.get(m), "brier") for m in ("b0", "ft", "ftcf")) + " | "
                 + " / ".join(num(e.get(m), "ece") for m in ("b0", "ft", "ftcf")) + " | "
                 + " / ".join(pct((e.get(m) or {}).get("coverage_at_5pct_error")) for m in ("b0", "ft", "ftcf")) + " |")
    L += ["", "原话与训练集某条原话完全相同的测试记录（短指令会重复）去掉后再算一次 FT−B0：", "",
          "| 尺寸 / 数据集 | 去掉的记录 | 剩余题数 | FT−B0（百分点，95% 区间） |", "|---|---|---|---|"]
    for key, e in summary["sets"].items():
        d = e.get("ft_vs_b0_unseen_text")
        if e.get("records_with_training_text"):
            L.append(f"| {key} | {e['records_with_training_text']} | {d['questions'] if d else '—'} | {ci(d)} |")
    L += ["", "## 4. 每个问题：准确率与平衡准确率（各标签召回率的平均，不受多数标签影响）", "",
          "| 尺寸 / 数据集 / 问题 | 题数 | 多数标签占比 | 准确率 B0 / B0-policy / FT / FT-cf | 平衡准确率 B0 / B0-policy / FT / FT-cf |",
          "|---|---|---|---|---|"]
    for key, e in summary["sets"].items():
        if key.split("/")[1].startswith("dev"):
            continue
        pq = e.get("per_question") or {}
        for q, base in (pq.get("b0") or {}).items():
            vals = [pq.get(m, {}).get(q, {}) for m in MODELS]
            L.append(f"| {key} / {q} | {base['n']} | {pct(base['majority_rate'])} | "
                     + " / ".join(pct(v.get("acc")) for v in vals) + " | " + " / ".join(pct(v.get("balanced_acc")) for v in vals) + " |")
    L += ["", "## 5. 通用能力回归：Kev 公开 transfer-v4 开发集", "",
          "| 尺寸 / 模型 | 题数 | 发布版准确率 | 微调后准确率 | 下降（百分点） | Brier 发布版 → 微调后 |", "|---|---|---|---|---|---|"]
    for key, p in summary["public"].items():
        L.append(f"| {key} | {p['n']} | {pct(p['b0_acc'])} | {pct(p['acc'])} | {p['acc_drop_pp']:.1f} | {p['b0_brier']:.3f} → {p['brier']:.3f} |")
    L += ["", "## 6. 训练资源（1× H100 NVL）", "",
          "| 尺寸 / 模型 | 墙钟时间（含加载） | 显存峰值：nvidia-smi / PyTorch 分配 | micro-batch × accum | 训练记录（含重复的 epoch） | 优化步数 | 被截断的记录 | 温度校准 |",
          "|---|---|---|---|---|---|---|---|"]
    for key, t in summary["training"].items():
        if not t.get("wall_s"):
            continue
        m = t.get("training_metrics") or {}
        dev = m.get("peak_device_bytes")
        L.append(f"| {key} | {int(t['wall_s']) / 60:.1f} 分钟 | {t.get('peak_gpu_mib', '—')} MiB / "
                 + ("—" if dev is None else f"{dev / 2**20:.0f} MiB") + f" | {t.get('batch', '1')} × {t.get('accum', '8')} | "
                 + f"{m.get('records_seen', '—')} | {m.get('optimizer_steps', '—')} | {m.get('truncated_records', '—')} | "
                 + (t.get("calibrated") or "—") + " |")
    (out / "summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    (out / "report_blocks.json").write_text(json.dumps(report_blocks(summary), ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(L))


SET_NAME = {"test_support": "工单·同分布", "test_assistant": "助手·同分布", "ood_support": "工单·分布外", "ood_assistant": "助手·分布外",
            "test_cf_support": "工单·测试变体", "test_cf_assistant": "助手·测试变体", "ood_cf_support": "工单·分布外变体",
            "ood_cf_assistant": "助手·分布外变体", "dev_cf_support": "工单·开发变体", "dev_cf_assistant": "助手·开发变体",
            "dev_support": "工单·开发集", "dev_assistant": "助手·开发集"}
Q_NAME = {"queue": "分派队列（8 选 1）", "onsite_eligible": "能否上门（是/否）", "urgency": "紧急度（4 级）",
          "tool": "调用工具（14 选 1）", "run_on_device": "只在本机处理（是/否）", "needs_confirmation": "执行前要确认（是/否）"}


def report_blocks(summary):
    """Tables for the report (文档/微调与端侧验证报告_*.md), keyed by the TABLE:<name> markers there."""
    S = summary["sets"]
    rows = lambda names: [(k, e) for k, e in S.items() if k.split("/")[1] in names]
    split = lambda k: (k.split("/")[0].upper(), SET_NAME[k.split("/")[1]])
    main_sets = ("test_support", "test_assistant", "ood_support", "ood_assistant")
    cf_sets = ("test_cf_support", "test_cf_assistant", "ood_cf_support", "ood_cf_assistant", "dev_cf_support", "dev_cf_assistant")
    b = {}

    t = ["| 尺寸 | 测试集 | 题数 | B0 | B0-policy | FT | FT-cf | FT−B0（百分点，95% 区间） | FT−B0-policy | FT-cf−FT |", "|---|---|---|---|---|---|---|---|---|---|"]
    for k, e in rows(main_sets):
        size, name = split(k)
        n = next((e[m]["n"] for m in MODELS if e.get(m)), None)
        P = e.get("paired", {})
        t.append(f"| {size} | {name} | {'—' if n is None else format(n, ',')} | " + " | ".join(pct((e.get(m) or {}).get("acc")) for m in MODELS) + " | "
                 + " | ".join(ci(P.get(x)) for x in ("ft_vs_b0", "ft_vs_b0policy", "ftcf_vs_ft")) + " |")
    t += ["", "配对差值按题计；95% 区间把同一句原话的所有记录放在一起重抽样 10,000 次。实验协议指定的 `kev.compare` 先按题型求准确率再平均（宏平均），结论相同：", "",
          "| 尺寸 | 测试集 | FT−B0（kev.compare） | FT-cf−B0（kev.compare） | FT-cf−FT（kev.compare） |", "|---|---|---|---|---|"]
    for k, e in rows(main_sets):
        kc = e.get("kev_compare") or {}
        if kc:
            size, name = split(k)
            t.append(f"| {size} | {name} | " + " | ".join(ci(kc.get(x)) for x in ("ft_vs_b0", "ftcf_vs_b0", "ftcf_vs_ft")) + " |")
    b["ACC"] = "\n".join(t)

    def count(set_name, kind):
        for set_key, entry in S.items():
            if set_key.endswith("/" + set_name):
                total = entry.get("changed_questions") if kind == "changed" else next(
                    (entry[model]["n"] for model in MODELS if entry.get(model)), None)
                if total:
                    return total
        return None

    readme_methods = {
        "B0": "微调前：发布版",
        "B0-policy": "微调前：仅在提示词中加入业务规则",
        "FT": "微调后：业务数据微调",
        "FT-cf": "微调后：业务数据＋字段变体增强",
    }
    t = []
    for heading, columns, kind in (
        ("同分布测试：原话生成方式与训练集相同", ("test_support", "test_assistant"), "acc"),
        ("分布外测试：更换生成模型与字段分布", ("ood_support", "ood_assistant"), "acc"),
        ("字段变体测试：仅统计答案因字段改变的题", ("test_cf_support", "test_cf_assistant"), "changed"),
    ):
        headers = [f"{SET_NAME[set_name]}准确率（{count(set_name, kind):,} 题）"
                   if count(set_name, kind) else f"{SET_NAME[set_name]}准确率（题数未知）"
                   for set_name in columns]
        t += [f"**{heading}**", "", "| 参数规模 | 阶段与做法 | " + " | ".join(headers) + " |", "|---|---|---|---|"]
        for size in ("0.8b", "4b"):
            if not any(set_key.startswith(size + "/") for set_key in S):
                continue
            for model, label in MODELS.items():
                values = []
                for set_name in columns:
                    entry = S.get(f"{size}/{set_name}", {})
                    result = ((entry.get("changed_acc") or {}).get(model) or {}) if kind == "changed" else (entry.get(model) or {})
                    values.append(pct(result.get("acc")))
                t.append(f"| {size.upper()} | {readme_methods[label]} | " + " | ".join("未跑" if value == "—" else value for value in values) + " |")
        t.append("")
    b["README_ACC"] = "\n".join(t).rstrip()

    t = ["| 尺寸 | 测试集 | 问题 | 多数标签占比 | 准确率 B0 / B0-policy / FT / FT-cf | 平衡准确率 B0 / B0-policy / FT / FT-cf |", "|---|---|---|---|---|---|"]
    for k, e in rows(main_sets):
        size, name = split(k)
        pq = e.get("per_question") or {}
        for q, base in (pq.get("b0") or {}).items():
            vals = [pq.get(m, {}).get(q, {}) for m in MODELS]
            t.append(f"| {size} | {name} | {Q_NAME.get(q, q)} | {pct(base['majority_rate'])} | " + " / ".join(pct(v.get("acc")) for v in vals)
                     + " | " + " / ".join(pct(v.get("balanced_acc")) for v in vals) + " |")
    b["PERQ"] = "\n".join(t)

    t = ["只统计\"答案和原话那条不同\"的题（看懂了被改的字段才能答对）：", "",
         "| 尺寸 | 变体集 | 题数 | B0 | B0-policy | FT | FT-cf | FT-cf−FT（百分点，95% 区间） |", "|---|---|---|---|---|---|---|---|"]
    for k, e in rows(cf_sets):
        if "changed_acc" in e:
            size, name = split(k)
            ca = e["changed_acc"]
            t.append(f"| {size} | {name} | {e['changed_questions']:,} | " + " | ".join(pct((ca.get(m) or {}).get("acc")) for m in MODELS)
                     + f" | {ci(e['changed_paired'].get('ftcf_vs_ft'))} |")
    field_name = {"warranty_plan": "保修类型", "days_since_purchase": "购买天数", "region": "地区", "battery_cycles": "电池循环次数",
                  "network": "网络", "enterprise_managed": "是否企业管理", "battery": "电源与电量"}
    t += ["", "按被改的字段拆开（测试变体与分布外变体合计，只统计答案改变的题）：", "",
          "| 尺寸 | 被改字段 | 题数 | B0 | B0-policy | FT | FT-cf |", "|---|---|---|---|---|---|---|"]
    for size in ("0.8b", "4b"):
        agg = {}
        for s in ("test_cf_support", "ood_cf_support", "test_cf_assistant", "ood_cf_assistant"):
            for m, by in (S.get(f"{size}/{s}", {}).get("changed_by_field") or {}).items():
                for fld, v in by.items():
                    if v:
                        a_ = agg.setdefault(fld, {}).setdefault(m, [0.0, 0])
                        a_[0] += v["acc"] * v["n"]
                        a_[1] += v["n"]
        for fld, by_m in agg.items():
            n = max(v[1] for v in by_m.values())
            t.append(f"| {size.upper()} | {field_name.get(fld, fld)} | {n} | "
                     + " | ".join(pct(by_m[m][0] / by_m[m][1]) if m in by_m and by_m[m][1] else "—" for m in MODELS) + " |")
    t += ["", "原测试集里的配对样本（同一句原话、只改一个字段、答案随之改变）两条都答对的比例：", "",
          "| 尺寸 | 测试集 | 答案改变的题数 | B0 | B0-policy | FT | FT-cf |", "|---|---|---|---|---|---|---|"]
    for k, e in rows(main_sets):
        fp = e.get("flip_pairs") or {}
        n = next((v["changed_questions"] for v in fp.values() if v), None)
        if n:
            size, name = split(k)
            t.append(f"| {size} | {name} | {n} | " + " | ".join(pct((fp.get(m) or {}).get("rate")) for m in MODELS) + " |")
    b["CF"] = "\n".join(t)

    num = lambda x, key: "—" if not x or x.get(key) is None else f"{x[key]:.3f}"
    t = ["| 尺寸 | 测试集 | ECE B0 / B0-policy / FT / FT-cf | Brier B0 / B0-policy / FT / FT-cf | 5% 错误预算下可自动处理 B0 / B0-policy / FT / FT-cf |", "|---|---|---|---|---|"]
    for k, e in rows(main_sets):
        size, name = split(k)
        t.append(f"| {size} | {name} | " + " / ".join(num(e.get(m), "ece") for m in MODELS) + " | "
                 + " / ".join(num(e.get(m), "brier") for m in MODELS) + " | "
                 + " / ".join(pct((e.get(m) or {}).get("coverage_at_5pct_error")) for m in MODELS) + " |")
    b["CAL"] = "\n".join(t)

    t = ["| 模型与训练方案 | 通用题数 | 发布版准确率 | 微调后准确率 | 变化（百分点） |", "|---|---|---|---|---|"]
    for k, p in summary["public"].items():
        size, m = k.split("/")
        change = "0.0" if abs(p["acc_drop_pp"]) < 0.05 else f"{-p['acc_drop_pp']:+.1f}"  # avoid printing "-0.0"
        t.append(f"| {size.upper()} {MODELS[m]} | {p['n']} | {pct(p['b0_acc'])} | {pct(p['acc'])} | {change} |")
    t += ["", "**通用题的置信度：Brier 越低越好**", "",
          "| 模型与训练方案 | 发布版 Brier | 微调后 Brier |", "|---|---|---|"]
    for key, result in summary["public"].items():
        size, model = key.split("/")
        t.append(f"| {size.upper()} {MODELS[model]} | {result['b0_brier']:.3f} | {result['brier']:.3f} |")
    b["PUBLIC"] = "\n".join(t)

    t = ["**训练配方：每个配置运行一次，有效 batch 均为 8**", "",
         "| 模型与训练方案 | micro-batch × accum | 训练记录（2 个 epoch 合计） | 优化步数 |", "|---|---|---|---|"]
    for key, training in summary["training"].items():
        if not training.get("wall_s"):
            continue
        size, model = key.split("/")
        metrics = training.get("training_metrics") or {}
        steps = format(metrics["optimizer_steps"], ",") if "optimizer_steps" in metrics else "—"
        t.append(f"| {size.upper()} {MODELS[model]} | {training.get('batch', '1')} × {training.get('accum', '8')} | "
                 f"{metrics.get('records_seen', 0):,} | {steps} |")
    t += ["", "**训练消耗：1 张 H100 NVL，时间包含模型加载与保存**", "",
          "| 模型与训练方案 | 墙钟时间 | 整卡显存峰值（nvidia-smi） | PyTorch 分配峰值 | 校准温度 |", "|---|---|---|---|---|"]
    for k, tr in summary["training"].items():
        if not tr.get("wall_s"):
            continue
        size, m = k.split("/")
        mt = tr.get("training_metrics") or {}
        dev = mt.get("peak_device_bytes")
        t.append(f"| {size.upper()} {MODELS[m]} | {int(tr['wall_s']) / 60:.1f} 分钟 | {int(tr.get('peak_gpu_mib', 0)):,} MiB | "
                 + ("—" if dev is None else f"{dev / 2**20:,.0f} MiB")
                 + f" | {tr.get('temperature', '—')} |")
    b["TRAIN"] = "\n".join(t)
    return b


if __name__ == "__main__":
    main()

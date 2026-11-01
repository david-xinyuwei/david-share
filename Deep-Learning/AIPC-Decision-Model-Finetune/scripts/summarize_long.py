"""Long-input accuracy summary: did the model read the case history?

Input: the engine rows for the long test set (support/rows.jsonl from run_engine_eval.ps1 -DataPrefix long_test_) and
the test records (data/contoso/final/long_test_support.jsonl, whose _meta carries long_kind / decisive /
short_policy_labels). Output: Markdown tables + JSON.

The decisive comparison is per clause: on "decisive" records the correct answer differs from the short-record policy, so
a model that ignores the history scores 0 on the changed question; on the matched controls the short-record answer is
correct, so a model that over-reacts to a long history scores 0 there. Both halves are reported.

  python scripts/summarize_long.py --rows 验证结果/端侧引擎_x64长输入真题_<t>/<label>/support/rows.jsonl \
      --data data/contoso/final/long_test_support.jsonl --out 验证结果/端侧引擎_x64长输入真题_<t>/summary
Standard library only.
"""
import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

CLAUSE_NAME = {"H1": "H1 电池已换过 → sales_ops", "H2": "H2 远程重置已试过 → 硬件故障", "H3": "H3 报告无备份 → 紧急度 3"}
CLAUSE_Q = {"H1": "queue", "H2": "queue", "H3": "urgency"}


def load_rows(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def pct(k, n):
    return "—" if not n else f"{100 * k / n:.1f}% ({k}/{n})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--short-rows", default="", help="optional: same model on the short test set (for the 'all questions' reference row)")
    a = ap.parse_args()
    data = load_rows(a.data)
    meta = {r["_meta"]["case"]: r["_meta"] for r in data}
    cases = [r["_meta"]["case"] for r in data]
    all_rows = load_rows(a.rows)
    rejected = [r for r in all_rows if "error" in r]  # the server refused the request (e.g. context size exceeded); not scored
    rows = [r for r in all_rows if "questions" in r]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    # per question overall
    overall = defaultdict(lambda: [0, 0])
    per_clause = defaultdict(lambda: {"decisive": [0, 0], "control": [0, 0], "decisive_other_q": [0, 0], "control_other_q": [0, 0]})
    by_len = defaultdict(lambda: [0, 0])
    lat = []
    tokens = []
    for r in rows:
        m = meta[r["case"]]
        clause, decisive = m["clause"], m["decisive"]
        qd = CLAUSE_Q[clause]
        lat.append(r["latency_ms"])
        if r.get("input_tokens"):
            tokens.append(r["input_tokens"] / max(1, len(r["questions"])))  # server counts the state once per question
        bucket = f"{(m['history_chars'] // 5000) * 5}k–{(m['history_chars'] // 5000) * 5 + 5}k 字符"
        for q, v in r["questions"].items():
            ok = str(v["pred"]) == str(v["label"])
            overall[q][0] += ok; overall[q][1] += 1
            by_len[bucket][0] += ok; by_len[bucket][1] += 1
            key = ("decisive" if decisive else "control") + ("" if q == qd else "_other_q")
            per_clause[clause][key][0] += ok; per_clause[clause][key][1] += 1

    n_q = sum(v[1] for v in overall.values()); k_q = sum(v[0] for v in overall.values())
    lines = ["# 长输入真题：模型读历史了吗（自动生成）", "",
             f"记录 {len(all_rows)} 条，其中 {len(rejected)} 条被服务端拒绝（不计分），{len(rows)} 条评分、题 {n_q} 道；请求耗时中位数 {statistics.median(lat):.0f} ms，p90 {sorted(lat)[int(0.9 * len(lat)) - 1]:.0f} ms"
             + (f"；每道题输入中位数约 {statistics.median(tokens):.0f} token" if tokens else ""), ""]
    if rejected:
        lines += ["## 0. 被服务端拒绝的请求", "", "| 记录 | 错误 | 条款 / 决定性 | 历史字符数 |", "|---|---|---|---|"]
        for r in rejected:
            m = meta[cases[r["i"]]]
            lines.append(f"| {cases[r['i']]} | {r['error'][:60]} | {m['clause']} / {'决定性' if m['decisive'] else '对照'} | {m['history_chars']:,} |")
        lines.append("")
    lines += [
             "## 1. 按条款：决定性记录（答案必须随历史改变）与对照记录（历史在、事实相反，答案不变）", "",
             "| 条款 | 决定性记录·受影响题答对 | 对照记录·同一题答对 | 决定性记录·其余两题 | 对照记录·其余两题 |", "|---|---|---|---|---|"]
    for c in ("H1", "H2", "H3"):
        p = per_clause[c]
        lines.append(f"| {CLAUSE_NAME[c]} | {pct(*p['decisive'])} | {pct(*p['control'])} | {pct(*p['decisive_other_q'])} | {pct(*p['control_other_q'])} |")
    dec = [sum(per_clause[c]["decisive"][i] for c in per_clause) for i in (0, 1)]
    ctl = [sum(per_clause[c]["control"][i] for c in per_clause) for i in (0, 1)]
    # the "ignore the history" strategy: answer every question with the short-record policy label
    short_ok = sum(str(meta[r["case"]]["short_policy_labels"][q]) == str(v["label"]) for r in rows for q, v in r["questions"].items())
    same_short = sum(str(v["pred"]) == str(meta[r["case"]]["short_policy_labels"][q]) for r in rows for q, v in r["questions"].items())
    lines += ["", f"合计：决定性记录受影响题 {pct(*dec)}；对照记录同一题 {pct(*ctl)}；全部 {n_q} 题 {pct(k_q, n_q)}。", "",
              f"参照策略：完全不读历史、按短记录规则作答，在同一批评分题上会得 {pct(short_ok, n_q)}；模型的答案与短记录规则答案相同的只有 {pct(same_short, n_q)}。", "",
              "读法：决定性列低、对照列高 = 模型忽视历史、按短记录答；两列都低 = 长输入让它乱答；两列都高 = 读到了也没过度反应。", "",
              "## 2. 按题型（含预测值分布）", "", "| 题 | 答对 | 预测值分布 | 标签分布 |", "|---|---|---|---|"]
    pred_dist = {q: {} for q in overall}
    lab_dist = {q: {} for q in overall}
    for r in rows:
        for q, v in r["questions"].items():
            pred_dist[q][str(v["pred"])] = pred_dist[q].get(str(v["pred"]), 0) + 1
            lab_dist[q][str(v["label"])] = lab_dist[q].get(str(v["label"]), 0) + 1
    fmt = lambda d: ", ".join(f"{k}: {v}" for k, v in sorted(d.items(), key=lambda kv: -kv[1]))
    lines += [f"| {q} | {pct(*v)} | {fmt(pred_dist[q])} | {fmt(lab_dist[q])} |" for q, v in overall.items()]
    lines += ["", "## 3. 按历史长度", "", "| 历史长度 | 答对（三题合计） |", "|---|---|"]
    lines += [f"| {b} | {pct(*v)} |" for b, v in sorted(by_len.items())]
    if a.short_rows:
        srows = load_rows(a.short_rows)
        sk = sum(str(v["pred"]) == str(v["label"]) for r in srows for v in r["questions"].values())
        sn = sum(len(r["questions"]) for r in srows)
        lines += ["", f"参考：同一模型在短输入测试集（{len(srows)} 条）上 {pct(sk, sn)}，请求耗时中位数 {statistics.median(r['latency_ms'] for r in srows):.0f} ms。"]
    (out / "long_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "long_summary.json").write_text(json.dumps({"records": len(all_rows), "rejected": [{"i": r["i"], "case": cases[r["i"]], "error": r["error"]} for r in rejected],
        "scored_records": len(rows), "questions": n_q, "correct": k_q, "short_policy_strategy_correct": short_ok, "model_equals_short_policy": same_short,
        "per_clause": per_clause, "overall": overall, "prediction_distribution": pred_dist, "label_distribution": lab_dist,
        "by_length": by_len, "latency_ms_median": statistics.median(lat)}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

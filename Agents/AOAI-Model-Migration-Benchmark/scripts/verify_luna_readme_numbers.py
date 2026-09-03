"""Recompute every number used in README Section 3.5 from the raw JSON files and check the README text.

Usage:
    python verify_readme_numbers.py <outputs-dir> <README.md> [<README-CN.md>]

Prints one line per (file, model, effort, mode) cell with the 2-decimal strings that must appear on the
README line for that model inside the matching subsection, followed by PASS/FAIL. Also runs
permutation tests for the round-3 "no TTFT effect" claim and recomputes the customer screenshot stats.
"""
from __future__ import annotations

import json
import math
import random
import re
import statistics
import sys
from pathlib import Path

CUSTOMER_SCREENSHOT = [21.841, 1.119, 61.918, 1.022, 1.893, 13.685, 2.810, 1.500, 1.818, 0.974, 22.470, 1.693, 15.238,
         4.601, 20.513, 0.979, 5.225, 5.554, 17.956, 1.294, 11.544, 0.907, 1.776, 1.176, 1.035]


def pct(values: list[float], f: float) -> float:
    o = sorted(values)
    r = (len(o) - 1) * f
    lo = int(r)
    hi = min(lo + 1, len(o) - 1)
    return o[lo] + (o[hi] - o[lo]) * (r - lo)


def cells(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    recs = [r for r in data["records"] if not r["warmup"]]
    per_query = "capability-spread" in path.name
    keys = sorted({(r["model"], r.get("reasoning_effort", "default"), r["stream"], r["query"] if per_query else "*", r.get("condition") or "") for r in recs})
    out = []
    for model, effort, stream, query, condition in keys:
        g = [r for r in recs if r["model"] == model and r.get("reasoning_effort", "default") == effort and r["stream"] == stream
             and (query == "*" or r["query"] == query) and (r.get("condition") or "") == condition]
        # mirror the script: records whose timing includes a client token refresh are not latency samples
        ok = [r for r in g if r["success"] and (r.get("auth_seconds") or 0) <= 0.5]
        e2e = [r["e2e"] for r in ok]
        ttft = [r["ttft"] for r in ok if r.get("ttft") is not None]
        tps = [r["visible_tps"] for r in ok if r.get("visible_tps") is not None]
        outt = [r["output_tokens"] for r in ok]
        reas = [r["reasoning_tokens"] or 0 for r in ok]
        cached = [r.get("cached_tokens") or 0 for r in ok]
        inp = [r["input_tokens"] for r in ok]
        row = {
            "file": path.name, "model": model, "effort": effort, "mode": "stream" if stream else "nonstream", "query": query,
            "condition": condition,
            "n_ok": len(ok), "n": len(g), "ttft": ttft, "e2e": e2e,
            "nums": {
                "e2e_mean": statistics.mean(e2e) if e2e else None,
                "e2e_p50": statistics.median(e2e) if e2e else None,
                "e2e_p95": pct(e2e, 0.95) if e2e else None,
                "e2e_max": max(e2e) if e2e else None,
                "ttft_p50": statistics.median(ttft) if ttft else None,
                "ttft_p95": pct(ttft, 0.95) if ttft else None,
            },
            "ints": {
                "over5": sum(v > 5 for v in e2e),
                "out_tokens": round(statistics.mean(outt)) if outt else None,
                "reasoning": round(statistics.mean(reas)) if reas else None,
                "tps_p50": round(statistics.median(tps)) if tps else None,
                "input": round(statistics.mean(inp)) if inp else None,
                "cached": round(statistics.mean(cached)) if cached else None,
                "cache_hits": sum(1 for c in cached if c > 0),
            },
        }
        out.append(row)
    return out


def check_readme(readme: Path, rows: list[dict], label: str) -> int:
    text = readme.read_text(encoding="utf-8")
    lines = text.splitlines()
    failures = 0
    for row in rows:
        if row["n_ok"] == 0 or "sol-sdk-default-retries" in row["file"]:
            continue  # the retries run is presented per request, checked separately below
        if (
            "4omini-vs-56" in row["file"]
            or "terra-62s-confirm" in row["file"]
            or "aligned-effort-matrix" in row["file"]
            or "effort-ladder-1to1" in row["file"]
            or "final-balanced-effort-t2t" in row["file"]
        ):
            continue  # Sections 3.5.7/3.5.8 use dedicated metric-oriented gates.
        per_query = "capability-spread" in row["file"]
        if per_query:
            needles = [f"{row['nums']['ttft_p50']:.2f}s", f"{row['nums']['e2e_p50']:.2f}s"]
        else:
            needles = [f"{v:.2f}s" for v in row["nums"].values() if v is not None]
        model_tag = f"`{row['model']}`" if row["effort"] == "default" else f"`{row['model']}:{row['effort']}`"
        alt_tag = f"| {row['model']} |" if row["effort"] == "default" else f"| {row['model']} | `{row['effort']}` |"
        alt_tag2 = f"| **{row['model']}** |"
        candidates = [ln for ln in lines if (model_tag in ln or alt_tag in ln or alt_tag2 in ln or f"| {row['model']} | " in ln or f"| **{row['model']}** | " in ln)]
        hit = any(all(nd in ln for nd in needles) for ln in candidates)
        # tolerate one 0.01 rounding step (e.g. 2.9645 -> 2.96 vs 2.97)
        if not hit:
            def variants(v: float) -> set[str]:
                return {f"{v:.2f}s", f"{v + 0.005:.2f}s", f"{v - 0.005:.2f}s"}
            hit = any(all(any(x in ln for x in variants(v)) for v in row["nums"].values() if v is not None) for ln in candidates)
        status = "PASS" if hit else "FAIL"
        if not hit:
            failures += 1
        print(f"[{label}] {status} {row['file'][27:60]:<34} {row['model']:<14} {row['effort']:<8} {row['mode']:<9} {row['query']:<14} "
              f"N={row['n_ok']:>2}/{row['n']:<2} needles={needles} cached_hits={row['ints']['cache_hits']}/{row['n_ok']}")
    return failures


def check_retries_table(readme: Path, outputs: Path, label: str) -> int:
    files = list(outputs.glob("*sol-sdk-default-retries.json"))
    if not files:
        return 0
    data = json.loads(files[0].read_text(encoding="utf-8"))
    text = readme.read_text(encoding="utf-8")
    failures = 0
    for r in data["records"]:
        needle = f"{r['e2e']:.1f}s"
        ok = needle in text
        failures += 0 if ok else 1
        print(f"[{label}] {'PASS' if ok else 'FAIL'} retries-run i{r['iteration']:>2} status={r['http_status']} e2e={needle} retries_taken={r.get('retries_taken')}")
    return failures


def check_section_357(readme: Path, outputs: Path, label: str) -> int:
    """Section 3.5.7 quotes metric-oriented tables (SKU comparison, baseline, 62 s hold).

    Every value asserted below is recomputed from the raw JSON and must appear verbatim in the file.
    """
    main = list(outputs.glob("*4omini-vs-56-datazone-vs-global.json"))
    clean = list(outputs.glob("*terra-62s-confirm.json"))
    if not main or not clean:
        return 0
    whole = readme.read_text(encoding="utf-8")
    # Scope the search to section 3.5.7 so a value that happens to appear elsewhere in the README
    # cannot produce a false PASS.
    start = next((i for i, ln in enumerate(whole.splitlines()) if ln.startswith("#### 3.5.7 ")), None)
    if start is None:
        print(f"[{label}] FAIL 3.5.7 section heading not found")
        return 1
    lines = whole.splitlines()
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("#### ") and not lines[i].startswith("#### 3.5.7")), len(lines))
    text = "\n".join(lines[start:end])
    failures = 0

    def ok(path: Path) -> list[dict]:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [r for r in data["records"]
                if not r["warmup"] and r["success"] and (r.get("auth_seconds") or 0) <= 0.5]

    def vals(recs: list[dict], model: str, stream: bool, key: str) -> list[float]:
        return [r[key] for r in recs if r["model"] == model and r["stream"] == stream and r.get(key) is not None]

    def assert_in(name: str, value: float, fmt_str: str = "{:.2f}s") -> None:
        nonlocal failures
        needle = fmt_str.format(value)
        hit = needle in text
        if not hit:
            failures += 1
        print(f"[{label}] {'PASS' if hit else 'FAIL'} 3.5.7 {name:<46} {needle}")

    m = ok(main[0])
    # SKU comparison: gpt-5.6-luna GlobalStandard vs DataZoneStandard
    for stream, tag in ((True, "stream"), (False, "nonstream")):
        for model, sku in (("gpt-5.6-luna", "global"), ("gpt-5.6-luna-datazone", "datazone")):
            e = vals(m, model, stream, "e2e")
            assert_in(f"SKU {tag} {sku} E2E p50", statistics.median(e))
            assert_in(f"SKU {tag} {sku} E2E p95", pct(e, 0.95))
            assert_in(f"SKU {tag} {sku} E2E max", max(e))
            if stream:
                assert_in(f"SKU stream {sku} TTFT p50", statistics.median(vals(m, model, True, "ttft")))

    c = ok(clean[0])
    # Baseline table: the clean window, stream only
    for model in ("gpt-4o-mini-dz", "gpt-5.6-luna", "gpt-5.6-terra"):
        t = vals(c, model, True, "ttft")
        e = vals(c, model, True, "e2e")
        assert_in(f"baseline {model} TTFT p50", statistics.median(t))
        assert_in(f"baseline {model} TTFT p95", pct(t, 0.95))
        assert_in(f"baseline {model} E2E p50", statistics.median(e))
        assert_in(f"baseline {model} E2E max", max(e))
        tps = vals(c, model, True, "visible_tps")
        assert_in(f"baseline {model} decode", statistics.median(tps), "{:.0f} tok/s")

    # The ~62 s hold, pooled across both runs
    both = json.loads(main[0].read_text(encoding="utf-8"))["records"] + \
           json.loads(clean[0].read_text(encoding="utf-8"))["records"]
    terra = [r for r in both if r["model"] == "gpt-5.6-terra" and r["success"]]
    holds = [r for r in terra if r["e2e"] > 60]
    first = [r["ttft"] for r in holds if r.get("ttft")]
    others = [r for r in both if r["model"] != "gpt-5.6-terra" and r["success"] and r["e2e"] > 60]
    checks = [
        (f"hold count {len(holds)} of {len(terra)}", f"{len(holds)} of {len(terra)}" in text or f"{len(holds)} 次" in text),
        ("hold min", f"{min(first):.2f}" in text),
        ("hold max", f"{max(first):.2f}" in text),
        ("hold median", f"{statistics.median(first):.2f}" in text),
        ("hold stdev", f"{statistics.stdev(first):.2f}" in text),
        ("no retries on holds", all(r["http_status"] == 200 and (r.get("retries_taken") or 0) == 0 for r in holds)),
        ("other pools have zero >60s", len(others) == 0),
    ]
    for name, hit in checks:
        if not hit:
            failures += 1
        print(f"[{label}] {'PASS' if hit else 'FAIL'} 3.5.7 62s-hold {name}")
    return failures


def check_section_358(readme: Path, outputs: Path, label: str) -> int:
    """Check the final balanced effort / derived-TPOT matrix in Section 3.5.8."""
    files = list(outputs.glob("*final-balanced-effort-t2t.json"))
    if not files:
        return 0
    whole = readme.read_text(encoding="utf-8")
    lines = whole.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("#### 3.5.8 ")), None)
    if start is None:
        print(f"[{label}] FAIL 3.5.8 section heading not found")
        return 1
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("#### ") and not lines[i].startswith("#### 3.5.8")), len(lines))
    text = "\n".join(lines[start:end])
    data = json.loads(files[0].read_text(encoding="utf-8"))
    records = [r for r in data["records"] if not r["warmup"] and r["success"] and (r.get("auth_seconds") or 0) <= 0.5]
    failures = 0

    def rows(model: str, effort: str) -> list[dict]:
        return [r for r in records if r["model"] == model and r.get("reasoning_effort", "default") == effort]

    def values(model: str, effort: str, key: str) -> list[float]:
        return [r[key] for r in rows(model, effort) if r.get(key) is not None]

    def assert_text(name: str, needle) -> None:
        nonlocal failures
        needles = (needle,) if isinstance(needle, str) else tuple(needle)
        hit = any(n in text for n in needles)
        if not hit:
            failures += 1
        print(f"[{label}] {'PASS' if hit else 'FAIL'} 3.5.8 {name:<56} {' | '.join(needles)}")

    cells = [("gpt-4o-mini-dz", "default")]
    cells += [("gpt-5.6-luna-datazone", e) for e in ("none", "low", "medium", "high", "xhigh", "max", "default")]
    cells += [("gpt-5.4-nano", e) for e in ("none", "low", "medium", "high", "xhigh", "default")]
    cells += [("gpt-5.6-luna", e) for e in ("none", "low", "medium", "high", "xhigh", "max", "default")]
    for model, effort in cells:
        row = rows(model, effort)
        reasoning = values(model, effort, "reasoning_tokens")
        visible = [(r["output_tokens"] or 0) - (r["reasoning_tokens"] or 0) for r in row]
        cache_hits = sum((r.get("cached_tokens") or 0) > 0 for r in row)
        assert_text(f"{model}:{effort} reasoning mean", f"{statistics.mean(reasoning):.1f}")
        assert_text(f"{model}:{effort} visible mean", f"{statistics.mean(visible):.1f}")
        assert_text(f"{model}:{effort} cache hits", f"{cache_hits}/{len(row)}")
        assert_text(f"{model}:{effort} TTFT p50", f"{statistics.median(values(model, effort, 'ttft')):.3f}s")
        assert_text(f"{model}:{effort} TPOT p50", f"{statistics.median(values(model, effort, 't2t_ms')):.2f}ms")
        assert_text(f"{model}:{effort} E2E p50", f"{statistics.median(values(model, effort, 'e2e')):.3f}s")

    checks = [
        ("balanced order", data["meta"].get("order") == "balanced"),
        ("balanced seed", data["meta"].get("order_seed") == 20260903),
        ("20 unique positions per cell", all(len({r["call_position"] for r in rows(m, e)}) == 20 for m, e in cells)),
        ("stream only", data["meta"]["modes"] == ["stream"]),
        ("2,048 max output tokens", data["meta"]["queries"][0]["max_output_tokens"] == 2048),
        ("zero retries", data["meta"]["max_retries"] == 0),
        ("420 effective samples", len(records) == 420),
        ("420 unique request ids", len({r["request_id"] for r in records}) == 420),
        ("zero failures", not any(not r["success"] for r in data["records"])),
        ("zero incomplete", not any(r.get("response_status") == "incomplete" for r in data["records"])),
        ("all sanity pass", all(r["sanity_pass"] for r in records)),
        ("zero auth artifacts", not any((r.get("auth_seconds") or 0) > 0.5 for r in data["records"])),
        ("derived TPOT label", ("Derived T2T / TPOT" in text)),
        ("derived metric caveat", ("not the median of individually timestamped token gaps" in text or "不是对每个 token 单独打时间戳" in text)),
        ("visible-output column", ("Avg Visible Output Tokens" in text or "平均可见输出 tokens" in text)),
        ("P50 tail boundary", ("central tendency only" in text and "establish P95/P99" in text) or "不能**证明 P95/P99" in text),
        ("same-label budget boundary", ("does not imply the same reasoning budget" in text or "不代表相同 reasoning 预算" in text)),
        ("Holm correction declared", ("Holm-corrected" in text or "Holm 校正" in text)),
    ]
    for name, hit in checks:
        if not hit:
            failures += 1
        print(f"[{label}] {'PASS' if hit else 'FAIL'} 3.5.8 contract {name}")

    # Fairness cross-checks added after the final audit: every number quoted in the
    # 4o-mini paragraph, the SKU cross-check and the within-run tail note must recompute.
    mini = rows("gpt-4o-mini-dz", "default")
    luna_none = rows("gpt-5.6-luna-datazone", "none")
    mini_hit = [r["ttft"] for r in mini if (r.get("cached_tokens") or 0) > 0]
    luna_hit = [r["ttft"] for r in luna_none if (r.get("cached_tokens") or 0) > 0]
    assert_text("4o-mini cache-hit-only TTFT p50", f"{statistics.median(mini_hit):.3f} vs {statistics.median(luna_hit):.3f}s")
    assert_text("4o-mini cache-hit-only raw p", f"raw p = {permutation_p(mini_hit, luna_hit):.3f}")
    assert_text("4o-mini all-request raw p", (f"raw p = {permutation_p([r['ttft'] for r in mini], [r['ttft'] for r in luna_none]):.3f}, paired p", f"raw p={permutation_p([r['ttft'] for r in mini], [r['ttft'] for r in luna_none]):.3f}，paired p"))
    mini_by_iter = {r["iteration"]: r["ttft"] for r in mini}
    luna_by_iter = {r["iteration"]: r["ttft"] for r in luna_none}
    wins = sum(mini_by_iter[i] < luna_by_iter[i] for i in mini_by_iter if i in luna_by_iter)
    n_pairs = sum(1 for i in mini_by_iter if i in luna_by_iter)
    paired_p = 2 * sum(math.comb(n_pairs, k) for k in range(max(wins, n_pairs - wins), n_pairs + 1)) / 2 ** n_pairs
    assert_text("4o-mini paired sign-test p", (f"paired p = {min(paired_p, 1.0):.3f}", f"paired p={min(paired_p, 1.0):.3f}"))
    assert_text("4o-mini paired split", f"{wins}/{n_pairs}")
    assert_text("4o-mini TTFT max", f"{max(r['ttft'] for r in mini):.3f}s")
    assert_text("Luna none TTFT max", f"{max(r['ttft'] for r in luna_none):.3f}s")

    def chars_per_second(r: dict) -> float:
        return r["text_len"] / (r["e2e"] - r["ttft"])

    def chars_per_token(r: dict) -> float:
        return r["text_len"] / ((r["output_tokens"] or 0) - (r["reasoning_tokens"] or 0))

    cps_mini = [chars_per_second(r) for r in mini]
    cps_luna = [chars_per_second(r) for r in luna_none]
    assert_text("chars/s medians", f"{statistics.median(cps_mini):.0f} vs {statistics.median(cps_luna):.0f}")
    assert_text("chars/s p < 0.0001", "p < 0.0001" if permutation_p(cps_mini, cps_luna) < 0.0001 else "CHARS_PER_SECOND_NOT_SIGNIFICANT")
    assert_text("chars/token means", f"{statistics.mean(chars_per_token(r) for r in mini):.2f} vs {statistics.mean(chars_per_token(r) for r in luna_none):.2f}")
    mini_tokens = statistics.mean((r["output_tokens"] or 0) - (r["reasoning_tokens"] or 0) for r in mini)
    luna_tokens = statistics.mean((r["output_tokens"] or 0) - (r["reasoning_tokens"] or 0) for r in luna_none)
    luna_at_mini_len = statistics.median(values("gpt-5.6-luna-datazone", "none", "ttft")) + mini_tokens * statistics.median(values("gpt-5.6-luna-datazone", "none", "t2t_ms")) / 1000
    mini_at_luna_len = statistics.median(values("gpt-4o-mini-dz", "default", "ttft")) + luna_tokens * statistics.median(values("gpt-4o-mini-dz", "default", "t2t_ms")) / 1000
    assert_text("length-normalised Luna", f"{luna_at_mini_len:.3f}s")
    assert_text("length-normalised 4o-mini", f"{mini_at_luna_len:.3f}s")

    for effort in ("none", "medium", "max"):
        p_ttft = permutation_p(values("gpt-5.6-luna-datazone", effort, "ttft"), values("gpt-5.6-luna", effort, "ttft"))
        assert_text(f"SKU cross-check {effort} TTFT p", f"p = {p_ttft:.3f}")
    e2e_ps = [permutation_p(values("gpt-5.6-luna-datazone", e, "e2e"), values("gpt-5.6-luna", e, "e2e")) for e in ("low", "xhigh", "max")]
    assert_text("SKU cross-check low/xhigh/max E2E p", "p = " + " / ".join(f"{p:.3f}" for p in e2e_ps))
    ns_ps = [permutation_p(values("gpt-5.6-luna-datazone", e, "ttft"), values("gpt-5.6-luna", e, "ttft")) for e in ("low", "high", "default")]
    assert_text("SKU cross-check low/high/default TTFT p", "p = " + " / ".join(f"{p:.3f}" for p in ns_ps))

    worst_ttft = max(records, key=lambda r: r["ttft"])
    worst_e2e = max(records, key=lambda r: r["e2e"])
    assert_text("worst TTFT is nano xhigh", f"{worst_ttft['ttft']:.3f}s" if (worst_ttft["model"], worst_ttft["reasoning_effort"]) == ("gpt-5.4-nano", "xhigh") else "WORST_TTFT_NOT_NANO_XHIGH")
    assert_text("worst TTFT reasoning tokens", (f"{worst_ttft['reasoning_tokens']} reasoning token", f"{worst_ttft['reasoning_tokens']} 个 reasoning token"))
    assert_text("worst E2E is nano xhigh", f"{worst_e2e['e2e']:.3f}s" if (worst_e2e["model"], worst_e2e["reasoning_effort"]) == ("gpt-5.4-nano", "xhigh") else "WORST_E2E_NOT_NANO_XHIGH")
    luna_rows = [r for r in records if r["model"].startswith("gpt-5.6-luna")]
    assert_text("Luna worst TTFT", f"{max(r['ttft'] for r in luna_rows):.3f}s")
    assert_text("no request above 15s", "15s" if max(r["e2e"] for r in records) < 15 else "REQUEST_ABOVE_15S")
    return failures


def check_tail_ledger(readme: Path, outputs: Path, label: str) -> int:
    """Check the cross-file Luna tail sentence in Findings #1 against all data files."""
    files = sorted(outputs.glob("benchmark_luna_knowledge_qa_*.json"))
    if len(files) < 13:
        return 0
    text = readme.read_text(encoding="utf-8")
    failures = 0

    def assert_text(name: str, needle) -> None:
        nonlocal failures
        needles = (needle,) if isinstance(needle, str) else tuple(needle)
        hit = any(n in text for n in needles)
        if not hit:
            failures += 1
        print(f"[{label}] {'PASS' if hit else 'FAIL'} ledger {name:<56} {' | '.join(needles)}")

    total = 0
    luna = []
    mini = []
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        total += len(data["records"])
        luna += [r for r in data["records"] if r["model"].startswith("gpt-5.6-luna")]
        mini += [r for r in data["records"] if r["model"] == "gpt-4o-mini-dz"]
    luna_ok = [r for r in luna if r["success"]]
    luna_none = [r for r in luna_ok if r.get("reasoning_effort") == "none"]
    mini_ok = [r for r in mini if r["success"]]
    assert_text("file count", (f"{len(files)} data files", f"{len(files)} 个数据文件"))
    assert_text("record total", (f"({total:,} records)", f"（{total:,} 条）"))
    assert_text("Luna completed/total", (f"{len(luna_ok):,} of {len(luna):,} requests", f"{len(luna):,} 次请求完成 {len(luna_ok):,} 次"))
    assert_text("Luna max successful TTFT", f"{max(r['ttft'] for r in luna_ok if r.get('ttft') is not None):.2f} s")
    assert_text("Luna max successful E2E", f"{max(r['e2e'] for r in luna_ok):.2f} s")
    assert_text("4o-mini max TTFT", f"{max(r['ttft'] for r in mini_ok if r.get('ttft') is not None):.2f} s TTFT")
    assert_text("4o-mini max E2E", f"{max(r['e2e'] for r in mini_ok):.2f} s E2E")
    assert_text("Luna none count", (f"{len(luna_none)} Luna requests", f"{len(luna_none)} 次 Luna 请求"))
    assert_text("Luna none max TTFT", f"{max(r['ttft'] for r in luna_none):.2f} s TTFT")
    assert_text("Luna none max E2E", f"{max(r['e2e'] for r in luna_none):.2f} s E2E")
    failed = [r for r in luna if not r["success"]]
    assert_text("single Luna failure is the 1,775 s connection error", "1,775 s" if len(failed) == 1 and round(failed[0]["e2e"]) == 1775 and "APIConnectionError" in str(failed[0].get("error")) else "LUNA_FAILURE_LEDGER_MISMATCH")
    return failures

def permutation_p(a: list[float], b: list[float], iters: int = 20000, seed: int = 7) -> float:
    rng = random.Random(seed)
    obs = abs(statistics.median(a) - statistics.median(b))
    pooled = a + b
    n = len(a)
    hits = 0
    for _ in range(iters):
        rng.shuffle(pooled)
        if abs(statistics.median(pooled[:n]) - statistics.median(pooled[n:])) >= obs:
            hits += 1
    return hits / iters


def main() -> int:
    outputs = Path(sys.argv[1])
    readmes = [Path(p) for p in sys.argv[2:]]
    files = sorted(outputs.glob("benchmark_luna_knowledge_qa_2026*.json"))
    files = [f for f in files if "canary" not in f.name]
    all_rows: list[dict] = []
    for f in files:
        all_rows.extend(cells(f))

    print("== Customer screenshot (25 transcribed values) recompute ==")
    print(f"mean={statistics.mean(CUSTOMER_SCREENSHOT):.3f} median={statistics.median(CUSTOMER_SCREENSHOT):.3f} p95={pct(CUSTOMER_SCREENSHOT, 0.95):.3f} "
          f"max={max(CUSTOMER_SCREENSHOT):.3f} over5={sum(v > 5 for v in CUSTOMER_SCREENSHOT)}/25 n={len(CUSTOMER_SCREENSHOT)}")

    failures = 0
    for rd in readmes:
        print(f"\n== README number check: {rd.name} ==")
        failures += check_readme(rd, all_rows, rd.stem)
        failures += check_retries_table(rd, outputs, rd.stem)
        failures += check_section_357(rd, outputs, rd.stem)
        failures += check_section_358(rd, outputs, rd.stem)
        failures += check_tail_ledger(rd, outputs, rd.stem)

    print("\n== Round 3 permutation tests on Luna TTFT (median difference) ==")
    r3 = {row["file"]: row for row in all_rows if row["model"] == "gpt-5.6-luna" and "sysprompt" in row["file"]}
    by = {k.split("_sysprompt-")[1].split(".json")[0]: v for k, v in r3.items()}
    if {"1200tok-cached", "1200tok-cachebust", "none-control"} <= set(by):
        c, b, n = by["1200tok-cached"]["ttft"], by["1200tok-cachebust"]["ttft"], by["none-control"]["ttft"]
        print(f"cached vs never-cached: medians {statistics.median(c):.3f} vs {statistics.median(b):.3f}  p={permutation_p(c, b):.3f}")
        print(f"cached vs no-system   : medians {statistics.median(c):.3f} vs {statistics.median(n):.3f}  p={permutation_p(c, n):.3f}")
        print(f"never-cached vs none  : medians {statistics.median(b):.3f} vs {statistics.median(n):.3f}  p={permutation_p(b, n):.3f}")
        for name, model in (("terra", "gpt-5.6-terra"), ("sol", "gpt-5.6-sol"), ("nano", "gpt-5.4-nano")):
            rows = {row["file"].split("_sysprompt-")[1].split(".json")[0]: row for row in all_rows if row["model"] == model and "sysprompt" in row["file"]}
            print(f"{name}: cached vs never-cached p={permutation_p(rows['1200tok-cached']['ttft'], rows['1200tok-cachebust']['ttft']):.3f}")

    print("\n== Round 3 effort ladder: Luna none vs low vs default(round1) ==")
    ladder = {row["effort"]: row for row in all_rows if row["model"] == "gpt-5.6-luna" and "effort-ladder" in row["file"]}
    r1 = [row for row in all_rows if row["model"] == "gpt-5.6-luna" and "seven-wonders-5models" in row["file"] and row["mode"] == "stream"]
    if ladder and r1:
        print(f"none vs low     p={permutation_p(ladder['none']['ttft'], ladder['low']['ttft']):.4f}")
        print(f"none vs default p={permutation_p(ladder['none']['ttft'], r1[0]['ttft']):.4f}")

    print(f"\nREADME_NUMBER_CHECK={'PASS' if failures == 0 else 'FAIL'} failures={failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

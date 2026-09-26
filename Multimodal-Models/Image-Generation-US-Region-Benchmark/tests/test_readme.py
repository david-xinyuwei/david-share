"""Contracts on the rendered README.md, not on render.py internals. Run: python -m pytest tests -q"""
import json
import re
import statistics
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
RUNS = ROOT / "runs"


def run_dir():
    dirs = [p for p in RUNS.iterdir() if (p / "5way_v2_results.json").is_file()] if RUNS.is_dir() else []
    if not dirs:
        pytest.skip("no run directory with 5way_v2_results.json under runs/")
    return sorted(dirs)[-1]


@pytest.fixture(scope="module")
def readme():
    if not README.is_file():
        pytest.skip("README.md not rendered yet")
    return README.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def results():
    return json.loads((run_dir() / "5way_v2_results.json").read_text(encoding="utf-8"))


def test_check_mode_passes_against_committed_readme():
    proc = subprocess.run([sys.executable, str(ROOT / "render.py"), str(run_dir()), "--check"],
                          capture_output=True, text=True, cwd=ROOT)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_required_sections_in_reader_order(readme):
    order = ["## Results", "## Cost", "## Robustness against earlier runs", "## Images", "## Method", "## Reproduce"]
    positions = [readme.index(h) for h in order]
    assert positions == sorted(positions), "sections out of order"


def test_robustness_section_names_reference_runs_with_hashes(readme):
    refs = json.loads((ROOT / "references.json").read_text(encoding="utf-8"))
    section = readme.split("## Robustness against earlier runs", 1)[1].split("## Images", 1)[0]
    used = {m["run"] for m in refs["group_map"].values()}
    for run in used:
        assert f"`{run}`" in section, f"reference run {run} not named"
    assert re.search(r"SHA-256 `[0-9a-f]{12}…`", section), "reference hash missing"
    assert "Latency ordering" in section and ("**yes**" in section or "**no**" in section)


def test_cost_section_recomputes_from_raw_tokens_and_pricing(readme, results):
    """Every priced row's USD/1,000 images must equal mean(per-image cost) recomputed from raw token counts."""
    pricing = json.loads((ROOT / "pricing.json").read_text(encoding="utf-8"))
    raw = [r for r in results["raw_data"] if r.get("ok")]
    cost_section = readme.split("## Cost", 1)[1].split("## Images", 1)[0]
    checked = 0
    for gc in results["config"]["group_configurations"]:
        model, gid = gc["model"], gc["id"]
        price = pricing.get(model) or {}
        rs = [r for r in raw if r["group"] == gid]
        if not price.get("verified") or not rs:
            continue
        per = []
        for r in rs:
            info = r.get("token_info") or {}
            if "output_image_tokens" in info:
                tin, tout = info["input_tokens"], info["output_image_tokens"]
            else:
                usage = info.get("usage") or {}
                tin, tout = usage.get("num_input_text_tokens"), info.get("num_output_tokens") or usage.get("num_output_tokens")
            per.append(tin / 1e6 * price["input_text"] + tout / 1e6 * price["output_image"])
        expected = f"| {statistics.mean(per) * 1000:,.2f} |"
        assert expected in cost_section, f"{gid}: USD/1k images {expected} not found in Cost section"
        checked += 1
    assert checked, "no priced group was checked"
    assert "Model charges for this run:" in cost_section
    for model in {gc["model"] for gc in results["config"]["group_configurations"]}:
        p = pricing.get(model) or {}
        if p.get("verified"):
            assert p["source_kind"] in cost_section and str(p["verified"])[:40] in cost_section, f"provenance for {model} missing"


def test_every_prompt_is_quoted_verbatim_before_its_images(readme, results):
    prompts_csv = next(iter(sorted((run_dir() / "source").glob("prompts*.csv"))))
    import csv
    rows = list(csv.DictReader(prompts_csv.read_text(encoding="utf-8").splitlines()))
    for row in rows:
        assert f"> {row['prompt']}" in readme, f"prompt not quoted verbatim: {row['prompt'][:50]}"


def _pct(xs, p):
    """Independent re-implementation (linear interpolation, inclusive) so the test does not import render.py."""
    xs = sorted(xs)
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def _tokens(r):
    info = r.get("token_info") or {}
    if "output_image_tokens" in info:
        return info["input_tokens"], info["output_image_tokens"]
    usage = info.get("usage") or {}
    return usage.get("num_input_text_tokens"), info.get("num_output_tokens") or usage.get("num_output_tokens")


def test_results_table_has_p50_p90_p95_latency_matching_raw_data(readme, results):
    raw = [r for r in results["raw_data"] if r.get("ok")]
    groups = sorted({r["group"] for r in raw})
    section = readme.split("## Results", 1)[1].split("## Cost", 1)[0]
    header = next(l for l in section.splitlines() if l.startswith("| Configuration"))
    assert "P50 s" in header and "P90 s" in header and "P95 s" in header
    data_rows = [l for l in section.splitlines() if l.startswith("| ") and not l.startswith("| Configuration")]
    assert len(data_rows) == len(groups), f"Results table has {len(data_rows)} rows, run has {len(groups)} groups"
    for g in groups:
        times = [r["time"] for r in raw if r["group"] == g]
        expected = f"| {len(times)} | {_pct(times, 50):,.2f} | {_pct(times, 90):,.2f} | {_pct(times, 95):,.2f} |"
        assert expected in section, f"{g}: latency percentiles {expected} not in Results table"


def test_cost_table_has_p50_p90_p95_cost_matching_raw_tokens(readme, results):
    pricing = json.loads((ROOT / "pricing.json").read_text(encoding="utf-8"))
    raw = [r for r in results["raw_data"] if r.get("ok")]
    section = readme.split("## Cost", 1)[1].split("## Robustness", 1)[0]
    header = next(l for l in section.splitlines() if l.startswith("| Configuration"))
    assert "USD / image P50" in header and "USD / image P90" in header and "USD / image P95" in header
    checked = 0
    for gc in results["config"]["group_configurations"]:
        price = pricing.get(gc["model"]) or {}
        rs = [r for r in raw if r["group"] == gc["id"]]
        if not price.get("verified") or not rs:
            continue
        costs = [tin / 1e6 * price["input_text"] + tout / 1e6 * price["output_image"] for tin, tout in map(_tokens, rs)]
        expected = f"| {_pct(costs, 50):,.4f} | {_pct(costs, 90):,.4f} | {_pct(costs, 95):,.4f} |"
        assert expected in section, f"{gc['id']}: cost percentiles {expected} not in Cost table"
        checked += 1
    assert checked


def test_every_linked_image_exists_and_matches_record_hash(readme, results):
    import hashlib
    linked = set(re.findall(r'<img src="(images/[^"]+)"', readme))
    assert linked, "no images linked"
    by_key = {(r["group"], r["round"], r["prompt_idx"]): r for r in results["raw_data"] if r.get("ok")}
    for rel in linked:
        path = ROOT / rel
        assert path.is_file(), rel
        m = re.match(r"images/(.+)-r(\d)-p(\d+)\.png", rel)
        rec = by_key[(m.group(1), int(m.group(2)), int(m.group(3)))]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == rec["image_sha256"], rel


def test_every_image_caption_shows_its_own_seconds_and_cost(readme, results):
    """Each thumbnail caption is '<s> s · $<usd>' recomputed from that record's own time and returned tokens;
    auto captions also carry the tier the service echoed for that request."""
    pricing = json.loads((ROOT / "pricing.json").read_text(encoding="utf-8"))
    model_of = {gc["id"]: gc["model"] for gc in results["config"]["group_configurations"]}
    by_key = {(r["group"], r["round"], r["prompt_idx"]): r for r in results["raw_data"] if r.get("ok")}
    cells = re.findall(r'<img src="images/(.+?)-r(\d)-p(\d+)\.png" width="160"></a><br>([^|]+?) \|', readme)
    assert cells, "no captioned images"
    for gid, rnd, idx, caption in cells:
        rec = by_key[(gid, int(rnd), int(idx))]
        price = pricing.get(model_of[gid]) or {}
        tin, tout = _tokens(rec)
        expected = f"{rec['time']:.1f} s · "
        expected += f"${tin / 1e6 * price['input_text'] + tout / 1e6 * price['output_image']:.4f}" if price.get("verified") else "$ n/a"
        if rec.get("quality") == "auto":
            expected += f" · {(rec.get('token_info') or {}).get('service_quality') or 'tier not echoed'}"
        assert caption.strip() == expected, f"{gid} r{rnd} p{idx}: caption {caption.strip()!r} != {expected!r}"


def test_no_secrets_or_subscription_ids(readme):
    assert not re.search(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", readme), "GUID in README"
    assert not re.search(r"api-key|AZURE_API_KEY=|AZURE_OPENAI_API_KEY=", readme), "key material in README"


def test_cost_column_never_shows_a_number_for_unverified_price(readme):
    pricing = json.loads((ROOT / "pricing.json").read_text(encoding="utf-8"))
    unverified = [k for k, v in pricing.items() if isinstance(v, dict) and not v.get("verified")]
    if not unverified:
        pytest.skip("all prices verified")
    assert "price unverified" in readme


def test_auto_groups_disclose_service_echoed_tiers(readme, results):
    """quality=auto is a per-request choice by the service; the README must show which tiers were echoed."""
    auto_records = [r for r in results["raw_data"] if r.get("ok") and r.get("quality") == "auto"]
    if not auto_records:
        pytest.skip("run has no auto group")
    assert "`auto` is not a fixed tier" in readme
    echoed = {(r.get("token_info") or {}).get("service_quality") for r in auto_records} - {None}
    assert echoed, "runner did not record service_quality for auto requests"
    for q in echoed:
        assert re.search(rf"\b{re.escape(q)} ×\d+", readme), f"echoed tier {q!r} not disclosed in README"

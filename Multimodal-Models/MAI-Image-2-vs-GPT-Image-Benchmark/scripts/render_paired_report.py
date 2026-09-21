"""Render README.md and README-CN.md from the archived MAI-Image-2.6 vs GPT-Image-2.5 evidence.

The same-session run (MAI, 2.5 flare medium, 2.5 flare high interleaved by one client) is the spine
of the report. The other 2.5 tiers, the edit test, text rendering, the invoice and web grounding are
sections drawn from their own archives. Every number is recomputed from data/ on each render, and
`--check` fails when either README differs from what the evidence produces.
"""
import argparse
import csv
import json
import re
import statistics
from pathlib import Path

from summarize_paired_run import summarize
from summarize_web_grounding import summarize as summarize_grounding
from summarize_edit_hat_swap import summarize as summarize_edit


# Same-session run: the primary comparison. Its three configurations were called alternately by one
# client on one account in one region, so its latencies and images carry no date caveat.
PRIMARY_ARCHIVE = "data/mai-vs-gpt25-20260920"
# The remaining 2.5 tiers, measured with the same client and prompt file in two earlier sessions.
SUPPLEMENT_ARCHIVE = "data/gpt25-paired-20260917"   # flare + sunburst, low/medium/high
TIER_ARCHIVE = "data/gpt25-tiers-20260918"          # flare + sunburst, xhigh/max/auto
EDIT_ARCHIVE = "data/edit-hat-swap-gpt25-20260921"
GROUNDING_ARCHIVE = "data/lenovo-web-grounding-20260908"
BILLING_ARCHIVE = "data/billing-20260920"
TEXT_ARCHIVES = (("data/text-rendering-20260918", "prompts-text-rendering.csv", "easy"),
                 ("data/text-hard-20260919", "prompts-text-hard.csv", "hard"))
# Archives from the report's earlier GPT-Image-2 comparison. They are evidence only and feed no table.
RETIRED_ARCHIVES = ("data/paired-all-quality-20260907", "data/mai-image-2.6-20260907",
                    "data/edit-hat-swap-20260908", "data/edit-hat-swap-20260909-auto")
# Tiers each deployment accepts, per the Azure OpenAI image generation reference and verified
# against the live service on 2026-09-18. Used to decide whether the report may claim it covered
# every tier.
OFFICIAL_TIERS = {
    "gpt-image-2": ("low", "medium", "high"),
    "gpt-image-2.5-flare": ("low", "medium", "high", "xhigh", "max", "auto"),
    "gpt-image-2.5-sunburst": ("low", "medium", "high", "xhigh", "max", "auto"),
}
TIER_ORDER = ("low", "medium", "high", "xhigh", "max", "auto")
# The deployment whose images appear in the side-by-side tables. Sunburst is a second deployment of
# the same model with identical token behaviour; its images stay in the archive to keep the page readable.
SHOWN_GPT_MODEL = "gpt-image-2.5-flare"
RETIRED_MODEL_PREFIX = "gpt-image-2-"


def table(headers, rows):
    if any(len(row) != len(headers) for row in rows):
        raise ValueError("Table row does not match its header")
    return "\n".join(["| " + " | ".join(headers) + " |",
                      "| " + " | ".join("---" for _ in headers) + " |",
                      *("| " + " | ".join(str(value) for value in row) + " |" for row in rows)])


def number(value, decimals=2):
    return "N/A" if value is None else f"{value:,.{decimals}f}"


def label_for(configuration):
    """Column label from a group configuration, e.g. gpt-image-2.5-flare/low -> GPT-Image-2.5 Flare low."""
    model = configuration["model"]
    if configuration["provider"] == "mai":
        return model
    parts = model.split("-")
    if len(parts) < 3 or parts[0] != "gpt" or parts[1] != "image":
        raise ValueError(f"Unrecognised GPT image model name: {model}")
    name = f"GPT-Image-{parts[2]}" + (" " + parts[3].capitalize() if len(parts) > 3 else "")
    return f"{name} {configuration['quality']}"


def group_label(group_id):
    """Label from a group id such as gpt-image-2.5-flare-medium or mai-image-2.6."""
    if group_id.startswith("mai-image"):
        return "MAI-Image-" + group_id.split("mai-image-", 1)[1]
    model, tier = group_id.rsplit("-", 1)
    return label_for({"provider": "gpt", "model": model, "quality": tier})


def count_tests(root):
    """Number of test functions under tests/, so the badge cannot go stale."""
    return sum(len(re.findall(r"(?m)^\s+def test_", path.read_text("utf-8")))
               for path in (root / "tests").glob("test_*.py"))


def measured_tiers(*summaries):
    """Tiers actually present in the data, per GPT deployment."""
    tiers = {}
    for summary in summaries:
        if not summary:
            continue
        for configuration in summary.get("config", {}).get("group_configurations", ()):
            if configuration["provider"] == "gpt":
                tiers.setdefault(configuration["model"], set()).add(configuration["quality"])
    return tiers


def tier_coverage(*summaries):
    """Which deployments were measured at every tier they accept, and which tiers are missing.

    Derived from the data so the title cannot claim 'All Quality Tiers' ahead of the measurement;
    with no tier data at all the answer is 'not complete', never 'complete by default'.
    """
    measured = measured_tiers(*summaries)
    missing = {}
    for model, tiers in measured.items():
        official = OFFICIAL_TIERS.get(model)
        if official is None:
            raise ValueError(f"No official tier list recorded for {model}; add it before claiming coverage")
        absent = [tier for tier in official if tier not in tiers]
        if absent:
            missing[model] = absent
    return {"measured": {model: sorted(tiers) for model, tiers in measured.items()},
            "missing": missing, "complete": bool(measured) and not missing}


# --------------------------------------------------------------------------------------------------
# Loaders: every archive is validated by its summarizer; nothing here is optional once present.
# --------------------------------------------------------------------------------------------------

def load_run(root, prompts_path, archive):
    """A validated text-to-image run over the original prompts, or None when it is not archived."""
    directory = root / archive
    if not (directory / "5way_v2_results.json").is_file():
        return None
    summary = summarize(directory, prompts_path)
    regions = {group["configuration"].get("deployment_region") for group in summary["groups"]}
    if len(regions) != 1:
        raise ValueError(f"{archive}: configurations must share one deployment region")
    return {"summary": summary, "archive": archive,
            "groups": [group["group"] for group in summary["groups"]],
            "labels": [label_for(group["configuration"]) for group in summary["groups"]],
            "date": summary["formal_started_at_utc"][:10], "region": regions.pop()}


def load_tier_supplement(root, prompts_path, archive=TIER_ARCHIVE):
    """The xhigh/max/auto run with, per auto group, the tier the service reported for each request."""
    run = load_run(root, prompts_path, archive)
    if run is None:
        return None
    directory = root / archive
    results = json.loads((directory / "5way_v2_results.json").read_text("utf-8"))
    # Read from the response rather than inferred from tokens: an explicit tier always returns a fixed
    # token count, but auto's self-reported medium came back at both 439 and 781 tokens.
    echoed = {}
    for line in (directory / "attempts.jsonl").read_text("utf-8").splitlines():
        if line.strip():
            attempt = json.loads(line)
            if attempt.get("ok") and attempt.get("service_quality"):
                echoed[attempt["sample_id"]] = attempt["service_quality"]
    chosen, auto_tokens = {}, {}
    for row in results["raw_data"]:
        if not row["ok"] or row.get("quality") != "auto":
            continue
        tier = echoed.get(f"{row['group']}-r{row['round']}-p{row['prompt_idx']:02d}")
        if not tier:
            continue
        chosen.setdefault(row["group"], {}).setdefault(tier, 0)
        chosen[row["group"]][tier] += 1
        auto_tokens.setdefault(row["group"], {}).setdefault(tier, set()).add(
            (row.get("token_info") or {}).get("output_tokens"))
    run["auto_choices"] = chosen
    run["auto_tokens"] = {group: {tier: sorted(values) for tier, values in tiers.items()}
                          for group, tiers in auto_tokens.items()}
    return run


def load_text_study(root, archive, prompts_name, kind):
    """A Chinese/English text-rendering study, or None when it has not been archived yet."""
    directory = root / archive
    scoring = directory / "text-scoring.json"
    if not scoring.is_file():
        return None
    data = json.loads(scoring.read_text("utf-8"))
    prompts = []
    with (directory / prompts_name).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        next(reader)
        for row in reader:
            if row and row[0].strip():
                prompts.append({"prompt": row[0], "pair_id": row[1], "language": row[2],
                                "target": row[3], "chars": int(row[4]), "scene": row[5],
                                "tests": row[6] if len(row) > 6 else ""})
    calibration_path = directory / "judge-calibration" / "calibration.json"
    calibration = json.loads(calibration_path.read_text("utf-8")) if calibration_path.is_file() else None
    # Shards were archived under their own sub-directories; locate each sample's image once.
    subdirs = [p.name for p in directory.iterdir() if p.is_dir()]
    located = {}
    for sample in data["samples"]:
        if sample["group"].startswith(RETIRED_MODEL_PREFIX):
            continue
        hits = [sub for sub in subdirs if (directory / sub / sample["image"]).is_file()]
        if len(hits) != 1:
            raise ValueError(f"{archive}: image {sample['image']} of {sample['run']} found in {hits}")
        located[(sample["group"], sample["round"], sample["prompt_idx"])] = f"{hits[0]}/{sample['image']}"
    return {**data, "archive": archive, "prompts": prompts, "kind": kind, "prompts_name": prompts_name,
            "calibration": calibration, "image_paths": located}


def load_billing(root, archive=BILLING_ARCHIVE):
    path = root / archive / "effective-prices.json"
    if not path.is_file():
        return None
    return {**json.loads(path.read_text("utf-8")), "archive": archive}


# --------------------------------------------------------------------------------------------------
# Side-by-side images
# --------------------------------------------------------------------------------------------------

def scenario_record(run, prompt_index, prompt_text):
    matches = [item for item in run["summary"]["per_prompt"] if item["prompt_index"] == prompt_index]
    if len(matches) != 1 or matches[0]["prompt"] != prompt_text:
        raise ValueError(f"{run['archive']}: scenario {prompt_index} does not match the primary prompt")
    return matches[0]


def round_result(prompt_record, group, round_number):
    configuration = next((c for c in prompt_record["configurations"] if c["group"] == group), None)
    if configuration is None:
        raise ValueError(f"Scenario {prompt_record['prompt_index']} has no configuration {group}")
    matches = [row for row in configuration["rounds"] if row["round"] == round_number]
    if len(matches) != 1:
        raise ValueError("Every configuration must contain exactly one result for this round")
    return matches[0]


def image_table(cells, round_number, language, show_date=False):
    """One image row and one detail row; each cell names its archive so mixed sessions stay honest.

    cells: sequence of (label, run, prompt_record, group).
    """
    headers, images, details = [], [], []
    for label, run, prompt_record, group in cells:
        headers.append(f"{label}<br>({run['date']})" if show_date else label)
        row = round_result(prompt_record, group, round_number)
        if row["ok"]:
            expected = f"{group}/r{round_number}/{prompt_record['prompt_index']:02d}_test.png"
            if row["image"] != expected:
                raise ValueError("Displayed image does not belong to its configuration")
            alt = f"{label}, prompt {prompt_record['prompt_index']}, round {round_number}"
            images.append(f"![{alt}]({run['archive']}/{row['image']})")
            details.append(f"{row['request_seconds']:.2f} s<br>{row['image_kib']:.0f} KiB")
        else:
            if row["image"] is not None:
                raise ValueError("Failed sample cannot display a replacement image")
            images.append("未返回图片" if language == "zh" else "No image returned")
            details.append((f"{row['attempts']} 次尝试；任务耗时 {row['logical_request_seconds']:.2f} s"
                            if language == "zh" else
                            f"{row['attempts']} attempts; logical duration {row['logical_request_seconds']:.2f} s"))
    return table(headers, [images, details])


def other_tier_cells(primary, supplement, tier, prompt_record):
    """The shown GPT model's tiers that the same-session run did not include, in tier order."""
    cells = []
    for run in (supplement, tier):
        if not run:
            continue
        record = scenario_record(run, prompt_record["prompt_index"], prompt_record["prompt"])
        for group, label in zip(run["groups"], run["labels"]):
            if group.rsplit("-", 1)[0] == SHOWN_GPT_MODEL and group not in primary["groups"]:
                cells.append((label, run, record, group))
    cells.sort(key=lambda cell: TIER_ORDER.index(cell[3].rsplit("-", 1)[1]))
    return cells


def render_side_by_side(primary, supplement, tier, titles, language):
    chinese = language == "zh"
    heading = "## 并排图片对比" if chinese else "## Side-by-Side Image Comparison"
    shown = label_for({"provider": "gpt", "model": SHOWN_GPT_MODEL, "quality": ""}).strip()
    other_dates = "、".join(run["date"] for run in (supplement, tier) if run) if chinese else \
        " and ".join(run["date"] for run in (supplement, tier) if run)
    second_row_cn = (f"；第二行是 {shown} 其余档位，来自 {other_dates} 用同一客户端、同一提示词文件的测量，日期标在表头。两行不是同一时段，图下耗时要连带日期看。"
                     f"Sunburst 是同一模型的第二个部署，图片留在证据目录，数字在后面的档位表里" if other_dates else "")
    second_row_en = (f"; the second row is the remaining {shown} tiers, measured on {other_dates} with the same client and prompt file, dated in the "
                     f"header. The rows are not the same session, so read the latencies under the images together with their dates. Sunburst is a "
                     f"second deployment of the same model; its images stay in the evidence directory and its numbers are in the tier table below"
                     if other_dates else "")
    description = (
        f"第 1–11 题为文生图，每题两轮。每轮第一行是 {primary['date']} 同一会话交错调用的 {'、'.join(primary['labels'])}{second_row_cn}。"
        "点击图片查看原始 1024x1024 PNG。第 12 题为图像编辑，输入为一张真实照片。"
        if chinese else
        f"Scenarios 1-11 are text-to-image, two rounds each. In every round the first row is {', '.join(primary['labels'])}, called alternately "
        f"in one session on {primary['date']}{second_row_en}. Click an image for the original 1024x1024 PNG. Scenario 12 is an image edit of one "
        "real photograph.")
    sections = [heading, description]
    for prompt_record in primary["summary"]["per_prompt"]:
        index = prompt_record["prompt_index"]
        sections.extend([f"### Test {index}: {titles[index]}", "> **Prompt**: " + prompt_record["prompt"]])
        primary_cells = [(label, primary, prompt_record, group)
                         for label, group in zip(primary["labels"], primary["groups"])]
        others = other_tier_cells(primary, supplement, tier, prompt_record)
        for round_number in (1, 2):
            sections.extend([f"**Round {round_number}:**", image_table(primary_cells, round_number, language)])
            if others:
                sections.append(image_table(others, round_number, language, show_date=True))
    return sections


# --------------------------------------------------------------------------------------------------
# Masthead and highlights
# --------------------------------------------------------------------------------------------------

def total_samples(primary, supplement, tier, text_studies, edit, grounding):
    total = sum(run["summary"]["formal_samples"] for run in (primary, supplement, tier) if run)
    total += sum(study["scored_samples"] for study in text_studies if study)
    if edit:
        total += sum(len(r["outputs"]) for r in edit["rounds"])
    if grounding:
        total += grounding["planned_samples"]
    return total


def render_masthead(primary, author_line, language, data_through, test_count, sample_total):
    chinese = language == "zh"
    versions = {item["model_version"] for item in primary["summary"]["config"]["group_configurations"]
                if item.get("provider") == "mai" and item.get("model_version")}
    mai_version = sorted(versions)[0] if versions else "2026-07-31"
    badges = [
        ("Models", "MAI--Image--2.6%20vs%20GPT--Image--2.5", "0067b8",
         "https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai-image"),
        ("Samples", f"{sample_total}%20measured", "2e7d32", "data"),
        ("Resolution", "1024%C3%971024", "455a64", None),
        ("MAI version", mai_version.replace("-", "--"), "6a1b9a", None),
        ("Data through", data_through.replace("-", "--"), "37474f", None),
        ("Status", "Preview%20%C2%B7%20no%20SLA", "b26500",
         "https://azure.microsoft.com/support/legal/preview-supplemental-terms/"),
        ("Tests", f"{test_count}%20offline", "00695c", "tests"),
    ]
    rendered = []
    for label, value, colour, link in badges:
        image = f"https://img.shields.io/badge/{label.replace(' ', '%20')}-{value}-{colour}"
        rendered.append(f"[![{label}]({image})]({link})" if link else f"![{label}]({image})")
    scope = (
        f"MAI-Image-2.6 对 GPT-Image-2.5 的实测对比：同一客户端、同一账户、同一区域（{primary['region']}）。"
        f"主线是 {primary['date']} 的同会话运行——MAI 与 2.5 flare 的 medium、high 在 11 个文生图场景上交错调用两轮；"
        "其余档位、图像编辑、中英文文字渲染、账单成本和联网信息补充各有自己的小节与证据目录。"
        "所有画面判断为非盲评的差异描述，不产出质量评分或偏好胜负。"
        if chinese else
        f"A measured comparison of MAI-Image-2.6 against GPT-Image-2.5 from one client, one account and one region "
        f"({primary['region']}). The spine is the same-session run of {primary['date']}, in which MAI and 2.5 flare "
        "medium and high were called alternately over 11 text-to-image scenarios in two rounds; the remaining tiers, "
        "image editing, Chinese/English text rendering, invoice cost and web grounding each have their own section "
        "and evidence directory. Image judgements are unblinded difference descriptions and produce no quality score "
        "or preference verdict.")
    nav = " · ".join([
        f"[{'逐题图片' if chinese else 'Side-by-side images'}](#{'并排图片对比' if chinese else 'side-by-side-image-comparison'})",
        f"[{'图像编辑' if chinese else 'Image edit'}](#{'test-12-换帽子图像编辑' if chinese else 'test-12-headwear-swap-image-edit'})",
        f"[{'耗时与请求' if chinese else 'Latency and requests'}](#{'耗时与请求成功情况' if chinese else 'performance-and-reliability'})",
        f"[{'六个档位' if chinese else 'Six tiers'}](#{'gpt-image-25-的六个质量档位' if chinese else 'the-six-gpt-image-25-quality-tiers'})",
        f"[{'成本' if chinese else 'Cost'}](#{'每张图的实际成本来自本账户账单' if chinese else 'actual-cost-per-image-from-this-accounts-invoice'})",
        f"[{'文字渲染' if chinese else 'Text rendering'}](#{'中英文文字渲染' if chinese else 'chinese-and-english-text-rendering'})",
        f"[{'联网补测' if chinese else 'Web grounding'}](#{'联网信息补充测试' if chinese else 'web-grounding-test'})",
        f"[{'复现' if chinese else 'Reproduction'}](#reproduction-how-to)",
        f"[{'原始证据' if chinese else 'Raw evidence'}]({primary['archive']})",
    ])
    return "\n\n".join([" ".join(rendered), scope, f"> {author_line.lstrip('> ')}",
                        "[English](README.md) | [中文](README-CN.md)", nav, "---"])


def relation(ratio, chinese):
    """Within ±5% the two are indistinguishable at this sample size."""
    if abs(ratio - 1) <= 0.05:
        return "持平" if chinese else "level"
    if ratio > 1:
        return f"MAI 慢 {ratio:.2f} 倍" if chinese else f"MAI {ratio:.2f}x slower"
    return f"MAI 快 {1 / ratio:.2f} 倍" if chinese else f"MAI {1 / ratio:.2f}x faster"


def p50_by_group(run):
    return {group["group"]: (group.get("successful_request_latency") or {}).get("p50_seconds")
            for group in run["summary"]["groups"]}


def text_misses(study):
    """Configurations (retired GPT-Image-2 excluded) that missed an exact segment, with the pairs."""
    misses = {}
    for sample in study["samples"]:
        if sample["group"].startswith(RETIRED_MODEL_PREFIX):
            continue
        if sample["exact_segments"] < sample["segments"]:
            misses.setdefault(sample["group"], set()).add(f"{sample['pair_id']} {sample['language']} r{sample['round']}")
    return {group: sorted(items) for group, items in sorted(misses.items())}


def render_highlights(primary, supplement, billing, hard_study, edit, has_grounding, language):
    chinese = language == "zh"
    p50 = p50_by_group(primary)
    mai, med, high = p50.get("mai-image-2.6"), p50.get(f"{SHOWN_GPT_MODEL}-medium"), p50.get(f"{SHOWN_GPT_MODEL}-high")
    low = p50_by_group(supplement).get(f"{SHOWN_GPT_MODEL}-low") if supplement else None
    returned, planned = primary["summary"]["successful_samples"], primary["summary"]["formal_samples"]
    items = []
    if None not in (mai, med, high):
        low_cn = f" 2.5 low 在 {supplement['date']} 自己的会话里 P50 {low:.2f} s，快于 MAI，但不是同一时段。" if low else ""
        low_en = f" 2.5 low, in its own session on {supplement['date']}, had a P50 of {low:.2f} s, faster than MAI but not the same session." if low else ""
        items.append(
            (f"**同一会话里，MAI 的出图速度与 2.5 high 持平、慢于 2.5 medium。** {returned}/{planned} 个样本返回图片；"
             f"P50：MAI {mai:.2f} s，2.5 medium {med:.2f} s（{relation(mai / med, True)}），2.5 high {high:.2f} s（{relation(mai / high, True)}）。"
             f"三组由同一客户端交错调用，没有区域或日期差。{low_cn}"
             if chinese else
             f"**In one session, MAI is level with 2.5 high on speed and slower than 2.5 medium.** {returned}/{planned} "
             f"samples returned images; P50: MAI {mai:.2f} s, 2.5 medium {med:.2f} s ({relation(mai / med, False)}), "
             f"2.5 high {high:.2f} s ({relation(mai / high, False)}). The three were called alternately by one client, "
             f"with no region or date difference.{low_en}"))
    if billing:
        per = billing["usd_per_1000_images"]
        mai_cost, low_cost, med_cost, high_cost = (per["MAI-Image-2.6"], per["gpt-image-2.5 low"], per["gpt-image-2.5 medium"],
                                                    per["gpt-image-2.5 high"])
        items.append(
            (f"**按本账户账单，MAI 每千张 ${mai_cost:.2f}：是 2.5 low（${low_cost:.2f}）的 {mai_cost / low_cost:.1f} 倍、"
             f"2.5 medium（${med_cost:.2f}）的 {mai_cost / med_cost:.1f} 倍，比 2.5 high（${high_cost:.2f}）便宜 {1 - mai_cost / high_cost:.0%}。** "
             "单价来自 Azure Cost Management 的实际计费，不是定价页；2.5 尚无公布价。「贵」只有先说清对比档位才成立；各档的画面差异在并排图里。"
             if chinese else
             f"**On this account's invoice, MAI costs ${mai_cost:.2f} per 1,000 images: {mai_cost / low_cost:.1f}x 2.5 low (${low_cost:.2f}), "
             f"{mai_cost / med_cost:.1f}x 2.5 medium (${med_cost:.2f}) and {1 - mai_cost / high_cost:.0%} less than 2.5 high (${high_cost:.2f}).** "
             "Rates come from Azure Cost Management actuals, not a price page; 2.5 has no published price. \"Expensive\" only holds once "
             "the comparison tier is named; what each tier's images look like is in the side-by-side tables."))
    if hard_study:
        misses = text_misses(hard_study)
        mai_stats = hard_study["summary"].get("mai-image-2.6", {})
        mai_ok = all(mai_stats.get(lang, {}).get("exact_rate") == 1 for lang in ("en", "zh"))
        shown_miss = {g: v for g, v in misses.items() if g.rsplit("-", 1)[0] == SHOWN_GPT_MODEL}
        miss_text_cn = "；".join(f"{group_label(g)} 漏 {len(v)} 处（{'、'.join(v)}）" for g, v in shown_miss.items()) or "flare 六档全部满分"
        miss_text_en = "; ".join(f"{group_label(g)} missed {len(v)} ({', '.join(v)})" for g, v in shown_miss.items()) or "every flare tier scored 100%"
        items.append(
            (f"**难题集文字渲染：MAI 中英文{'都 100%' if mai_ok else '未全对'}，含简繁体陷阱。** 6 个场景 × 2 语言 × 2 轮，"
             f"由校准过的视觉判读器读回：{miss_text_cn}。官方文档把 MAI 的 Languages 标为 `en`，中文结果是声明范围之外的观察。"
             if chinese else
             f"**Hard-set text rendering: MAI scores {'100% in both languages' if mai_ok else 'below 100%'}, including the "
             f"simplified-vs-traditional trap.** 6 scenes × 2 languages × 2 rounds, read back by a calibrated vision judge: "
             f"{miss_text_en}. The documentation lists MAI's Languages as `en`; the Chinese result is an observation outside "
             "that declared scope."))
    if edit:
        outputs = [o for r in edit["rounds"] for o in r["outputs"]]
        all_kept = all(o["preserved_count"] == o["preserved_total"] for o in outputs)
        sizes = {o["group"]: f"{o['width']}×{o['height']}" for o in outputs}
        mai_size = sizes.get("mai-image-2.6", "")
        gpt_size = next((v for g, v in sizes.items() if g != "mai-image-2.6"), "")
        items.append(
            (f"**图像编辑：{'三个配置两轮都换上博士帽并保住全部 5 个保持项' if all_kept else '并非每张输出都保住全部保持项'}。** "
             f"MAI 输出（{mai_size}）色彩与取景几乎等同原图，像只重绘了头部；2.5（{gpt_size}）是整幅重生成，构图保持但纹理重绘，"
             "2.5 medium 两轮都把标题 ADVISORS 拼成 ASVISORS。逐图清单见第 12 题。"
             if chinese else
             f"**Image edit: {'all three configurations add the graduation cap and keep all 5 preservation items in both rounds' if all_kept else 'not every output kept every preservation item'}.** "
             f"MAI's output ({mai_size}) matches the input in colour and framing and reads as a head-only repaint; 2.5 "
             f"({gpt_size}) regenerates the whole frame, keeping composition but re-rendering texture, and 2.5 medium "
             "misspells the title ADVISORS as ASVISORS in both rounds. Per-image checklist in Scenario 12."))
    if has_grounding:
        items.append(
            ("**`web_grounding=true` 可以在生成时补充联网信息。** 开启后模型从 Bing Search 检索当前信息作为额外上下文，"
             "实测让两个题目的产品文字事实从错误变为与官方发布一致；代价是首试成功率下降、耗时明显上升。这是 MAI 独有参数，无 GPT 对照。"
             if chinese else
             "**`web_grounding=true` adds current web information at generation time.** The model retrieves current "
             "information from Bing Search as extra context, which moved the product text facts in two subjects from "
             "wrong to matching the official announcement; the cost is a lower first-attempt success rate and clearly "
             "higher latency. This is a MAI-only parameter with no GPT counterpart."))
    heading = "## 本仓库实测说明了什么" if chinese else "## What the Measurements Show"
    scope = (f"以下 {len(items)} 条都只依据本仓库的实测记录；MAI-Image-2.6 处于 Preview，无 SLA。画质没有数值分数：并排图是证据，读者的判断是结论。"
             if chinese else
             f"All {len(items)} items rest on the measurements in this repository; MAI-Image-2.6 is in preview with no SLA. "
             "Image quality has no numeric score: the side-by-side images are the evidence and the reader's judgement is the conclusion.")
    return "\n\n".join([heading, scope] + [f"{index}. {text}" for index, text in enumerate(items, 1)])


# --------------------------------------------------------------------------------------------------
# Test 12: image edit
# --------------------------------------------------------------------------------------------------

def render_edit_scenario(edit, archive_path, language):
    """One real photo, one requested change, every configuration; judged on checkable preservation items."""
    chinese = language == "zh"
    rounds = edit["rounds"]
    source = edit["source"]
    groups = edit["groups"]
    labels = [group_label(g) for g in groups]
    gpt_size = edit.get("gpt_size_parameter") or "auto"
    deployment = edit.get("gpt_deployment", "gpt-image-2.5-flare")
    lead = (
        f"前 11 题都是纯文生图。第 12 题改为图像编辑：把同一张真实照片交给 {len(groups)} 个配置的编辑接口，"
        f"只要求改一处，并明确列出必须保持不变的内容。因此每张输出都能按清单逐项核对，不需要审美打分。"
        f"与前 11 题相同，本题跑 {len(rounds)} 轮，第二轮配置顺序反转。"
        if chinese else
        f"The first eleven scenarios are pure text-to-image. Scenario 12 switches to image editing: the same real "
        f"photograph goes to each of the {len(groups)} configurations' edit endpoints with a prompt that asks for "
        f"exactly one change and lists what must stay the same, so every output can be checked item by item without "
        f"an aesthetic score. As in the first eleven scenarios it runs {len(rounds)} rounds, with the configuration "
        f"order reversed in round 2.")
    input_note = (
        f"输入为一张 {source['width']}x{source['height']} 的 JPEG 照片（{source['bytes']:,} 字节，"
        f"SHA-256 `{source['sha256'][:16]}…`）：前景人物头戴冕冠，身着刺绣龙袍，左侧持戈侍卫，"
        "右侧紫衣人物与门廊建筑，左上角有剧名标题与印章。"
        if chinese else
        f"The input is one {source['width']}x{source['height']} JPEG photograph ({source['bytes']:,} bytes, "
        f"SHA-256 `{source['sha256'][:16]}…`): a foreground figure in a crown and embroidered robe, spear-bearing "
        "guards on the left, a purple-robed figure and gallery on the right, and a title with a seal in the top-left.")
    prompt_line = f"**{'提示词（逐字）' if chinese else 'Prompt (verbatim)'}**"
    prompt_quote = "> " + edit["prompt"]
    controlled = (
        f"MAI 走 `/mai/v1/images/edits`，GPT 走 `/openai/deployments/{deployment}/images/edits`。GPT 各档只在 `quality` 上不同，"
        f"`size` 传 `{gpt_size}` 由服务自选输出尺寸；MAI 编辑接口没有尺寸参数，同样由服务自选。两边因此处于同一契约：都没有被要求固定尺寸。"
        f"每轮每个配置各调用一次，共 {len(rounds)} 轮，同一账户同一区域同一会话。"
        if chinese else
        f"MAI uses `/mai/v1/images/edits` and GPT uses `/openai/deployments/{deployment}/images/edits`. The GPT tiers differ "
        f"only in `quality` and pass `size={gpt_size}`, so the service chooses the output dimensions; the MAI edit endpoint "
        "has no size parameter and the service likewise chooses. Both sides are therefore under the same contract: neither "
        f"was told to produce a fixed size. Each configuration was called once per round over {len(rounds)} rounds, on one "
        "account, in one region, in one session per round.")
    check_labels = [
        ("headwear_replaced_with_graduation_cap", "换成博士帽" if chinese else "Headwear became a graduation cap"),
        ("face_and_beard_preserved", "人脸与胡须保留" if chinese else "Face and beard preserved"),
        ("robe_embroidery_preserved", "龙袍纹样保留" if chinese else "Robe embroidery preserved"),
        ("bystanders_and_background_unchanged", "侍卫与背景不变" if chinese else "Bystanders and background unchanged"),
        ("title_and_seal_preserved", "标题与印章保留" if chinese else "Title and seal preserved"),
        ("input_aspect_ratio_preserved", "保持原图宽高比" if chinese else "Input aspect ratio kept"),
    ]
    yes, no = ("是", "否") if chinese else ("yes", "no")
    input_image = table([("输入图" if chinese else "Input photograph")],
                        [[f"![Input photograph]({archive_path}/{source['file']})"]])
    round_blocks = []
    for round_item in rounds:
        by_group = {item["group"]: item for item in round_item["outputs"]}
        n = round_item["round"]
        images = table(labels, [
            [f"![{label}, edit round {n}]({archive_path}/{by_group[g]['output']})" for g, label in zip(groups, labels)],
            [f"{by_group[g]['request_seconds']:.2f} s<br>{by_group[g]['output_kib']:.0f} KiB<br>"
             f"{by_group[g]['width']}x{by_group[g]['height']}" for g in groups],
        ])
        check_rows = [[("保持项命中" if chinese else "Preservation items kept"),
                       *(f"{by_group[g]['preserved_count']}/{by_group[g]['preserved_total']}" for g in groups)]]
        for key, label in check_labels:
            check_rows.append([label, *(yes if by_group[g]["checks"][key] else no for g in groups)])
        checks = table([("核对项" if chinese else "Checklist"), *labels], check_rows)
        prose = table([("配置" if chinese else "Configuration"), ("画面观察" if chinese else "Observation")],
                      [[label, by_group[g]["observation"][language]] for g, label in zip(groups, labels)])
        round_blocks.extend([f"**{'第' + str(n) + '轮' if chinese else 'Round ' + str(n)}:**", images, checks, prose])
    per_group_kept = {g: [item["preserved_count"] for r in rounds for item in r["outputs"] if item["group"] == g]
                      for g in groups}
    total = rounds[0]["outputs"][0]["preserved_total"]
    kept_summary = table(
        [("跨轮汇总" if chinese else "Across rounds"), *labels],
        [[("保持项命中（每轮）" if chinese else "Items kept (per round)"),
          *(" / ".join(f"{k}/{total}" for k in per_group_kept[g]) for g in groups)],
         [("请求耗时（每轮）" if chinese else "Latency per round"),
          *(" / ".join(f"{item['request_seconds']:.2f} s" for r in rounds for item in r["outputs"] if item["group"] == g)
            for g in groups)]])
    reading = edit.get("summary_observation", {}).get(language)
    if not reading:
        raise ValueError("The edit review must carry a bilingual summary observation")
    boundary = (
        f"共 {len(rounds)} 轮，每轮每个配置一次调用，两轮只说明结果是否重复出现，不构成统计样本；观察为非盲评，只描述与原图的差异，不是画质评分。"
        "每张输出都是重新生成，「保留」指元素在位且可辨，不是像素相同。耗时为客户端 `requests.post` 往返时间。输出 PNG 均无 alpha 通道。"
        if chinese else
        f"{len(rounds)} rounds with one call per configuration per round; two rounds show whether the outcome repeats and "
        "are not a statistical sample. Observations are unblinded and describe departures from the input, not image "
        "quality. Every output is a regeneration: 'preserved' means present, in place and recognisable, not pixel-identical. "
        "Latency is client-side `requests.post` round-trip time. No output PNG carries an alpha channel.")
    links = []
    for round_item in rounds:
        sub = "" if round_item["round"] == 1 else f"r{round_item['round']}/"
        tag = (f"第{round_item['round']}轮" if chinese else f"round {round_item['round']}")
        links.append(f"[{'请求记录' if chinese else 'Request records'} {tag}]({archive_path}/{sub}edit-results.json)")
        links.append(f"[{'逐图核对' if chinese else 'Per-image checklist'} {tag}]({archive_path}/{sub}edit-review.json)")
    if (Path(__file__).resolve().parents[1] / archive_path / "review-compact.png").is_file():
        links.append(f"[{'标题区域对照图' if chinese else 'Title-corner contact sheet'}]({archive_path}/review-compact.png)")
    links.append(f"[{'公开复现脚本' if chinese else 'Public reproduction runner'}](scripts/run_edit_hat_swap.py)")
    title = "### Test 12: 换帽子（图像编辑）" if chinese else "### Test 12: Headwear Swap (Image Edit)"
    return "\n\n".join([title, lead, input_note, prompt_line, prompt_quote,
                        f"**{'受控变量' if chinese else 'Controlled variables'}**", controlled, input_image,
                        *round_blocks, kept_summary, f"**{'怎么读' if chinese else 'How to read this'}**: {reading}",
                        boundary, " | ".join(links)])


# --------------------------------------------------------------------------------------------------
# Primary metrics
# --------------------------------------------------------------------------------------------------

def metrics_table(run, language):
    definitions = [
        ("成功 / 计划样本", "Successful / planned samples", lambda g: f"{g['successful_samples']} / {g['planned_samples']}"),
        ("首试成功 / 计划样本", "First-attempt successes / planned", lambda g: f"{g['first_attempt_successful_samples']} / {g['planned_samples']}"),
        ("HTTP 尝试次数 / 429", "HTTP attempts / 429 responses", lambda g: f"{g['formal_http_attempts']} / {g['http_429_attempts']}"),
        ("平均请求耗时 (s)", "Mean request latency (s)", lambda g: number((g['successful_request_latency'] or {}).get('mean_seconds'))),
        ("P50 / 描述性 P95 (s)", "P50 / descriptive P95 (s)", lambda g: number((g['successful_request_latency'] or {}).get('p50_seconds')) + " / " + number((g['successful_request_latency'] or {}).get('p95_seconds'))),
        ("样本标准差 (s)", "Sample standard deviation (s)", lambda g: number((g['successful_request_latency'] or {}).get('sample_stddev_seconds'))),
        ("最小 / 最大请求耗时 (s)", "Minimum / maximum request latency (s)", lambda g: number((g['successful_request_latency'] or {}).get('minimum_seconds')) + " / " + number((g['successful_request_latency'] or {}).get('maximum_seconds'))),
        ("第一轮 / 第二轮平均 (s)", "Round 1 / round 2 mean (s)", lambda g: " / ".join(number(item['latency']['mean_seconds']) if item['latency'] else "N/A" for item in g['per_round'])),
        ("全部样本平均任务耗时 (s)", "Mean logical duration, all samples (s)", lambda g: number(g['logical_request_latency_all_samples']['mean_seconds'])),
        ("返回的输出 token", "Returned output tokens", lambda g: str(g['returned_output_tokens'][0]) if len(g['returned_output_tokens']) == 1 else "N/A"),
        ("成功图片平均大小 (KiB)", "Mean successful PNG size (KiB)", lambda g: number(g['mean_image_kib'], 0)),
    ]
    rows = [[zh if language == "zh" else en, *(value(group) for group in run["summary"]["groups"])]
            for zh, en, value in definitions]
    return table(["指标" if language == "zh" else "Metric", *run["labels"]], rows)


def prompt_latency_table(run, language):
    rows = []
    for prompt_record in run["summary"]["per_prompt"]:
        for round_number in (1, 2):
            values = [round_result(prompt_record, group, round_number) for group in run["groups"]]
            rows.append([f"{prompt_record['prompt_index']:02d} / R{round_number}",
                         *(f"{row['request_seconds']:.2f}" if row["ok"] else ("失败" if language == "zh" else "Failed")
                           for row in values)])
    return table(["场景 / 轮次" if language == "zh" else "Scenario / round", *run["labels"]], rows)


def exception_section(run, language):
    attempts = list(run["summary"]["unsuccessful_attempts"])
    if not attempts:
        return "本轮未记录失败尝试。" if language == "zh" else "No unsuccessful attempts were recorded."
    headers = (["样本", "尝试", "HTTP / 异常类型", "客户端耗时 (s)", "开始 (UTC)", "结束 (UTC)"] if language == "zh" else
               ["Sample", "Attempt", "HTTP / exception", "Client duration (s)", "Started (UTC)", "Finished (UTC)"])
    rows = [[a["sample_id"], str(a["attempt"]), a["exception_type"] or str(a["http_status"]), number(a["request_seconds"]),
             a["started_at_utc"], a["finished_at_utc"]] for a in attempts]
    text = ("异常保留在任务耗时、请求计数和实际完成速率中，未返回图片的样本仍计入计划分母。" if language == "zh" else
            "Exceptions remain in logical durations, attempt counts and observed completion rate; missing-image samples remain in the planned denominator.")
    return text + "\n\n" + table(headers, rows)


def render_overview(primary, supplement, tier, billing, edit, text_studies, grounding, language):
    chinese = language == "zh"
    summary = primary["summary"]
    coverage = tier_coverage(summary, supplement["summary"] if supplement else None, tier["summary"] if tier else None)
    heading = lambda en, zh: zh if chinese else en
    contract_rows = [[label, item.get("model_version") or "not recorded", item["quality"] or ("未传入" if chinese else "omitted"),
                      "1024x1024", item.get("deployment_region") or "not recorded", str(group["planned_samples"]), primary["date"]]
                     for label, item, group in zip(primary["labels"], summary["config"]["group_configurations"], summary["groups"])]
    contract = table(["配置" if chinese else "Configuration", "模型版本" if chinese else "Model version",
                      "质量参数" if chinese else "Quality field", "尺寸" if chinese else "Dimensions",
                      "区域" if chinese else "Resource region", "正式样本" if chinese else "Formal samples",
                      "测量日期" if chinese else "Measured on"], contract_rows)
    pacing = summary["config"].get("rate_pacing") or {}
    procedure = (
        f"输入是同一份 11 题 CSV。每组先用 `blue circle` 预热一次；第一轮每题依次调用 {'、'.join(primary['labels'])}，第二轮反转。"
        f"并发为 1，每次逻辑调用后间隔 5 秒，最多尝试 3 次并退避。两个部署都是 GlobalStandard、每分钟 2 次请求；"
        f"为了不触发自己的配额，同一部署任意 {pacing.get('window_seconds', 60)} 秒内最多起请 {pacing.get('max_requests', 2)} 次，等待时长逐样本记在 `pacing_wait_seconds`，不进入请求耗时。"
        "MAI 请求超时 180 秒，GPT 为 900 秒。"
        if chinese else
        f"The input is the same eleven-prompt CSV. Each configuration receives one `blue circle` warmup; round 1 calls "
        f"{', '.join(primary['labels'])} in that order for every prompt, round 2 reverses it. Concurrency is 1 with 5 seconds after "
        f"each logical call, at most 3 attempts with backoff. Both deployments are GlobalStandard at 2 requests per minute; to stay "
        f"inside that quota the client starts at most {pacing.get('max_requests', 2)} requests per {pacing.get('window_seconds', 60)} seconds "
        "per deployment, recording the wait per sample as `pacing_wait_seconds`, excluded from request latency. Request timeouts "
        "are 180 seconds for MAI and 900 for GPT.")
    timing = ("请求耗时从 `requests.post` 调用前到完整 HTTP 响应返回，只统计有图片的成功尝试，不含 JSON/base64 处理和写盘。任务耗时覆盖失败尝试、重试等待和响应处理，按全部计划样本统计。"
              "失败不以 0 秒进入平均值，也不从成功率分母删除。P95 为每组最多 22 个值的描述性线性插值，不是生产尾延迟保证。token 用量取自接口返回的 usage；输出 token 数和 PNG 大小都不能单独证明画质。"
              if chinese else
              "Request latency measures `requests.post` through receipt of the complete HTTP response, for successful image-producing "
              "attempts only, before JSON/base64 processing and file writes. Logical duration includes failed attempts, retry waits and "
              "response processing across all planned samples. Failures are not averaged as zero-second responses or removed from the "
              "success-rate denominator. P95 is descriptive linear interpolation over at most 22 observations per group, not a production "
              "tail guarantee. Token counts come from returned usage; neither output tokens nor PNG size establishes image quality on its own.")
    api = table(["接口项目" if chinese else "API item", "MAI-Image-2.6", "GPT-Image-2.5"], [
        ["POST", "`/mai/v1/images/generations`", "`/openai/deployments/{deployment}/images/generations?api-version=2025-04-01-preview`"],
        ["Payload", "`model`, `prompt`, `width=1024`, `height=1024`", "`prompt`, `n=1`, `size=1024x1024`, `quality=<tier>`"],
        ["Auth", "`api-key`", "`api-key`"],
        ["Output", "`data[0].b64_json`, PNG", "`data[0].b64_json`, PNG"],
        ["Usage", "`usage.num_input_text_tokens`, `usage.num_output_tokens`", "`usage.input_tokens_details`, `usage.output_tokens_details`"],
    ])
    absent = sorted({t for tiers in coverage["missing"].values() for t in tiers}, key=TIER_ORDER.index)
    absent_cn = f"；2.5 另有 {'、'.join(absent)} 档本报告没有测" if absent else ""
    absent_en = f"; 2.5 also offers {', '.join(absent)}, which were not run" if absent else ""
    retired = ", ".join(f"[{a}]({a})" for a in RETIRED_ARCHIVES if (Path(__file__).resolve().parents[1] / a).is_dir())
    shown_tiers = sorted(coverage["measured"].get(SHOWN_GPT_MODEL, []), key=TIER_ORDER.index)
    limits = (
        f"本报告只对比 MAI-Image-2.6 与 GPT-Image-2.5（flare 与 sunburst 两个部署，{'、'.join(shown_tiers)} 档）{absent_cn}。"
        "耗时与并排图的主线来自同一会话；其余档位来自另外两个日期的会话，表头带日期。MAI 没有传质量参数，不能称为任何 GPT 档位的等价档。"
        "11 个场景没有逐图文字评述，画质由读者从并排图判断；文字准确率只覆盖后文两节列出的场景与字符。不覆盖 2K、多图参考、并发压测或其他认证方式。"
        f"本报告早先版本对比的是 GPT-Image-2；那些归档仍保留为证据（{retired}），不进入任何表格。"
        if chinese else
        f"This report compares only MAI-Image-2.6 with GPT-Image-2.5 (the flare and sunburst deployments at "
        f"{', '.join(shown_tiers)}){absent_en}. The latency and side-by-side spine comes from one "
        "session; the remaining tiers come from sessions on two other dates and carry their dates in the headers. MAI sends no quality "
        "parameter and is not labeled as equivalent to any GPT tier. The eleven scenarios carry no per-image prose review; image quality "
        "is for the reader to judge from the side-by-side images, and exact-text accuracy covers only the scenes and characters listed in "
        "the two text-rendering sections. Not covered: 2K, multiple reference images, concurrency capacity or other authentication modes. "
        f"Earlier versions of this report compared GPT-Image-2; those archives remain as evidence ({retired}) and feed no table.")
    body = f"""## {heading('Same-Session Run: MAI-Image-2.6 vs GPT-Image-2.5', '同会话运行：MAI-Image-2.6 对 GPT-Image-2.5')}

[{'逐题图片' if chinese else 'Side-by-side images'}](#{'并排图片对比' if chinese else 'side-by-side-image-comparison'}) | [{'测量记录' if chinese else 'Measurements'}]({primary['archive']}/5way_v2_results.json) | [{'指标' if chinese else 'Metrics'}]({primary['archive']}/summary.json) | [{'请求记录' if chinese else 'Attempts'}]({primary['archive']}/attempts.jsonl)

**{'本轮' if chinese else 'This run returned images for'} {summary['successful_samples']}/{summary['formal_samples']} {'个正式样本返回图片' if chinese else 'formal samples'}{'，' if chinese else '; '}{summary['failed_samples']} {'个未返回；另有' if chinese else 'returned no image; the'} {summary['warmup_samples']} {'次预热不计入分母。' if chinese else 'warmups are excluded from the denominator.'}** {'三组由同一客户端在同一区域交错调用，耗时差可以直接比较；画质没有数值分数，见并排图。' if chinese else 'The three configurations were called alternately by one client in one region, so latency differences are directly comparable; image quality has no numeric score, see the side-by-side images.'}

### {heading('Test Contract', '测试口径')}

{contract}

{procedure}

{'客户端' if chinese else 'Client'}: {summary['environment']['platform']}, {summary['environment']['architecture']}, Python {summary['environment']['python']}, requests {summary['environment']['requests']}. {'正式起止时间 (UTC)' if chinese else 'Formal interval (UTC)'}: `{summary['formal_started_at_utc']}` – `{summary['formal_ended_at_utc']}`.

```mermaid
flowchart LR
    prompts["Original 11 prompts"] --> runner["Local Windows Python runner"]
    runner --> mai["MAI-Image-2.6 / {primary['region']}"]
    runner --> gpt["GPT-Image-2.5 flare / {primary['region']} / medium, high"]
    mai --> evidence["PNG, usage, request IDs, timestamps, failures"]
    gpt --> evidence
    evidence --> summary["Offline validation and report"]
```

### {heading('Performance and Reliability', '耗时与请求成功情况')}

{metrics_table(primary, language)}

{timing}

### {heading('Exceptions and Waiting', '异常与等待')}

{exception_section(primary, language)}

### {heading('Every Scenario, Both Rounds', '逐场景两轮耗时')}

{'单位为秒；失败格对应原始请求记录，不用其他轮次替换。' if chinese else 'Seconds; failed cells remain tied to their original requests and are not replaced by another round.'}

{prompt_latency_table(primary, language)}

### {heading('Measured API Settings', '本轮实际接口设置')}

{api}

{reproduction_section(primary, supplement, tier, edit, grounding, text_studies, billing, language)}

### {heading('Limits', '结论边界')}

{limits}

{'证据目录' if chinese else 'Evidence directory'}: [{primary['archive']}]({primary['archive']}). {'含原始图片、测量记录、逐次请求、响应元数据和执行时的源码副本；' if chinese else 'Original images, measurement records, attempts, response metadata and the source snapshot that ran; '}{'提示词 SHA-256' if chinese else 'prompt SHA-256'}: `{summary['prompts_sha256']}`.
"""
    return body


# --------------------------------------------------------------------------------------------------
# The six 2.5 tiers
# --------------------------------------------------------------------------------------------------

def render_tier_section(supplement, tier, language):
    """The six 2.5 tiers as one row per configuration, transposed because twelve columns do not read."""
    chinese = language == "zh"
    pairs = list(zip(supplement["labels"], supplement["summary"]["groups"]))
    pairs += list(zip(tier["labels"], tier["summary"]["groups"]))
    order = {name: index for index, name in enumerate(TIER_ORDER)}
    pairs.sort(key=lambda item: (item[0].rsplit(" ", 1)[0], order.get(item[0].rsplit(" ", 1)[1], 9)))
    rows = []
    for label, group in pairs:
        latency = group["successful_request_latency"] or {}
        tokens = group["returned_output_tokens"]
        token_text = str(tokens[0]) if len(tokens) == 1 else (f"{min(tokens)}–{max(tokens)}" if tokens else "N/A")
        choices = tier["auto_choices"].get(group["group"])
        if choices:
            picked = []
            for name, count in sorted(choices.items(), key=lambda item: -item[1]):
                values = tier["auto_tokens"].get(group["group"], {}).get(name, [])
                suffix = f" [{'/'.join(str(value) for value in values)}]" if len(values) > 1 else ""
                picked.append(f"{name} x{count}{suffix}")
            token_text += f" ({', '.join(picked)})"
        rows.append([label, f"{group['successful_samples']} / {group['planned_samples']}", token_text,
                     number(latency.get("mean_seconds")), number(latency.get("p50_seconds")),
                     number(latency.get("p95_seconds")), number(group["mean_image_kib"], 0)])
    headers = (["配置", "成功 / 计划", "返回的输出 token", "平均耗时 (s)", "P50 (s)", "描述性 P95 (s)", "平均 PNG (KiB)"]
               if chinese else
               ["Configuration", "Successful / planned", "Returned output tokens", "Mean latency (s)",
                "P50 (s)", "Descriptive P95 (s)", "Mean PNG (KiB)"])
    heading = "## GPT-Image-2.5 的六个质量档位" if chinese else "## The Six GPT-Image-2.5 Quality Tiers"
    intro = (f"`gpt-image-2.5-flare` 和 `gpt-image-2.5-sunburst` 接受六个质量档位。low、medium、high 来自 {supplement['date']} 的运行，"
             f"xhigh、max、auto 来自 {tier['date']} 的运行，两次使用同一客户端、同一提示词文件和同一部署，区域 {supplement['region']}。"
             "显式指定某一档时，输出 token 是固定值，两个部署完全一致；`auto` 不是这样，见表下说明。这两次与上一节不是同一会话，跨节比耗时要连带日期。"
             if chinese else
             f"`gpt-image-2.5-flare` and `gpt-image-2.5-sunburst` accept six quality tiers. low, medium and high come from the "
             f"{supplement['date']} run and xhigh, max and auto from the {tier['date']} run, both using the same client, prompt file and "
             f"deployments in {supplement['region']}. When a tier is requested explicitly its output-token count is constant and identical "
             "across the two deployments; `auto` behaves differently, as noted below the table. Neither run is the same session as the "
             "previous section, so compare latencies across sections together with their dates.")
    explicit_tokens = {}
    for label, group in zip(supplement["labels"], supplement["summary"]["groups"]):
        explicit_tokens.setdefault(label.rsplit(" ", 1)[1], set()).update(group["returned_output_tokens"])
    for label, group in zip(tier["labels"], tier["summary"]["groups"]):
        name = label.rsplit(" ", 1)[1]
        if name != "auto":
            explicit_tokens.setdefault(name, set()).update(group["returned_output_tokens"])
    extra = sorted({token for tiers in tier["auto_tokens"].values() for name, values in tiers.items()
                    for token in values if token not in explicit_tokens.get(name, set())})
    divergence_cn = divergence_en = ""
    if extra:
        listed = "、".join(str(token) for token in extra)
        divergence_cn = (f"另外，`auto` 自报为某一档时，返回的 output token 不一定等于显式请求该档时的固定值：本轮出现了 {listed} 这样的值，"
                         "而显式请求同一档位在 22/22 个样本上都返回同一个固定值。也就是说 `auto` 并不等同于替你选了某个档位，它的开销无法由自报档位推算。")
        divergence_en = (f" Moreover, when `auto` reports a tier, the returned output-token count is not necessarily the fixed value that "
                         f"tier returns when requested explicitly: this run produced {', '.join(str(token) for token in extra)}, while every "
                         "explicitly requested tier returned one constant across all 22 of its samples. `auto` is therefore not equivalent to "
                         "selecting that tier, and its cost cannot be derived from the tier it reports.")
    auto_note = ("`auto` 不是一个固定档位。服务按请求自行选择，并在响应里回显它实际使用的档位。上表的 `auto` 行在括号中列出服务自报的档位及次数，取自响应字段。"
                 + divergence_cn + "因此 `auto` 的耗时和 token 反映的是服务的选择行为，不能当作一个质量水平来比较。"
                 if chinese else
                 "`auto` is not a fixed tier. The service chooses per request and echoes the tier it used; the `auto` rows list, in parentheses, "
                 "the tiers the service reported and how often, taken from the response field." + divergence_en +
                 " Their latency and token figures therefore describe the service's selection behaviour, not one quality level.")
    evidence = (f"证据目录：[{supplement['archive']}]({supplement['archive']})、[{tier['archive']}]({tier['archive']})。" if chinese else
                f"Evidence directories: [{supplement['archive']}]({supplement['archive']}), [{tier['archive']}]({tier['archive']}).")
    return "\n\n".join([heading, intro, table(headers, rows), auto_note, evidence])


# --------------------------------------------------------------------------------------------------
# Cost
# --------------------------------------------------------------------------------------------------

def render_cost_section(billing, language):
    chinese = language == "zh"
    prices = billing["usd_per_million_output_image_tokens"]
    per_image = {k: v for k, v in billing["usd_per_1000_images"].items() if not k.startswith("gpt-image-2 ")}
    tokens = billing["tokens_per_1024_image"]
    mai_cost = per_image["MAI-Image-2.6"]
    heading = "## 每张图的实际成本（来自本账户账单）" if chinese else "## Actual Cost per Image, from This Account's Invoice"
    question = ("**问题**：MAI-Image-2.6 到底贵不贵。答案取决于跟 2.5 的哪个质量档位比，而档位之间的算力相差 36 倍。"
                if chinese else
                "**Question**: is MAI-Image-2.6 expensive? The answer depends on which 2.5 quality tier it is compared against, "
                "and the tiers differ by 36x in billed compute.")
    source = (f"**数据来源**：Azure Cost Management 对运行本仓库全部测试的账户（Sweden Central）的实际计费查询，周期 {billing['period']}，字段 `PreTaxCost`。"
              "每个模型的输出图 token 单独计费，金额除以计费 token 数得到实际单价。同一账单上 gpt-image-2 的单价与其公布价 $30/1M 完全一致，说明读数准确；"
              "GPT-Image-2.5 的价格在定价页上尚未公布，账单是目前唯一的官方数据。"
              if chinese else
              f"**Source**: an Azure Cost Management ActualCost query against the account that ran every test in this repository "
              f"(Sweden Central), period {billing['period']}, field `PreTaxCost`. Each model's output-image tokens are metered separately; "
              "dividing cost by billed tokens gives the effective rate. On the same invoice gpt-image-2 bills at exactly its published "
              "$30 per 1M tokens, which confirms the reading; GPT-Image-2.5 has no published price yet, so the invoice is the only official figure.")
    price_rows = [[name, f"${rate:.2f}"] for name, rate in sorted(prices.items(), key=lambda i: i[1])]
    price_table = table(["模型", "实际计费 USD / 1M 输出图 token"] if chinese else ["Model", "Billed USD per 1M output-image tokens"], price_rows)
    rows = [[config + (" **(MAI)**" if config.startswith("MAI") else ""), f"{tokens[config]:,}", f"${cost:.2f}", f"{cost / mai_cost:.2f}x"]
            for config, cost in sorted(per_image.items(), key=lambda i: i[1])]
    cost_table = table(["配置", "token / 张", "USD / 1,000 张", "相对 MAI"] if chinese else
                       ["Configuration", "Tokens / image", "USD / 1,000 images", "vs MAI"], rows)
    mai_rate, gpt_rate = prices["MAI-Image-2.6"], prices["gpt-image-2.5-flare"]
    premium = (mai_rate - gpt_rate) / gpt_rate
    low, med, high = per_image["gpt-image-2.5 low"], per_image["gpt-image-2.5 medium"], per_image["gpt-image-2.5 high"]
    reading = (f"**怎么读**：按单 token 计，MAI 比 2.5 贵 {premium:.0%}（${mai_rate:.0f} 对 ${gpt_rate:.0f}）。但 MAI 每张固定 {tokens['MAI-Image-2.6']:,} token，"
               f"而 2.5 的算力随档位变化。于是 MAI 每千张 ${mai_cost:.2f}：是 2.5 low（${low:.2f}）的 {mai_cost / low:.1f} 倍、medium（${med:.2f}）的 {mai_cost / med:.1f} 倍，比 high（${high:.2f}）便宜 {1 - mai_cost / high:.0%}，"
               f"比 max（${per_image['gpt-image-2.5 max']:.2f}）便宜 {1 - mai_cost / per_image['gpt-image-2.5 max']:.0%}。「贵」这个词只有先绑定对比档位才有意义；哪一档与 MAI 画质相当，由并排图回答，不由价格回答。"
               if chinese else
               f"**How to read this**: per token, MAI costs {premium:.0%} more than 2.5 (${mai_rate:.0f} vs ${gpt_rate:.0f}). But MAI is a constant "
               f"{tokens['MAI-Image-2.6']:,} tokens per image while 2.5 compute varies by tier. MAI therefore costs ${mai_cost:.2f} per 1,000 images: "
               f"{mai_cost / low:.1f}x 2.5 low (${low:.2f}), {mai_cost / med:.1f}x medium (${med:.2f}), {1 - mai_cost / high:.0%} less than high (${high:.2f}) and "
               f"{1 - mai_cost / per_image['gpt-image-2.5 max']:.0%} less than max (${per_image['gpt-image-2.5 max']:.2f}). \"Expensive\" is meaningless "
               "until the comparison tier is named; which tier matches MAI in quality is answered by the side-by-side images, not by price.")
    boundary = ("**边界**：单价是本账户 GlobalStandard 按需计费的实际值，不含协议折扣；token 数是各配置在本仓库全部测试中恒定不变的实测值，`auto` 因 token 不固定不列；"
                "不含输入文本 token（每张不到 $0.001）。这是按 token 的成本，不是按质量的成本。"
                if chinese else
                "**Boundary**: rates are this account's GlobalStandard pay-as-you-go actuals with no negotiated discount; token counts are the "
                "measured constants each configuration returned across every run here, and `auto` is omitted because its tokens are not constant; "
                "input text tokens (under $0.001 per image) are excluded. This is cost per token, not cost per unit of quality.")
    evidence = (f"证据：[{billing['archive']}]({billing['archive']})（原始 Cost Management 响应；`scripts/effective_prices.py --check` 可离线重算）。"
                if chinese else
                f"Evidence: [{billing['archive']}]({billing['archive']}) (raw Cost Management response; `scripts/effective_prices.py --check` recomputes it offline).")
    return "\n\n".join([heading, question, source, price_table, cost_table, reading, boundary, evidence])


# --------------------------------------------------------------------------------------------------
# Text rendering
# --------------------------------------------------------------------------------------------------

def shown_text_groups(study):
    """Configurations whose images appear: MAI plus the shown GPT model's tiers, in tier order."""
    groups = sorted({s["group"] for s in study["samples"]})
    mai = [g for g in groups if g.startswith("mai")]
    flare = sorted((g for g in groups if g.rsplit("-", 1)[0] == SHOWN_GPT_MODEL),
                   key=lambda g: TIER_ORDER.index(g.rsplit("-", 1)[1]))
    return mai + flare


def render_text_images(study, language):
    """Per scene: the rendered text of every shown configuration, both languages, with what the judge read."""
    chinese = language == "zh"
    groups = shown_text_groups(study)
    labels = [group_label(g) for g in groups]
    by_key = {(s["group"], s["round"], s["prompt_idx"]): s for s in study["samples"]}
    prompt_index = {(p["pair_id"], p["language"]): i + 1 for i, p in enumerate(study["prompts"])}
    blocks = []
    for pair in [p for p in study["prompts"] if p["language"] == "en"]:
        pid = pair["pair_id"]
        zh_target = next(p["target"] for p in study["prompts"] if p["pair_id"] == pid and p["language"] == "zh")
        blocks.append(f"**{pid} — {pair['scene']}**: `{pair['target'].replace('|', ' / ')}` / `{zh_target.replace('|', ' / ')}`")
        rows = []
        for lang in ("en", "zh"):
            idx = prompt_index[(pid, lang)]
            images, captions = [], []
            for group in groups:
                r1, r2 = by_key.get((group, 1, idx)), by_key.get((group, 2, idx))
                # Show round 1 unless only round 2 missed something: the hard set exists to surface misses.
                shown = r2 if (r1 and r2 and r1["exact_segments"] == r1["segments"] and r2["exact_segments"] < r2["segments"]) else (r1 or r2)
                if shown is None:
                    images.append("未返回图片" if chinese else "No image")
                    captions.append("—")
                    continue
                path = study["image_paths"][(group, shown["round"], idx)]
                images.append(f"![{group} {pid} {lang} round {shown['round']}]({study['archive']}/{path})")
                scores = " · ".join(f"r{s['round']} {s['matched']}/{s['chars']}" for s in (r1, r2) if s)
                if shown["exact_segments"] == shown["segments"]:
                    read = "完整正确" if chinese else "exact"
                else:
                    windows = [d["best_match"].strip() for d in shown["detail"] if not d["exact"]][:2]
                    read = ("读到 " if chinese else "read ") + " / ".join(f"`{w}`" for w in windows if w)
                marker = f" (r{shown['round']})" if shown["round"] == 2 else ""
                captions.append(f"{scores}<br>{read}{marker}")
            rows.append([("英文" if chinese else "English") if lang == "en" else ("中文" if chinese else "Chinese"), *images])
            rows.append(["", *captions])
        blocks.append(table([("语言" if chinese else "Language"), *labels], rows))
    intro = (f"下面每个场景一张表：列是配置（MAI 与 {label_for({'provider': 'gpt', 'model': SHOWN_GPT_MODEL, 'quality': ''}).strip()} 各档，sunburst 的图在证据目录），"
             "行是英文版与中文版；图下给两轮的字符得分和判读器读到的内容。默认展示第一轮的图；若只有第二轮出错，则展示第二轮并标注 (r2)。点击图片看原图。"
             if chinese else
             f"One table per scene: columns are configurations (MAI and each {label_for({'provider': 'gpt', 'model': SHOWN_GPT_MODEL, 'quality': ''}).strip()} tier; "
             "sunburst images are in the evidence directory), rows are the English and Chinese versions, with both rounds' character scores and what "
             "the judge read under each image. Round 1 is shown by default; when only round 2 missed, round 2 is shown and marked (r2). Click an image for the original.")
    return "\n\n".join([f"**{'实际输出' if chinese else 'Actual outputs'}**", intro, *blocks])


def render_text_section(study, language):
    chinese = language == "zh"
    scenes = [item for item in study["prompts"] if item["language"] == "en"]
    per_round = {}
    for sample in study["samples"]:
        if sample["round"] == 1 and sample["group"] == study["samples"][0]["group"]:
            per_round[sample["language"]] = per_round.get(sample["language"], 0) + sample["chars"]
    en_chars, zh_chars = per_round.get("en", 0), per_round.get("zh", 0)
    hard = study.get("kind") == "hard"
    scene_count = len(scenes)
    first_pair = scenes[0]["pair_id"]
    kept_groups = [g for g in sorted(study["summary"]) if not g.startswith(RETIRED_MODEL_PREFIX)]
    if hard:
        heading = ("## 中英文文字渲染：难题集" if chinese else "## Chinese and English Text Rendering: Hard Set")
        question = ("**问题**：上一节的短词每个模型都接近满分，没有区分度。换成专门针对中文难点的题目——长句、简繁体陷阱、数字混排、竖排、多行、手写——"
                    "且 2.5 两个部署的每个档位都测，差距会在哪里出现。"
                    if chinese else
                    "**Question**: the short targets in the previous section scored near 100% for every model and had no discriminating power. "
                    "With scenes built around known Chinese failure modes (long strings, simplified-vs-traditional traps, digits mixed with script, "
                    "vertical layout, multi-line, handwriting) and every tier of both 2.5 deployments measured, where do gaps appear?")
    else:
        heading = "## 中英文文字渲染" if chinese else "## Chinese and English Text Rendering"
        question = ("**问题**：同一个场景，只把要写的文字从英文换成中文，模型把字写对的比例差多少。"
                    if chinese else
                    "**Question**: for the same scene, with only the language of the required text changed, how much does the share of "
                    "correctly rendered characters differ?")

    def target_of(pair_id, lang):
        return "`" + next(p["target"].replace("|", " / ") for p in study["prompts"] if p["pair_id"] == pair_id and p["language"] == lang) + "`"

    if hard:
        prompt_rows = [[i["pair_id"], i["scene"], i["tests"], target_of(i["pair_id"], "en"), target_of(i["pair_id"], "zh")] for i in scenes]
        prompt_table = table(["场景", "画面", "针对的难点", "英文目标", "中文目标"] if chinese else
                             ["Pair", "Scene", "Tests", "English target", "Chinese target"], prompt_rows)
    else:
        prompt_rows = [[i["pair_id"], i["scene"], target_of(i["pair_id"], "en"), target_of(i["pair_id"], "zh")] for i in scenes]
        prompt_table = table(["场景", "画面", "英文目标", "中文目标"] if chinese else ["Pair", "Scene", "English target", "Chinese target"], prompt_rows)
    example = next(i["prompt"] for i in study["prompts"] if i["pair_id"] == first_pair and i["language"] == "en")
    example_zh = next(i["prompt"] for i in study["prompts"] if i["pair_id"] == first_pair and i["language"] == "zh")
    inputs = (f"**真实输入**：{scene_count} 个场景，每个写成中英两版，除了要求写的文字之外场景描述一致。例如 {first_pair} 的两版提示词：\n\n> {example}\n>\n> {example_zh}\n\n"
              f"每轮的分母是固定的：英文 {en_chars} 个字符，中文 {zh_chars} 个字符。中文表达同样内容用字更少，所以两种语言各按自己的分母计算，不互相通分。"
              if chinese else
              f"**Actual input**: {scene_count} scenes, each written in English and Chinese, identical apart from the text to be rendered. "
              f"The two {first_pair} prompts, verbatim:\n\n> {example}\n>\n> {example_zh}\n\nDenominators are fixed per round: {en_chars} English "
              f"characters and {zh_chars} Chinese characters. Chinese expresses the same content in fewer characters, so each language is scored "
              "against its own denominator and the two are never pooled.")
    controlled = ("**受控变量**：同一客户端、同一账户、同一区域（Sweden Central）、同一 GlobalStandard 部署配额、同一 1024x1024 分辨率、两轮。配对内唯一变化的是文字的语言。"
                  if chinese else
                  "**Controlled variables**: one client, one account, one region (Sweden Central), the same GlobalStandard quota, 1024x1024, two rounds. "
                  "Within a pair, only the language of the text changes.")
    rows = []
    for group in kept_groups:
        stats = study["summary"][group]
        row = [group_label(group)]
        for lang in ("en", "zh"):
            item = stats.get(lang)
            row += (["N/A", "N/A"] if not item else
                    [f"{item['matched_chars']}/{item['total_chars']} = {item['char_accuracy']:.0%}",
                     f"{item['exact_segments']}/{item['total_segments']} = {item['exact_rate']:.0%}"])
        rows.append(row)
    results = table(["配置", "英文字符准确率", "英文整段正确", "中文字符准确率", "中文整段正确"] if chinese else
                    ["Configuration", "English character accuracy", "English exact segments", "Chinese character accuracy", "Chinese exact segments"], rows)
    judging = ("**判读方法**：每张图交给 `gpt-5.6-terra` 读出图中文字，再与目标字符串程序化比对，比对时忽略全部空白。两个口径同时给出：字符准确率取整段转录中与目标最接近的等长窗口逐字符算分，"
               "整段正确要求目标串以子串形式完整出现、不给部分分。这是模型判读，不是人工盲评。判读器是 OpenAI 系列模型，而被判的一方也包括 OpenAI 的图像模型；下面的校准只能排除它读不清中文，"
               "不能排除它对某一家的风格更宽容，所以每张图都附在下方供人眼复核。"
               if chinese else
               "**How it was judged**: each image is transcribed by `gpt-5.6-terra` and compared with the target string programmatically, ignoring all whitespace. "
               "Two denominators are reported: character accuracy scores the best-matching window of equal length anywhere in the transcription, character by "
               "character; exact segments requires the target to appear verbatim as a substring, with no partial credit. This is model-judged, not a blind human "
               "study. The judge is an OpenAI-family model and some of the judged images come from OpenAI image models; the calibration below rules out an "
               "inability to read Chinese, not a lenience toward one vendor's style, which is why every image is shown below for human review.")
    superseded = study.get("superseded")
    correction = ""
    if superseded:
        correction = ("**口径更正**：第一版评分把每个目标串只与转录中的**单独一行**比对。判读器每个视觉文字块输出一行，所以模型把一句话分两行排版就被判成拼写错误；"
                      "这个惩罚随目标长度增长，而英文目标是中文的 2–4 倍长，于是英文被系统性低估。更正后的规则忽略空白、在整段转录中匹配；"
                      f"第一版结果保留为 [`{superseded['file']}`]({study['archive']}/{superseded['file']})。"
                      if chinese else
                      "**Scoring correction**: the first pass matched each target against a **single transcribed line**. The judge emits one line per visual text "
                      "block, so a model that wrapped a phrase onto two lines was scored as misspelling it; the penalty grew with target length, and the English "
                      "targets are two to four times longer than the Chinese ones, so English was systematically understated. The corrected rule ignores "
                      f"whitespace and matches anywhere in the transcription; the first-pass scores are kept as [`{superseded['file']}`]({study['archive']}/{superseded['file']}).")
    cal = study.get("calibration")
    if cal:
        en_cal, zh_cal = cal["summary"]["en"], cal["summary"]["zh"]
        font = cal.get("font", "msyh.ttc")
        font_cn = "微软雅黑" if font.lower().startswith("msyh") else font
        font_en = "Microsoft YaHei" if font.lower().startswith("msyh") else font
        calibration = (f"**判读器的误差下限**：把本节同样的目标文字用{font_cn}渲染成图再让判读器读回来，英文 {en_cal['matched_chars']}/{en_cal['total_chars']}"
                       f"（{en_cal['char_accuracy']:.1%}），中文 {zh_cal['matched_chars']}/{zh_cal['total_chars']}（{zh_cal['char_accuracy']:.1%}），与上表同一套评分规则。"
                       "也就是说判读器对这些字符没有系统性偏见，上表的差距可以归到生成模型。边界：这只证明判读器能读清晰的横排文字；生成图里扭曲、艺术化或竖排的字更难读，"
                       f"所以上表可能低估、不会高估。校准的渲染图与转录在 [judge-calibration]({study['archive']}/judge-calibration)，`calibrate_text_judge.py --check` 可离线重算。"
                       if chinese else
                       f"**The judge's own error floor**: rendering this section's targets with {font_en} and asking the judge to read them back scores "
                       f"{en_cal['matched_chars']}/{en_cal['total_chars']} ({en_cal['char_accuracy']:.1%}) for English and {zh_cal['matched_chars']}/{zh_cal['total_chars']} "
                       f"({zh_cal['char_accuracy']:.1%}) for Chinese under the same scoring rule as the table. The judge therefore has no systematic bias against "
                       "these characters, and the gaps above are attributable to the image models. Boundary: this only establishes that the judge reads clean "
                       "horizontal renders; distorted, stylised or vertical text in generated images is harder, so the table may understate accuracy and will not "
                       f"overstate it. The renders and transcriptions are in [judge-calibration]({study['archive']}/judge-calibration) and "
                       "`calibrate_text_judge.py --check` recomputes them offline.")
    else:
        calibration = ("**判读器的误差下限**：本节的目标文字没有做判读器校准，上表的差距里包含未知大小的判读误差。" if chinese else
                       "**The judge's own error floor**: the judge was not calibrated on this section's targets, so the gaps above include a judging error of unknown size.")
    kept_samples = sum(1 for s in study["samples"] if not s["group"].startswith(RETIRED_MODEL_PREFIX))
    boundary = (f"**结论边界**：{kept_samples} 个成功样本，覆盖 {scene_count} 个场景、2 轮、{len(kept_groups)} 个配置。这是指定字符串的拼写准确率，不是排版美观度、字体质量或中文设计感的评价。"
                "MAI-Image-2.6 不接受质量参数，它的行只有一个配置。**官方支持范围**：Foundry 模型文档将 MAI-Image-2.6 的 Languages 标为 `en`，中文不在其声明的支持范围内；"
                "本节的中文结果是在声明范围之外观察到的行为，不构成产品承诺，也不应被当作已支持的能力来引用。"
                if chinese else
                f"**Boundary**: {kept_samples} successful samples across {scene_count} scenes, 2 rounds and {len(kept_groups)} configurations. This measures spelling "
                "accuracy for a specified string, not typographic quality, font choice or design appeal. MAI-Image-2.6 takes no quality parameter and therefore has a "
                "single row. **Declared support**: the Foundry model documentation lists MAI-Image-2.6 Languages as `en`; Chinese is outside its declared scope. The "
                "Chinese results here are observed behaviour outside that scope, not a product commitment, and should not be cited as a supported capability.")
    evidence = (f"证据目录：[{study['archive']}]({study['archive']})（含每组拼图 `review/`）。提示词 SHA-256：`{study['prompt_sha256']}`。" if chinese else
                f"Evidence directory: [{study['archive']}]({study['archive']}) (per-group contact sheets in `review/`). Prompt SHA-256: `{study['prompt_sha256']}`.")
    return "\n\n".join(part for part in [heading, question, inputs, prompt_table, controlled, results, render_text_images(study, language),
                                          judging, correction, calibration, boundary, evidence] if part)


# --------------------------------------------------------------------------------------------------
# Web grounding (MAI only)
# --------------------------------------------------------------------------------------------------

def grounding_reproduction_commands(archive_path):
    return (f"python scripts/summarize_web_grounding.py {archive_path} --require-complete --check\n"
            f"python {archive_path}/source/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --mai-web-grounding both "
            f"--prompts-csv {archive_path}/source/prompts.csv --output runs/web-grounding-reproduction --dry-run\n"
            f"python {archive_path}/source/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --mai-web-grounding both "
            f"--prompts-csv {archive_path}/source/prompts.csv --output runs/web-grounding-reproduction")


def render_grounding_section(summary, archive_path, language):
    if not summary["complete"]:
        raise ValueError("Grounding results must be complete before publication")
    chinese = language == "zh"
    selected = [sample for sample in summary["samples"] if sample["prompt_idx"] in (1, 2)]
    settings = [False, True]
    rows_by_setting = [[sample for sample in selected if sample["web_grounding"] is enabled] for enabled in settings]
    selected_ids = {(sample["group"], sample["round"], sample["prompt_idx"]) for sample in selected}
    unsuccessful = [attempt for attempt in summary["unsuccessful_attempts"]
                    if (attempt["group"], attempt["round"], attempt["prompt_idx"]) in selected_ids]
    metrics = []
    for label, measure in (
        ("返回图片 / 展示样本" if chinese else "Images returned / displayed samples", lambda rows: f"{sum(s['ok'] for s in rows)}/{len(rows)}"),
        ("首试成功 / 展示样本" if chinese else "First-attempt successes / displayed samples", lambda rows: f"{sum(s['first_attempt_ok'] for s in rows)}/{len(rows)}"),
        ("HTTP 请求次数" if chinese else "HTTP attempts", lambda rows: str(sum(s["attempt_count"] for s in rows))),
        ("HTTP 408 次数" if chinese else "HTTP 408 responses",
         lambda rows: str(sum(a.get("http_status") == 408 and a["group"] == rows[0]["group"] for a in unsuccessful))),
    ):
        metrics.append([label, *(measure(rows) for rows in rows_by_setting)])
    unit = "秒" if chinese else "s"
    for label, statistic, field, successful_only in (
        ("成功请求平均耗时" if chinese else "Mean successful request", statistics.mean, "time", True),
        ("成功请求 P50" if chinese else "Successful request P50", statistics.median, "time", True),
        ("含失败重试的逻辑调用平均耗时" if chinese else "Mean logical call including retries", statistics.mean, "logical_request_seconds", False),
    ):
        values = [[s[field] for s in rows if s["ok"] or not successful_only] for rows in rows_by_setting]
        metrics.append([label, *(f"{statistic(v):.2f} {unit}" if v else "N/A" for v in values)])
    headers = ["指标", "关闭联网", "开启联网"] if chinese else ["Metric", "Grounding off", "Grounding on"]
    intro = ("本节测试 MAI 独有的联网信息补充参数：在相同提示词下，对比 MAI-Image-2.6 的 `web_grounding=false/true`，观察文字事实准确性与生成耗时。"
             "公开新品资料只是测试题材，不是客户项目或客户采纳案例。GPT-Image-2.5 没有对应参数，本节无 GPT 对照。"
             if chinese else
             "This section tests a MAI-only parameter: identical prompts are sent to MAI-Image-2.6 with `web_grounding=false/true` to compare text factual "
             "accuracy and latency. Public product announcements supply the test subjects; this is not a customer project or adoption case. GPT-Image-2.5 has no "
             "equivalent parameter, so there is no GPT column here.")
    scope = (f"完整补测为 {summary['planned_samples']} 个正式样本，另有 {summary['warmups_excluded']} 次预热。按已观察到的文字事实改善选取两个题目，保留全部两轮开／关对照，"
             f"共 {len(selected)} 张原图，每组 {len(rows_by_setting[0])} 个样本。下表仅统计这些选例，不是全量提升率。"
             if chinese else
             f"The complete supplement contains {summary['planned_samples']} formal samples and {summary['warmups_excluded']} excluded warmups. Two subjects were "
             f"selected after observing improved text facts; all off/on results from both rounds are shown, {len(selected)} original images and "
             f"{len(rows_by_setting[0])} samples per setting. The table covers only these examples, not an overall improvement rate.")
    findings = ([["新品配色与尺寸", "两轮均出现非官方配色名和错误屏幕选项", "两轮均匹配七种官方配色名及 14/15 英寸选项"],
                 ["产品规格与使用模式", "屏幕尺寸和计算平台错误，均漏掉 Canvas 模式", "两轮均写对 16 英寸、NVIDIA RTX Spark、五种模式及笔输入表面"]]
                if chinese else
                [["New-product colours and sizes", "Both rounds used unofficial colour names and incorrect screen options", "Both matched all seven official colour names and the 14/15-inch options"],
                 ["Product specifications and usage modes", "Screen size and computing platform were wrong; Canvas mode was missing", "Both matched 16 inches, NVIDIA RTX Spark, five mode names and the pen-input surfaces"]])
    boundaries = ("固定 1024x1024、`auto_aspect_ratio=false`，同一模型版本 2026-07-31、Sweden Central GlobalStandard 部署；第二轮反转请求顺序。两组仅联网开关不同，核对答案未加入提示词。"
                  "成功请求耗时不含 JSON/base64 处理；逻辑调用耗时包含失败、退避和响应处理。所有 HTTP 408 和重试均保留，服务未说明内部超时环节，不能把全部额外时间归因于搜索。"
                  "文字事实改善不等于画面质量或产品外观保真：第二题第二轮开启图中，`Tablet Mode` 标签下仍画着竖起的屏幕，存在图文不一致。"
                  "观察为 AI 辅助非盲评；响应没有提供检索查询、来源 URL 或调用轨迹。"
                  if chinese else
                  "Both settings used 1024x1024, `auto_aspect_ratio=false`, model version 2026-07-31 and the same Sweden Central GlobalStandard deployment; round 2 "
                  "reversed request order. Only the grounding switch differed; reference answers were not included in prompts. Successful request time excludes "
                  "JSON/base64 processing; logical call time includes failures, backoff and response processing. All HTTP 408 responses and retries are retained; the "
                  "internal timeout stage was not returned, so the additional time cannot all be attributed to search. Improved text facts do not establish better "
                  "aesthetics or product fidelity: in subject 2, round 2, the grounding-on `Tablet Mode` illustration still has an upright screen. Inspection was "
                  "AI-assisted and unblinded; responses included no search queries, source URLs or retrieval traces.")
    subject_labels = ("新品配色与尺寸", "产品规格与使用模式") if chinese else ("New-product colours and sizes", "Product specifications and usage modes")
    prompt_block = []
    for index, label in enumerate(subject_labels):
        prompt_text = " ".join(summary["prompts"][index].split())
        prompt_block.append((f"题目 {index + 1}（{label}）发给模型的完整提示词：" if chinese else f"The exact prompt sent for subject {index + 1} ({label}):") + f"\n\n> {prompt_text}")
    controlled = ("唯一变化的是 `web_grounding` 开关。提示词、尺寸、模型版本、部署与轮数完全相同。" if chinese else
                  "The only thing that changes is the `web_grounding` switch. Prompt, dimensions, model version, deployment and round count are identical.")
    asked = ("两个题目都要求模型把真实产品信息画进海报：题目 1 要求列出官方发布的全部配色名与屏幕尺寸选项，题目 2 要求写出产品名、屏幕尺寸、计算平台，"
             "并标出官方命名的翻转使用模式与支持笔输入的表面。提示词只要求以官方发布信息为准，没有把正确答案写进提示词。"
             if chinese else
             "Both subjects ask the model to put real product information into a poster. Subject 1 asks for every officially announced colour name and the "
             "screen-size options; subject 2 asks for the product name, screen size, computing platform, the officially named convertible modes and which "
             "surfaces accept pen input. The prompts only instruct the model to follow the official announcement; no correct answer is supplied in the prompt.")
    sections = [f"## {'联网信息补充测试' if chinese else 'Web Grounding Test'}", intro,
                f"**{'我们向模型提出的问题' if chinese else 'What we asked the model'}**", asked, *prompt_block,
                f"**{'受控变量' if chinese else 'Controlled variable'}**", controlled, scope,
                f"**{'文字事实核对结果' if chinese else 'Text-fact findings'}**",
                table(["测试项", "关闭联网", "开启联网"] if chinese else ["Test subject", "Grounding off", "Grounding on"], findings),
                f"**{'耗时与请求情况' if chinese else 'Latency and request outcomes'}**", table(headers, metrics), boundaries]
    for prompt_index, subject in zip((1, 2), subject_labels):
        for round_number in (1, 2):
            rows = [next(s for s in selected if s["prompt_idx"] == prompt_index and s["round"] == round_number and s["web_grounding"] is enabled)
                    for enabled in settings]
            images = [f"![Web grounding {'on' if enabled else 'off'}, subject {prompt_index}, round {round_number}]({archive_path}/{s['image']})"
                      if s["ok"] else ("未返回图片" if chinese else "No image returned") for enabled, s in zip(settings, rows)]
            sections.extend([f"#### {subject} / {'第' + str(round_number) + '轮' if chinese else 'Round ' + str(round_number)}",
                             table(["`web_grounding=false`", "`web_grounding=true`"], [images])])
    sections.extend([
        f"[{'原始结果' if chinese else 'Raw results'}]({archive_path}/5way_v2_results.json) | [{'全部请求' if chinese else 'All attempts'}]({archive_path}/attempts.jsonl) | "
        f"[{'逐图观察' if chinese else 'Visual observations'}]({archive_path}/visual-review.json) | [{'完整12样本统计' if chinese else 'Full 12-sample statistics'}]({archive_path}/web-grounding-summary.json) | "
        f"[{'出处与哈希' if chinese else 'Provenance and hashes'}]({archive_path}/provenance.json)",
        f"{'结果 SHA-256' if chinese else 'Result SHA-256'}: `{summary['result_sha256']}`. " + ("官方参考：" if chinese else "Official references: ") +
        "[IdeaPad Vibe](https://news.lenovo.com/pressroom/press-releases/colorful-ideapad-vibe-series-all-in-one-ai-pcs/) | "
        "[Yoga](https://news.lenovo.com/pressroom/press-releases/yoga-portfolio-new-ai-pcs-and-tablets/) | "
        "[MAI API](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai-image#request-parameters)",
    ])
    return "\n\n".join(sections)


# --------------------------------------------------------------------------------------------------
# Reproduction
# --------------------------------------------------------------------------------------------------

def reproduction_section(primary, supplement, tier, edit, grounding, text_studies, billing, language):
    zh = language == "zh"
    steps = []

    def step(number, title_en, title_zh, body_en, body_zh, commands):
        steps.append("\n\n".join([f"### {number}. {title_zh if zh else title_en}", body_zh if zh else body_en, f"```powershell\n{commands}\n```"]))

    step(1, "Clone and install dependencies", "克隆并安装依赖",
         "JSON and CSV in this repository are stored with Git LFS; fetch them before validating anything.",
         "本仓库的 JSON 与 CSV 由 Git LFS 存储，核验前先拉取。",
         "git clone https://github.com/david-xinyuwei/david-share.git\ncd david-share/Multimodal-Models/MAI-Image-2-vs-GPT-Image-Benchmark\n"
         "git lfs pull --include \"Multimodal-Models/MAI-Image-2-vs-GPT-Image-Benchmark/**\"\npython -m pip install requests pillow")
    step(2, "Configure your deployments", "配置自己的部署",
         "One MAI-Image-2.6 deployment and the GPT-Image-2.5 deployments you want to measure, on accounts you control. Verify the underlying model "
         "versions; deployment names alone are not model identity. Supply `AZURE_API_KEY` (MAI) and `AZURE_OPENAI_API_KEY` (GPT) through your own "
         "secret management, never source control. The metadata variables must state your verified deployments; the values below describe ours.",
         "需要一个 MAI-Image-2.6 部署和要测的 GPT-Image-2.5 部署，都在您自己的账户下。部署身份由您查询确认，不能仅凭 deployment 名称判断底层模型。"
         "`AZURE_API_KEY`（MAI）和 `AZURE_OPENAI_API_KEY`（GPT）通过您自己的秘密管理机制提供，不进源码和 Git。元数据变量必须填您查到的实际值；下面是本次实测的值。",
         "$env:MAI_ENDPOINT = 'https://<your-mai-resource>.services.ai.azure.com'\n$env:GPT_ENDPOINT = 'https://<your-openai-resource>.openai.azure.com'\n"
         "$env:MAI_MODEL_VERSION = '2026-07-31'\n$env:GPT_MODEL_VERSIONS = '{\"gpt-image-2.5-flare\": \"2026-09-08\", \"gpt-image-2.5-sunburst\": \"2026-09-08\"}'\n"
         f"$env:MAI_DEPLOYMENT_REGION = '{primary['region']}'\n$env:GPT_DEPLOYMENT_REGION = '{primary['region']}'\n$env:MAI_DEPLOYMENT_SKU = 'GlobalStandard'\n"
         "$env:GPT_DEPLOYMENT_SKU = 'GlobalStandard'\n$env:MAI_RATE_LIMIT_RPM = '2.0'\n$env:GPT_RATE_LIMIT_RPM = '2.0'\n"
         "$env:BENCHMARK_CLIENT_LOCATION = 'Describe your actual client location'\n"
         "python scripts/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --gpt-model gpt-image-2.5-flare:medium,high --dry-run")
    step(3, "Rerun the same-session comparison", "重跑同会话对比",
         f"The primary run: MAI and 2.5 flare medium and high interleaved on the eleven prompts. `--gpt-model` accepts `deployment:tier,tier`. "
         "The first command runs one warmup per configuration; the second continues the same output directory through the formal matrix. Existing results "
         "are never overwritten and recorded samples are not rerun. Save the script and CSV into the run before starting and keep them unchanged during execution.",
         "主线运行：MAI 与 2.5 flare 的 medium、high 在 11 题上交错调用。`--gpt-model` 接受 `部署名:档位,档位`。第一条每组预热一次；第二条从同一输出目录继续正式矩阵。"
         "已有结果不覆盖，已记录样本不重跑。开跑前把脚本和 CSV 存进 run 目录，运行期间不得修改。",
         f"python scripts/summarize_paired_run.py {primary['archive']}\n$run = 'runs/mai-vs-gpt25-new-run'\nNew-Item -ItemType Directory -Path \"$run/source\" -ErrorAction Stop\n"
         "Copy-Item -LiteralPath scripts/benchmark_5way_v2.py -Destination \"$run/source/benchmark_5way_v2.py\"\nCopy-Item -LiteralPath prompts.csv -Destination \"$run/source/prompts.csv\"\n"
         "python -u scripts/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --gpt-model gpt-image-2.5-flare:medium,high --output $run --warmup-only\n"
         "python -u scripts/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --gpt-model gpt-image-2.5-flare:medium,high --output $run --resume\n"
         "python scripts/summarize_paired_run.py $run")
    step(4, "Verify published evidence without model calls", "只读核验已发布证据",
         "Recomputes every archive from its raw records and confirms both READMEs match; regressions cover request contracts, failure denominators, "
         "image ownership, the scoring rule, the invoice derivation and report coverage. HTTP mocks exist only in offline tests.",
         "从原始记录重算每个归档并确认两份 README 与之一致；回归覆盖请求契约、失败分母、图片归属、评分规则、账单反算和报告覆盖。模拟 HTTP 只用于离线单元测试。",
         f"python scripts/render_paired_report.py {primary['archive']} --check\npython -m unittest discover -s tests -v")
    number = 5
    if grounding:
        step(number, "Rerun the web-grounding comparison", "重跑联网信息补充测试",
             "Needs only the MAI deployment. The first command verifies the archive; the second checks parameters offline; the third reruns all three subjects into a new directory.",
             "只需 MAI 部署。第一条只读核验归档；第二条离线检查参数；第三条真实重跑三题写入新目录。",
             grounding_reproduction_commands(GROUNDING_ARCHIVE))
        number += 1
    if edit:
        tiers = [g.rsplit("-", 1)[1] for g in edit["groups"] if g != "mai-image-2.6"]
        quality_args = " ".join(f"--gpt-quality {t}" for t in tiers)
        step(number, "Rerun the headwear-swap image edit", "重跑换帽图像编辑",
             f"Set `GPT_DEPLOYMENT` to the 2.5 deployment (`{edit['gpt_deployment']}` here) and name the tiers with `--gpt-quality`. The first command verifies the "
             "published outputs; the second is a credential-free dry run; the next two perform the live rounds; the last checks order, `size=auto` and hashes. "
             "The per-image checklist is a manual review under the published method, not generated automatically.",
             f"把 `GPT_DEPLOYMENT` 设为 2.5 部署（本次为 `{edit['gpt_deployment']}`），用 `--gpt-quality` 指定档位。第一条只读核验已发布输出；第二条是无凭据 dry-run；"
             "接下来两条真实执行两轮；最后一条核对顺序、`size=auto` 与 hash。逐图清单需按已发布方法人工复核，不会自动生成。",
             f"python scripts/summarize_edit_hat_swap.py {edit['archive']} --check\n$env:GPT_DEPLOYMENT = '{edit['gpt_deployment']}'\n$out = 'runs/edit-hat-swap-reproduction'\n"
             f"python scripts/run_edit_hat_swap.py --input {edit['archive']}/input.jpg --output $out --round 1 --gpt-size auto {quality_args} --dry-run\n"
             f"python scripts/run_edit_hat_swap.py --input {edit['archive']}/input.jpg --output $out --round 1 --gpt-size auto {quality_args}\n"
             f"python scripts/run_edit_hat_swap.py --input {edit['archive']}/input.jpg --output $out --round 2 --gpt-size auto {quality_args}\n"
             "python scripts/run_edit_hat_swap.py --output $out --check")
        number += 1
    if supplement:
        step(number, "Rerun GPT-Image-2.5 low/medium/high on both deployments", "重跑 GPT-Image-2.5 两个部署的 low/medium/high",
             "`--gpt-model` may be repeated; `--gpt-quality all` expands to low, medium and high. The client starts at most 2 requests per 60 seconds per deployment "
             "to match the 2 RPM quota; raise `RATE_PACING` if yours is higher.",
             "`--gpt-model` 可重复传入；`--gpt-quality all` 展开为 low、medium、high。客户端对同一部署每 60 秒最多起请 2 次，与 2 RPM 配额对齐；配额更高可改 `RATE_PACING`。",
             f"python scripts/summarize_paired_run.py {supplement['archive']}\n$run = 'runs/gpt25-paired-new-run'\nNew-Item -ItemType Directory -Path \"$run/source\" -ErrorAction Stop\n"
             "Copy-Item -LiteralPath scripts/benchmark_5way_v2.py -Destination \"$run/source/benchmark_5way_v2.py\"\nCopy-Item -LiteralPath prompts.csv -Destination \"$run/source/prompts.csv\"\n"
             "python -u scripts/benchmark_5way_v2.py --gpt-model gpt-image-2.5-flare --gpt-model gpt-image-2.5-sunburst --gpt-quality all --output $run --warmup-only\n"
             "python -u scripts/benchmark_5way_v2.py --gpt-model gpt-image-2.5-flare --gpt-model gpt-image-2.5-sunburst --gpt-quality all --output $run --resume")
        number += 1
    if tier:
        step(number, "Rerun xhigh/max/auto", "重跑 xhigh/max/auto",
             "Only gpt-image-2.5-* accepts these tiers. A single max request measured 229 s, so the runner's request timeout is 900 s. `auto` lets the service choose "
             "per request; the tier it used is recorded per attempt as `service_quality`.",
             "只有 gpt-image-2.5-* 接受这三档。max 单次请求实测 229 秒，执行脚本的请求超时为 900 秒。`auto` 由服务按请求自选档位，实际使用的档位记在每次尝试的 `service_quality`。",
             f"python scripts/summarize_paired_run.py {tier['archive']}\n$run = 'runs/gpt25-tiers-new-run'\nNew-Item -ItemType Directory -Path \"$run/source\" -ErrorAction Stop\n"
             "Copy-Item -LiteralPath scripts/benchmark_5way_v2.py -Destination \"$run/source/benchmark_5way_v2.py\"\nCopy-Item -LiteralPath prompts.csv -Destination \"$run/source/prompts.csv\"\n"
             "python -u scripts/benchmark_5way_v2.py --gpt-model gpt-image-2.5-flare --gpt-model gpt-image-2.5-sunburst --gpt-quality xhigh --gpt-quality max --gpt-quality auto --output $run --warmup-only\n"
             "python -u scripts/benchmark_5way_v2.py --gpt-model gpt-image-2.5-flare --gpt-model gpt-image-2.5-sunburst --gpt-quality xhigh --gpt-quality max --gpt-quality auto --output $run --resume")
        number += 1
    studies = [s for s in text_studies if s]
    if studies:
        easy = studies[0]
        checks = "\n".join(f"python scripts/score_text_rendering.py --check {s['archive']}/text-scoring.json" for s in studies)
        checks += "".join(f"\npython scripts/calibrate_text_judge.py --check {s['archive']}/judge-calibration/calibration.json" for s in studies if s.get("calibration"))
        step(number, "Rerun text rendering and score it", "重跑中英文文字渲染并判读",
             "Text rendering uses its own prompt file (`--prompts-csv`); the runner reads only the first column. Each deployment has its own quota, so shards run per "
             "deployment and are merged at scoring with repeated `--run`; the scorer refuses shards whose frozen prompt file differs. Scoring needs a vision-capable "
             "chat deployment via `JUDGE_ENDPOINT`, `JUDGE_DEPLOYMENT` and `AZURE_OPENAI_API_KEY`; calibrate it first, or its errors will be attributed to the image "
             "models. `--check` recomputes every score from saved transcriptions with no model calls.",
             "文字渲染用自己的提示词文件（`--prompts-csv`），执行脚本只读第一列。每个部署各自有配额，所以按部署分片跑，判读时用多个 `--run` 合并；判读器拒绝提示词文件不一致的分片。"
             "判读需要支持图像输入的 chat 部署，通过 `JUDGE_ENDPOINT`、`JUDGE_DEPLOYMENT`、`AZURE_OPENAI_API_KEY` 提供；先校准，否则它的误差会被算到图像模型头上。"
             "`--check` 用归档里的转录重算全部分数，不调用模型。",
             f"{checks}\n$env:JUDGE_ENDPOINT = 'https://<openai-resource>.openai.azure.com'\n$env:JUDGE_DEPLOYMENT = '<vision-capable-chat-deployment>'\n"
             f"python scripts/calibrate_text_judge.py --prompts {easy['archive']}/{easy['prompts_name']} --out runs/judge-calibration\n$run = 'runs/text-new-run-mai'\n"
             f"New-Item -ItemType Directory -Path \"$run/source\" -ErrorAction Stop\nCopy-Item -LiteralPath scripts/benchmark_5way_v2.py -Destination \"$run/source/benchmark_5way_v2.py\"\n"
             f"Copy-Item -LiteralPath {easy['archive']}/{easy['prompts_name']} -Destination \"$run/source/{easy['prompts_name']}\"\n"
             f"python -u scripts/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --prompts-csv \"$run/source/{easy['prompts_name']}\" --output $run\n"
             f"python scripts/score_text_rendering.py --run $run --prompts {easy['archive']}/{easy['prompts_name']} --out runs/text-new-run-scored")
        number += 1
    if billing:
        step(number, "Recompute cost per image from your own invoice", "从自己的账单重算每张图成本",
             "The first command recomputes `effective-prices.json` from the archived Cost Management response, offline. The second issues the same query against your "
             "own account (needs `az login`; the query is free) and writes a new archive; re-rendering then reads your invoice instead of ours.",
             "第一条从已归档的 Cost Management 响应离线重算 `effective-prices.json`；第二条对您自己的账户发同样的查询（需 `az login`，查询不计费）写入新归档，之后重新渲染就读您的账单。",
             f"python scripts/effective_prices.py {billing['archive']} --check\n"
             "python scripts/effective_prices.py data/billing-<date> --query --subscription <id> --resource-group <rg> --account <cognitive-services-account>")
    intro = ("每个数据目录都对应下面的一步：第 4 步不调用模型，其余会消耗 Azure 用量。所有执行脚本、汇总器和判读器都在 `scripts/`，复现用的就是产出本报告的同一套代码。"
             if zh else
             "Every data directory maps to one step below: step 4 makes no model calls, the rest consume Azure usage. All runners, summarizers and the judge live in "
             "`scripts/`; reproduction uses the same code that produced this report.")
    tools = (f"{'脚本' if zh else 'Scripts'}: [benchmark_5way_v2.py](scripts/benchmark_5way_v2.py) · [run_edit_hat_swap.py](scripts/run_edit_hat_swap.py) · "
             "[summarize_paired_run.py](scripts/summarize_paired_run.py) · [summarize_edit_hat_swap.py](scripts/summarize_edit_hat_swap.py) · "
             "[score_text_rendering.py](scripts/score_text_rendering.py) · [calibrate_text_judge.py](scripts/calibrate_text_judge.py) · "
             "[effective_prices.py](scripts/effective_prices.py) · [render_paired_report.py](scripts/render_paired_report.py) · [tests](tests).")
    return "\n\n".join([f"### {'复现与测试' if zh else 'Reproduction and Tests'}\n\n<a id=\"reproduction-how-to\"></a>", intro, *steps, tools])


# --------------------------------------------------------------------------------------------------
# Document assembly
# --------------------------------------------------------------------------------------------------

def update_document(text, primary, supplement, tier, edit, grounding, text_studies, billing, language, test_count):
    chinese = language == "zh"
    coverage = tier_coverage(primary["summary"], supplement["summary"] if supplement else None, tier["summary"] if tier else None)
    tiers = sorted({t for ts in coverage["measured"].values() for t in ts}, key=TIER_ORDER.index)
    if coverage["complete"]:
        title = "# MAI-Image-2.6 与 GPT-Image-2.5：全质量档位图像生成对比" if chinese else "# MAI-Image-2.6 vs GPT-Image-2.5: All Quality Tiers"
    else:
        listed = "、".join(tiers) if chinese else ", ".join(tiers)
        title = f"# MAI-Image-2.6 与 GPT-Image-2.5：{listed} 档图像生成对比" if chinese else f"# MAI-Image-2.6 vs GPT-Image-2.5: {listed} Tiers"
    author = re.search(r"(?m)^> \*\*(?:Author|作者)\*\*:[^\n]+", text)
    if author is None:
        raise ValueError("Existing report author attribution was not found")
    titles = {int(index): heading.strip() for index, heading in re.findall(r"(?m)^### Test (\d+): ([^\n]+)$", text)}
    if not set(range(1, 12)) <= set(titles) or [i["prompt_index"] for i in primary["summary"]["per_prompt"]] != list(range(1, 12)):
        raise ValueError("All eleven original scenarios are required")
    ends = [run["summary"]["formal_ended_at_utc"] for run in (primary, supplement, tier) if run]
    if edit:
        ends.extend(r["measured_at_utc"][1] or r["measured_at_utc"][0] for r in edit["rounds"])
    data_through = max(ends)[:10]
    hard_study = next((s for s in text_studies if s and s.get("kind") == "hard"), None)
    sections = [title,
                render_masthead(primary, author.group(), language, data_through, test_count,
                                total_samples(primary, supplement, tier, text_studies, edit, grounding)),
                render_highlights(primary, supplement, billing, hard_study, edit, bool(grounding), language),
                *render_side_by_side(primary, supplement, tier, titles, language)]
    if edit:
        sections.append(render_edit_scenario(edit, edit["archive"], language))
    sections.append(render_overview(primary, supplement, tier, billing, edit, text_studies, grounding, language).strip())
    if supplement and tier:
        sections.append(render_tier_section(supplement, tier, language))
    if billing:
        sections.append(render_cost_section(billing, language))
    for study in text_studies:
        if study:
            sections.append(render_text_section(study, language))
    if grounding:
        sections.append(render_grounding_section(grounding, GROUNDING_ARCHIVE, language))
    return "\n\n".join(sections) + "\n"


def load_everything(root):
    prompts = root / "prompts.csv"
    primary = load_run(root, prompts, PRIMARY_ARCHIVE)
    if primary is None:
        raise SystemExit(f"Primary archive {PRIMARY_ARCHIVE} is missing")
    supplement = load_run(root, prompts, SUPPLEMENT_ARCHIVE)
    tier = load_tier_supplement(root, prompts)
    edit = summarize_edit(root / EDIT_ARCHIVE) if (root / EDIT_ARCHIVE).is_dir() else None
    if edit:
        edit["archive"] = EDIT_ARCHIVE
    grounding = summarize_grounding(root / GROUNDING_ARCHIVE) if (root / GROUNDING_ARCHIVE).is_dir() else None
    text_studies = tuple(load_text_study(root, archive, prompts_name, kind) for archive, prompts_name, kind in TEXT_ARCHIVES)
    billing = load_billing(root)
    return primary, supplement, tier, edit, grounding, text_studies, billing


def main():
    parser = argparse.ArgumentParser(description="Generate both language reports from the archived evidence.")
    parser.add_argument("run_directory", type=Path, nargs="?", help="Primary archive; defaults to the same-session run.")
    parser.add_argument("--check", action="store_true", help="Check generated content without editing either README.")
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    global PRIMARY_ARCHIVE
    if arguments.run_directory is not None:
        PRIMARY_ARCHIVE = arguments.run_directory.resolve().relative_to(root).as_posix()
    primary, supplement, tier, edit, grounding, text_studies, billing = load_everything(root)
    test_count = count_tests(root)
    documents = []
    for filename, language in (("README.md", "en"), ("README-CN.md", "zh")):
        path = root / filename
        original = path.read_text("utf-8")
        generated = update_document(original, primary, supplement, tier, edit, grounding, text_studies, billing, language, test_count)
        documents.append((path, original, generated))
    if arguments.check:
        changed = [path.name for path, original, generated in documents if original != generated]
        if changed:
            raise SystemExit("Report differs from current evidence: " + ", ".join(changed))
    else:
        for path, _, generated in documents:
            path.write_text(generated, encoding="utf-8")
    print(json.dumps({"status": "PASS", "primary": primary["archive"], "formal_samples": primary["summary"]["formal_samples"],
                      "supplement": supplement["archive"] if supplement else None, "tier_supplement": tier["archive"] if tier else None,
                      "edit": edit["archive"] if edit else None, "grounding": GROUNDING_ARCHIVE if grounding else None,
                      "text_studies": [s["archive"] for s in text_studies if s], "billing": billing["archive"] if billing else None,
                      "readme_bytes": [len(generated.encode("utf-8")) for _, _, generated in documents]}))


if __name__ == "__main__":
    main()

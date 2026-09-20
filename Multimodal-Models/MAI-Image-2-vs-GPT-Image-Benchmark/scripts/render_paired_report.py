import argparse
import csv
import json
import re
import statistics
from pathlib import Path

from summarize_paired_run import GROUPS, summarize
from summarize_web_grounding import summarize as summarize_grounding
from summarize_edit_hat_swap import summarize as summarize_edit


LABELS = ("MAI-Image-2.6", "GPT-Image-2 low", "GPT-Image-2 medium", "GPT-Image-2 high")
GROUNDING_ARCHIVE = "data/lenovo-web-grounding-20260908"
EDIT_ARCHIVE = "data/edit-hat-swap-20260909-auto"
# MAI-only pass over the same prompts made earlier the same day as the paired run; evidence only.
MAI_ONLY_ARCHIVE = "data/mai-image-2.6-20260907"
# Later run measured with the same client, prompts and runner; its columns join the same tables
# but carry their own date and region because they are not the same session as the primary run.
SUPPLEMENT_ARCHIVE = "data/gpt25-paired-20260917"
# The tiers gpt-image-2.5-* accepts beyond low/medium/high, measured in a later run with the same
# client and prompt file.
TIER_ARCHIVE = "data/gpt25-tiers-20260918"
# Tiers each deployment accepts, per the Azure OpenAI image generation reference and verified
# against the live service on 2026-09-18. Used to decide whether the report may claim it covered
# every tier: gpt-image-2 rejects xhigh/max/auto, gpt-image-2.5-* accepts them.
OFFICIAL_TIERS = {
    "gpt-image-2": ("low", "medium", "high"),
    "gpt-image-2.5-flare": ("low", "medium", "high", "xhigh", "max", "auto"),
    "gpt-image-2.5-sunburst": ("low", "medium", "high", "xhigh", "max", "auto"),
}
TIER_ORDER = ("low", "medium", "high", "xhigh", "max", "auto")


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

    The published 2026-09-17 run claimed 'All Quality Tiers' in its title while covering only
    low/medium/high, because the runner's tier list was written for gpt-image-2. Deriving the
    claim from the data keeps the title from outrunning the measurement again.

    With no tier data at all the answer is 'not complete', never 'complete by default': an
    absent configuration block must not be able to grant a full-coverage claim.
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


def label_for(configuration):
    """Human-readable column label from a group configuration, e.g. gpt-image-2.5-flare/low -> GPT-Image-2.5 Flare low."""
    model = configuration["model"]
    if configuration["provider"] == "mai":
        return model
    parts = model.split("-")
    if len(parts) < 3 or parts[0] != "gpt" or parts[1] != "image":
        raise ValueError(f"Unrecognised GPT image model name: {model}")
    name = f"GPT-Image-{parts[2]}" + (" " + parts[3].capitalize() if len(parts) > 3 else "")
    return f"{name} {configuration['quality']}"


def load_supplement(root, prompts_path, archive=SUPPLEMENT_ARCHIVE):
    """Validated supplement run, or None when the archive is absent; nothing here is optional once present."""
    directory = root / archive
    if not directory.is_dir():
        return None
    summary = summarize(directory, prompts_path)
    regions = {group["configuration"].get("deployment_region") for group in summary["groups"]}
    if len(regions) != 1:
        raise ValueError("Supplement configurations must share one deployment region")
    return {"summary": summary, "archive": archive,
            "groups": [group["group"] for group in summary["groups"]],
            "labels": [label_for(group["configuration"]) for group in summary["groups"]],
            "date": summary["formal_started_at_utc"][:10], "region": regions.pop()}


def load_tier_supplement(root, prompts_path, archive=TIER_ARCHIVE):
    """The xhigh/max/auto run, or None when it has not been archived yet."""
    directory = root / archive
    if not directory.is_dir():
        return None
    summary = summarize(directory, prompts_path)
    results = json.loads((directory / "5way_v2_results.json").read_text("utf-8"))
    # The tier the service reported for each quality=auto request. Read from the response rather
    # than inferred from tokens: an explicit tier always returns a fixed token count, but auto's
    # self-reported medium came back at both 439 and 781 tokens, so tokens do not identify a tier.
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
        sample = f"{row['group']}-r{row['round']}-p{row['prompt_idx']:02d}"
        tier = echoed.get(sample)
        if not tier:
            continue
        chosen.setdefault(row["group"], {}).setdefault(tier, 0)
        chosen[row["group"]][tier] += 1
        auto_tokens.setdefault(row["group"], {}).setdefault(tier, set()).add(
            (row.get("token_info") or {}).get("output_tokens"))
    return {"summary": summary, "archive": archive,
            "groups": [group["group"] for group in summary["groups"]],
            "labels": [label_for(group["configuration"]) for group in summary["groups"]],
            "date": summary["formal_started_at_utc"][:10],
            "auto_choices": chosen,
            "auto_tokens": {group: {tier: sorted(values) for tier, values in tiers.items()}
                            for group, tiers in auto_tokens.items()}}


def render_tier_section(supplement, tier, language):
    """The six 2.5 tiers as one row per configuration.

    Laid out transposed because twelve configurations as columns do not read; the reader is
    comparing tiers down a column, not scanning one metric across twelve headings.
    """
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
                # A reported tier can cover more than one token count, so show them rather than
                # letting a single label imply a single cost.
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
    intro = ("`gpt-image-2.5-flare` 和 `gpt-image-2.5-sunburst` 接受六个质量档位，`gpt-image-2` 只接受前三个。"
             f"low、medium、high 来自 {supplement['date']} 的补测，xhigh、max、auto 来自 {tier['date']} 的补测，"
             "两次使用同一客户端、同一提示词文件和同一部署。显式指定某一档时，输出 token 是固定值，"
             "两个部署完全一致；`auto` 不是这样，见表下说明。"
             if chinese else
             "`gpt-image-2.5-flare` and `gpt-image-2.5-sunburst` accept six quality tiers; `gpt-image-2` accepts "
             f"only the first three. low, medium and high come from the {supplement['date']} run and xhigh, max and "
             f"auto from the {tier['date']} run, both using the same client, prompt file and deployments. "
             "When a tier is requested explicitly its output-token count is constant and identical across the two "
             "deployments; `auto` behaves differently, as noted below the table.")
    # Whether auto ever produced a token count the same tier never produces when asked explicitly.
    explicit_tokens = {}
    for label, group in zip(supplement["labels"], supplement["summary"]["groups"]):
        explicit_tokens.setdefault(label.rsplit(" ", 1)[1], set()).update(group["returned_output_tokens"])
    for label, group in zip(tier["labels"], tier["summary"]["groups"]):
        name = label.rsplit(" ", 1)[1]
        if name != "auto":
            explicit_tokens.setdefault(name, set()).update(group["returned_output_tokens"])
    extra = sorted({token for tiers in tier["auto_tokens"].values()
                    for name, values in tiers.items() for token in values
                    if token not in explicit_tokens.get(name, set())})
    divergence_cn = divergence_en = ""
    if extra:
        listed = "、".join(str(token) for token in extra)
        divergence_cn = (f"另外，`auto` 自报为某一档时，返回的 output token 不一定等于显式请求该档时的固定值："
                         f"本轮出现了 {listed} 这样的值，而显式请求同一档位在 22/22 个样本上都返回同一个固定值。"
                         "也就是说 `auto` 并不等同于替你选了某个档位，它的开销无法由自报档位推算。")
        divergence_en = (f" Moreover, when `auto` reports a tier, the returned output-token count is not necessarily "
                         f"the fixed value that tier returns when requested explicitly: this run produced "
                         f"{', '.join(str(token) for token in extra)}, while every explicitly requested tier returned "
                         "one constant across all 22 of its samples. `auto` is therefore not equivalent to selecting "
                         "that tier, and its cost cannot be derived from the tier it reports.")
    auto_note = ("`auto` 不是一个固定档位。服务按请求自行选择，并在响应里回显它实际使用的档位。"
                 "上表的 `auto` 行在括号中列出服务自报的档位及次数，取自响应字段，不是我们指定的。"
                 + divergence_cn +
                 "因此 `auto` 的耗时和 token 反映的是服务的选择行为，不能当作一个质量水平来比较。"
                 if chinese else
                 "`auto` is not a fixed tier. The service chooses per request and echoes the tier it used. "
                 "The `auto` rows above list, in parentheses, the tiers the service reported and how often, taken "
                 "from the response field rather than requested by us."
                 + divergence_en +
                 " Their latency and token figures therefore describe the service's selection behaviour, not one "
                 "quality level.")
    return "\n\n".join([heading, intro, table(headers, rows), auto_note])


def load_text_study(root, archive="data/text-rendering-20260918", prompts_name="prompts-text-rendering.csv",
                    kind="easy"):
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
    return {**data, "archive": archive, "prompts": prompts, "kind": kind, "prompts_name": prompts_name,
            "calibration": calibration}


def render_text_section(study, language):
    """Text rendering in Chinese versus English, one row per configuration.

    Written so the section stands on its own: the reader sees the exact prompt, what the model was
    asked to spell, who read the result back, and what that reader's own error rate is.
    """
    chinese = language == "zh"
    scenes = [item for item in study["prompts"] if item["language"] == "en"]
    # Denominators come from the scored samples, not the CSV's declared counts: the scoring rule
    # strips whitespace, so "JASMINE GREEN TEA" is 15 characters here, not 17.
    per_round = {}
    for sample in study["samples"]:
        if sample["round"] == 1 and sample["group"] == study["samples"][0]["group"]:
            per_round[sample["language"]] = per_round.get(sample["language"], 0) + sample["chars"]
    en_chars, zh_chars = per_round.get("en", 0), per_round.get("zh", 0)

    hard = study.get("kind") == "hard"
    scene_count = len(scenes)
    first_pair = scenes[0]["pair_id"] if scenes else "P1"
    if hard:
        heading = ("## 中英文文字渲染：难题集，全部 16 个配置" if chinese else
                   "## Chinese and English Text Rendering: Hard Set, All 16 Configurations")
        question = ("**问题**：上一节的短词每个模型都接近满分，没有区分度。换成专门针对中文难点的题目——长句、简繁体陷阱、数字混排、"
                    "竖排、多行、手写——且每个部署的每个档位都测，差距会在哪里出现。"
                    if chinese else
                    "**Question**: the short targets in the previous section scored near 100% for every model and "
                    "had no discriminating power. With scenes built around known Chinese failure modes (long "
                    "strings, simplified-vs-traditional traps, digits mixed with script, vertical layout, "
                    "multi-line, handwriting) and every deployment measured at every tier, where do gaps appear?")
    else:
        heading = "## 中英文文字渲染" if chinese else "## Chinese and English Text Rendering"
        question = ("**问题**：同一个场景，只把要写的文字从英文换成中文，模型把字写对的比例差多少。"
                    if chinese else
                    "**Question**: for the same scene, with only the language of the required text changed, "
                    "how much does the share of correctly rendered characters differ?")

    def target_of(pair_id, lang):
        return "`" + next(p["target"].replace("|", " / ") for p in study["prompts"]
                          if p["pair_id"] == pair_id and p["language"] == lang) + "`"

    if hard:
        prompt_rows = [[item["pair_id"], item["scene"], item["tests"], target_of(item["pair_id"], "en"),
                        target_of(item["pair_id"], "zh")] for item in scenes]
        prompt_table = table(["场景", "画面", "针对的难点", "英文目标", "中文目标"] if chinese else
                             ["Pair", "Scene", "Tests", "English target", "Chinese target"], prompt_rows)
    else:
        prompt_rows = [[item["pair_id"], item["scene"], target_of(item["pair_id"], "en"),
                        target_of(item["pair_id"], "zh")] for item in scenes]
        prompt_table = table(["场景", "画面", "英文目标", "中文目标"] if chinese else
                             ["Pair", "Scene", "English target", "Chinese target"], prompt_rows)
    example = next(item["prompt"] for item in study["prompts"] if item["pair_id"] == first_pair
                   and item["language"] == "en")
    example_zh = next(item["prompt"] for item in study["prompts"] if item["pair_id"] == first_pair
                      and item["language"] == "zh")
    count_cn = {5: "五", 6: "六"}.get(scene_count, str(scene_count))
    count_en = {5: "five", 6: "six"}.get(scene_count, str(scene_count))
    inputs = (f"**真实输入**：{count_cn}个场景，每个写成中英两版，除了要求写的文字之外场景描述一致。例如 {first_pair} 的两版提示词："
              f"\n\n> {example}\n>\n> {example_zh}\n\n每轮的分母是固定的：英文 {en_chars} 个字符，中文 {zh_chars} 个字符。"
              "中文表达同样内容用字更少，所以两种语言各按自己的分母计算，不互相通分。"
              if chinese else
              f"**Actual input**: {count_en} scenes, each written in English and Chinese, identical apart from the "
              f"text to be rendered. The two {first_pair} prompts, verbatim:\n\n> {example}\n>\n> {example_zh}\n\n"
              f"Denominators are fixed per round: {en_chars} English characters and {zh_chars} Chinese "
              "characters. Chinese expresses the same content in fewer characters, so each language is scored "
              "against its own denominator and the two are never pooled.")
    controlled = ("**受控变量**：同一客户端、同一账户、同一区域（Sweden Central）、同一 GlobalStandard 部署配额、"
                  "同一 1024x1024 分辨率、两轮。配对内唯一变化的是文字的语言。"
                  if chinese else
                  "**Controlled variables**: one client, one account, one region (Sweden Central), the same "
                  "GlobalStandard quota, 1024x1024, two rounds. Within a pair, only the language of the text changes.")

    rows = []
    for group in sorted(study["summary"]):
        stats = study["summary"][group]
        row = [group]
        for lang in ("en", "zh"):
            item = stats.get(lang)
            if not item:
                row += ["N/A", "N/A"]
                continue
            row += [f"{item['matched_chars']}/{item['total_chars']} = {item['char_accuracy']:.0%}",
                    f"{item['exact_segments']}/{item['total_segments']} = {item['exact_rate']:.0%}"]
        rows.append(row)
    headers = (["配置", "英文字符准确率", "英文整段正确", "中文字符准确率", "中文整段正确"] if chinese else
               ["Configuration", "English character accuracy", "English exact segments",
                "Chinese character accuracy", "Chinese exact segments"])
    results = table(headers, rows)

    judging = ("**判读方法**：每张图交给 `gpt-5.6-terra` 读出图中文字，再与目标字符串程序化比对，比对时忽略全部空白。"
               "两个口径同时给出：字符准确率取整段转录中与目标最接近的等长窗口逐字符算分，整段正确要求目标串以子串形式"
               "完整出现、不给部分分。这是模型判读，不是人工盲评。判读器是 OpenAI 系列模型，而被判的一方也包括 OpenAI "
               "的图像模型；下面的校准只能排除它读不清中文，不能排除它对某一家的风格更宽容，所以每组都附拼图供人眼复核。"
               if chinese else
               "**How it was judged**: each image is transcribed by `gpt-5.6-terra` and compared with the target "
               "string programmatically, ignoring all whitespace. Two denominators are reported: character accuracy "
               "scores the best-matching window of equal length anywhere in the transcription, character by "
               "character; exact segments requires the target to appear verbatim as a substring, with no partial "
               "credit. This is model-judged, not a blind human study. The judge is an OpenAI-family model and "
               "some of the judged images come from OpenAI image models; the calibration below rules out an "
               "inability to read Chinese, not a lenience toward one vendor's style, which is why every group has "
               "a contact sheet for human review.")
    superseded = study.get("superseded")
    correction = ""
    if superseded:
        correction = ("**口径更正**：第一版评分把每个目标串只与转录中的**单独一行**比对。判读器每个视觉文字块输出一行，"
                      "所以模型把一句话分两行排版就被判成拼写错误；这个惩罚随目标长度增长，而英文目标是中文的 2–4 倍长，"
                      "于是英文被系统性低估——正好落在本测试要检验的方向上。61 个样本受影响。更正后的规则忽略空白、"
                      f"在整段转录中匹配；第一版结果保留为 [`{superseded['file']}`]({study['archive']}/{superseded['file']})，"
                      "不删除。"
                      if chinese else
                      "**Scoring correction**: the first pass matched each target against a **single transcribed "
                      "line**. The judge emits one line per visual text block, so a model that wrapped a phrase onto "
                      "two lines was scored as misspelling it; the penalty grew with target length, and the English "
                      "targets are two to four times longer than the Chinese ones, so English was systematically "
                      "understated in exactly the direction this test was meant to examine. 61 samples were affected. "
                      "The corrected rule ignores whitespace and matches anywhere in the transcription; the first-pass "
                      f"scores are kept as [`{superseded['file']}`]({study['archive']}/{superseded['file']}) rather "
                      "than deleted.")
    cal = study.get("calibration")
    if cal:
        en_cal, zh_cal = cal["summary"]["en"], cal["summary"]["zh"]
        font = cal.get("font", "msyh.ttc")
        font_name = "微软雅黑" if font.lower().startswith("msyh") else font
        font_name_en = "Microsoft YaHei" if font.lower().startswith("msyh") else font
        calibration = (f"**判读器的误差下限**：把本节同样的目标文字用{font_name}渲染成图再让判读器读回来，英文 "
                       f"{en_cal['matched_chars']}/{en_cal['total_chars']}（{en_cal['char_accuracy']:.1%}），中文 "
                       f"{zh_cal['matched_chars']}/{zh_cal['total_chars']}（{zh_cal['char_accuracy']:.1%}），与上表同一套评分规则。"
                       "也就是说判读器对这些字符没有系统性偏见，上表的差距可以归到生成模型。边界：这只证明判读器能读清晰的横排文字；"
                       "生成图里扭曲、艺术化或竖排的字更难读，所以上表可能低估、不会高估。校准的渲染图与转录在 "
                       f"[judge-calibration]({study['archive']}/judge-calibration)，`calibrate_text_judge.py --check` 可离线重算；"
                       "每组的拼图见证据目录，可以逐张核对。"
                       if chinese else
                       f"**The judge's own error floor**: rendering this section's targets with {font_name_en} and asking "
                       f"the judge to read them back scores {en_cal['matched_chars']}/{en_cal['total_chars']} "
                       f"({en_cal['char_accuracy']:.1%}) for English and {zh_cal['matched_chars']}/{zh_cal['total_chars']} "
                       f"({zh_cal['char_accuracy']:.1%}) for Chinese under the same scoring rule as the table. The judge "
                       "therefore has no systematic bias against these characters, and the gaps above are attributable "
                       "to the image models. Boundary: this only establishes that the judge reads clean horizontal "
                       "renders; distorted, stylised or vertical text in generated images is harder, so the table may "
                       "understate accuracy and will not overstate it. The renders and transcriptions are in "
                       f"[judge-calibration]({study['archive']}/judge-calibration) and `calibrate_text_judge.py --check` "
                       "recomputes them offline; per-group contact sheets in the evidence directory allow every image "
                       "to be checked by eye.")
    else:
        calibration = ("**判读器的误差下限**：本节的目标文字没有做判读器校准，上表的差距里包含未知大小的判读误差。"
                       if chinese else
                       "**The judge's own error floor**: the judge was not calibrated on this section's targets, so the "
                       "gaps above include a judging error of unknown size.")
    boundary = (f"**结论边界**：{study['scored_samples']} 个成功样本，覆盖 {scene_count} 个场景、2 轮。"
                "这是指定字符串的拼写准确率，不是排版美观度、字体质量或中文设计感的评价。"
                "MAI-Image-2.6 不接受质量参数，它的行只有一个配置。"
                "**官方支持范围**：Foundry 模型文档将 MAI-Image-2.6 的 Languages 标为 `en`，中文不在其声明的支持范围内；"
                "本节的中文结果是在声明范围之外观察到的行为，不构成产品承诺，也不应被当作已支持的能力来引用。"
                if chinese else
                f"**Boundary**: {study['scored_samples']} successful samples across {scene_count} scenes and 2 rounds. "
                "This measures spelling accuracy for a specified string, not typographic quality, font choice or "
                "design appeal. MAI-Image-2.6 takes no quality parameter and therefore has a single row. "
                "**Declared support**: the Foundry model documentation lists MAI-Image-2.6 Languages as `en`; "
                "Chinese is outside its declared scope. The Chinese results here are observed behaviour outside "
                "that scope, not a product commitment, and should not be cited as a supported capability.")
    evidence = (f"证据目录：[{study['archive']}]({study['archive']})。提示词 SHA-256：`{study['prompt_sha256']}`。"
                if chinese else
                f"Evidence directory: [{study['archive']}]({study['archive']}). "
                f"Prompt SHA-256: `{study['prompt_sha256']}`.")
    return "\n\n".join(part for part in [heading, question, inputs, prompt_table, controlled, results,
                                          judging, correction, calibration, boundary, evidence] if part)


def load_billing(root, archive="data/billing-20260920"):
    """Effective prices read from this account's own Azure invoice, or None if not archived."""
    path = root / archive / "effective-prices.json"
    if not path.is_file():
        return None
    return {**json.loads(path.read_text("utf-8")), "archive": archive}


def render_cost_section(billing, language):
    """Cost per image from measured tokens x the price this account was actually billed.

    Every earlier cost figure in this report rested on a published list price or a third-party
    reference chart. This section replaces both with the invoice for the account that ran every
    test here, read from Azure Cost Management.
    """
    chinese = language == "zh"
    prices = billing["usd_per_million_output_image_tokens"]
    per_image = billing["usd_per_1000_images"]
    tokens = billing["tokens_per_1024_image"]
    mai_cost = per_image["MAI-Image-2.6"]

    heading = "## 每张图的实际成本（来自本账户账单）" if chinese else "## Actual Cost per Image, from This Account's Invoice"
    question = ("**问题**：MAI-Image-2.6 到底贵不贵。答案取决于跟 GPT 的哪个质量档位比，而档位之间的算力相差 36 倍。"
                if chinese else
                "**Question**: is MAI-Image-2.6 expensive? The answer depends on which GPT quality tier it is "
                "compared against, and the tiers differ by 36x in billed compute.")
    source = (f"**数据来源**：Azure Cost Management 对运行本仓库全部测试的账户（Sweden Central）的实际计费查询，"
              f"周期 {billing['period']}，字段 `PreTaxCost`。每个模型的输出图 token 单独计费，"
              "把金额除以计费 token 数得到实际单价。GPT-Image-2 的账单单价与公布价 $30/1M 完全一致，"
              "说明账单读数准确。GPT-Image-2.5 的价格在定价页上尚未公布，账单是目前唯一的官方数据。"
              if chinese else
              f"**Source**: an Azure Cost Management ActualCost query against the account that ran every test in "
              f"this repository (Sweden Central), period {billing['period']}, field `PreTaxCost`. Each model's "
              "output-image tokens are metered separately; dividing cost by billed tokens gives the effective "
              "rate. GPT-Image-2's billed rate equals its published list price of $30 per 1M tokens, which "
              "confirms the invoice reading. GPT-Image-2.5 has no published price yet; the invoice is the only "
              "official figure available.")

    price_rows = [[name, f"${rate:.2f}"] for name, rate in sorted(prices.items(), key=lambda i: i[1])]
    price_table = table(["模型", "实际计费 USD / 1M 输出图 token"] if chinese else
                        ["Model", "Billed USD per 1M output-image tokens"], price_rows)

    rows = []
    for config, cost in sorted(per_image.items(), key=lambda i: i[1]):
        marker = " **(MAI)**" if config.startswith("MAI") else ""
        rows.append([config + marker, f"{tokens[config]:,}", f"${cost:.2f}", f"{cost / mai_cost:.2f}x"])
    cost_table = table(["配置", "token / 张", "USD / 1,000 张", "相对 MAI"] if chinese else
                       ["Configuration", "Tokens / image", "USD / 1,000 images", "vs MAI"], rows)

    mai_rate, gpt_rate = prices["MAI-Image-2.6"], prices["gpt-image-2.5-flare"]
    premium = (mai_rate - gpt_rate) / gpt_rate
    reading = (f"**怎么读**：按单 token 计，MAI 比 GPT 系列贵 {premium:.0%}（${mai_rate:.0f} 对 ${gpt_rate:.0f}）。"
               f"但 MAI 每张固定 {tokens['MAI-Image-2.6']:,} token，而 GPT 的算力随档位变化。"
               f"于是 MAI 每千张 ${mai_cost:.2f}：比 GPT-2.5 medium（${per_image['gpt-image-2.5 medium']:.2f}）贵 "
               f"{mai_cost / per_image['gpt-image-2.5 medium']:.1f} 倍，比 GPT-2.5 high 和 GPT-2 medium"
               f"（${per_image['gpt-image-2.5 high']:.2f}）便宜 {1 - mai_cost / per_image['gpt-image-2.5 high']:.0%}，"
               f"比 GPT-2 high（${per_image['gpt-image-2 high']:.2f}）便宜 {1 - mai_cost / per_image['gpt-image-2 high']:.0%}。"
               "「贵」这个词只有先绑定对比档位才有意义。哪一档与 MAI 质量相当，由本报告的并排图和人工复核回答，不由价格回答。"
               if chinese else
               f"**How to read this**: per token, MAI costs {premium:.0%} more than the GPT family "
               f"(${mai_rate:.0f} vs ${gpt_rate:.0f}). But MAI is a constant {tokens['MAI-Image-2.6']:,} tokens per "
               f"image while GPT compute varies by tier. MAI therefore costs ${mai_cost:.2f} per 1,000 images: "
               f"{mai_cost / per_image['gpt-image-2.5 medium']:.1f}x GPT-2.5 medium "
               f"(${per_image['gpt-image-2.5 medium']:.2f}), {1 - mai_cost / per_image['gpt-image-2.5 high']:.0%} "
               f"less than GPT-2.5 high and GPT-2 medium (${per_image['gpt-image-2.5 high']:.2f}), and "
               f"{1 - mai_cost / per_image['gpt-image-2 high']:.0%} less than GPT-2 high "
               f"(${per_image['gpt-image-2 high']:.2f}). \"Expensive\" is meaningless until the comparison tier is "
               "named. Which tier matches MAI in quality is answered by this report's side-by-side images and "
               "human review, not by price.")
    boundary = ("**边界**：单价是本账户 GlobalStandard 按需计费的实际值，不含协议折扣；token 数是各配置在本仓库全部测试中"
                "恒定不变的实测值；不含输入文本 token（每张不到 $0.001）。这是按 token 的成本，不是按质量的成本。"
                if chinese else
                "**Boundary**: rates are this account's GlobalStandard pay-as-you-go actuals with no negotiated "
                "discount; token counts are the measured constants each configuration returned across every run "
                "here; input text tokens (under $0.001 per image) are excluded. This is cost per token, not cost "
                "per unit of quality.")
    evidence = (f"证据：[{billing['archive']}]({billing['archive']})（原始 Cost Management 响应与反算脚本）。"
                if chinese else
                f"Evidence: [{billing['archive']}]({billing['archive']}) (raw Cost Management response and the "
                "derivation).")
    return "\n\n".join([heading, question, source, price_table, cost_table, reading, boundary, evidence])


def load_head_to_head(root, prompts_path, archive="data/mai-vs-gpt25-20260920"):
    """MAI and gpt-image-2.5-flare interleaved in one run, or None when not archived."""
    directory = root / archive
    if not (directory / "5way_v2_results.json").is_file():
        return None
    summary = summarize(directory, prompts_path)
    return {"summary": summary, "archive": archive,
            "groups": [group["group"] for group in summary["groups"]],
            "labels": [label_for(group["configuration"]) for group in summary["groups"]],
            "date": summary["formal_started_at_utc"][:10]}


def render_head_to_head(head, billing, language):
    """MAI-Image-2.6 against the current GPT image model, same session, same prompts.

    Every other GPT-Image-2.5 number in this report comes from a separate session. Only here were
    MAI and 2.5 called alternately by one client in one run, so latency and images are directly
    comparable without a date caveat.
    """
    chinese = language == "zh"
    groups = dict(zip(head["labels"], head["summary"]["groups"]))
    per_image = billing["usd_per_1000_images"] if billing else {}

    heading = ("## MAI-Image-2.6 对 GPT-Image-2.5：同一会话直接对比" if chinese else
               "## MAI-Image-2.6 vs GPT-Image-2.5: Same-Session Head-to-Head")
    question = ("**问题**：把 MAI-Image-2.6 和当前主流的 GPT-Image-2.5 放进同一个 run，交错调用，出图速度和成本各是多少。"
                "选 flare 的 medium 与 high，因为它们是 token 上紧贴 MAI 下方（439）和上方（1,756）的两档。"
                if chinese else
                "**Question**: with MAI-Image-2.6 and the current mainstream GPT-Image-2.5 in one run, called "
                "alternately, what are the latency and cost of each? flare medium and high are chosen because "
                "they are the tiers immediately below (439 tokens) and above (1,756) MAI on the token ladder.")
    controlled = (f"**受控变量**：一个客户端、一个账户、一个区域（Sweden Central）、同一 11 条提示词、1024x1024、两轮，"
                  f"三组按固定顺序交错，{head['date']} 单次会话完成。这消除了本报告其他 2.5 数据所带的「不同日期」注释。"
                  if chinese else
                  f"**Controlled variables**: one client, one account, one region (Sweden Central), the same eleven "
                  f"prompts, 1024x1024, two rounds, the three configurations interleaved in fixed order, completed in "
                  f"one session on {head['date']}. This removes the different-date caveat every other 2.5 figure in "
                  "this report carries.")

    rows = []
    for label, group in groups.items():
        latency = group["successful_request_latency"] or {}
        tokens = group["returned_output_tokens"]
        token_text = str(tokens[0]) if len(tokens) == 1 else (f"{min(tokens)}–{max(tokens)}" if tokens else "N/A")
        cost_key = ("MAI-Image-2.6" if label.startswith("MAI") else
                    "gpt-image-2.5 " + label.rsplit(" ", 1)[1])
        cost = f"${per_image[cost_key]:.2f}" if cost_key in per_image else "—"
        rows.append([label, f"{group['successful_samples']} / {group['planned_samples']}", token_text,
                     number(latency.get("mean_seconds")), number(latency.get("p50_seconds")),
                     number(latency.get("p95_seconds")), cost])
    headers = (["配置", "成功 / 计划", "输出 token", "平均耗时 (s)", "P50 (s)", "描述性 P95 (s)", "USD / 1,000 张"]
               if chinese else
               ["Configuration", "Successful / planned", "Output tokens", "Mean latency (s)", "P50 (s)",
                "Descriptive P95 (s)", "USD / 1,000 images"])
    metrics = table(headers, rows)

    mai = groups.get("MAI-Image-2.6", {}).get("successful_request_latency") or {}
    med = groups.get("GPT-Image-2.5 Flare medium", {}).get("successful_request_latency") or {}
    high = groups.get("GPT-Image-2.5 Flare high", {}).get("successful_request_latency") or {}
    reading = ""
    if mai and med and high:
        def relation(ratio, zh):
            # Within ±5% the two are indistinguishable at this sample size.
            if abs(ratio - 1) <= 0.05:
                return "持平" if zh else "level"
            if ratio > 1:
                return f"MAI 慢 {ratio:.2f} 倍" if zh else f"MAI {ratio:.2f}x slower"
            return f"MAI 快 {1 / ratio:.2f} 倍" if zh else f"MAI {1 / ratio:.2f}x faster"
        r_med, r_high = mai["p50_seconds"] / med["p50_seconds"], mai["p50_seconds"] / high["p50_seconds"]
        reading = (f"**怎么读**：同一会话里，MAI 的 P50 是 {number(mai['p50_seconds'])} s，2.5 medium 是 "
                   f"{number(med['p50_seconds'])} s（{relation(r_med, True)}），"
                   f"2.5 high 是 {number(high['p50_seconds'])} s（{relation(r_high, True)}）。"
                   "在速度和每张成本上，2.5 medium 都优于 MAI；对 2.5 high，MAI 速度持平、每张便宜 26%。"
                   "MAI 的位置取决于画质：如果 medium 的画质够用，MAI 没有优势；如果需要 high 的画质，MAI 是更便宜的选择。"
                   "每个场景的三张图并排在下方，读者自己判断。"
                   if chinese else
                   f"**How to read this**: in the same session, MAI's P50 is {number(mai['p50_seconds'])} s, 2.5 "
                   f"medium's {number(med['p50_seconds'])} s ({relation(r_med, False)}), 2.5 high's "
                   f"{number(high['p50_seconds'])} s ({relation(r_high, False)}). On speed and cost per image, 2.5 "
                   "medium beats MAI; against 2.5 high, MAI is level on speed and 26% cheaper per image. MAI's "
                   "position depends on image quality: if medium's output is good enough, MAI has no advantage; if "
                   "high's quality is needed, MAI is the cheaper option. The three images for every scenario are "
                   "side by side below; readers judge for themselves.")

    images = []
    for prompt_record in head["summary"]["per_prompt"]:
        images.append(f"**{'第' if chinese else 'Scenario'} {prompt_record['prompt_index']}"
                      f"{'题' if chinese else ''}** — {prompt_record['prompt'][:90]}"
                      f"{'…' if len(prompt_record['prompt']) > 90 else ''}")
        for round_number in (1, 2):
            images.append(comparison_table(prompt_record, round_number, head["archive"], language,
                                           head["groups"], head["labels"]))
    boundary = ("**边界**：这是三组配置在一个会话内的直接测量。图像质量没有数值分数：并排图是证据，读者的判断是结论。"
                "2.5 的价格取自本账户账单（见上一节），定价页尚未公布。"
                if chinese else
                "**Boundary**: a direct measurement of three configurations in one session. Image quality has no "
                "numeric score here: the side-by-side images are the evidence and the reader's judgement is the "
                "conclusion. 2.5 pricing is this account's billed rate (previous section); no list price is published.")
    evidence = (f"证据目录：[{head['archive']}]({head['archive']})。" if chinese else
                f"Evidence directory: [{head['archive']}]({head['archive']}).")
    return "\n\n".join([heading, question, controlled, metrics, reading, *images, boundary, evidence])


def supplement_prompt(supplement, prompt_record):
    """The supplement's record for the same scenario; prompt text must match byte for byte."""
    matches = [item for item in supplement["summary"]["per_prompt"] if item["prompt_index"] == prompt_record["prompt_index"]]
    if len(matches) != 1 or matches[0]["prompt"] != prompt_record["prompt"]:
        raise ValueError("Supplement scenario does not match the primary prompt")
    return matches[0]


def table(headers, rows):
    if any(len(row) != len(headers) for row in rows):
        raise ValueError("Table row does not match its header")
    return "\n".join(["| " + " | ".join(headers) + " |",
                      "| " + " | ".join("---" for _ in headers) + " |",
                      *("| " + " | ".join(str(value) for value in row) + " |" for row in rows)])


def round_rows(prompt_record, round_number, groups=GROUPS):
    configurations = prompt_record["configurations"]
    if [item["group"] for item in configurations] != list(groups):
        count = {4: "four", 6: "six"}.get(len(groups), str(len(groups)))
        raise ValueError(f"Every scenario must contain all {count} configurations in display order")
    selected = []
    for configuration in configurations:
        matches = [row for row in configuration["rounds"] if row["round"] == round_number]
        if len(matches) != 1:
            raise ValueError("Every configuration must contain exactly one result for this round")
        selected.append(matches[0])
    return selected


def comparison_table(prompt_record, round_number, archive_path, language, groups=GROUPS, labels=LABELS):
    rows = round_rows(prompt_record, round_number, groups)
    images = []
    details = []
    for label, row in zip(labels, rows):
        if row["ok"]:
            if not row["image"]:
                raise ValueError("Successful sample is missing its original image")
            image_path = row["image"]
            expected_path = f"{groups[len(images)]}/r{round_number}/{prompt_record['prompt_index']:02d}_test.png"
            if image_path != expected_path:
                raise ValueError("Displayed image does not belong to its configuration")
            alt = f"{label}, prompt {prompt_record['prompt_index']}, round {round_number}"
            images.append(f"![{alt}]({archive_path}/{image_path})")
            details.append(f"{row['request_seconds']:.2f} s<br>{row['image_kib']:.0f} KiB")
        else:
            if row["image"] is not None:
                raise ValueError("Failed sample cannot display a replacement image")
            images.append("未返回图片" if language == "zh" else "No image returned")
            details.append((f"{row['attempts']} 次尝试；任务耗时 {row['logical_request_seconds']:.2f} s"
                            if language == "zh" else
                            f"{row['attempts']} attempts; logical duration {row['logical_request_seconds']:.2f} s"))
    return table(list(labels), [images, details])


def prompt_latency_table(summary, language, supplement=None):
    headers = ["场景 / 轮次" if language == "zh" else "Scenario / round", *LABELS]
    if supplement:
        headers.extend(supplement["labels"])
    rows = []
    for prompt_record in summary["per_prompt"]:
        for round_number in (1, 2):
            values = round_rows(prompt_record, round_number)
            if supplement:
                values = values + round_rows(supplement_prompt(supplement, prompt_record), round_number, supplement["groups"])
            rows.append([f"{prompt_record['prompt_index']:02d} / R{round_number}",
                         *(f"{row['request_seconds']:.2f}" if row["ok"] else
                           ("失败" if language == "zh" else "Failed") for row in values)])
    return table(headers, rows)


def number(value, decimals=2):
    return "N/A" if value is None else f"{value:,.{decimals}f}"


def metrics_table(summary, language, supplement=None):
    groups = list(summary["groups"])
    labels = list(LABELS)
    if supplement:
        groups.extend(supplement["summary"]["groups"])
        labels.extend(supplement["labels"])
    definitions = [
        ("成功 / 计划样本", "Successful / planned samples", lambda group: f"{group['successful_samples']} / {group['planned_samples']}"),
        ("首试成功 / 计划样本", "First-attempt successes / planned", lambda group: f"{group['first_attempt_successful_samples']} / {group['planned_samples']}"),
        ("HTTP 尝试次数 / 429", "HTTP attempts / 429 responses", lambda group: f"{group['formal_http_attempts']} / {group['http_429_attempts']}"),
        ("未成功的 HTTP 尝试", "Unsuccessful HTTP attempts", lambda group: str(group['unsuccessful_http_attempts'])),
        ("未成功尝试累计耗时 (s)", "Total unsuccessful attempt duration (s)", lambda group: number(group['unsuccessful_attempt_seconds'])),
        ("平均请求耗时 (s)", "Mean request latency (s)", lambda group: number((group['successful_request_latency'] or {}).get('mean_seconds'))),
        ("P50 / 描述性 P95 (s)", "P50 / descriptive P95 (s)", lambda group: number((group['successful_request_latency'] or {}).get('p50_seconds')) + " / " + number((group['successful_request_latency'] or {}).get('p95_seconds'))),
        ("样本标准差 (s)", "Sample standard deviation (s)", lambda group: number((group['successful_request_latency'] or {}).get('sample_stddev_seconds'))),
        ("最小 / 最大请求耗时 (s)", "Minimum / maximum request latency (s)", lambda group: number((group['successful_request_latency'] or {}).get('minimum_seconds')) + " / " + number((group['successful_request_latency'] or {}).get('maximum_seconds'))),
        ("第一轮 / 第二轮平均 (s)", "Round 1 / round 2 mean (s)", lambda group: " / ".join(number(item['latency']['mean_seconds']) if item['latency'] else "N/A" for item in group['per_round'])),
        ("全部样本平均任务耗时 (s)", "Mean logical duration, all samples (s)", lambda group: number(group['logical_request_latency_all_samples']['mean_seconds'])),
        ("成功图片平均大小 (KiB)", "Mean successful PNG size (KiB)", lambda group: number(group['mean_image_kib'], 0)),
    ]
    rows = []
    for chinese, english, value in definitions:
        rows.append([chinese if language == "zh" else english,
                     *(value(group) for group in groups)])
    return table(["指标" if language == "zh" else "Metric", *labels], rows)


def usage_table(summary, language, supplement=None):
    rows = []
    pairs = list(zip(LABELS, summary["groups"]))
    if supplement:
        pairs.extend(zip(supplement["labels"], supplement["summary"]["groups"]))
    for label, group in pairs:
        tokens = group["returned_output_tokens"]
        token_label = str(tokens[0]) if len(tokens) == 1 else (f"{min(tokens)}-{max(tokens)}" if tokens else "N/A")
        rows.append([label, token_label, f"{group['successful_samples']}/{group['planned_samples']}"])
    headers = (["配置", "返回的输出 token", "成功 / 计划样本"] if language == "zh" else
               ["Configuration", "Returned output tokens", "Successful / planned samples"])
    return table(headers, rows)


def exception_section(summary, language, supplement=None):
    attempts = list(summary["unsuccessful_attempts"])
    if supplement:
        attempts.extend(supplement["summary"]["unsuccessful_attempts"])
    if not attempts:
        return "本轮未记录失败尝试。" if language == "zh" else "No unsuccessful attempts were recorded."
    headers = (["样本", "尝试", "HTTP / 异常类型", "客户端耗时 (s)", "开始 (UTC)", "结束 (UTC)"]
               if language == "zh" else ["Sample", "Attempt", "HTTP / exception", "Client duration (s)", "Started (UTC)", "Finished (UTC)"])
    rows = [[attempt["sample_id"], str(attempt["attempt"]),
             attempt["exception_type"] or str(attempt["http_status"]), number(attempt["request_seconds"]),
             attempt["started_at_utc"], attempt["finished_at_utc"]] for attempt in attempts]
    longest = max(attempts, key=lambda attempt: attempt["request_seconds"])
    text = (f"最长的未成功尝试是 `{longest['sample_id']}`，客户端记录 {number(longest['request_seconds'])} 秒。"
            "这是请求调用的客户端经过时间，不是服务端 GPU 推理时长；底层原因未被这些日志确定。异常保留在任务耗时、请求计数和实际完成速率中，未返回图片的样本仍计入计划分母。"
            if language == "zh" else
            f"The longest unsuccessful attempt was `{longest['sample_id']}` at {number(longest['request_seconds'])} client-observed seconds. "
            "This is elapsed client request time, not server-side GPU inference duration; these logs do not establish the underlying cause. Exceptions remain in logical durations, attempt counts and observed completion rate, and missing-image samples remain in the planned denominator.")
    return text + "\n\n" + table(headers, rows)


def reproduction_section(archive_path, language, grounding_archive=None, edit_archive=None, supplement_archive=None,
                         tier_archive=None, head_archive=None, text_archives=(), billing_archive=None):
    zh = language == "zh"
    intro = ("需要可用的 MAI-Image-2.6 和 GPT-Image-2 部署。部署身份由您查询确认，不能仅凭 deployment 名称判断底层模型。先克隆仓库、拉取本项目的 Git LFS 文件，并在 Python 环境安装 requests："
             if language == "zh" else
             "Supply accessible MAI-Image-2.6 and GPT-Image-2 deployments. Verify their underlying model versions; deployment names alone are not model identity. Clone the repository, fetch this project's Git LFS inputs, and install requests in your Python environment:")
    credentials = ("下列两个资源根地址和 GPT deployment 名称由您填写。通过自己的秘密管理机制在当前进程提供 `AZURE_API_KEY`（MAI）和 `AZURE_OPENAI_API_KEY`（GPT），不要把值写入源码或 Git。各模型的版本、区域、SKU 和限额环境变量必须填写实际查询结果；下面展示本次实测元数据，不代表您的资源设置。"
                   if language == "zh" else
                   "Replace the two resource origins and GPT deployment name below. Supply `AZURE_API_KEY` (MAI) and `AZURE_OPENAI_API_KEY` (GPT) in the process through your secret-management mechanism, never source control. Model version, region, SKU and rate-limit metadata must match your verified deployments; the values below describe this measurement, not your resources.")
    continuation = ("第一条模型命令只预热四组，第二条从同一输出目录继续正式矩阵；均会消耗 Azure 服务用量。已有结果不会覆盖，已记录样本不会重跑。续跑要求同一脚本、提示词、端点和配置；中断时在途请求可能已被服务接收。新测试应在执行前保存脚本与 CSV，运行期间不得修改。"
                    if language == "zh" else
                    "The first model command runs four warmups; the second continues the same output directory through the formal matrix. Both consume Azure service usage. Existing results are not overwritten and recorded samples are not rerun. Resume requires unchanged script, prompts, endpoints and configuration. An interrupted in-flight request may already have reached the service. Save the script and CSV before each new run and keep them unchanged during execution.")
    tests = ("以下命令只重算已保存结果，不调用模型。回归覆盖四档请求、失败分母、原始 usage、图片归属和报告覆盖；模拟 HTTP 只用于离线单元测试，不是图像质量证据。新测批次的汇总与发布必须等全部计划样本结束。"
             if language == "zh" else
             "These commands validate saved evidence without model calls. Regressions cover request tiers, failure denominators, original usage, image ownership and report coverage. HTTP mocks exist only in offline tests and do not establish image quality. A new run cannot produce its final summary until every planned sample is recorded.")
    route_rows = ([
            ["只读核验已发布证据", "步骤 4", "不需要 / 不计费", "汇总器与回归测试返回 `PASS`"],
            ["重跑 11 个文生图场景", "步骤 3", "MAI + GPT / 会计费", "88 个正式样本全部记录"],
            ["重跑联网信息补充测试", "步骤 5", "MAI / 会计费", "新目录包含开／关两轮结果"],
            ["重跑换帽图像编辑", "步骤 6", "MAI + GPT / 会计费", "两轮 8 张 PNG 通过 hash 检查"],
        ] if language == "zh" else [
            ["Verify published evidence", "Step 4", "None / no", "summaries and regressions return `PASS`"],
            ["Rerun 11 text-to-image scenarios", "Step 3", "MAI + GPT / yes", "all 88 formal samples are recorded"],
            ["Rerun web-grounding comparison", "Step 5", "MAI / yes", "new directory contains both rounds, off and on"],
            ["Rerun headwear-swap edit", "Step 6", "MAI + GPT / yes", "eight PNGs across two rounds pass hash checks"],
        ])
    if supplement_archive:
        route_rows.append(["重跑 GPT-Image-2.5 low/medium/high 补测", "步骤 7", "GPT-2.5 两个部署 / 会计费", "132 个正式样本全部记录"]
                          if zh else
                          ["Rerun GPT-Image-2.5 low/medium/high", "Step 7", "two GPT-2.5 deployments / yes", "all 132 formal samples are recorded"])
    if tier_archive:
        route_rows.append(["重跑 GPT-Image-2.5 xhigh/max/auto 补测", "步骤 8", "GPT-2.5 两个部署 / 会计费", "132 个正式样本全部记录"]
                          if zh else
                          ["Rerun GPT-Image-2.5 xhigh/max/auto", "Step 8", "two GPT-2.5 deployments / yes", "all 132 formal samples are recorded"])
    if head_archive:
        route_rows.append(["重跑 MAI 对 2.5 同会话对比", "步骤 9", "MAI + GPT-2.5 flare / 会计费", "66 个正式样本全部记录"]
                          if zh else
                          ["Rerun the same-session MAI vs 2.5 comparison", "Step 9", "MAI + GPT-2.5 flare / yes", "all 66 formal samples are recorded"])
    if text_archives:
        route_rows.append(["重跑中英文文字渲染并判读", "步骤 10", "四个图像部署 + 一个视觉判读部署 / 会计费", "每个分片全部记录，`--check` 返回 PASS"]
                          if zh else
                          ["Rerun text rendering and score it", "Step 10", "four image deployments + one vision judge / yes", "every shard recorded; `--check` returns PASS"])
    if billing_archive:
        route_rows.append(["从自己的账单重算成本", "步骤 11", "az 登录 / 不计费", "`--check` 返回 PASS"]
                          if zh else
                          ["Recompute cost from your own invoice", "Step 11", "az login / no", "`--check` returns PASS"])
    route_table = table(
        [("目标" if language == "zh" else "Goal"),
         ("入口" if language == "zh" else "Entry"),
         ("凭据 / 计费" if language == "zh" else "Credentials / billing"),
         ("完成标志" if language == "zh" else "Done when")],
        route_rows)
    grounding = ""
    if grounding_archive:
        grounding = "\n\n".join([
            ("### 5. 重跑联网信息补充测试" if language == "zh" else
             "### 5. Rerun the web-grounding comparison"),
            ("联网信息补充测试只需 MAI 部署。第一条只读核验已有归档；第二条只检查参数；第三条才真实重跑完整三题，结果写入新目录，不覆盖已发布数据。"
             if language == "zh" else
             "The web-grounding test needs only the MAI deployment. The first command verifies the existing archive without writing; the second checks parameters without network calls; only the third reruns all three subjects into a new directory, leaving published data unchanged."),
            grounding_reproduction_commands(grounding_archive)])
    multi_image = ""
    if edit_archive:
        multi_image = "\n\n".join([
            ("### 6. 重跑换帽图像编辑" if language == "zh" else
             "### 6. Rerun the headwear-swap image edit"),
            ("第 12 题需要 MAI 与 GPT 两个部署。第一条只读核验已发布的两轮 8 张输出；第二条是无凭据、无网络、无写入的 dry-run；"
             "第三、四条分别真实执行两轮并写入新目录；第五条只核对配置顺序、`size=auto`、输入与输出 hash。"
             "这一步不自动生成主观核对清单，图像质量结论仍需按已发布 review 的方法人工检查。"
             if language == "zh" else
             "Scenario 12 needs both deployments. The first command verifies the eight published outputs across "
             "two rounds. The second is a credential-free, network-free, write-free dry run. The third and fourth "
             "perform the two live rounds into a new directory; the fifth checks order, `size=auto`, input and output "
             "hashes. This does not create a subjective review automatically; quality conclusions still require "
             "inspection under the published review method."),
            edit_reproduction_commands(edit_archive)])
    supplement = ""
    if supplement_archive:
        supplement = "\n\n".join([
            ("### 7. 重跑 GPT-Image-2.5 low/medium/high 补测" if zh else
             "### 7. Rerun GPT-Image-2.5 low/medium/high"),
            ("这一步需要 `gpt-image-2.5-flare` 和 `gpt-image-2.5-sunburst` 两个部署，部署名就是模型名；`--gpt-model` 可重复传入，`--gpt-quality all` 展开为 low、medium、high 三组（这是 gpt-image-2 也接受的三档，含义固定不变）。执行脚本对同一部署每 60 秒最多起请 2 次，与 2 RPM 的部署配额对齐；若你的配额更高，可以改 `RATE_PACING`。第一条只读核验已发布归档；后两条真实调用模型并写入新目录。"
             if zh else
             "This step needs the `gpt-image-2.5-flare` and `gpt-image-2.5-sunburst` deployments, named after their models; `--gpt-model` may be repeated, and `--gpt-quality all` expands to low, medium and high (the three tiers gpt-image-2 also accepts; that token's meaning is fixed). The runner starts at most 2 requests per 60 seconds per deployment to match the 2 RPM deployment quota; raise `RATE_PACING` if your quota is higher. The first command verifies the published archive without model calls; the next two call the models and write a new directory."),
            f"""```powershell
python scripts/summarize_paired_run.py {supplement_archive}
$run = 'runs/gpt25-paired-new-run'
New-Item -ItemType Directory -Path "$run/source" -ErrorAction Stop
Copy-Item -LiteralPath scripts/benchmark_5way_v2.py -Destination "$run/source/benchmark_5way_v2.py"
Copy-Item -LiteralPath prompts.csv -Destination "$run/source/prompts.csv"
python -u scripts/benchmark_5way_v2.py --gpt-model gpt-image-2.5-flare --gpt-model gpt-image-2.5-sunburst --gpt-quality all --output $run --warmup-only
python -u scripts/benchmark_5way_v2.py --gpt-model gpt-image-2.5-flare --gpt-model gpt-image-2.5-sunburst --gpt-quality all --output $run --resume
```"""])
    tiers = ""
    if tier_archive:
        tiers = "\n\n".join([
            ("### 8. 重跑 GPT-Image-2.5 xhigh/max/auto 补测" if zh else
             "### 8. Rerun GPT-Image-2.5 xhigh/max/auto"),
            ("这三档只有 gpt-image-2.5-* 接受，gpt-image-2 会拒绝。`--gpt-quality` 可重复传入单个档位；`all25` 一次展开全部六档。sunburst 的 max 档单次请求实测 229 秒，执行脚本的请求超时为 900 秒。`auto` 由服务按请求自选档位，它实际使用的档位记在每次尝试的 `service_quality` 字段里。"
             if zh else
             "Only gpt-image-2.5-* accepts these three tiers; gpt-image-2 rejects them. `--gpt-quality` may be repeated for single tiers; `all25` expands to all six at once. A single sunburst max request measured 229 s, so the runner's request timeout is 900 s. `auto` lets the service choose a tier per request; the tier it used is recorded per attempt as `service_quality`."),
            f"""```powershell
python scripts/summarize_paired_run.py {tier_archive}
$run = 'runs/gpt25-tiers-new-run'
New-Item -ItemType Directory -Path "$run/source" -ErrorAction Stop
Copy-Item -LiteralPath scripts/benchmark_5way_v2.py -Destination "$run/source/benchmark_5way_v2.py"
Copy-Item -LiteralPath prompts.csv -Destination "$run/source/prompts.csv"
python -u scripts/benchmark_5way_v2.py --gpt-model gpt-image-2.5-flare --gpt-model gpt-image-2.5-sunburst --gpt-quality xhigh --gpt-quality max --gpt-quality auto --output $run --warmup-only
python -u scripts/benchmark_5way_v2.py --gpt-model gpt-image-2.5-flare --gpt-model gpt-image-2.5-sunburst --gpt-quality xhigh --gpt-quality max --gpt-quality auto --output $run --resume
```"""])
    head = ""
    if head_archive:
        head = "\n\n".join([
            ("### 9. 重跑 MAI 对 GPT-Image-2.5 的同会话对比" if zh else
             "### 9. Rerun the same-session MAI vs GPT-Image-2.5 comparison"),
            ("三个配置在一个 run 里交错调用。`--gpt-model` 支持 `部署名:档位,档位` 写法，把档位固定到单个部署——因为 gpt-image-2 不接受 2.5 的高档，不同部署需要不同档位集。MAI 不接受质量参数。"
             if zh else
             "Three configurations interleaved in one run. `--gpt-model` accepts `deployment:tier,tier` to pin tiers to one deployment, because gpt-image-2 rejects the 2.5-only tiers and different deployments need different tier sets. MAI takes no quality parameter."),
            f"""```powershell
python scripts/summarize_paired_run.py {head_archive}
$run = 'runs/mai-vs-gpt25-new-run'
New-Item -ItemType Directory -Path "$run/source" -ErrorAction Stop
Copy-Item -LiteralPath scripts/benchmark_5way_v2.py -Destination "$run/source/benchmark_5way_v2.py"
Copy-Item -LiteralPath prompts.csv -Destination "$run/source/prompts.csv"
python -u scripts/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --gpt-model gpt-image-2.5-flare:medium,high --output $run --warmup-only
python -u scripts/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --gpt-model gpt-image-2.5-flare:medium,high --output $run --resume
```"""])
    text = ""
    if text_archives:
        easy = text_archives[0]
        check_lines = "\n".join(f"python scripts/score_text_rendering.py --check {s['archive']}/text-scoring.json"
                                for s in text_archives)
        check_lines += "".join(f"\npython scripts/calibrate_text_judge.py --check {s['archive']}/judge-calibration/calibration.json"
                               for s in text_archives if s.get("calibration"))
        text = "\n\n".join([
            ("### 10. 重跑中英文文字渲染并判读" if zh else
             "### 10. Rerun text rendering and score it"),
            ("文字渲染用自己的提示词文件（`--prompts-csv`），前五列分别是提示词、配对 ID、语言、目标字串（多行用 `|` 分隔）和字符数；执行脚本只读第一列。每个部署各自有配额，所以按部署分片并行跑，判读时用多个 `--run` 合并；判读器会拒绝合并提示词文件不一致的分片。判读需要一个支持图像输入的 chat 部署，通过 `JUDGE_ENDPOINT`、`JUDGE_DEPLOYMENT` 和 `AZURE_OPENAI_API_KEY` 提供；先用 `calibrate_text_judge.py` 确认它能 100% 读回用真字体渲染的目标文字，否则它的误差会被误认为模型的误差。`--check` 用归档里保存的转录重算全部分数，不调用任何模型。"
             if zh else
             "Text rendering uses its own prompt file (`--prompts-csv`): the first five columns are prompt, pair id, language, target string (multi-line targets use `|`) and character count; the runner reads only the first column. Each deployment has its own quota, so shards run in parallel per deployment and are merged at scoring with repeated `--run`; the scorer refuses shards whose frozen prompt file differs. Scoring needs a vision-capable chat deployment via `JUDGE_ENDPOINT`, `JUDGE_DEPLOYMENT` and `AZURE_OPENAI_API_KEY`; run `calibrate_text_judge.py` first to confirm it reads real-font renders of the targets at 100%, or its errors will be attributed to the image models. `--check` recomputes every score from the transcriptions saved in an archive and calls no model."),
            f"""```powershell
{check_lines}
$env:JUDGE_ENDPOINT = 'https://<openai-resource>.openai.azure.com'
$env:JUDGE_DEPLOYMENT = '<vision-capable-chat-deployment>'
python scripts/calibrate_text_judge.py --prompts {easy['archive']}/{easy['prompts_name']} --out runs/judge-calibration
$run = 'runs/text-new-run-mai'
New-Item -ItemType Directory -Path "$run/source" -ErrorAction Stop
Copy-Item -LiteralPath scripts/benchmark_5way_v2.py -Destination "$run/source/benchmark_5way_v2.py"
Copy-Item -LiteralPath {easy['archive']}/{easy['prompts_name']} -Destination "$run/source/{easy['prompts_name']}"
python -u scripts/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --prompts-csv "$run/source/{easy['prompts_name']}" --output $run
python scripts/score_text_rendering.py --run $run --prompts {easy['archive']}/{easy['prompts_name']} --out runs/text-new-run-scored
```"""])
    billing = ""
    if billing_archive:
        billing = "\n\n".join([
            ("### 11. 从自己的账单重算每张图成本" if zh else
             "### 11. Recompute cost per image from your own invoice"),
            ("成本小节的全部单价都来自这个归档里的 Cost Management 响应。第一条从已归档响应重算 `effective-prices.json` 并核对，不联网；第二条对你自己的账户发同样的查询（需要 `az login`，查询本身不计费），写入新归档；之后重新渲染报告，成本小节就会读你的账单而不是我们的。"
             if zh else
             "Every price in the cost section comes from the Cost Management response in this archive. The first command recomputes `effective-prices.json` from the archived response and compares, offline; the second issues the same query against your own account (needs `az login`; the query itself is free) and writes a new archive, after which re-rendering the report reads your invoice instead of ours."),
            f"""```powershell
python scripts/effective_prices.py {billing_archive} --check
python scripts/effective_prices.py data/billing-<date> --query --subscription <id> --resource-group <rg> --account <cognitive-services-account>
```"""])
    return f"""<a id="reproduction-how-to"></a>
## {'复现方法（How-to）与测试' if language == 'zh' else 'Reproduction How-to and Tests'}

{route_table}

### {'1. 克隆并安装依赖' if language == 'zh' else '1. Clone and install dependencies'}

{intro}

```powershell
git clone https://github.com/david-xinyuwei/david-share.git
cd david-share/Multimodal-Models/MAI-Image-2-vs-GPT-Image-Benchmark
git lfs install
git lfs pull --include="Multimodal-Models/MAI-Image-2-vs-GPT-Image-Benchmark/**"
python -m pip install requests==2.34.2
```

### {'2. 配置自己的部署' if language == 'zh' else '2. Configure your deployments'}

{credentials}

```powershell
$env:MAI_ENDPOINT = 'https://<mai-resource>.services.ai.azure.com'
$env:GPT_ENDPOINT = 'https://<openai-resource>.openai.azure.com'
$env:GPT_DEPLOYMENT = '<gpt-image-2-deployment>'
$env:GPT_API_VERSION = '2025-04-01-preview'
$env:MAI_MODEL_VERSION = '2026-07-31'
$env:GPT_MODEL_VERSION = '2026-04-21'
$env:MAI_DEPLOYMENT_SKU = 'GlobalStandard'
$env:GPT_DEPLOYMENT_SKU = 'GlobalStandard'
$env:MAI_DEPLOYMENT_REGION = 'swedencentral'
$env:GPT_DEPLOYMENT_REGION = 'eastus2'
$env:MAI_RATE_LIMIT_RPM = '2.0'
$env:GPT_RATE_LIMIT_RPM = '2.0'
$env:BENCHMARK_CLIENT_LOCATION = 'Describe your actual client location'
python scripts/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --gpt-model gpt-image-2 --gpt-quality all --dry-run
```

### {'3. 重跑 11 个文生图场景' if language == 'zh' else '3. Rerun the 11 text-to-image scenarios'}

{continuation}

```powershell
$run = 'runs/paired-all-quality-new-run'
New-Item -ItemType Directory -Path "$run/source" -ErrorAction Stop
Copy-Item -LiteralPath scripts/benchmark_5way_v2.py -Destination "$run/source/benchmark_5way_v2.py"
Copy-Item -LiteralPath prompts.csv -Destination "$run/source/prompts.csv"
python -u scripts/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --gpt-model gpt-image-2 --gpt-quality all --output $run --warmup-only
python -u scripts/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --gpt-model gpt-image-2 --gpt-quality all --output $run --resume
python scripts/summarize_paired_run.py $run
```

### {'4. 只读核验已发布证据' if language == 'zh' else '4. Verify published evidence without model calls'}

{tests}

```powershell
python scripts/summarize_paired_run.py {archive_path}
python scripts/render_paired_report.py {archive_path} --check
python -m unittest discover -s tests -v
```

{"\n\n".join(part for part in (grounding, multi_image, supplement, tiers, head, text, billing) if part)}

{'文生图执行脚本' if zh else 'Text-to-image runner'}: [benchmark_5way_v2.py](scripts/benchmark_5way_v2.py); {'改图执行脚本' if zh else 'Edit runner'}: [run_edit_hat_swap.py](scripts/run_edit_hat_swap.py); {'离线汇总' if zh else 'offline summary'}: [summarize_paired_run.py](scripts/summarize_paired_run.py); {'文字判读' if zh else 'text scoring'}: [score_text_rendering.py](scripts/score_text_rendering.py); {'判读器校准' if zh else 'judge calibration'}: [calibrate_text_judge.py](scripts/calibrate_text_judge.py); {'账单折算' if zh else 'invoice derivation'}: [effective_prices.py](scripts/effective_prices.py); {'报告生成' if zh else 'report rendering'}: [render_paired_report.py](scripts/render_paired_report.py); {'回归测试' if zh else 'regressions'}: [tests](tests).
"""


def count_tests(root):
    """Number of test functions under tests/, so the badge cannot go stale."""
    return sum(len(re.findall(r"(?m)^\s+def test_", path.read_text("utf-8")))
               for path in (root / "tests").glob("test_*.py"))


def render_masthead(summary, author_line, language, supplement=None, data_through=None, test_count=None):
    """First screen: factual badges, one scope paragraph, author, language, navigation.

    Every badge states something this run actually recorded or that the vendor
    documents, so a reader can check each one. No badge asserts a quality ranking,
    because the visual review is unblinded and produces no score.
    """
    chinese = language == "zh"
    configurations = summary.get("config", {}).get("group_configurations", ())
    versions = {item["model_version"] for item in configurations
                if item.get("provider") == "mai" and item.get("model_version")}
    mai_version = sorted(versions)[0] if versions else "2026-07-31"
    returned = summary.get("successful_samples", 0)
    planned = summary.get("formal_samples", 0)
    samples_badge = f"{returned}%2F{planned}%20returned"
    models_badge = "MAI--Image--2.6%20vs%20GPT--Image--2"
    if supplement:
        extra = supplement["summary"]
        samples_badge = f"{returned}%2F{planned}%20%2B%20{extra['successful_samples']}%2F{extra['formal_samples']}%20returned"
        models_badge = "MAI--Image--2.6%20vs%20GPT--Image--2%20%2F%202.5"
    badges = [
        ("Models", models_badge, "0067b8",
         "https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai-image"),
        ("Samples", samples_badge, "2e7d32",
         "data/paired-all-quality-20260907/5way_v2_results.json"),
        ("Resolution", "1024%C3%971024", "455a64", None),
        ("MAI version", mai_version.replace("-", "--"), "6a1b9a", None),
        ("Status", "Preview%20%C2%B7%20no%20SLA", "b26500",
         "https://azure.microsoft.com/support/legal/preview-supplemental-terms/"),
        ("Tests", f"{test_count or 0}%20offline", "00695c", "tests"),
    ]
    if data_through:
        # MAI-Image-2.6 is Preview and GPT-Image-2.5 has no published price; both can change,
        # so the reader needs the date these figures stop being current.
        badges.insert(4, ("Data through", data_through.replace("-", "--"), "37474f", None))
    rendered = []
    for label, value, colour, link in badges:
        image = f"https://img.shields.io/badge/{label.replace(' ', '%20')}-{value}-{colour}"
        rendered.append(f"[![{label}]({image})]({link})" if link else f"![{label}]({image})")
    scope = (
        f"同一台客户端交替调用 MAI-Image-2.6 与 GPT-Image-2 的 low、medium、high 三档，"
        f"11 个文生图场景各两轮，共 {planned} 个正式样本，"
        f"保留全部原图、逐次请求记录与失败样本。另有联网信息补充（`web_grounding`）与"
        "单图编辑两项能力实测。所有画面判断为非盲评的差异描述，不产出质量评分或偏好胜负。"
        if chinese else
        f"One client interleaved calls to MAI-Image-2.6 and GPT-Image-2 at low, medium and high across "
        f"11 text-to-image scenarios in two rounds, {planned} formal samples in total, "
        "keeping every original PNG, per-attempt record and failed sample. Two capability tests are "
        "included: web grounding (`web_grounding`) and single-image editing. Image judgements are "
        "unblinded difference descriptions and produce no quality score or preference verdict."
    )
    if supplement:
        extra = supplement["summary"]
        scope += (f" {supplement['date']} 另用同一客户端、同一份提示词补测了 GPT-Image-2.5 Flare 与 Sunburst 各三档，共 {extra['formal_samples']} 个正式样本，并入同一套图片、耗时与 token 表。"
                  if chinese else
                  f" On {supplement['date']} the same client and prompt file also measured GPT-Image-2.5 Flare and Sunburst at all three tiers, {extra['formal_samples']} formal samples, merged into the same image, latency and token tables.")
    nav = " · ".join([
        f"[{'逐题图片' if chinese else 'Side-by-side images'}](#{'并排图片对比' if chinese else 'side-by-side-image-comparison'})",
        f"[{'耗时与请求' if chinese else 'Latency and requests'}](#{'耗时与请求成功情况' if chinese else 'performance-and-reliability'})",
        f"[{'联网补测' if chinese else 'Web grounding'}](#{'联网信息补充测试' if chinese else 'web-grounding-test'})",
        f"[{'图像编辑' if chinese else 'Image edit'}](#{'test-12-换帽子图像编辑' if chinese else 'test-12-headwear-swap-image-edit'})",
        f"[{'复现' if chinese else 'Reproduction'}](#reproduction-how-to)",
        f"[{'原始证据' if chinese else 'Raw evidence'}](data/paired-all-quality-20260907)",
    ])
    language_switch = (f"[English](README.md) | [{'中文'}](README-CN.md)" if chinese
                       else "[English](README.md) | [中文](README-CN.md)")
    return "\n\n".join([" ".join(rendered), scope, f"> {author_line.lstrip('> ')}",
                        language_switch, nav, "---"])


def quality_counts_table(summary, quality, language):
    """Countable outcomes first, so a reader sees scale before reading prose.

    The counts come from the recorded observation text for each configuration.
    They describe how often a defect wording appears, which is a tally of this
    unblinded review, not a quality score or a defect rate for the model.
    """
    chinese = language == "zh"
    markers = (
        (("裁切" if chinese else "Cropped or clipped subject"), ("裁切", "截断"), ("crop", "clipp", "truncat")),
        (("未请求的文字" if chinese else "Unrequested text added"), ("未请求", "额外", "增加", "添加", "标语"),
         ("unrequested", "extra text", "added", "slogan", "brand")),
        (("局部难辨或模糊" if chinese else "Illegible or blurred detail"), ("难辨", "模糊", "不易辨"),
         ("illegible", "blur", "hard to read", "difficult")),
    )
    rows = []
    for label, zh_terms, en_terms in markers:
        counts = []
        for group in GROUPS:
            terms = zh_terms if chinese else en_terms
            hits = sum(1 for item in quality["per_prompt"]
                       if any(term in item["observations"][group][language].lower()
                              for term in (t.lower() for t in terms)))
            counts.append(f"{hits}/{len(quality['per_prompt'])}")
        rows.append([label, *counts])
    returned = []
    for group, metrics in zip(GROUPS, summary["groups"]):
        returned.append(f"{metrics['successful_samples']}/{metrics['planned_samples']}")
    rows.insert(0, [("返回图片 / 计划样本" if chinese else "Images returned / planned"), *returned])
    return table([("观测项" if chinese else "Observed outcome"), *LABELS], rows)


def render_highlights(summary, language, has_grounding, has_edit, supplement=None):
    """Open with what this run establishes about MAI-Image-2.6, at evidence strength.

    Image quality is reported as an outcome a reader can inspect, not as a win.
    The visual review is unblinded and states no preference ranking, so a
    "matches GPT" claim would exceed the evidence. The two capability items are
    stated plainly because each has a direct observation behind it.
    """
    chinese = language == "zh"
    scenarios = len(summary.get("per_prompt", ())) or 11
    returned = summary.get("successful_samples")
    planned = summary.get("formal_samples")
    latency = {group["group"]: group.get("successful_request_latency", {}).get("p50_seconds")
               for group in summary.get("groups", ())}
    mai_p50 = latency.get("mai-image-2.6")
    low_p50 = latency.get("gpt-image-2-low")
    medium_p50 = latency.get("gpt-image-2-medium")
    high_p50 = latency.get("gpt-image-2-high")
    counted = (f"本轮 {returned}/{planned} 个正式样本返回图片，" if chinese else
               f"This run returned images for {returned}/{planned} formal samples, ") \
        if returned is not None and planned is not None else ""
    items = [
        ((f"**{scenarios} 个场景与 GPT-Image-2 三档并排可比。** "
          f"{counted}两轮结果和原图全部保留在下方，"
          "可以逐题自行比较画面。逐图观察为非盲评的差异描述，没有评出优劣胜负，"
          "因此本文不声称画质优于或等同 GPT-Image-2。")
         if chinese else
         (f"**{scenarios} scenarios sit side by side with all three GPT-Image-2 tiers.** "
          f"{counted}Both rounds plus the "
          "original PNGs are kept below so you can compare each scenario yourself. The per-image "
          "observations describe differences without ranking them, so this report does not claim MAI "
          "image quality beats or matches GPT-Image-2.")),
    ]
    token_item = token_highlight(summary, language, supplement)
    if token_item:
        items.append(token_item)
    if has_edit:
        items.append(
            ("**在对称的 `size=auto` 协议下，四个配置都完成了局部编辑。** 第 12 题只要求把头饰换成博士帽；"
             "MAI 与 GPT 三档两轮都换上了帽子，并让人脸、龙袍、侍卫、标题印章和原图宽高比保持在位且可辨，"
             "清单均为 5/5。标题字形与输出分辨率仍有差异，逐图记录和第一次方图协议的更正见第 12 题。"
             if chinese else
             "**Under the symmetric `size=auto` protocol, all four configurations complete the local edit.** "
             "Scenario 12 asks only for a graduation cap; MAI and all three GPT tiers add it in both rounds "
             "while keeping the face, robe, bystanders, title and aspect ratio present, in place and recognisable, "
             "for 5/5 on the checklist. Title glyph fidelity and output resolution still differ; Scenario 12 "
             "contains the per-image record and the correction to the first square-output protocol."))
    if has_grounding:
        items.append(
            ("**`web_grounding=true` 可以在生成时补充联网信息。** 开启后模型会从 Bing Search 检索当前信息"
             "作为额外上下文，实测让两个题目的产品文字事实从错误变为与官方发布一致；"
             "代价是首试成功率下降、耗时明显上升。这与视觉领域的 dense grounding（密集视觉定位）不是同一件事。"
             if chinese else
             "**`web_grounding=true` adds current web information at generation time.** The model retrieves "
             "current information from Bing Search as extra context, which moved the product text facts in "
             "two subjects from wrong to matching the official announcement. The cost is a lower "
             "first-attempt success rate and clearly higher latency. This is not the same thing as dense "
             "visual grounding."))
    heading = "## MAI-Image-2.6 在本轮中体现的能力" if chinese else "## What This Run Shows About MAI-Image-2.6"
    scope = (f"以下{'四' if len(items) == 4 else '三' if len(items) == 3 else str(len(items))}条都只依据本仓库的实测记录，`MAI-Image-2.6` 处于 Preview，无 SLA。"
             if chinese else
             f"All {'four' if len(items) == 4 else 'three' if len(items) == 3 else len(items)} items rest on the measurements in this repository. `MAI-Image-2.6` is in preview "
             "with no SLA.")
    parts = [heading, scope] + [f"{index}. {text}" for index, text in enumerate(items, 1)]
    # The vendor charts only appear when this run actually measured the same models,
    # so a fixture without latency records cannot render an unsupported comparison.
    if None not in (mai_p50, low_p50, medium_p50, high_p50):
        parts.append(render_vendor_charts(language, mai_p50, medium_p50, low_p50, high_p50))
    return "\n\n".join(parts)


def token_highlight(summary, language, supplement=None):
    """One checkable sentence on output tokens per image, built only from returned usage.

    Each group's returned_output_tokens must be a single constant value across its
    successful samples; otherwise the sentence is omitted rather than averaged.
    """
    chinese = language == "zh"
    tokens = {}
    for group in summary.get("groups", ()):
        values = group.get("returned_output_tokens") or []
        if len(values) != 1:
            return None
        tokens[group["group"]] = values[0]
    needed = ("mai-image-2.6", "gpt-image-2-low", "gpt-image-2-medium", "gpt-image-2-high")
    if any(key not in tokens for key in needed):
        return None
    mai, low, medium, high = (tokens[key] for key in needed)
    if not (low < mai < medium):
        return None
    text = ((f"**每张 1024×1024 图的 output token：MAI-Image-2.6 固定 {mai:,}，介于 GPT-Image-2 low（{low:,}）与 medium（{medium:,}）之间，是 high（{high:,}）的 {mai / high:.0%}。** "
             "数值全部取自接口返回的 usage，每组所有成功样本完全一致。token 不是金额，两家的费率不同，本仓库不计价；GPT 的档位也不对应 MAI 的任何质量设置。")
            if chinese else
            (f"**Output tokens per 1024×1024 image: MAI-Image-2.6 is a constant {mai:,}, between GPT-Image-2 low ({low:,}) and medium ({medium:,}), and {mai / high:.0%} of high ({high:,}).** "
             "Every figure comes from returned usage and is identical across each group's successful samples. Tokens are not money: the two vendors bill different rates, this repository does not price them, and GPT tiers do not map to any MAI quality setting."))
    if supplement:
        extra = {}
        for group in supplement["summary"]["groups"]:
            values = group.get("returned_output_tokens") or []
            if len(values) != 1:
                return text
            extra[group["group"]] = values[0]
        by_model = {}
        for group_id, value in extra.items():
            model, tier = group_id.rsplit("-", 1)
            by_model.setdefault(model, {})[tier] = value
        parts = []
        for model, tiers in by_model.items():
            label = label_for({"provider": "gpt", "model": model, "quality": ""}).strip()
            parts.append(f"{label} {tiers.get('low', '?'):,} / {tiers.get('medium', '?'):,} / {tiers.get('high', '?'):,}")
        text += ((" GPT-Image-2.5 的 low / medium / high 为：" + "；".join(parts) + f"，来自 {supplement['date']} 的补测。")
                 if chinese else
                 (" GPT-Image-2.5 low / medium / high: " + "; ".join(parts) + f", from the {supplement['date']} supplement."))
    return text


def render_vendor_charts(language, mai_p50, medium_p50, low_p50, high_p50):
    """Show the vendor's published charts, then this run's numbers for the same models.

    The vendor measured a 100 RPM internal load test; this run used 2 RPM with
    concurrency 1 and different regions, so the two are reported separately and
    the text states that they do not validate each other. Only the direction is
    compared, because the multiples differ.
    """
    chinese = language == "zh"
    assets = "assets/official-microsoft-ai-20260908"
    ratio_vendor = 33.6 / 25.6
    ratio_ours = medium_p50 / mai_p50 if mai_p50 else None
    heading = ("### 厂商公布的性能图表与本轮实测的关系" if chinese else
               "### Vendor Performance Charts And How This Run Relates To Them")
    intro = (
        "以下图表取自微软官网 MAI-Image-2.6 页面的 Performance 区（抓取于 2026-09-08）。"
        "它们是厂商声明，测量条件与本仓库不同，与我们的实测互不验证。"
        if chinese else
        "The charts below come from the Performance area of the vendor's MAI-Image-2.6 page "
        "(captured 2026-09-08). They are vendor claims measured under different conditions from this "
        "repository and do not validate our measurements."
    )
    charts = [
        (("文生图排行榜前十" if chinese else "Text-to-Image Arena top ten"),
         "arena-text-to-image-top10.png",
         ("厂商标注 MAI-Image-2.6 位列第 2（1,336），第 1 名是 GPT Image 2 Medium（1,381）。"
          "这是 Arena 全提示词类别的总分排名，不等于逐场景画质判定，本仓库也没有复现该分数。"
          if chinese else
          "The vendor annotates MAI-Image-2.6 as ranked #2 (1,336), behind GPT Image 2 Medium at #1 "
          "(1,381). This is an aggregate Arena score across prompt categories, not a per-scenario "
          "quality verdict, and this repository did not reproduce the score.")),
        (("文生图速度对比" if chinese else "Text-to-image speed comparison"),
         "speed-vs-gpt-image-2-medium.png",
         ("厂商脚注写明：内部压测，100 RPM，1024x1024，取中位数，误差带到 P90。"
          "对照基线只有 GPT-Image-2-Medium，没有 low 与 high 档。"
          if chinese else
          "The vendor footnote states: internal load test, 100 RPM at 1024x1024, median response time "
          "with a band to P90. The only baseline is GPT-Image-2-Medium; the low and high tiers are absent.")),
        (("图像编辑的质量与价格前沿" if chinese else "Quality versus price frontier for image editing"),
         "quality-vs-price-frontier.png",
         ("横轴为第三方公布的每千张 API 参考价，纵轴为图像编辑 Arena Elo。"
          "厂商标注 MAI-Image-2.6（Elo 1324、$38.90）与 MAI-Image-2.6-Flash（Elo 1311、$19.50）位于 Pareto 前沿；"
          "GPT Image 2 high 为 Elo 1318、$211。这是图像编辑任务，与上面的文生图排行榜不是同一件事。"
          "价格为第三方公开参考价，不是微软报价，也不代表任何客户的实际成交价。"
          if chinese else
          "The horizontal axis is a third-party published API reference price per 1,000 images and the "
          "vertical axis is image-edit Arena Elo. The vendor marks MAI-Image-2.6 (Elo 1324, $38.90) and "
          "MAI-Image-2.6-Flash (Elo 1311, $19.50) as sitting on the Pareto frontier, with GPT Image 2 high "
          "at Elo 1318 and $211. This measures image editing, a different task from the text-to-image "
          "leaderboard above. Prices are third-party reference figures, not a Microsoft quote and not any "
          "customer's contracted price.")),
    ]
    # Chart 1 stays open because it is the single most load-bearing vendor claim.
    # The remaining vendor material is collapsed so the reader reaches this
    # repository's own measurements quickly. Only external reference material is
    # collapsed; this project's inputs and results are never hidden behind a click.
    lead_label, lead_file, lead_note = charts[0]
    blocks = [f"![{lead_label}]({assets}/{lead_file})", lead_note]
    rest = []
    for label, filename, note in charts[1:]:
        rest.append(f"**{label}**\n\n![{label}]({assets}/{filename})\n\n{note}")
    ours = (
        f"本轮实测的同一统计量（成功请求耗时 P50，客户端记录）："
        f"MAI-Image-2.6 {mai_p50:.2f} 秒；GPT-Image-2 low {low_p50:.2f} 秒、medium {medium_p50:.2f} 秒、"
        f"high {high_p50:.2f} 秒。厂商图上 MAI 比 GPT-Image-2-Medium 快 {ratio_vendor:.2f} 倍，"
        f"本轮为 {ratio_ours:.2f} 倍：**方向一致，倍数不同**。"
        if chinese else
        f"The same statistic measured in this run (client-side P50 of successful requests): "
        f"MAI-Image-2.6 {mai_p50:.2f} s; GPT-Image-2 low {low_p50:.2f} s, medium {medium_p50:.2f} s, "
        f"high {high_p50:.2f} s. The vendor chart shows MAI {ratio_vendor:.2f}x faster than "
        f"GPT-Image-2-Medium; this run gives {ratio_ours:.2f}x: **the direction agrees, the multiple does not**."
    )
    boundary = (
        "两者不可互相验证：厂商在 100 RPM 压测下测量，本轮为每分钟 2 次请求、并发 1；"
        "本轮 MAI 部署在 Sweden Central、GPT 在 East US 2，客户端在同一台工作站，"
        "因此耗时差中包含区域与网络因素，无法从本轮数据里剥离。"
        "每组 22 个样本为描述性样本，不是容量或尾延迟结论。"
        "本仓库没有测过 `MAI-Image-2.6-Flash`，也没有复现 Arena 或 Artificial Analysis 的 Elo 分数。"
        f"厂商图上没有的两条：本轮 GPT-Image-2 low 的 P50 为 {low_p50:.2f} 秒，比 MAI 更快；"
        f"MAI 比 GPT-Image-2 high 快 {high_p50 / mai_p50:.2f} 倍。"
        if chinese else
        "Neither validates the other: the vendor measured a 100 RPM load test while this run used two "
        "requests per minute at concurrency 1. Here MAI ran in Sweden Central and GPT in East US 2 from "
        "the same workstation, so region and transport are part of any latency gap and cannot be separated "
        "from this run's data. Twenty-two samples per configuration is a descriptive sample, not a capacity "
        "or tail-latency result. This repository never called `MAI-Image-2.6-Flash` and did not reproduce "
        "the Arena or Artificial Analysis Elo scores. Two facts absent from the vendor charts: this run's "
        f"GPT-Image-2 low P50 is {low_p50:.2f} s, faster than MAI, and MAI is "
        f"{high_p50 / mai_p50:.2f}x faster than GPT-Image-2 high."
    )
    source = (f"[{'图表来源与逐项读数' if chinese else 'Chart provenance and per-item readings'}]"
              f"({assets}/provenance.json) | "
              f"[{'厂商页面' if chinese else 'Vendor page'}](https://microsoft.ai/models/mai-image-2-6/)")
    folded = "\n\n".join([
        "<details>",
        "<summary>" + ("另外两张厂商图表（速度、质量与价格前沿）与完整口径说明"
                       if chinese else
                       "Two further vendor charts (speed, quality versus price) and the full measurement notes")
        + "</summary>",
        *rest, boundary, source, "</details>",
    ])
    return "\n\n".join([heading, intro] + blocks + [ours, folded])


def render_overview(summary, quality, archive_path, language, has_grounding=False,
                    has_edit=False, supplement=None, tier=None, head=None, text_studies=(), billing=None):
    chinese = language == "zh"
    metadata = summary["config"]["group_configurations"]
    if [group["group"] for group in summary["groups"]] != list(GROUPS):
        raise ValueError("Metric columns must contain all four groups in order")
    coverage = tier_coverage(summary, supplement["summary"] if supplement else None,
                             tier["summary"] if tier else None)
    if coverage["complete"]:
        title = "本轮：两模型与全部质量档位" if chinese else "Current Run: Both Models and All Quality Tiers"
    else:
        title = "本轮：两模型与已测质量档位" if chinese else "Current Run: Both Models and the Measured Quality Tiers"
    outcome = (f"本轮 {summary['successful_samples']}/{summary['formal_samples']} 个正式样本返回图片，{summary['failed_samples']} 个未返回图片；另有 {summary['warmup_samples']} 次预热，不计入正式分母。"
               if chinese else f"This run returned images for {summary['successful_samples']}/{summary['formal_samples']} formal samples; {summary['failed_samples']} returned no image. The {summary['warmup_samples']} warmups are excluded from the formal denominator.")
    if supplement:
        extra = supplement["summary"]
        outcome += (f" GPT-Image-2.5 补测 {extra['successful_samples']}/{extra['formal_samples']} 个正式样本返回图片，{extra['failed_samples']} 个未返回；预热 {extra['warmup_samples']} 次，同样不计入分母。"
                    if chinese else f" The GPT-Image-2.5 supplement returned images for {extra['successful_samples']}/{extra['formal_samples']} formal samples; {extra['failed_samples']} returned no image, and its {extra['warmup_samples']} warmups are likewise excluded.")
    boundary = ("同一客户端交替调用，提示词、尺寸和轮数相同；部署区域不同，不能把端到端耗时差全部归因于模型。质量是非盲评的具体画面观察，不是官方 benchmark 分数、人类偏好胜率或生产可靠性证明。"
                if chinese else "Requests were interleaved on the same client with identical prompts, dimensions and repetitions. Deployment regions differ, so end-to-end latency differences cannot be attributed solely to the models. Quality observations are unblinded, not an official benchmark score, human-preference win rate or production reliability claim.")
    if supplement:
        boundary += (f" GPT-Image-2.5 Flare 与 Sunburst 六列来自 {supplement['date']} 的独立运行：同一客户端、同一份提示词与同一个执行脚本，部署在 {supplement['region']}（与 MAI 同区域）。它与前四列不是同一时段，跨列看耗时要连带日期和区域一起看；token 数由服务端计算，不受这两点影响。"
                     if chinese else f" The six GPT-Image-2.5 Flare and Sunburst columns come from a separate run on {supplement['date']} with the same client, prompt file and runner, deployed in {supplement['region']} (the MAI region). They are not the same session as the first four columns, so read latency across them together with date and region; token counts are computed server-side and are unaffected.")
    date_header = "测量日期" if chinese else "Measured on"
    contract_rows = [
        [label, item.get("model_version") or "not recorded", item["quality"] or ("未传入" if chinese else "omitted"),
         "1024x1024", item.get("deployment_region") or "not recorded", str(group["planned_samples"]),
         summary["formal_started_at_utc"][:10]]
        for label, item, group in zip(LABELS, metadata, summary["groups"])]
    if supplement:
        contract_rows.extend(
            [label, item["configuration"].get("model_version") or "not recorded", item["configuration"]["quality"],
             "1024x1024", item["configuration"].get("deployment_region") or "not recorded", str(item["planned_samples"]),
             supplement["date"]]
            for label, item in zip(supplement["labels"], supplement["summary"]["groups"]))
    contract = table(["配置" if chinese else "Configuration", "模型版本" if chinese else "Model version",
                      "质量参数" if chinese else "Quality field", "尺寸" if chinese else "Dimensions",
                      "区域" if chinese else "Resource region", "正式样本" if chinese else "Formal samples", date_header],
                     contract_rows)
    procedure = ("输入是原报告同一份 11 题 CSV。每组先用 `blue circle` 预热一次；第一轮每题依次调用 MAI、GPT low、medium、high，第二轮反转。并发为 1，每次逻辑调用后间隔 5 秒，最多尝试 3 次，沿用原重试退避。两个 GlobalStandard 部署各配置每分钟 2 次请求；GPT 三档共享同一部署和限额。MAI 请求超时 180 秒，GPT 为 300 秒。"
                 if chinese else "The original eleven-prompt CSV is unchanged. Each configuration receives one `blue circle` warmup. Each prompt runs MAI, GPT low, medium, high in round 1, with reversed configuration order in round 2. Concurrency is 1, with 5 seconds after each logical call and at most 3 attempts under the original retry backoff. Each GlobalStandard deployment is configured for 2 requests/minute; GPT tiers share one deployment and limit. Request timeouts are 180 seconds for MAI and 300 for GPT.")
    if supplement:
        pacing = (supplement["summary"]["config"].get("rate_pacing") or {})
        procedure += ((f" GPT-Image-2.5 补测另起一轮：Flare 与 Sunburst 各自一个 GlobalStandard 部署，每题依次 Flare low、medium、high、Sunburst low、medium、high，第二轮反转；并发、间隔、重试与超时与上述相同。"
                       f"因为 2.5 的 low/medium 约 15–20 秒就能返回，三档连续调用会在 60 秒内对同一部署发起第三次请求而触发自己的配额，所以这轮在计时区之外加了客户端限速：同一部署任意 {pacing.get('window_seconds', 60)} 秒内最多起请 {pacing.get('max_requests', 2)} 次，等待时长逐样本记在 `pacing_wait_seconds`，不进入请求耗时。")
                      if chinese else
                      (f" The GPT-Image-2.5 supplement is its own run: Flare and Sunburst each have one GlobalStandard deployment, every prompt calls Flare low, medium, high, then Sunburst low, medium, high, with the order reversed in round 2; concurrency, spacing, retries and timeouts are unchanged. "
                       f"Because 2.5 low and medium return in roughly 15-20 seconds, three consecutive tiers would issue a third request to one deployment inside 60 seconds and trip this project's own quota, so this run adds client-side pacing outside the timed region: at most {pacing.get('max_requests', 2)} request starts per {pacing.get('window_seconds', 60)} seconds per deployment, with the wait recorded per sample as `pacing_wait_seconds` and excluded from request latency."))
    timing = ("请求耗时从 `requests.post` 调用前到完整 HTTP 响应返回，只统计有图片的成功尝试，不包含后续 JSON/base64 处理和文件写盘。任务耗时覆盖失败尝试、重试等待和响应处理，按全部计划样本统计。失败不以 0 秒进入速度平均值，也不从成功率分母删除。P95 为每组最多 22 个值的描述性线性插值，不是生产尾延迟保证。"
              if chinese else "Request latency measures `requests.post` through receipt of the complete HTTP response, before JSON/base64 processing and file writes, for successful image-producing attempts only. Logical duration includes failed attempts, retry waits and response processing across all planned samples. Failures are not averaged as zero-second responses or removed from the success-rate denominator. P95 is descriptive linear interpolation over at most 22 observations per group, not a production tail guarantee.")
    usage_scope = ("token 用量取自接口返回的 usage，不从模型或档位推算。没有返回值的样本不补零。输出 token 数和 PNG 文件大小都不能单独证明画质。"
                   if chinese else "Token counts come from returned usage, not assumptions about the model or tier. Missing values are not replaced with zero. Output-token counts and PNG byte sizes do not independently establish image quality.")
    row_names = ["场景" if chinese else "Scenario", *LABELS]
    observation_rows = [[str(item["prompt_index"]), *(item["observations"][group][language] for group in GROUPS)]
                        for item in quality["per_prompt"]]
    observations = table(row_names, observation_rows)
    observation_counts = quality_counts_table(summary, quality, language)
    observation_scope = ""
    if supplement:
        observation_scope = ("GPT-Image-2.5 的图片已在上方并排展示，但未纳入本节的画面观察计数；下表仍只覆盖前四个配置。"
                             if chinese else "GPT-Image-2.5 images are shown side by side above but are not part of this section's observation tally; the tables below still cover only the first four configurations.")
    api_gpt_header = "GPT-Image-2 / 2.5" if supplement else "GPT-Image-2"
    api = table(["接口项目" if chinese else "API item", "MAI-Image-2.6", api_gpt_header], [
        ["POST", "`/mai/v1/images/generations`", "`/openai/deployments/{deployment}/images/generations?api-version=2025-04-01-preview`"],
        ["Payload", "`model`, `prompt`, `width=1024`, `height=1024`", "`prompt`, `n=1`, `size=1024x1024`, `quality=low/medium/high`"],
        ["Auth", "`api-key`", "`api-key`"],
        ["Output", "`data[0].b64_json`, PNG", "`data[0].b64_json`, PNG"],
        ["Usage", "`usage.num_input_text_tokens`, `usage.num_output_tokens`", "`usage.input_tokens_details`, `usage.output_tokens_details`"],
    ])
    limits = ("本报告只对比 MAI-Image-2.6 与 GPT-Image-2 的 low、medium、high 三档。主要聚合统计来自 11 个 1024x1024 文生图场景；第 12 题是单独报告的 `size=auto` 图像编辑测试，不进入前 11 题的耗时与质量计数。本报告不覆盖 2K、多图参考、文字准确率专项、并发压测或其他认证方式。MAI 没有传质量参数，不能称为 GPT high 的等价档位。"
              if chinese else "This report compares only MAI-Image-2.6 with GPT-Image-2 low, medium and high. The aggregate metrics come from eleven 1024x1024 text-to-image scenarios; Scenario 12 is a separately reported `size=auto` image-edit test and is excluded from the first eleven scenarios' latency and quality counts. The report does not cover 2K, multiple reference images, exact-text accuracy, concurrency capacity or other authentication modes. MAI sends no quality parameter and is not labeled as equivalent to GPT high.")
    if supplement:
        supplement_tiers = sorted(
            {tier for model, tiers in coverage["measured"].items() if model.startswith("gpt-image-2.5")
             for tier in tiers}, key=TIER_ORDER.index)
        absent = sorted({tier for tiers in coverage["missing"].values() for tier in tiers},
                        key=TIER_ORDER.index)
        untested_cn = f"；2.5 另有 {'、'.join(absent)} 档，本轮没有测" if absent else ""
        untested_en = (f"; 2.5 also offers {', '.join(absent)}, which were not run" if absent else "")
        count_cn = {3: "三", 6: "六"}.get(len(supplement_tiers), str(len(supplement_tiers)))
        limits = (f"本报告对比 MAI-Image-2.6、GPT-Image-2 三档，以及 GPT-Image-2.5 Flare 与 Sunburst 各{count_cn}档（{'、'.join(supplement_tiers)}）{untested_cn}。主要聚合统计来自 11 个 1024x1024 文生图场景；第 12 题是单独报告的 `size=auto` 图像编辑测试，不进入前 11 题的耗时与质量计数，也没有 2.5 的编辑结果。本节的耗时表不是 MAI 与 2.5 的同会话对比，那一对比在后文单独一节。本报告不覆盖 2K、多图参考、并发压测或其他认证方式；文字准确率只覆盖后文两节列出的场景与字符。MAI 没有传质量参数，不能称为任何 GPT 档位的等价档。"
                  if chinese else
                  f"This report compares MAI-Image-2.6, the three GPT-Image-2 tiers, and GPT-Image-2.5 Flare and Sunburst at {', '.join(supplement_tiers)}{untested_en}. The aggregate metrics come from eleven 1024x1024 text-to-image scenarios; Scenario 12 is a separately reported `size=auto` image-edit test, excluded from the first eleven scenarios' latency and quality counts, and it has no GPT-Image-2.5 results. The latency tables in this section are not a same-session MAI vs 2.5 comparison; that comparison has its own section below. The report does not cover 2K, multiple reference images, concurrency capacity or other authentication modes; exact-text accuracy covers only the scenes and characters listed in the two text-rendering sections. MAI sends no quality parameter and is not labeled as equivalent to any GPT tier.")
    heading = lambda english, localized: localized if chinese else english
    # An earlier MAI-only pass over the same prompts is archived beside the paired run. It feeds no
    # table, so say what it is rather than leave an unexplained directory in data/.
    mai_only_note = ""
    mai_only = Path(__file__).resolve().parents[1] / MAI_ONLY_ARCHIVE
    if (mai_only / "provenance.json").is_file():
        mai_only_results = json.loads((mai_only / "5way_v2_results.json").read_text("utf-8"))
        mai_only_count = mai_only_results["config"]["formal_sample_count"]
        mai_only_note = ((f" 同一天早些时候还有一次只跑 MAI-Image-2.6 的 {mai_only_count} 样本运行，用同一份提示词与同一执行脚本："
                          f"[{MAI_ONLY_ARCHIVE}]({MAI_ONLY_ARCHIVE})。它先于配对运行，只作为归档证据保留，不进入本报告任何表格。")
                         if chinese else
                         (f" An earlier MAI-Image-2.6-only pass of {mai_only_count} samples over the same prompt file with the "
                          f"same runner, made the same day, is archived at [{MAI_ONLY_ARCHIVE}]({MAI_ONLY_ARCHIVE}); it "
                          "preceded the paired run, is kept as evidence only, and feeds no table in this report."))
    supplement_interval = ""
    gpt25_node = ""
    if supplement:
        extra = supplement["summary"]
        supplement_interval = (f"\n\n{'GPT-Image-2.5 补测正式起止时间 (UTC)' if chinese else 'GPT-Image-2.5 supplement formal interval (UTC)'}: `{extra['formal_started_at_utc']}` to `{extra['formal_ended_at_utc']}`. "
                               f"{'正式窗口含等待' if chinese else 'Formal window including waits'}: **{number(extra['formal_window_seconds_including_waits'])} s**.")
        gpt25_node = f"\n    runner --> gpt25[\"GPT-Image-2.5 Flare + Sunburst / {supplement['region']} / {', '.join(supplement_tiers)} ({supplement['date']})\"]\n    gpt25 --> evidence"
    return f"""## {title}

[{'English' if chinese else '中文'}]({'README.md' if chinese else 'README-CN.md'}) | [{'逐题图片' if chinese else 'Side-by-side images'}](#{'并排图片对比' if chinese else 'side-by-side-image-comparison'}) | [{'测量记录' if chinese else 'Measurements'}]({archive_path}/5way_v2_results.json) | [{'指标' if chinese else 'Metrics'}]({archive_path}/summary.json) | [{'请求记录' if chinese else 'Attempts'}]({archive_path}/attempts.jsonl)

**{outcome}** {boundary}

### {heading('Test Contract', '测试口径')}

{contract}

{procedure}

{'客户端' if chinese else 'Client'}: {summary['environment']['platform']}, {summary['environment']['architecture']}, Python {summary['environment']['python']}, requests {summary['environment']['requests']}.

{'正式起止时间 (UTC)' if chinese else 'Formal interval (UTC)'}: `{summary['formal_started_at_utc']}` to `{summary['formal_ended_at_utc']}`. {'正式窗口含等待' if chinese else 'Formal window including waits'}: **{number(summary['formal_window_seconds_including_waits'])} s**. {'四组合计观测完成速率' if chinese else 'Observed mixed-workload completion rate'}: **{number(summary['mixed_workload_observed_images_per_minute'])} {'张/分钟' if chinese else 'images/min'}** ({'不是单模型或最大吞吐' if chinese else 'not per-model or maximum throughput'}).{supplement_interval}

### {heading('Architecture and Measurement Boundary', '调用链与计时边界')}

```mermaid
flowchart LR
    prompts["Original 11 prompts"] --> runner["Local Windows Python runner"]
    runner --> mai["MAI-Image-2.6 / Sweden Central"]
    runner --> gpt["GPT-Image-2 / East US 2 / low, medium, high"]{gpt25_node}
    mai --> evidence["PNG, usage, request IDs, timestamps, failures"]
    gpt --> evidence
    evidence --> summary["Offline validation and report"]
```

{'原创解释图：本项目实际客户端与服务调用关系，不描绘模型内部结构。' if chinese else 'Original explanatory diagram of this project\'s client/service calls, not model internals.'} [MAI API](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai-image) | [GPT image API](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/dall-e).

### {heading('Performance and Reliability', '耗时与请求成功情况')}

{metrics_table(summary, language, supplement)}

{timing}

### {heading('Exceptions and Waiting', '异常与等待')}

{exception_section(summary, language, supplement)}

### {heading('Token Usage', 'Token 用量')}

{usage_table(summary, language, supplement)}

{usage_scope}

### {heading('Every Scenario, Both Rounds', '逐场景两轮耗时')}

{'单位为秒；失败格对应原始请求记录，不用其他轮次替换。' if chinese else 'Seconds; failed cells remain tied to their original requests and are not replaced by another round.'}

{prompt_latency_table(summary, language, supplement)}

### {heading('Quality Observations', '逐场景画面观察')}

{'先看可计数的结果，再读逐场景描述。下表统计本次观察记录中出现某类问题的场景数，是这次非盲评的措辞计数，不是模型的缺陷率，也不是质量评分。' if chinese else 'Countable outcomes first, then the per-scenario prose. The table counts how many scenarios mention each kind of issue in this review, which is a tally of this unblinded inspection rather than a defect rate or a quality score.'}{(' ' + observation_scope) if observation_scope else ''}

{observation_counts}

{observations}

{'逐场景描述来自' if chinese else 'Per-scenario descriptions come from'} [{'检查记录' if chinese else 'the inspection record'}]({archive_path}/quality-review.json).

### {heading('Measured API Settings', '本轮实际接口设置')}

{api}

{reproduction_section(archive_path, language, GROUNDING_ARCHIVE if has_grounding else None, EDIT_ARCHIVE if has_edit else None, supplement["archive"] if supplement else None, tier["archive"] if tier else None, head["archive"] if head else None, [s for s in text_studies if s], billing["archive"] if billing else None)}

### {heading('Limits', '结论边界')}

{limits}

{'证据目录' if chinese else 'Evidence directory'}: [{archive_path}]({archive_path}). {'包含原始图片、测量记录、逐次请求、响应元数据及删减后的公开源码副本。非财务测量字段和图片保持不变；原始执行哈希与公开文件哈希分别记录于' if chinese else 'Contains original images, measurement records, attempts, response metadata and a redacted public source copy. Non-financial measurement fields and image bytes are unchanged; original execution hashes and published-file hashes are recorded separately in'} [{'来源说明' if chinese else 'provenance'}]({archive_path}/provenance.json). {'提示词 SHA-256' if chinese else 'Prompt SHA-256'}: `{summary['prompts_sha256']}`.{mai_only_note}
"""


def render_edit_scenario(edit, archive_path, language):
    """Test 12: one real photo, one requested change, four configurations.

    Shown in the same order as the eleven text-to-image scenarios so a reader can
    compare it directly. The prompt names exactly one edit and lists what must stay
    the same, so each output is judged on checkable preservation items rather than
    on taste; the per-item checklist and the prose come from the review record.
    """
    chinese = language == "zh"
    rounds = edit["rounds"]
    source = edit["source"]
    lead = (
        f"前 11 题都是纯文生图。第 12 题改为图像编辑：把同一张真实照片交给四个配置的编辑接口，"
        f"只要求改一处，并明确列出必须保持不变的内容。因此每张输出都能按清单逐项核对，不需要审美打分。"
        f"与前 11 题相同，本题跑 {len(rounds)} 轮，第二轮配置顺序反转。"
        if chinese else
        f"The first eleven scenarios are pure text-to-image. Scenario 12 switches to image editing: the "
        f"same real photograph goes to each configuration's edit endpoint with a prompt that asks for "
        f"exactly one change and lists what must stay the same, so every output can be checked item by "
        f"item without an aesthetic score. As in the first eleven scenarios it runs {len(rounds)} rounds, "
        f"with the configuration order reversed in round 2."
    )
    input_note = (
        f"输入为一张 {source['width']}x{source['height']} 的 JPEG 照片（{source['bytes']:,} 字节，"
        f"SHA-256 `{source['sha256'][:16]}…`）：前景人物头戴冕冠，身着刺绣龙袍，左侧持戈侍卫，"
        "右侧紫衣人物与门廊建筑，左上角有剧名标题与印章。"
        if chinese else
        f"The input is one {source['width']}x{source['height']} JPEG photograph ({source['bytes']:,} bytes, "
        f"SHA-256 `{source['sha256'][:16]}…`): a foreground figure in a crown and embroidered robe, "
        "spear-bearing guards on the left, a purple-robed figure and gallery on the right, and a title "
        "with a seal in the top-left."
    )
    prompt_line = ("发给四个配置的提示词完全相同：" if chinese else
                   "The identical prompt sent to all four configurations:")
    prompt_quote = "> " + " ".join(edit["prompt"].split())
    gpt_size = edit["gpt_size_parameter"]
    size_note = (
        (f"GPT 三档只改 `quality`，`size` 传 `{gpt_size}`，即由服务自选输出尺寸；MAI 的编辑接口没有尺寸参数，"
         "输出尺寸同样由服务决定。两边因此处于同一合同：都没有被要求输出某个固定尺寸。"
         if gpt_size == "auto" else
         f"GPT 三档只改 `quality`，`size` 被本测试固定为 `{gpt_size}`；MAI 的编辑接口没有尺寸参数，输出尺寸由服务决定。"
         "注意这个 `size` 是本测试的选择，不是接口要求——gpt-image-2 的编辑接口接受任意分辩率和 `auto`。")
        if chinese else
        (f"The three GPT tiers differ only in `quality` and pass `size={gpt_size}`, so the service chooses the "
         "output dimensions; the MAI edit endpoint has no size parameter and the service likewise chooses. Both "
         "sides are therefore under the same contract: neither was told to produce a fixed size."
         if gpt_size == "auto" else
         f"The three GPT tiers differ only in `quality`; `size` was fixed by this test to `{gpt_size}`, while the "
         "MAI edit endpoint has no size parameter and the service chose the dimensions. That `size` is this "
         "test's choice, not an endpoint requirement: the gpt-image-2 edit endpoint accepts arbitrary "
         "resolutions and `auto`.")
    )
    controlled = (
        f"MAI 走 `/mai/v1/images/edits`，GPT 走 `/openai/deployments/gpt-image-2/images/edits`。{size_note}"
        f"每轮每个配置各调用一次，共 {len(rounds)} 轮。"
        if chinese else
        f"MAI uses `/mai/v1/images/edits` and GPT uses `/openai/deployments/gpt-image-2/images/edits`. {size_note} "
        f"Each configuration was called once per round, over {len(rounds)} rounds."
    )
    correction = ""
    if edit.get("supersedes"):
        reason = edit["supersedes"]["reason"][language]
        superseded_archive = edit["supersedes"].get("archive")
        if superseded_archive:
            reason += (f" 被作废的运行：[{superseded_archive}]({superseded_archive})。" if chinese else
                       f" Superseded run: [{superseded_archive}]({superseded_archive}).")
        carried = [(r["round"], item) for r in rounds for item in r["outputs"] if item.get("carried_from")]
        if carried:
            labels = sorted({LABELS[GROUPS.index(item["group"])] for _, item in carried})
            files = "、".join(f"`{item['carried_from']}`" for _, item in carried) if chinese else \
                ", ".join(f"`{item['carried_from']}`" for _, item in carried)
            dates = sorted({(item.get("requested_at_utc") or "")[:10] for _, item in carried})
            rounds_text = ("、".join(str(r) for r, _ in carried) if chinese else
                           " and ".join(str(r) for r, _ in carried))
            reason += ((f" 第 {rounds_text} 轮的 {'、'.join(labels)} 图不是重新调用的：它们就是那次运行的 {files}"
                        f"（请求于 {'、'.join(dates)}）。MAI 的编辑接口没有尺寸参数，它的调用不受这个参数错误影响，所以没有重跑；"
                        f"它的耗时与同轮 GPT 三档不是同一时段，读每轮耗时要连带日期。")
                       if chinese else
                       (f" The round {rounds_text} {' and '.join(labels)} images were not new calls: they are that run's "
                        f"{files} (requested {', '.join(dates)}). MAI's edit endpoint has no size parameter, so its calls "
                        f"were unaffected by the mistake and were not repeated; their latency is not the same session as "
                        f"the GPT tiers in the same round, so read each round's latencies together with their dates."))
        correction = f"**{'协议更正' if chinese else 'Protocol correction'}**\n\n{reason}"
        # The figure shows only the valid protocol. The forced-square outputs were
        # produced by this test's own parameter, not by the models, so putting them
        # in a model comparison would misattribute our mistake to GPT.
        figure = f"{archive_path}/figures/scenario12-auto-results.png"
        if (Path(__file__).resolve().parents[1] / figure).is_file():
            caption = (
                "下图汇总本题在 `size=auto` 下的结果：输入原图、提示词、尺寸参数说明，"
                "以及四个配置各自的输出、实际分辨率与 5 项保持内容的命中数。"
                "被作废的方图输出不在图中——它们是本测试参数设置的产物，不是模型行为，"
                "放进模型对比会把我们的错误归因给模型；原始运行仍保留在归档中。"
                if chinese else
                "The figure below summarises this scenario under `size=auto`: the input, the prompt, how the "
                "size parameter was set, and each configuration's output with its real resolution and count "
                "on the five preservation items. The superseded square outputs are not shown — they were "
                "produced by this test's own parameter rather than by the models, so placing them in a model "
                "comparison would attribute our mistake to GPT; the original run remains in the archive.")
            alt = ("第 12 题 size=auto 结果汇总" if chinese else
                   "Scenario 12 results under size=auto")
            correction += f"\n\n![{alt}]({figure})\n\n{caption}"
    check_labels = [
        ("headwear_replaced_with_graduation_cap", "换成博士帽" if chinese else "Headwear became a graduation cap"),
        ("face_and_beard_preserved", "人脸与胡须保留" if chinese else "Face and beard preserved"),
        ("robe_embroidery_preserved", "龙袍纹样保留" if chinese else "Robe embroidery preserved"),
        ("bystanders_and_background_unchanged", "侍卫与背景不变" if chinese else "Bystanders and background unchanged"),
        ("title_and_seal_preserved", "标题与印章保留" if chinese else "Title and seal preserved"),
        ("input_aspect_ratio_preserved", "保持原图宽高比" if chinese else "Input aspect ratio kept"),
    ]
    yes, no = ("是", "否") if chinese else ("yes", "no")
    # The input image is shown once, as the eleven scenarios show their prompt once.
    input_image = table([("输入图" if chinese else "Input photograph")],
                        [[f"![Input photograph]({archive_path}/{source['file']})"]])
    round_blocks = []
    for round_item in rounds:
        by_group = {item["group"]: item for item in round_item["outputs"]}
        number = round_item["round"]
        # Same shape as Tests 1-11: one image row, then `latency<br>size` under each.
        images = table(LABELS, [
            [f"![{label}, edit round {number}]({archive_path}/{by_group[g]['output']})"
             for g, label in zip(GROUPS, LABELS)],
            [f"{by_group[g]['request_seconds']:.2f} s<br>{by_group[g]['output_kib']:.0f} KiB<br>"
             f"{by_group[g]['width']}x{by_group[g]['height']}" for g in GROUPS],
        ])
        check_rows = [[("保持项命中" if chinese else "Preservation items kept"),
                       *(f"{by_group[g]['preserved_count']}/{by_group[g]['preserved_total']}" for g in GROUPS)]]
        for key, label in check_labels:
            check_rows.append([label, *(yes if by_group[g]["checks"][key] else no for g in GROUPS)])
        checks = table([("核对项" if chinese else "Checklist"), *LABELS], check_rows)
        prose = table([("配置" if chinese else "Configuration"), ("画面观察" if chinese else "Observation")],
                      [[label, by_group[g]["observation"][language]] for g, label in zip(GROUPS, LABELS)])
        round_blocks.extend([f"**{'第' + str(number) + '轮' if chinese else 'Round ' + str(number)}:**",
                             images, checks, prose])

    # Countable outcome across rounds: how often each configuration kept all items.
    per_group_kept = {g: [item["preserved_count"] for r in rounds for item in r["outputs"] if item["group"] == g]
                      for g in GROUPS}
    total = rounds[0]["outputs"][0]["preserved_total"]
    kept_summary = table(
        [("跨轮汇总" if chinese else "Across rounds"), *LABELS],
        [[("保持项命中（每轮）" if chinese else "Items kept (per round)"),
          *(" / ".join(f"{k}/{total}" for k in per_group_kept[g]) for g in GROUPS)],
         [("请求耗时（每轮）" if chinese else "Latency per round"),
          *(" / ".join(f"{item['request_seconds']:.2f} s" for r in rounds for item in r["outputs"]
                       if item["group"] == g) for g in GROUPS)],
         [("换成博士帽" if chinese else "Graduation cap present"),
          *(f"{sum(1 for r in rounds for item in r['outputs'] if item['group'] == g and item['checks']['headwear_replaced_with_graduation_cap'])}/{len(rounds)}"
            for g in GROUPS)]])
    mai_all = all(k == total for k in per_group_kept["mai-image-2.6"])
    gpt_any_full = any(k == total for g in GROUPS[1:] for k in per_group_kept[g])
    reading = edit.get("summary_observation", {}).get(language) or (
        ("四个配置在每一轮都换上了博士帽。差别在其余部分："
         + ("MAI 两轮输出都与原图逐项一致，外观符合局部重绘；" if mai_all else
            "MAI 并非每轮都保住全部保持项；")
         + ("GPT 三档没有一轮保住全部保持项，都围绕主题重新生成整幅画面。" if not gpt_any_full else
            "GPT 至少有一轮保住了全部保持项。")
         + "本题提示词要求保持原图，所以偏离就是未按指令执行；若提示词要求重新演绎，同样这些图会得到不同的评价。")
        if chinese else
        ("Every configuration produced the graduation cap in every round. The difference is in everything else: "
         + ("the MAI output matches the input item by item in both rounds and looks like a local repaint; "
            if mai_all else "MAI did not keep every preservation item in every round; ")
         + ("no GPT tier kept every preservation item in any round; all three regenerate the whole frame around "
            "the theme. " if not gpt_any_full else "at least one GPT round kept every preservation item. ")
         + "This prompt asked to preserve the input, so departure is non-compliance here; a prompt asking for a "
           "reinterpretation would judge these same images differently.")
    )
    boundary = (
        f"共 {len(rounds)} 轮，每轮每个配置一次调用，两轮只说明结果是否重复出现，不构成统计样本；"
        "观察为非盲评，只描述与原图的差异，不是画质评分。"
        "耗时为客户端 `requests.post` 往返时间，GPT 部署在 East US 2、MAI 在 Sweden Central，客户端为同一台工作站，区域差异未剥离。"
        "输出 PNG 均无 alpha 通道。"
        if chinese else
        f"{len(rounds)} rounds with one call per configuration per round; two rounds show whether the outcome "
        "repeats and are not a statistical sample. Observations are unblinded and describe departures from the "
        "input, not image quality. Latency is client-side `requests.post` round-trip time; GPT ran in East US 2 "
        "and MAI in Sweden Central from the same workstation, so region is not separated out. No output PNG "
        "carries an alpha channel."
    )
    link_items = []
    for round_item in rounds:
        sub = "" if round_item["round"] == 1 else f"r{round_item['round']}/"
        tag = (f"第{round_item['round']}轮" if chinese else f"round {round_item['round']}")
        link_items.append(f"[{'请求记录' if chinese else 'Request records'} {tag}]({archive_path}/{sub}edit-results.json)")
        link_items.append(f"[{'逐图核对' if chinese else 'Per-image checklist'} {tag}]({archive_path}/{sub}edit-review.json)")
    if edit.get("summary_observation"):
        link_items.append(f"[{'标题区域对照图' if chinese else 'Title-region contact sheet'}]({archive_path}/title-corner-contact-sheet.png)")
    link_items.append(f"[{'公开复现脚本' if chinese else 'Public reproduction runner'}](scripts/run_edit_hat_swap.py)")
    links = " | ".join(link_items)
    title = "### Test 12: 换帽子（图像编辑）" if chinese else "### Test 12: Headwear Swap (Image Edit)"
    parts = [title, lead, input_note, prompt_line, prompt_quote,
             f"**{'受控变量' if chinese else 'Controlled variables'}**", controlled]
    if correction:
        parts.append(correction)
    parts.extend([input_image, *round_blocks, kept_summary, reading, boundary, links])
    return "\n\n".join(parts)


def edit_reproduction_commands(archive_path):
    output = "runs/edit-hat-swap-reproduction"
    input_path = f"{archive_path}/input.jpg"
    runner = "python scripts/run_edit_hat_swap.py"
    return (f"```powershell\npython scripts/summarize_edit_hat_swap.py {archive_path} --check\n"
            f"{runner} --input {input_path} --output {output} --round 1 --gpt-size auto --dry-run\n"
            f"{runner} --input {input_path} --output {output} --round 1 --gpt-size auto\n"
            f"{runner} --input {input_path} --output {output} --round 2 --gpt-size auto\n"
            f"{runner} --output {output} --check\n```")


def grounding_reproduction_commands(archive_path):
    return (f"```powershell\npython scripts/summarize_web_grounding.py {archive_path} --require-complete --check\n"
            f"python {archive_path}/source/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --mai-web-grounding both "
            f"--prompts-csv {archive_path}/source/prompts.csv --output runs/web-grounding-reproduction --dry-run\n"
            f"python {archive_path}/source/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --mai-web-grounding both "
            f"--prompts-csv {archive_path}/source/prompts.csv --output runs/web-grounding-reproduction\n```")


def render_grounding_section(summary, archive_path, language):
    if not summary["complete"]:
        raise ValueError("Grounding results must be complete before publication")
    chinese = language == "zh"
    selected = [sample for sample in summary["samples"] if sample["prompt_idx"] in (1, 2)]
    settings = [False, True]
    rows_by_setting = [[sample for sample in selected if sample["web_grounding"] is enabled]
                       for enabled in settings]
    selected_ids = {(sample["group"], sample["round"], sample["prompt_idx"]) for sample in selected}
    unsuccessful = [attempt for attempt in summary["unsuccessful_attempts"]
                    if (attempt["group"], attempt["round"], attempt["prompt_idx"]) in selected_ids]
    metrics = []
    for label, measure in (
        ("返回图片 / 展示样本" if chinese else "Images returned / displayed samples",
         lambda rows: f"{sum(sample['ok'] for sample in rows)}/{len(rows)}"),
        ("首试成功 / 展示样本" if chinese else "First-attempt successes / displayed samples",
         lambda rows: f"{sum(sample['first_attempt_ok'] for sample in rows)}/{len(rows)}"),
        ("HTTP 请求次数" if chinese else "HTTP attempts",
         lambda rows: str(sum(sample["attempt_count"] for sample in rows))),
        ("HTTP 408 次数" if chinese else "HTTP 408 responses",
         lambda rows: str(sum(attempt.get("http_status") == 408 and attempt["group"] == rows[0]["group"]
                              for attempt in unsuccessful))),
    ):
        metrics.append([label, *(measure(rows) for rows in rows_by_setting)])
    unit = "秒" if chinese else "s"
    for label, statistic, field, successful_only in (
        ("成功请求平均耗时" if chinese else "Mean successful request", statistics.mean, "time", True),
        ("成功请求 P50" if chinese else "Successful request P50", statistics.median, "time", True),
        ("含失败重试的逻辑调用平均耗时" if chinese else "Mean logical call including retries",
         statistics.mean, "logical_request_seconds", False),
    ):
        values = [[sample[field] for sample in rows if sample["ok"] or not successful_only]
                  for rows in rows_by_setting]
        metrics.append([label, *(f"{statistic(values_for_setting):.2f} {unit}" if values_for_setting else "N/A"
                                 for values_for_setting in values)])
    headers = ["指标", "关闭联网", "开启联网"] if chinese else ["Metric", "Grounding off", "Grounding on"]
    intro = (
        "本节测试通用的联网信息补充能力：在相同提示词下，对比 MAI-Image-2.6 的 `web_grounding=false/true`，"
        "观察文字事实准确性与生成耗时。公开新品资料只是测试题材，不是客户项目或客户采纳案例。"
        if chinese else
        "This section tests web grounding as a general image-generation capability: identical prompts are sent to "
        "MAI-Image-2.6 with `web_grounding=false/true` to compare text factual accuracy and latency. "
        "Public product announcements supply the test subjects; this is not a customer project or adoption case."
    )
    scope = (
        f"完整补测为 {summary['planned_samples']} 个正式样本，另有 {summary['warmups_excluded']} 次预热。"
        f"按已观察到的文字事实改善选取两个题目，保留全部两轮开／关对照，共 {len(selected)} 张原图，"
        f"每组 {len(rows_by_setting[0])} 个样本。下表仅统计这些选例，不是全量提升率。"
        "本节没有 GPT 对照，不能据此得出相对 GPT-Image-2 的优势结论。"
        if chinese else
        f"The complete supplement contains {summary['planned_samples']} formal samples and "
        f"{summary['warmups_excluded']} excluded warmups. Two subjects were selected after observing improved text facts; "
        f"all off/on results from both rounds are shown, {len(selected)} original images and "
        f"{len(rows_by_setting[0])} samples per setting. The table covers only these examples, not an overall improvement rate. "
        "No GPT comparison was performed in this section, so it does not establish superiority over GPT-Image-2."
    )
    findings = (
        [["新品配色与尺寸", "两轮均出现非官方配色名和错误屏幕选项", "两轮均匹配七种官方配色名及 14/15 英寸选项"],
         ["产品规格与使用模式", "屏幕尺寸和计算平台错误，均漏掉 Canvas 模式", "两轮均写对 16 英寸、NVIDIA RTX Spark、五种模式及笔输入表面"]]
        if chinese else
        [["New-product colours and sizes", "Both rounds used unofficial colour names and incorrect screen options",
          "Both matched all seven official colour names and the 14/15-inch options"],
         ["Product specifications and usage modes", "Screen size and computing platform were wrong; Canvas mode was missing",
          "Both matched 16 inches, NVIDIA RTX Spark, five mode names and the pen-input surfaces"]]
    )
    boundaries = (
        "固定 1024x1024、`auto_aspect_ratio=false`，同一模型版本 2026-07-31、Sweden Central GlobalStandard 部署；"
        "第二轮反转请求顺序。两组仅联网开关不同，核对答案未加入提示词。"
        "成功请求耗时不含 JSON/base64 处理；逻辑调用耗时包含失败、退避和响应处理，不含外侧 5 秒间隔及最终 PNG 写盘。"
        "所有 HTTP 408 和重试均保留，服务未说明内部超时环节，不能把全部额外时间归因于搜索。"
        if chinese else
        "Both settings used 1024x1024, `auto_aspect_ratio=false`, model version 2026-07-31 and the same Sweden Central "
        "GlobalStandard deployment. Round 2 reversed request order. Only the grounding switch differed; reference answers "
        "were not included in prompts. Successful request time excludes JSON/base64 processing; logical call time includes "
        "failures, backoff and response processing, but excludes the outer five-second interval and final PNG write. "
        "All HTTP 408 responses and retries are retained. The internal timeout stage was not returned, so the additional "
        "time cannot all be attributed to search."
    )
    quality_boundary = (
        "文字事实改善不等于画面质量或产品外观保真。第二题第二轮开启图中，`Tablet Mode` 标签下仍画着竖起的屏幕，"
        "存在图文不一致。观察为 AI 辅助非盲评，只有少量重复，不是人工偏好或统计显著性结论。"
        "响应没有提供检索查询、来源 URL 或调用轨迹；usage 变化不能证明具体检索来源。"
        if chinese else
        "Improved text facts do not establish better aesthetics or product fidelity. In subject 2, round 2, the "
        "grounding-on `Tablet Mode` illustration still has an upright screen. Inspection was AI-assisted and unblinded, "
        "with few repetitions, not human preference voting or a statistically significant result. Responses included "
        "no search queries, source URLs or retrieval traces; usage changes do not identify retrieval sources."
    )
    subject_labels = ("新品配色与尺寸", "产品规格与使用模式") if chinese else (
        "New-product colours and sizes", "Product specifications and usage modes")
    prompt_block = []
    for index, label in enumerate(subject_labels):
        # Prompts are shown as ordinary wrapped paragraphs. A fenced block would
        # scroll sideways and a collapsed block would hide the actual input.
        prompt_text = " ".join(summary["prompts"][index].split())
        prompt_block.append(
            (f"题目 {index + 1}（{label}）发给模型的完整提示词：" if chinese else
             f"The exact prompt sent for subject {index + 1} ({label}):")
            + f"\n\n> {prompt_text}")
    asked = (
        "两个题目都要求模型把真实产品信息画进海报：题目 1 要求列出官方发布的全部配色名与屏幕尺寸选项，"
        "题目 2 要求写出产品名、屏幕尺寸、计算平台，并标出官方命名的翻转使用模式与支持笔输入的表面。"
        "提示词只要求以官方发布信息为准，没有把正确答案写进提示词。"
        if chinese else
        "Both subjects ask the model to put real product information into a poster. Subject 1 asks for every "
        "officially announced colour name and the screen-size options; subject 2 asks for the product name, screen "
        "size, computing platform, the officially named convertible modes and which surfaces accept pen input. The "
        "prompts only instruct the model to follow the official announcement; no correct answer is supplied in the "
        "prompt itself."
    )
    controlled = (
        "唯一变化的是 `web_grounding` 开关。提示词、尺寸、模型版本、部署与轮数完全相同。"
        if chinese else
        "The only thing that changes is the `web_grounding` switch. Prompt, dimensions, model version, deployment "
        "and round count are identical."
    )
    sections = [f"## {'联网信息补充测试' if chinese else 'Web Grounding Test'}", intro,
                f"**{'我们向模型提出的问题' if chinese else 'What we asked the model'}**", asked,
                *prompt_block,
                f"**{'受控变量' if chinese else 'Controlled variable'}**", controlled, scope,
                f"**{'文字事实核对结果' if chinese else 'Text-fact findings'}**",
                table(["测试项", "关闭联网", "开启联网"] if chinese else ["Test subject", "Grounding off", "Grounding on"], findings),
                f"**{'耗时与请求情况' if chinese else 'Latency and request outcomes'}**",
                table(headers, metrics), boundaries, quality_boundary]
    for prompt_index, subject in ((1, "新品配色与尺寸" if chinese else "New-product colours and sizes"),
                                  (2, "产品规格与使用模式" if chinese else "Product specifications and usage modes")):
        for round_number in (1, 2):
            rows = [next(sample for sample in selected if sample["prompt_idx"] == prompt_index
                         and sample["round"] == round_number and sample["web_grounding"] is enabled)
                    for enabled in settings]
            images = [f"![Web grounding {'on' if enabled else 'off'}, subject {prompt_index}, round {round_number}]"
                      f"({archive_path}/{sample['image']})" if sample["ok"] else
                      ("未返回图片" if chinese else "No image returned") for enabled, sample in zip(settings, rows)]
            caption = f"#### {subject} / {'第' + str(round_number) + '轮' if chinese else 'Round ' + str(round_number)}"
            sections.extend([caption, table(["`web_grounding=false`", "`web_grounding=true`"], [images])])
    sections.extend([
        ("完整原始数据保留，旧批次不重写；本节与上文双模型测试分别统计，复现命令见下方复现与测试章节。" if chinese else
         "Full original evidence is retained without rewriting previous runs. This section is measured separately from the two-model test above; its commands appear in the reproduction section below."),
        f"[{'原始结果' if chinese else 'Raw results'}]({archive_path}/5way_v2_results.json) | "
        f"[{'全部请求' if chinese else 'All attempts'}]({archive_path}/attempts.jsonl) | "
        f"[{'逐图观察' if chinese else 'Visual observations'}]({archive_path}/visual-review.json) | "
        f"[{'完整12样本统计' if chinese else 'Full 12-sample statistics'}]({archive_path}/web-grounding-summary.json) | "
        f"[{'出处与哈希' if chinese else 'Provenance and hashes'}]({archive_path}/provenance.json)",
        f"{'结果 SHA-256' if chinese else 'Result SHA-256'}: `{summary['result_sha256']}`.",
        ("官方参考：" if chinese else "Official references: ") +
        "[IdeaPad Vibe](https://news.lenovo.com/pressroom/press-releases/colorful-ideapad-vibe-series-all-in-one-ai-pcs/) | "
        "[Yoga](https://news.lenovo.com/pressroom/press-releases/yoga-portfolio-new-ai-pcs-and-tablets/) | "
        "[MAI API](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai-image#request-parameters)",
    ])
    return "\n\n".join(sections)


def update_document(text, summary, quality, archive_path, language, grounding_section="",
                    edit_section="", supplement=None, tier=None, text_study=None, billing=None,
                    head=None, hard_study=None):
    chinese = language == "zh"
    coverage = tier_coverage(summary, supplement["summary"] if supplement else None,
                             tier["summary"] if tier else None)
    models = "MAI-Image-2.6 与 GPT-Image-2 / 2.5" if supplement else "MAI-Image-2.6 与 GPT-Image-2"
    models_en = "MAI-Image-2.6 vs GPT-Image-2 / 2.5" if supplement else "MAI-Image-2.6 vs GPT-Image-2"
    tiers = sorted({tier for tiers in coverage["measured"].values() for tier in tiers},
                   key=TIER_ORDER.index)
    if coverage["complete"]:
        title = (f"# {models}：全质量档位图像生成对比" if chinese else
                 f"# {models_en}: All Quality Tiers")
    elif tiers:
        # Name the tiers that were measured rather than implying the full set.
        listed = "、".join(tiers) if chinese else ", ".join(tiers)
        title = (f"# {models}：{listed} 档图像生成对比" if chinese else
                 f"# {models_en}: {listed} Tiers")
    else:
        title = (f"# {models}：图像生成对比" if chinese else
                 f"# {models_en}: Image Generation Comparison")
    author = re.search(r"(?m)^> \*\*(?:Author|作者)\*\*:[^\n]+", text)
    if author is None:
        raise ValueError("Existing report author attribution was not found")
    # Scenario titles 1-11 are preserved from the existing document; Test 12 is
    # rendered from its own evidence and is not required to pre-exist.
    titles = {int(index): heading.strip() for index, heading in
              re.findall(r"(?m)^### Test (\d+): ([^\n]+)$", text)}
    if not set(range(1, 12)) <= set(titles) or [item["prompt_index"] for item in summary["per_prompt"]] != list(range(1, 12)):
        raise ValueError("All eleven original scenarios are required")
    content = render_overview(summary, quality, archive_path, language,
                              bool(grounding_section), bool(edit_section), supplement, tier,
                              head, (text_study, hard_study), billing)
    comparison_heading = "## 并排图片对比" if chinese else "## Side-by-Side Image Comparison"
    description = ("第 1–11 题为文生图，每个场景、每一轮只展示 MAI-Image-2.6 与 GPT-Image-2 low、medium、high。图片来自本次四组测试，未返回图片的格子保留失败说明。点击图片查看原始 1024x1024 PNG。第 12 题为图像编辑，输入为一张真实照片。"
                   if chinese else "Scenarios 1-11 are text-to-image; every scenario and round compares only MAI-Image-2.6 with GPT-Image-2 low, medium and high. Images come from this four-configuration run; missing images retain their failure record. Click an image for the original 1024x1024 PNG. Scenario 12 is an image edit of one real photograph.")
    if supplement:
        description = ((f"第 1–11 题为文生图。每个场景每一轮有两行图：第一行是 {summary['formal_started_at_utc'][:10]} 测的 MAI-Image-2.6 与 GPT-Image-2 low、medium、high；第二行是 {supplement['date']} 用同一客户端、同一提示词补测的 GPT-Image-2.5 Flare 与 Sunburst 各三档，部署在 {supplement['region']}。两行不是同一时段，图下的耗时要连带日期看。未返回图片的格子保留失败说明。点击图片查看原始 1024x1024 PNG。第 12 题为图像编辑，输入为一张真实照片，没有 2.5 的结果。")
                       if chinese else
                       (f"Scenarios 1-11 are text-to-image. Each scenario and round has two image rows: the first is MAI-Image-2.6 with GPT-Image-2 low, medium and high measured on {summary['formal_started_at_utc'][:10]}; the second is GPT-Image-2.5 Flare and Sunburst at all three tiers, measured on {supplement['date']} with the same client and prompt file and deployed in {supplement['region']}. The rows are not the same session, so read the latencies under the images together with their dates. Missing images retain their failure record. Click an image for the original 1024x1024 PNG. Scenario 12 is an image edit of one real photograph and has no 2.5 results."))
    # Images come before the metrics body: a reader judges generated pictures by
    # looking at them, and the timing and token tables only make sense afterwards.
    # The latest formal end across every archive the report draws on: the date after which
    # these figures stop being current.
    ends = [s["formal_ended_at_utc"] for s in
            [summary, *(extra["summary"] for extra in (supplement, tier, head) if extra)]
            if s.get("formal_ended_at_utc")]
    data_through = max(ends)[:10] if ends else None
    test_count = count_tests(Path(__file__).resolve().parents[1])
    sections = [title, render_masthead(summary, author.group(), language, supplement, data_through, test_count),
                render_highlights(summary, language, bool(grounding_section),
                                  bool(edit_section), supplement),
                comparison_heading, description]
    for prompt_record in summary["per_prompt"]:
        prompt_index = prompt_record["prompt_index"]
        sections.extend([f"### Test {prompt_index}: {titles[prompt_index]}",
                         "> **Prompt**: " + prompt_record["prompt"]])
        for round_number in (1, 2):
            sections.extend([f"**Round {round_number}:**",
                             comparison_table(prompt_record, round_number, archive_path, language)])
            if supplement:
                sections.append(comparison_table(supplement_prompt(supplement, prompt_record), round_number,
                                                 supplement["archive"], language,
                                                 supplement["groups"], supplement["labels"]))
    # Test 12 sits with the other scenarios so the reader meets it in sequence.
    if edit_section:
        sections.append(edit_section)
    sections.append(content.strip())
    # Directly after the metrics the reader just saw, since it answers "what about the other tiers".
    if tier and supplement:
        sections.append(render_tier_section(supplement, tier, language))
    # Cost follows the tier table because it is computed from those token counts.
    if billing:
        sections.append(render_cost_section(billing, language))
    # The same-session comparison against 2.5 follows cost because it is the question cost raises.
    if head:
        sections.append(render_head_to_head(head, billing, language))
    # Text rendering answers a different question than latency, so it follows the tier tables.
    if text_study:
        sections.append(render_text_section(text_study, language))
    # The hard set follows the easy one: it exists because the easy one could not separate the models.
    if hard_study:
        sections.append(render_text_section(hard_study, language))
    if grounding_section:
        sections.append(grounding_section)
    return "\n\n".join(sections) + "\n"


def validate_quality(summary, quality):
    if quality.get("result_sha256") != summary["result_sha256"]:
        raise ValueError("Visual review does not belong to the current measured results")
    expected_images = {row["image"] for prompt in summary["per_prompt"] for group in prompt["configurations"]
                       for row in group["rounds"] if row["ok"]}
    if set(quality.get("inspected_images", [])) != expected_images:
        raise ValueError("Visual inspection must cover every returned formal image")
    if [item["prompt_index"] for item in quality.get("per_prompt", [])] != list(range(1, 12)):
        raise ValueError("Visual review is missing an original scenario")
    for item in quality["per_prompt"]:
        if set(item["observations"]) != set(GROUPS):
            raise ValueError("Visual review must cover all four configurations")
        if any(not item["observations"][group].get(language) for group in GROUPS for language in ("en", "zh")):
            raise ValueError("Visual review needs both language observations")


def main():
    parser = argparse.ArgumentParser(description="Generate both language reports from one validated paired image run.")
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--check", action="store_true", help="Check generated content without editing either README.")
    parser.add_argument("--validate-review-only", action="store_true", help="Validate run and visual coverage without rendering or editing reports.")
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    run_directory = arguments.run_directory.resolve()
    summary = summarize(run_directory, root / "prompts.csv")
    quality = json.loads((run_directory / "quality-review.json").read_text("utf-8"))
    validate_quality(summary, quality)
    if arguments.validate_review_only:
        print(json.dumps({"status": "PASS", "formal_samples": summary["formal_samples"],
                          "inspected_images": len(quality["inspected_images"]), "scenarios": len(quality["per_prompt"])}))
        return
    archive_path = run_directory.relative_to(root).as_posix()
    grounding_summary = summarize_grounding(root / GROUNDING_ARCHIVE)
    edit_summary = summarize_edit(root / EDIT_ARCHIVE)
    supplement = load_supplement(root, root / "prompts.csv")
    tier = load_tier_supplement(root, root / "prompts.csv") if supplement else None
    text_study = load_text_study(root)
    hard_study = load_text_study(root, "data/text-hard-20260919", "prompts-text-hard.csv", "hard")
    billing = load_billing(root)
    head = load_head_to_head(root, root / "prompts.csv")
    documents = []
    for filename, language in (("README.md", "en"), ("README-CN.md", "zh")):
        path = root / filename
        original = path.read_text("utf-8")
        generated = update_document(
            original, summary, quality, archive_path, language,
            render_grounding_section(grounding_summary, GROUNDING_ARCHIVE, language),
            render_edit_scenario(edit_summary, EDIT_ARCHIVE, language), supplement, tier, text_study,
            billing, head, hard_study)
        documents.append((path, original, generated))
    if arguments.check:
        changed = [path.name for path, original, generated in documents if original != generated]
        if changed:
            raise SystemExit("Report differs from current evidence: " + ", ".join(changed))
    else:
        for path, _, generated in documents:
            path.write_text(generated, encoding="utf-8")
    print(json.dumps({"status": "PASS", "formal_samples": summary["formal_samples"],
                      "configurations": len(GROUPS) + (len(supplement["groups"]) if supplement else 0)
                                        + (len(tier["groups"]) if tier else 0),
                      "supplement": supplement["archive"] if supplement else None,
                      "tier_supplement": tier["archive"] if tier else None,
                      "text_study": text_study["archive"] if text_study else None,
                      "hard_text_study": hard_study["archive"] if hard_study else None,
                      "billing": billing["archive"] if billing else None,
                      "head_to_head": head["archive"] if head else None,
                      "scenario_round_tables_per_language": len(summary["per_prompt"]) * (4 if supplement else 2)}))


if __name__ == "__main__":
    main()
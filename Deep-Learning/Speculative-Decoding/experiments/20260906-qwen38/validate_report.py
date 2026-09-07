"""Validate the saved experiment, generated report blocks and published hashes."""

import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
from statistics import median
from urllib.parse import unquote, urlsplit

from analyze_results import digest_file, dump_json, require, summarize


ROOT = Path(__file__).resolve().parent
MANIFEST = "evidence/files.json"
RULES = "evidence/rule-results.json"
IGNORED_PARTS = {"__pycache__", ".venv", "regenerated", ".pytest_cache"}
READMES = ("README.md", "README-CN.md")


def topic_dir(root):
    return root.parent.parent


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def markdown_table(headers, rows):
    return "\n".join("| " + " | ".join(map(str, row)) + " |" for row in
                     [headers, ["---"] * len(headers), *rows])


def display_route(route, chinese):
    labels = {"baseline": "基线" if chinese else "Baseline", "mtp7": "MTP7", "dflash2_7": "DFlash 2-7"}
    return labels.get(route, route)


def result_table(summary, chinese):
    performance, accuracy, normal_accuracy, truncation = [], [], [], []
    counts_equal = True
    separator = "、" if chinese else ", "
    for group in summary["matched_summary"]:
        code, maths = (group["datasets"][name] for name in ("humaneval_plus", "math_500"))
        identity = [group["concurrency"], display_route(group["route"], chinese)]
        performance.append(identity + [f"{group['throughput_tok_s']['median']:.2f}", f"{group['group_wall_s']['median']:.2f}"])
        for target, field in ((accuracy, "raw_correct"), (normal_accuracy, "normal_correct"), (truncation, "length_stopped")):
            target.append(identity + [separator.join(map(str, dataset[field])) for dataset in (code, maths)])
        counts_equal = counts_equal and all(dataset["raw_correct"] == dataset["normal_correct"] for dataset in (code, maths))
    if chinese:
        performance_header = ["并发", "路线", "吞吐（tok/s）", "整组耗时（秒）"]
        accuracy_header = ["并发", "路线", "代码答对数 /32", "数学答对数 /32"]
        truncation_header = ["并发", "路线", "代码截断数", "数学截断数"]
        sections = ["### 吞吐与整组耗时", markdown_table(performance_header, performance),
                    "### 代码与数学得分", markdown_table(accuracy_header, accuracy)]
        if counts_equal:
            sections.append("本次所有被评分器判对的回答都正常结束，因此“答对数”和“正常结束且答对数”相同，不重复列两遍。两项原始字段均保留在数据文件中。")
        else:
            sections.extend(["正常结束且答对的数量另列如下，不能用全部答对数替代：", markdown_table(accuracy_header, normal_accuracy)])
        sections.append("<details>\n<summary>查看三次运行的截断情况</summary>\n\n" + markdown_table(truncation_header, truncation) + "\n\n达到输出上限的回答仍保留在每次 32 题的分母中。\n\n</details>")
    else:
        performance_header = ["Concurrency", "Route", "Output tok/s", "Group wall (s)"]
        accuracy_header = ["Concurrency", "Route", "Code correct /32", "Math correct /32"]
        truncation_header = ["Concurrency", "Route", "Code length stops", "Math length stops"]
        sections = ["### Throughput and Group Duration", markdown_table(performance_header, performance),
                    "### Code and Math Scores", markdown_table(accuracy_header, accuracy)]
        if counts_equal:
            sections.append("All answers marked correct by the graders stopped normally in this run, so raw-correct and normal-stop-correct counts coincide. Both fields remain in the data; duplicate columns are omitted here.")
        else:
            sections.extend(["Normal-stop-correct counts are shown separately and must not be replaced by raw-correct counts:", markdown_table(accuracy_header, normal_accuracy)])
        sections.append("<details>\n<summary>Length stops across the three runs</summary>\n\n" + markdown_table(truncation_header, truncation) + "\n\nLength-stopped responses remain in each 32-task denominator.\n\n</details>")
    return "\n\n".join(sections)


def latency_table(groups, summary, chinese):
    cells = summary["matched_summary"]
    routes = list(dict.fromkeys(cell["route"] for cell in cells))
    concurrency_levels = sorted({cell["concurrency"] for cell in cells})
    headers = ["并发" if chinese else "Concurrency"] + [display_route(route, chinese) for route in routes]
    measurements = {}
    observations = []
    by_id = {group["group_id"]: group for group in groups}
    for cell in cells:
        clients = [by_id[name]["client"]["all"] for name in cell["source_groups"]]
        metrics = ("ttft_token_s", "tpot_s", "e2e_s")
        route = display_route(cell["route"], chinese)
        values = []
        for metric, scale in zip(metrics, (1000, 1000, 1)):
            values.append(f"{median(client[metric]['p50'] for client in clients) * scale:.3f}")
        for metric in metrics:
            valid = sum(client[metric]["valid_count"] for client in clients)
            missing = sum(client[metric]["missing_count"] for client in clients)
            observations.append([f"{route} / {cell['concurrency']}", metric, valid, missing])
        measurements[(cell["concurrency"], cell["route"])] = values
    titles = (["### 首 token 等待（TTFT，ms）", "### token 交付间隔（TPOT，ms/token）", "### 单次回答耗时（秒）"] if chinese else
              ["### Time to First Token (ms)", "### Time per Output Token (ms/token)", "### Response Time (s)"])
    sections = []
    for index, title in enumerate(titles):
        rows = [[concurrency] + [measurements[(concurrency, route)][index] for route in routes]
                for concurrency in concurrency_levels]
        sections.extend([title, markdown_table(headers, rows)])
    counts = {(row[2], row[3]) for row in observations}
    if len(counts) == 1:
        valid, missing = next(iter(counts))
        note = (f"每个配置、每项指标均有 {valid} 份有效响应记录，缺失 {missing} 份。这是重复运行的观测数，不是独立题目数。" if chinese else
                f"Each metric in each configuration has {valid} valid response observations and {missing} missing observations. These are repeated responses, not independent tasks.")
    else:
        count_headers = ["路线 / 并发", "指标", "有效", "缺失"] if chinese else ["Route / concurrency", "Metric", "Valid", "Missing"]
        note = markdown_table(count_headers, observations)
    return "\n\n".join([*sections, note])


def counterexample(groups, chinese):
    selected = {group["route"]: group for group in groups if group["stage"] == "S"
                and group["concurrency"] == 4 and group["base_seed"] == 20260908}
    candidate, reference = selected["dflash2_7"], selected["mtp7"]
    headers = (["路线", "整组耗时（秒）", "代码答对数 /32", "数学答对数 /32"] if chinese else
               ["Route", "This run's group wall (s)", "Normal-correct code /32", "Normal-correct math /32"])
    rows = [[display_route(group["route"], chinese), f"{group['elapsed_wall_s']:.2f}",
             group["scores"]["datasets"]["humaneval_plus"]["normal_correct"],
             group["scores"]["datasets"]["math_500"]["normal_correct"]] for group in (reference, candidate)]
    ratios = []
    for dataset in ("humaneval_plus", "math_500"):
        candidate_rate = candidate["scores"]["datasets"][dataset]["normal_correct"] / candidate["elapsed_wall_s"]
        reference_rate = reference["scores"]["datasets"][dataset]["normal_correct"] / reference["elapsed_wall_s"]
        ratios.append(candidate_rate / reference_rate)
    truncated = candidate["datasets"]["humaneval_plus"]["finish_counts"].get("length", 0)
    if chinese:
        introduction = "并发 4 的第三次运行（seed 20260908）出现了一个例外：**DFlash 2 输出 token 更快，但做完同一组题反而更慢。** 下表只统计正常结束且答对的回答，耗时取自这一次运行，不是三次运行的中位数。"
        conclusion = (f"DFlash 2 有 {truncated} 份代码回答达到输出上限。用“正常结束且答对数 ÷ 整组耗时”衡量正确答案的交付速度，"
                      f"DFlash 2 与 MTP7 的比值为：代码 **{ratios[0]:.4f}**，数学 **{ratios[1]:.4f}**。"
                      "两者都小于 1。这说明 token 吞吐优势不能直接当成正确答案的交付优势；这次差异的原因尚未定位。")
    else:
        introduction = "**Observed counterexample: concurrency 4, seed 20260908. This table uses that individual run, not the three-run medians above.**"
        conclusion = (f"DFlash 2 has {truncated} length-stopped code responses. Using each dataset's `normal_correct / entire group wall time`, "
                      f"the DFlash/MTP normal-correct answer-rate ratios are **{ratios[0]:.4f} for code** and **{ratios[1]:.4f} for math**. "
                      "Both are below 1 despite the higher DFlash token rate in this run. This is not a causal diagnosis or evidence that every performance metric improved.")
    return introduction + "\n\n" + markdown_table(headers, rows) + "\n\n" + conclusion


def generated_block(text, key, body, *, refresh):
    start, end = f"<!-- BEGIN {key} -->", f"<!-- END {key} -->"
    require(text.count(start) == 1 and text.count(end) == 1, "MISSING_OR_DUPLICATE_REPORT_BLOCK:" + key)
    before, rest = text.split(start)
    old, after = rest.split(end)
    expected = "\n" + body + "\n"
    if not refresh:
        require(old == expected, "REPORT_DATA_DRIFT:" + key)
    return before + start + expected + end + after


def published_files(root):
    return sorted(path for path in root.rglob("*") if path.is_file()
                  and not set(path.relative_to(root).parts) & IGNORED_PARTS
                  and path.suffix not in {".pyc", ".pyo"}
                  and path.relative_to(root).as_posix() not in {MANIFEST, RULES})


def file_manifest(root):
    records = {}
    for path in published_files(root):
        require(not path.is_symlink() and path.resolve().is_relative_to(root.resolve()), "PUBLISHED_SYMLINK")
        records[path.relative_to(root).as_posix()] = {"bytes": path.stat().st_size, "sha256": digest_file(path)}
    return {"files": records, "scope": "Published experiment files; generated rule results and this manifest excluded."}


def verify_manifest(root):
    saved = read_json(root / MANIFEST)
    for name in saved["files"]:
        relative = PurePosixPath(name)
        require(not relative.is_absolute() and ".." not in relative.parts and "\\" not in name and ":" not in name,
                "MANIFEST_PATH_ESCAPE")
    require(saved == file_manifest(root), "PUBLISHED_FILE_HASH_OR_SET_MISMATCH")


def verify_local_links(root):
    topic = topic_dir(root).resolve()
    experiment = f"experiments/{root.name}/"
    for filename in READMES:
        text = (topic / filename).read_text(encoding="utf-8")
        for link in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text):
            target = urlsplit(link)
            if target.scheme or link.startswith("#"):
                continue
            path = (topic / unquote(target.path)).resolve()
            require(path.is_relative_to(topic) and path.exists(), "BROKEN_LOCAL_LINK:" + target.path)
            require(path.suffix.lower() != ".md" or target.path in READMES, "NESTED_MARKDOWN_LINK:" + target.path)
        require(text.count("```") % 2 == 0, "UNPAIRED_CODE_FENCE")
        require(f"python {experiment}validate_report.py" in text, "REPLAY_ENTRY_MISSING")
        opening = text.split("\n## ", 1)[0]
        badges = re.findall(r"\[!\[[^\]]*\]\((https?://[^)]+)\)\]\([^)]+\)", opening)
        for signature in ("img.shields.io/badge/vLLM-", "img.shields.io/badge/GPU-",
                          "github.com/david-xinyuwei/david-share/actions/workflows/speculative-decoding-ci.yml/badge.svg"):
            require(any(signature in badge for badge in badges), "READER_BADGE_MISSING:" + filename)
        for marker in ("validate_report.py --refresh", "--figure ", "重新生成图片和报告", "Regenerating figures and report content",
                       "本次文档修订", "documentation revision"):
            require(marker not in text, "INTERNAL_MAINTENANCE_IN_READER_PAGE:" + filename)
        chinese = filename == "README-CN.md"
        require(("## 你能用它做什么" if chinese else "## What You Can Do With This Repository") in text, "CUSTOMER_VALUE_ENTRY_MISSING")
        flow = f"]({experiment}images/test-flow-{'cn' if chinese else 'en'}.png)"
        require(flow in text and (root / f"images/test-flow-{'cn' if chinese else 'en'}.png").is_file(), "TEST_FLOW_MISSING")
        duration_heading = "### 各阶段测试耗时" if chinese else "### Measured Duration by Stage"
        require(duration_heading in text, "STAGE_DURATION_SECTION_MISSING")
        for collapsed in re.findall(r"<details\b[^>]*>.*?</details>", text, re.S | re.I):
            require(duration_heading not in collapsed, "STAGE_DURATIONS_COLLAPSED")
    for path in topic.rglob("*.md"):
        relative = path.relative_to(topic).as_posix()
        require(relative in READMES or set(path.relative_to(topic).parts) & IGNORED_PARTS, "NESTED_MARKDOWN_FILE:" + relative)


def validate_data(root):
    saved = read_json(root / "data/groups.json")
    groups, coverage = saved["groups"], saved["coverage"]
    summary = summarize(groups, coverage)
    require(summary == read_json(root / "data/summary.json"), "SAVED_SUMMARY_MISMATCH")
    run = read_json(root / "evidence/run.json")
    require(not {"timing", "closure", "runway"}.intersection(run), "INTERNAL_OPERATIONS_IN_PUBLIC_EVIDENCE")
    config = read_json(root / "evidence/configuration.json")
    require(run["run_id"] == coverage["run_id"] == config["run_id"], "RUN_ID_MISMATCH")
    terminal = run["terminal"]
    require(terminal["run_id"] == run["run_id"], "TERMINAL_ID_MISMATCH")
    for field, target in (("completed", "completed_responses"), ("total", "planned_responses"),
                          ("groups_completed", "completed_groups"), ("groups_total", "planned_groups"),
                          ("phase", "campaign_phase"), ("error", "reason"), ("remaining_groups", "remaining_groups")):
        require(terminal[field] == coverage[target], "TERMINAL_COVERAGE_MISMATCH:" + field)
    require(len(groups) == coverage["completed_groups"], "GROUP_COUNT_MISMATCH")
    require(len(groups) + len(coverage["remaining_groups"]) == coverage["planned_groups"], "PLANNED_GROUP_COUNT_MISMATCH")
    full_tasks = sum(dataset["tasks"] for dataset in config["quality"]["datasets"])
    full_planned = full_tasks * len(config["routes"]) * len(config["quality"]["primary_concurrency_levels"])
    require(coverage["completed_responses"] + full_planned == coverage["planned_responses"], "PLANNED_RESPONSE_COUNT_MISMATCH")
    for field in ("target", "draft", "sampling"):
        require(config[field] == coverage[field], "CONFIGURATION_DRIFT:" + field)
    for field in ("vllm_version", "vllm_commit"):
        require(config["serving"][field] == coverage[field], "ENGINE_VERSION_DRIFT")
    require(run["source_archive"]["sha256"] == coverage["archive_sha256"], "ARCHIVE_IDENTITY_MISMATCH")
    for stage, evidence in run["stages"].items():
        selected = [group for group in groups if group["stage"] == stage]
        require(evidence["completed_groups"] == len(selected), "STAGE_GROUP_COUNT_MISMATCH")
        require(evidence["completed_responses"] == sum(group["completed"] for group in selected), "STAGE_RESPONSE_COUNT_MISMATCH")
        require(math.isclose(evidence["measured_group_wall_s"], sum(group["elapsed_wall_s"] for group in selected), rel_tol=1e-12), "STAGE_DURATION_MISMATCH")
    activation = {item["group_id"]: item for item in run["activation"]}
    require(len(activation) == len(run["activation"]) == len(groups), "ACTIVATION_SET_MISMATCH")
    for group in groups:
        observation = activation[group["group_id"]]
        require(observation["route"] == group["route"] and observation["status"] == "OBSERVED"
                and observation["engine_status"] == "RECONCILED", "ACTIVATION_NOT_OBSERVED")
        require("v2_runner" in observation["observed_checks"], "RUNNER_NOT_OBSERVED")
        require(observation["cold_start_contamination"] is False, "COLD_START_CONTAMINATION")
        require(run["source_members"][group["source"]["member"]]["sha256"] == group["source"]["sha256"], "GROUP_PROVENANCE_MISMATCH")
    for path in sorted((root / "source").glob("*.py")):
        require(digest_file(path) == run["source_members"]["src/" + path.name]["sha256"], "EXECUTED_SOURCE_CHANGED")
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    by_id = {group["group_id"]: group for group in groups}
    requests = read_json(root / "evidence/request-examples.json")
    require({sample["dataset"] for sample in requests} == {dataset["name"] for dataset in config["quality"]["datasets"]}, "REQUEST_EXAMPLE_COVERAGE")
    for sample in requests:
        raw = (json.dumps(sample["request"], ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
        require(hashlib.sha256(raw).hexdigest() == sample["request_sha256"], "REQUEST_HASH_MISMATCH")
        require(sample["task_id"] in by_id[sample["group_id"]]["ordered_task_ids"], "REQUEST_TASK_MISMATCH")
        require(sample["request"]["model"] == config["target"]["model_id"], "REQUEST_MODEL_MISMATCH")
    return groups, summary, run


def validate(root=ROOT, *, refresh=False):
    root = root.resolve()
    groups, summary, run = validate_data(root)
    for filename, chinese in (("README.md", False), ("README-CN.md", True)):
        path = topic_dir(root) / filename
        text = path.read_text(encoding="utf-8")
        for name, value in (("RESULT_TABLE", result_table(summary, chinese)),
                            ("LATENCY_TABLE", latency_table(groups, summary, chinese)),
                            ("COUNTEREXAMPLE", counterexample(groups, chinese))):
            text = generated_block(text, name, value, refresh=refresh)
        if refresh:
            path.write_text(text, encoding="utf-8")
    verify_local_links(root)
    if refresh:
        dump_json(root / MANIFEST, file_manifest(root))
    verify_manifest(root)
    records = [
        {"id": name, "status": "PASS", "evidence": evidence}
        for name, evidence in (
            ("recorded-group-score-and-token-reconciliation", ["data/groups.json", "data/summary.json"]),
            ("run-id-measurement-duration-and-coverage", ["evidence/run.json", "data/groups.json"]),
            ("actual-request-and-executed-source-hashes", ["evidence/request-examples.json", "source/"]),
            ("generated-bilingual-result-tables", ["../../README.md", "../../README-CN.md"]),
            ("local-links-and-reader-entry", ["../../README.md", "../../README-CN.md"]),
            ("single-readme-layout-and-maintenance-boundary", ["../../README.md", "../../README-CN.md"]),
            ("published-file-integrity", [MANIFEST]),
        )
    ]
    result = {"scope": "Offline report verification; not fresh GPU execution, regrading or precision noninferiority.",
              "checks": records, "manifest_sha256": digest_file(root / MANIFEST)}
    if refresh:
        dump_json(root / RULES, result)
    require(read_json(root / RULES) == result, "VALIDATION_RECORD_DRIFT")
    for record in records:
        print("RULE", record["id"], record["status"])
    print("REPORT_GATE=PASS", "groups=" + str(len(groups)), "responses=" + str(summary["coverage"]["completed_responses"]))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Regenerate result tables and file manifest after reviewing an edit")
    args = parser.parse_args()
    validate(refresh=args.refresh)


if __name__ == "__main__":
    main()
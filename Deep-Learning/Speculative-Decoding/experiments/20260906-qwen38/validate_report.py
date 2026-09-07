"""Validate the saved experiment, generated report blocks and published hashes."""

import argparse
from datetime import datetime
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


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def markdown_table(headers, rows):
    return "\n".join("| " + " | ".join(map(str, row)) + " |" for row in
                     [headers, ["---"] * len(headers), *rows])


def result_table(summary, chinese):
    headers = (["路线 / 并发", "tok/s 中位数", "组耗时中位数（秒）", "代码 raw /32", "代码 normal /32",
                "数学 raw /32", "数学 normal /32", "代码截断", "数学截断"] if chinese else
               ["Route / concurrency", "Median tok/s", "Median group wall (s)", "Code raw /32", "Code normal /32",
                "Math raw /32", "Math normal /32", "Code length", "Math length"])
    rows = []
    for group in summary["matched_summary"]:
        code, maths = (group["datasets"][name] for name in ("humaneval_plus", "math_500"))
        values = [f"{group['route']} / {group['concurrency']}", f"{group['throughput_tok_s']['median']:.2f}",
                  f"{group['group_wall_s']['median']:.2f}"]
        values.extend(", ".join(map(str, value)) for value in
                      (code["raw_correct"], code["normal_correct"], maths["raw_correct"],
                       maths["normal_correct"], code["length_stopped"], maths["length_stopped"]))
        rows.append(values)
    return markdown_table(headers, rows)


def latency_table(groups, summary, chinese):
    headers = (["路线 / 并发", "TTFT（ms）", "TPOT（ms/token）", "E2E（秒）", "TTFT 有效 / 缺失", "TPOT 有效 / 缺失", "E2E 有效 / 缺失"] if chinese else
               ["Route / concurrency", "TTFT (ms)", "TPOT (ms/token)", "E2E (s)", "TTFT valid / missing", "TPOT valid / missing", "E2E valid / missing"])
    rows = []
    by_id = {group["group_id"]: group for group in groups}
    for cell in summary["matched_summary"]:
        clients = [by_id[name]["client"]["all"] for name in cell["source_groups"]]
        metrics = ("ttft_token_s", "tpot_s", "e2e_s")
        values = [f"{cell['route']} / {cell['concurrency']}"]
        for metric, scale in zip(metrics, (1000, 1000, 1)):
            values.append(f"{median(client[metric]['p50'] for client in clients) * scale:.3f}")
        for metric in metrics:
            valid = sum(client[metric]["valid_count"] for client in clients)
            missing = sum(client[metric]["missing_count"] for client in clients)
            values.append(f"{valid} / {missing}")
        rows.append(values)
    return markdown_table(headers, rows)


def run_log(run):
    timing, terminal, closure = (run[key] for key in ("timing", "terminal", "closure"))
    return "\n".join((
        "```text",
        f"last_invocation_start_utc={timing['last_invocation_start_utc']} run_id={run['run_id']}",
        f"last_invocation_end_utc={timing['last_invocation_end_utc']} phase={terminal['phase']} completed={terminal['completed']} total={terminal['total']}",
        f"evidence_verified_utc={closure['evidence_verified_utc']} evidence_verified={str(closure['evidence_verified']).lower()}",
        f"power_verified_utc={closure['power_verified_utc']} power_decision={closure['power_decision']}",
        "```",
    ))


def counterexample(groups, chinese):
    selected = {group["route"]: group for group in groups if group["stage"] == "S"
                and group["concurrency"] == 4 and group["base_seed"] == 20260908}
    candidate, reference = selected["dflash2_7"], selected["mtp7"]
    headers = (["路线", "该次整组耗时（秒）", "正常答对代码 /32", "正常答对数学 /32"] if chinese else
               ["Route", "This run's group wall (s)", "Normal-correct code /32", "Normal-correct math /32"])
    rows = [[group["route"], f"{group['elapsed_wall_s']:.6f}",
             group["scores"]["datasets"]["humaneval_plus"]["normal_correct"],
             group["scores"]["datasets"]["math_500"]["normal_correct"]] for group in (reference, candidate)]
    ratios = []
    for dataset in ("humaneval_plus", "math_500"):
        candidate_rate = candidate["scores"]["datasets"][dataset]["normal_correct"] / candidate["elapsed_wall_s"]
        reference_rate = reference["scores"]["datasets"][dataset]["normal_correct"] / reference["elapsed_wall_s"]
        ratios.append(candidate_rate / reference_rate)
    truncated = candidate["datasets"]["humaneval_plus"]["finish_counts"].get("length", 0)
    if chinese:
        introduction = "**已测反例：并发 4、seed 20260908。下表只取这一次运行，不使用上方三次运行的中位数。**"
        conclusion = (f"DFlash 2 有 {truncated} 份代码回答因长度上限停止。按各数据集的 `normal_correct / 整组耗时` 计算，"
                      f"DFlash/MTP 的正常正确答案每秒速率比为：代码 **{ratios[0]:.4f}**，数学 **{ratios[1]:.4f}**。"
                      "这两个比率低于 1，尽管该次 DFlash 的 token 速率更高；不能据此作根因诊断或宣称所有性能指标都更好。")
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
    boundary = root.parent.parent.resolve()
    for filename in ("README.md", "README-CN.md"):
        text = (root / filename).read_text(encoding="utf-8")
        for link in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text):
            target = urlsplit(link)
            if target.scheme or link.startswith("#"):
                continue
            path = (root / unquote(target.path)).resolve()
            require(path.is_relative_to(boundary) and path.exists(), "BROKEN_LOCAL_LINK:" + target.path)
        require(text.count("```") % 2 == 0, "UNPAIRED_CODE_FENCE")
        parent_text = (boundary / filename).read_text(encoding="utf-8")
        require(f"experiments/{root.name}/{filename}" in parent_text, "PARENT_REPORT_ENTRY_MISSING")
        require(f"python experiments/{root.name}/validate_report.py" in parent_text, "PARENT_REPLAY_ENTRY_MISSING")


def validate_data(root):
    saved = read_json(root / "data/groups.json")
    groups, coverage = saved["groups"], saved["coverage"]
    summary = summarize(groups, coverage)
    require(summary == read_json(root / "data/summary.json"), "SAVED_SUMMARY_MISMATCH")
    run = read_json(root / "evidence/run.json")
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
    timing, closure = run["timing"], run["closure"]
    start = datetime.fromisoformat(timing["last_invocation_start_utc"])
    end = datetime.fromisoformat(timing["last_invocation_end_utc"])
    require(math.isclose((end - start).total_seconds(), timing["last_invocation_elapsed_s"], rel_tol=1e-12), "INVOCATION_DURATION_MISMATCH")
    require(end <= datetime.fromisoformat(closure["evidence_verified_utc"]) <= datetime.fromisoformat(closure["power_verified_utc"]), "CLOSURE_ORDER_MISMATCH")
    require(closure["evidence_verified"] is True and closure["power_decision"] == "STOPPED", "CLOSURE_NOT_VERIFIED")
    events = [json.loads(line) for line in (root / "evidence/events.jsonl").read_text(encoding="utf-8").splitlines()]
    require(all(event["run_id"] == run["run_id"] for event in events), "EVENT_RUN_MISMATCH")
    require(any(event["event"] == "CAMPAIGN_START" and event["updated_utc"] == timing["last_invocation_start_utc"] for event in events), "START_EVENT_MISSING")
    require(any(event["updated_utc"] == terminal["updated_utc"] and event["phase"] == terminal["phase"]
                and event["completed"] == terminal["completed"] for event in events), "TERMINAL_EVENT_MISSING")
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


def draw_timeline(root, run):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as pyplot

    figure, axis = pyplot.subplots(figsize=(15, 7.6), dpi=100)
    axis.set_position([0, 0, 1, 1])
    axis.set_xlim(0, 15)
    axis.set_ylim(0, 7.6)
    axis.axis("off")
    events = [
        ("Final invocation", run["timing"]["last_invocation_start_utc"], "Starts; earlier groups retained"),
        ("Admission check", run["timing"]["last_invocation_end_utc"], f"{run['terminal']['phase']}: full stage not started"),
        ("Evidence returned", run["closure"]["evidence_verified_utc"], "Local archive hashes verified"),
        ("GPU released", run["closure"]["power_verified_utc"], "Deallocation read back; disks retained"),
    ]
    positions = (1.9, 5.6, 9.35, 13.05)
    colors = ("#2773B4", "#B47516", "#16836F", "#16836F")
    axis.text(7.5, 6.95, "Qwen3.8 run: measured work, bounded stop, verified return", ha="center", fontsize=22, weight="bold")
    axis.text(7.5, 6.35, run["run_id"] + " | 2026-09-06 UTC | Event order shown; spacing is not elapsed time", ha="center", fontsize=12, color="#46525A")
    axis.plot(positions, [4.85] * len(positions), color="#BDC8CD", linewidth=3, zorder=1)
    for position, color, (label, timestamp, state) in zip(positions, colors, events):
        axis.scatter([position], [4.85], s=160, color=color, zorder=2)
        axis.text(position, 5.35, label, ha="center", fontsize=14, weight="bold", color=color)
        axis.text(position, 4.32, datetime.fromisoformat(timestamp).strftime("%H:%M:%S"), ha="center", fontsize=17)
        axis.text(position, 3.83, state, ha="center", fontsize=10)
    terminal = run["terminal"]
    axis.text(7.5, 2.75, f"C/G/S: {terminal['groups_completed']} completed groups, {terminal['completed']} responses | F: NOT_RUN", ha="center", fontsize=16, weight="bold")
    examples = read_json(root / "evidence/request-examples.json")
    axis.text(7.5, 2.08, "Actual request examples: " + " + ".join(sample["task_id"] for sample in examples), ha="center", fontsize=13)
    request = examples[0]["request"]
    axis.text(7.5, 1.55, f"reasoning_effort={request['reasoning_effort']} | max_completion_tokens={request['max_completion_tokens']} | complete payloads: evidence/request-examples.json", ha="center", fontsize=11)
    axis.text(7.5, 0.78, "Source: evidence/run.json and evidence/events.jsonl | Original explanatory diagram from recorded events", ha="center", fontsize=11, color="#46525A")
    axis.text(7.5, 0.33, "Final invocation includes restored groups and overhead; this is not the total GPU allocation duration.", ha="center", fontsize=11, color="#46525A")
    figure.savefig(root / "images/run-timeline.png", facecolor="white")
    pyplot.close(figure)


def validate(root=ROOT, *, refresh=False, timeline=False):
    root = root.resolve()
    groups, summary, run = validate_data(root)
    if timeline:
        require(refresh, "TIMELINE_REQUIRES_REFRESH")
        draw_timeline(root, run)
    for filename, chinese in (("README.md", False), ("README-CN.md", True)):
        path = root / filename
        text = path.read_text(encoding="utf-8")
        for name, value in (("RESULT_TABLE", result_table(summary, chinese)),
                            ("LATENCY_TABLE", latency_table(groups, summary, chinese)),
                            ("COUNTEREXAMPLE", counterexample(groups, chinese)),
                            ("RUN_LOG", run_log(run))):
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
            ("run-id-state-duration-and-coverage", ["evidence/run.json", "evidence/events.jsonl"]),
            ("actual-request-and-executed-source-hashes", ["evidence/request-examples.json", "source/"]),
            ("generated-bilingual-tables-and-reader-log", ["README.md", "README-CN.md"]),
            ("local-links-and-reader-entry", ["README.md", "README-CN.md"]),
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
    parser.add_argument("--refresh", action="store_true", help="Regenerate tables, reader log and file manifest after reviewing an edit")
    parser.add_argument("--timeline", action="store_true", help="With --refresh, render the recorded lifecycle PNG; requires matplotlib")
    args = parser.parse_args()
    validate(refresh=args.refresh, timeline=args.timeline)


if __name__ == "__main__":
    main()
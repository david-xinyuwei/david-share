"""Prepare immutable ACA responses for the official SWE-bench evaluation CLI."""

import argparse
import hashlib
import inspect
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path


OFFICIAL_COMMIT = "02e7a74ffd0b707aab73d203fe87bdc7c76afc8e"
DATASET = "SWE-bench/SWE-bench_Lite"


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def load_responses(run_dir):
    run_dir = Path(run_dir)
    run = read_json(run_dir / "run.json")
    if run["status"] != "COMPLETED":
        raise ValueError("Inference must be complete before grading")
    rows = {}
    source_files = []
    for path in sorted(run_dir.glob("responses_*.jsonl")):
        content = path.read_bytes()
        source_files.append({"file": path.name, "bytes": len(content), "sha256": digest(content)})
        for line in content.decode("utf-8").splitlines():
            record = json.loads(line)
            if not record["final"]:
                continue
            task = record["task_id"]
            if task in rows:
                raise ValueError(f"Duplicate final response: {task}")
            rows[task] = record
    config = run["config"]
    expected = set()
    for cell in config["cells"]:
        expected.add(f"{cell['cell_id']}|warmup")
        for problem in config["problem_ids"]:
            for repeat in range(1, config["repeats"] + 1):
                expected.add(f"{cell['cell_id']}|{problem}|r{repeat}")
    if set(rows) != expected or len(rows) != sum(run["planned"].values()):
        raise ValueError("Final response IDs do not equal the original plan")
    measured = [record for record in rows.values() if record["kind"] == "measured"]
    grouped = defaultdict(list)
    for record in measured:
        grouped[(record["cell_id"], record["repeat"])].append(record)
    for key, records in grouped.items():
        if {record["problem_id"] for record in records} != set(config["problem_ids"]):
            raise ValueError(f"Incomplete grading batch: {key}")
    expected_batches = len(config["cells"]) * config["repeats"]
    if len(grouped) != expected_batches:
        raise ValueError("Grading batch count does not match the inference plan")
    return run, measured, grouped, source_files


def audit_input(run_dir):
    run, rows, grouped, files = load_responses(run_dir)
    return {
        "status": "PASS_INPUT_AUDIT",
        "measured_responses": len(rows),
        "warmups_excluded": sum(run["planned"].values()) - len(rows),
        "batches": len(grouped),
        "instances_per_batch": len(run["config"]["problem_ids"]),
        "response_statuses": dict(Counter(record["status"] for record in rows)),
        "source_files": files,
    }


def prepare(run_dir, problems_path, output, evaluation_id):
    from datasets import load_dataset
    from huggingface_hub import HfApi
    from swebench.inference.make_datasets.utils import extract_diff

    output = Path(output)
    if output.exists():
        raise ValueError("Use a new evaluation directory; existing evidence is immutable")
    if not evaluation_id or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in evaluation_id):
        raise ValueError("Evaluation ID must contain only letters, digits, hyphens and underscores")
    run, rows, grouped, source_files = load_responses(run_dir)
    problems = read_json(problems_path)
    by_id = {item["id"]: item for item in problems["problems"]}
    if set(by_id) != set(run["config"]["problem_ids"]):
        raise ValueError("Problem manifest does not match the measured run")
    for problem in by_id.values():
        if digest(problem["user_message"].encode("utf-8")) != problem["user_message_sha256"]:
            raise ValueError(f"Prompt hash mismatch: {problem['id']}")
    revision = HfApi().dataset_info(DATASET).sha
    dataset = load_dataset(DATASET, revision=revision, split="test")
    selected = [dict(instance) for instance in dataset if instance["instance_id"] in by_id]
    if len(selected) != len(by_id):
        raise ValueError("Official dataset is missing a measured instance")
    for instance in selected:
        measured = by_id[instance["instance_id"]]
        if instance["base_commit"] != measured["base_commit"] or instance["repo"] != measured["repo"]:
            raise ValueError(f"Dataset identity mismatch: {instance['instance_id']}")
        for field in ("image", "eval_script", "patch", "test_patch", "FAIL_TO_PASS", "PASS_TO_PASS"):
            if field not in instance:
                raise ValueError(f"Official dataset lacks {field}: {instance['instance_id']}")
    output.mkdir(parents=True)
    write_json(output / "dataset.json", selected)
    tasks, batches = [], []
    for (cell, repeat), records in sorted(grouped.items()):
        label = f"{cell.replace('|', '-')}-r{repeat}"
        run_id = f"{evaluation_id}-{label}"
        prediction_path = Path("predictions") / f"{label}.jsonl"
        predictions = []
        for record in sorted(records, key=lambda item: item["problem_id"]):
            text = record.get("text") or ""
            patch = extract_diff(text)
            if patch is None:
                patch = ""
            predictions.append({"instance_id": record["problem_id"], "model_name_or_path": label, "model_patch": patch})
            tasks.append({"task_id": record["task_id"], "cell_id": cell, "repeat": repeat,
                          "instance_id": record["problem_id"], "model_name_or_path": label, "run_id": run_id,
                          "response_status": record["status"], "answer_sha256": digest(text.encode("utf-8")),
                          "patch_sha256": digest(patch.encode("utf-8")), "patch_chars": len(patch),
                          "empty_patch": not patch.strip(), "prediction_file": prediction_path.as_posix()})
        target = output / prediction_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in predictions), encoding="utf-8", newline="\n")
        batches.append({"cell_id": cell, "repeat": repeat, "run_id": run_id, "model_name_or_path": label,
                        "prediction_file": prediction_path.as_posix(), "prediction_sha256": digest(target.read_bytes()),
                        "instance_ids": [item["instance_id"] for item in predictions]})
    write_json(output / "tasks.json", tasks)
    manifest = {
        "prepared_utc": utcnow(), "status": "PREPARED_NOT_GRADED", "evaluation_id": evaluation_id,
        "denominator": len(rows), "warmups_excluded": sum(run["planned"].values()) - len(rows),
        "official_source": {"repository": "https://github.com/SWE-bench/SWE-bench", "commit": OFFICIAL_COMMIT,
                            "installed_version": version("swebench"),
                            "extractor": "swebench.inference.make_datasets.utils.extract_diff",
                            "extractor_file_sha256": digest(Path(inspect.getsourcefile(extract_diff)).read_bytes()),
                            "patch_repair_called": False},
        "dataset": {"name": DATASET, "revision": revision, "selected_instances": len(selected),
                    "file": "dataset.json", "sha256": digest((output / "dataset.json").read_bytes())},
        "source_responses": source_files,
        "source_problem_file_sha256": digest(Path(problems_path).read_bytes()),
        "source_run_file_sha256": digest((Path(run_dir) / "run.json").read_bytes()),
        "response_statuses": dict(Counter(record["status"] for record in rows)),
        "empty_patches": sum(task["empty_patch"] for task in tasks),
        "tasks_sha256": digest((output / "tasks.json").read_bytes()), "batches": batches,
    }
    write_json(output / "manifest.json", manifest)
    print(json.dumps({"status": manifest["status"], "denominator": len(rows), "batches": len(batches),
                      "empty_patches": manifest["empty_patches"], "dataset_revision": revision, "output": str(output)}))


def verify_prepared(output):
    output = Path(output)
    manifest = read_json(output / "manifest.json")
    checks = [("dataset.json", manifest["dataset"]["sha256"]), ("tasks.json", manifest["tasks_sha256"])]
    checks.extend((batch["prediction_file"], batch["prediction_sha256"]) for batch in manifest["batches"])
    for name, expected in checks:
        if digest((output / name).read_bytes()) != expected:
            raise ValueError(f"Frozen scoring input changed: {name}")
    tasks = read_json(output / "tasks.json")
    if len(tasks) != manifest["denominator"] or len({task["task_id"] for task in tasks}) != len(tasks):
        raise ValueError("Scoring task denominator mismatch")
    return manifest, tasks


def collect(output):
    output = Path(output)
    manifest, tasks = verify_prepared(output)
    results = []
    for task in tasks:
        directory = output / "logs/evaluation" / task["run_id"] / task["model_name_or_path"] / task["instance_id"]
        report = directory / "report.json"
        result = {**task, "official_resolved": None, "official_report": None}
        if task["patch_chars"] == 0:
            result["outcome"] = "EMPTY_ANSWER_TRUNCATED" if task["response_status"] == "max_tokens" else "EMPTY_PATCH"
        elif report.is_file():
            if digest((directory / "patch.diff").read_bytes()) != task["patch_sha256"]:
                raise ValueError(f"Applied patch does not match prediction: {task['task_id']}")
            native = read_json(report)[task["instance_id"]]
            if type(native.get("resolved")) is not bool:
                raise ValueError(f"Invalid official result: {report}")
            result["official_resolved"] = native["resolved"]
            result["official_report"] = report.relative_to(output).as_posix()
            result["outcome"] = "RESOLVED" if native["resolved"] else "UNRESOLVED"
        elif (directory / "run_instance.log").is_file():
            from swebench.harness.constants import APPLY_PATCH_FAIL

            log = (directory / "run_instance.log").read_text(encoding="utf-8", errors="replace")
            result["outcome"] = "PATCH_APPLY_FAILED" if APPLY_PATCH_FAIL in log else "EVALUATION_ERROR"
            result["diagnostic_log"] = (directory / "run_instance.log").relative_to(output).as_posix()
        else:
            result["outcome"] = "NOT_GRADED"
        results.append(result)
    outcomes = Counter(result["outcome"] for result in results)
    cells = []
    for cell in sorted({task["cell_id"] for task in tasks}):
        members = [result for result in results if result["cell_id"] == cell]
        cells.append({"cell_id": cell, "denominator": len(members),
                      "resolved": sum(result["official_resolved"] is True for result in members),
                      "outcomes": dict(Counter(result["outcome"] for result in members))})
    complete = not outcomes["NOT_GRADED"] and not outcomes["EVALUATION_ERROR"]
    summary = {"captured_utc": utcnow(), "evaluation_id": manifest["evaluation_id"],
               "status": "COMPLETE" if complete else "INCOMPLETE", "denominator": len(tasks),
               "resolved": outcomes["RESOLVED"], "outcomes": dict(outcomes), "cells": cells}
    write_json(output / "scored-responses.json", results)
    write_json(output / "score-summary.json", summary)
    return summary


def emit(output, event, **fields):
    record = {"utc": utcnow(), "event": event, **fields}
    text = json.dumps(record)
    with (Path(output) / "events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(text + "\n")
    print(text, flush=True)


def official_run(output, run_id, predictions, instances, workers):
    output = Path(output).resolve()
    argv = [sys.executable, "-u", "-m", "swebench.harness.run_evaluation", "--dataset_name",
            str(output / "dataset.json"), "--predictions_path", predictions, "--instance_ids", *instances,
            "--max_workers", str(workers), "--timeout", "1800", "--run_id", run_id]
    directory = output / "stage-logs"
    directory.mkdir(exist_ok=True)
    emit(output, "OFFICIAL_CLI_START", run_id=run_id, command=argv)
    with (directory / f"{run_id}.log").open("a", encoding="utf-8") as handle:
        process = subprocess.run(argv, cwd=output, stdout=handle, stderr=subprocess.STDOUT, check=False)
    emit(output, "OFFICIAL_CLI_EXIT", run_id=run_id, exit_code=process.returncode)
    if process.returncode:
        raise RuntimeError(f"Official CLI failed; read {directory / (run_id + '.log')}")


def run_batches(output, workers):
    import fcntl

    output = Path(output).resolve()
    manifest, tasks = verify_prepared(output)
    with (output / "worker.lock").open("a", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        write_json(output / "worker.json", {"pid": os.getpid(), "started_utc": utcnow(), "workers": workers,
                                           "script_sha256": digest(Path(__file__).read_bytes())})
        try:
            instances = sorted({task["instance_id"] for task in tasks})
            gold_id = manifest["evaluation_id"] + "-gold-canary"
            official_run(output, gold_id, "gold", instances, workers)
            for instance in instances:
                report = output / "logs/evaluation" / gold_id / "gold" / instance / "report.json"
                if not report.is_file() or read_json(report)[instance].get("resolved") is not True:
                    raise RuntimeError(f"Gold environment control failed: {instance}; model scoring not started")
            emit(output, "GOLD_CONTROLS_PASS", instances=len(instances))
            for index, batch in enumerate(manifest["batches"], 1):
                official_run(output, batch["run_id"], str(output / batch["prediction_file"]),
                             batch["instance_ids"], workers)
                summary = collect(output)
                emit(output, "BATCH_GRADED", batch=index, batches=len(manifest["batches"]),
                     cell=batch["cell_id"], repeat=batch["repeat"], resolved=summary["resolved"],
                     outcomes=summary["outcomes"])
                if summary["outcomes"].get("EVALUATION_ERROR", 0):
                    raise RuntimeError("Evaluation error detected; inspect the original instance logs before resuming")
            summary = collect(output)
            if summary["status"] != "COMPLETE":
                raise RuntimeError("Scoring finished without a terminal outcome for every answer")
            write_json(output / "driver-state.json", {"status": "COMPLETED", "updated_utc": utcnow(),
                                                      "denominator": summary["denominator"], "resolved": summary["resolved"]})
            emit(output, "COMPLETED", denominator=summary["denominator"], resolved=summary["resolved"])
        except BaseException as error:
            write_json(output / "driver-state.json", {"status": "BLOCKED", "updated_utc": utcnow(),
                                                      "error_type": type(error).__name__, "error": str(error)})
            emit(output, "BLOCKED", error_type=type(error).__name__, error=str(error))
            raise


def launch(output, workers):
    output = Path(output).resolve()
    verify_prepared(output)
    with (output / "driver.log").open("a", encoding="utf-8") as handle:
        process = subprocess.Popen([sys.executable, "-u", str(Path(__file__).resolve()), "run", "--out", str(output),
                                    "--workers", str(workers)], stdin=subprocess.DEVNULL, stdout=handle,
                                   stderr=subprocess.STDOUT, start_new_session=True)
    print(json.dumps({"status": "LAUNCHED_NOT_VERIFIED", "pid": process.pid, "output": str(output)}))


def local_path(path):
    value = os.path.abspath(path)
    if os.name == "nt" and not value.startswith("\\\\?\\"):
        if value.startswith("\\\\"):
            value = "UNC\\" + value[2:]
        value = "\\\\?\\" + value
    return Path(value)


def check_public(output, inference_dir=None):
    output = local_path(output)
    manifest, tasks = verify_prepared(output)
    export_manifest = output / "_export_manifest.json"
    if export_manifest.is_file():
        for item in read_json(export_manifest)["files"]:
            if digest((output / item["file"]).read_bytes()) != item["sha256"]:
                raise ValueError(f"Public evidence hash mismatch: {item['file']}")
    scored = read_json(output / "scored-responses.json")
    summary = read_json(output / "score-summary.json")
    indexed = {row["task_id"]: row for row in scored}
    if len(indexed) != len(tasks) or set(indexed) != {task["task_id"] for task in tasks}:
        raise ValueError("Published scoring task set differs from the frozen inputs")
    if inference_dir:
        answers = {}
        for path in local_path(inference_dir).glob("responses_*.jsonl"):
            for line in path.read_text(encoding="utf-8").splitlines():
                record = json.loads(line)
                if record["final"] and record["kind"] == "measured":
                    answers[record["task_id"]] = record["text_sha256"]
        if set(answers) != set(indexed):
            raise ValueError("Inference and grading populations differ")
        if any(answers[task["task_id"]] != task["answer_sha256"] for task in tasks):
            raise ValueError("Graded answer differs from the captured inference answer")
    flags = []
    for batch in manifest["batches"]:
        native = read_json(output / "logs/evaluation" / batch["run_id"] / "results.json")
        if set(native["submitted_ids"]) != set(batch["instance_ids"]):
            raise ValueError("Official batch did not receive the intended instances")
        if native["infra_failure_instances"]:
            raise ValueError("Official infrastructure failures remain unresolved")
        for instance in native["ambiguous_failure_ids"]:
            flags.append({"run_id": batch["run_id"], "instance_id": instance,
                          "official_reason": native["failure_reasons"][instance]})
        categories = {"RESOLVED": "resolved_ids", "UNRESOLVED": "unresolved_ids",
                      "PATCH_APPLY_FAILED": "error_ids", "EMPTY_PATCH": "empty_patch_ids",
                      "EMPTY_ANSWER_TRUNCATED": "empty_patch_ids"}
        for task in (item for item in tasks if item["run_id"] == batch["run_id"]):
            result = indexed[task["task_id"]]
            category = categories.get(result["outcome"])
            if category is None or task["instance_id"] not in native[category]:
                raise ValueError(f"Official outcome mismatch: {task['task_id']}")
            if result["official_report"]:
                report = read_json(output / result["official_report"])[task["instance_id"]]
                if report["resolved"] is not result["official_resolved"]:
                    raise ValueError("Per-instance official resolved flag differs")
                patch_path = (output / result["official_report"]).with_name("patch.diff")
                if digest(patch_path.read_bytes()) != task["patch_sha256"]:
                    raise ValueError("Applied patch differs from the frozen prediction")
    outcomes = dict(Counter(row["outcome"] for row in scored))
    resolved = sum(row["official_resolved"] is True for row in scored)
    if summary["outcomes"] != outcomes or summary["resolved"] != resolved or summary["denominator"] != len(tasks):
        raise ValueError("Published scoring summary differs from official records")
    for cell in summary["cells"]:
        members = [row for row in scored if row["cell_id"] == cell["cell_id"]]
        if cell["denominator"] != len(members) or cell["resolved"] != sum(row["official_resolved"] is True for row in members):
            raise ValueError("Per-cell score differs from official records")
    gold = read_json(output / "logs/evaluation" / (manifest["evaluation_id"] + "-gold-canary") / "results.json")
    if gold["resolved_instances"] != manifest["dataset"]["selected_instances"]:
        raise ValueError("Not all selected official gold controls passed")
    review_path = output / "ambiguous-review.json"
    if review_path.is_file():
        reviews = read_json(review_path)
        if {(item["run_id"], item["instance_id"]) for item in reviews} != {(item["run_id"], item["instance_id"]) for item in flags}:
            raise ValueError("Ambiguity review does not cover the official flags")
        for item in reviews:
            if digest((output / item["source"]).read_bytes()) != item["sha256"]:
                raise ValueError("Ambiguity review source changed")
    environment_path = output / "environment.json"
    if environment_path.is_file():
        environment = read_json(environment_path)
        required_images = {item["image"] for item in read_json(output / "dataset.json")}
        recorded_images = {tag for item in environment["images"] for tag in item["RepoTags"]}
        if not required_images.issubset(recorded_images) or any(not item["RepoDigests"] for item in environment["images"]):
            raise ValueError("Scoring image inventory is incomplete")
    return {"status": "PASS", "denominator": len(tasks), "resolved": resolved,
            "batches": len(manifest["batches"]), "gold_controls": gold["resolved_instances"],
            "official_ambiguous_flags": flags, "outcomes": outcomes}


def export_public(output, destination):
    output, destination = local_path(output), local_path(destination)
    result = check_public(output)
    if destination.exists():
        raise ValueError("Public scoring destination already exists")
    names = {Path(name) for name in ("manifest.json", "tasks.json", "dataset.json", "score-summary.json", "scored-responses.json")}
    names.update(path.relative_to(output) for path in (output / "predictions").glob("*.jsonl"))
    names.update(path.relative_to(output) for path in (output / "logs").rglob("*")
                 if path.is_file() and path.name in {"report.json", "results.json", "patch.diff", "run_instance.log"})
    for item in result["official_ambiguous_flags"]:
        batch = next(batch for batch in read_json(output / "manifest.json")["batches"] if batch["run_id"] == item["run_id"])
        names.add(Path("logs/evaluation") / item["run_id"] / batch["model_name_or_path"] / item["instance_id"] / "test_output.txt")
    files = []
    for name in sorted(names):
        original = (output / name).read_bytes()
        public = original
        if name.suffix in {".log", ".txt"}:
            text = original.decode("utf-8")
            text = re.sub(r"/home/[^/\s\"']+", "/home/benchmark-user", text)
            public = text.encode("utf-8")
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(public)
        files.append({"file": name.as_posix(), "source_sha256": digest(original), "sha256": digest(public),
                      "bytes": len(public), "redacted_home_path": original != public})
    write_json(destination / "verification.json", result)
    write_json(destination / "_export_manifest.json", {
        "files": files, "scope": "Official reports and frozen predictions; home directory names in text logs are de-identified.",
        "omitted": ["driver process metadata", "private command-line event logs", "unflagged full test-output logs"],
        "preparation_note": "The historical preparation count includes one whitespace-only patch; official final outcomes classify it as a patch application failure.",
    })
    check_public(destination)
    print(json.dumps({"status": "PASS_EXPORT", "files": len(files), "denominator": result["denominator"],
                      "resolved": result["resolved"], "ambiguous_flags": len(result["official_ambiguous_flags"])}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit-input")
    audit.add_argument("--run-dir", required=True)
    build = commands.add_parser("prepare")
    build.add_argument("--run-dir", required=True)
    build.add_argument("--problems", required=True)
    build.add_argument("--out", required=True)
    build.add_argument("--evaluation-id", required=True)
    for name in ("collect", "run", "launch", "export", "check-public"):
        command = commands.add_parser(name)
        command.add_argument("--out", required=True)
        if name in ("run", "launch"):
            command.add_argument("--workers", type=int, default=2)
        if name == "export":
            command.add_argument("--destination", required=True)
        if name == "check-public":
            command.add_argument("--inference-dir")
    args = parser.parse_args()
    if args.command == "audit-input":
        print(json.dumps(audit_input(args.run_dir), indent=2))
    elif args.command == "prepare":
        prepare(args.run_dir, args.problems, args.out, args.evaluation_id)
    elif args.command == "collect":
        summary = collect(args.out)
        print(json.dumps({key: summary[key] for key in ("status", "denominator", "resolved", "outcomes")}))
    elif args.command == "run":
        run_batches(args.out, args.workers)
    elif args.command == "export":
        export_public(args.out, args.destination)
    elif args.command == "check-public":
        print(json.dumps(check_public(args.out, args.inference_dir), indent=2))
    else:
        launch(args.out, args.workers)


if __name__ == "__main__":
    main()
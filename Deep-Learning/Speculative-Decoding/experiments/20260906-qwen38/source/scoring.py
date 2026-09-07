"""Invoke official graders and reconcile their artifacts without judging answers."""

from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import uuid


DATASETS = ("humaneval_plus", "math_500")
DOCKER = ("sudo", "-n", "docker")


class ScoringError(ValueError):
    """A missing or invalid measurement, never a model correctness verdict."""


def _validate_records(records: list[dict]) -> None:
    if not isinstance(records, list) or not records:
        raise ScoringError("Expected a nonempty list of complete records")
    for record in records:
        if not isinstance(record, dict):
            raise ScoringError("Invalid record schema")
        if record.get("dataset") not in DATASETS:
            raise ScoringError("Unsupported dataset")
        for field in ("task_id", "content", "finish_reason", "protocol_hash"):
            if not isinstance(record.get(field), str):
                raise ScoringError("Missing or invalid required record field")
        if not record["finish_reason"] or not record["protocol_hash"]:
            raise ScoringError("Missing finish reason or protocol identity")
        if "status" in record and record["status"] != "COMPLETE":
            raise ScoringError("Incomplete response cannot be scored")
        prefix = "HumanEval" if record["dataset"] == "humaneval_plus" else "MATH-500"
        if not re.fullmatch(prefix + r"/(0|[1-9][0-9]*)", record["task_id"]):
            raise ScoringError("Task identity does not match dataset")
    if len({record["task_id"] for record in records}) != len(records):
        raise ScoringError("Duplicate task identity in scoring group")
    if len({record["protocol_hash"] for record in records}) != 1:
        raise ScoringError("Mixed protocols in scoring group")


def _validate_sanitized(records: list[dict], original: list[dict], sanitized: list[dict]) -> None:
    _validate_records(records)
    if any(record["dataset"] != "humaneval_plus" for record in records):
        raise ScoringError("Non-code record in EvalPlus scorer")
    expected = [{"task_id": record["task_id"], "solution": record["content"]} for record in records]
    if original != expected:
        raise ScoringError("EvalPlus input does not match original records")
    if any(not isinstance(row, dict) or not isinstance(row.get("task_id"), str)
           or not isinstance(row.get("solution"), str) for row in sanitized):
        raise ScoringError("Invalid official sanitizer output schema")
    expected_ids = [row["task_id"] for row in original]
    actual_ids = [row["task_id"] for row in sanitized]
    if Counter(expected_ids) != Counter(actual_ids):
        raise ScoringError("Official sanitizer changed task/sample multiset")
    if actual_ids != expected_ids:
        raise ScoringError("Official sanitizer changed sample order")


def _parse_evalplus(records: list[dict], original: list[dict], sanitized: list[dict], result: dict) -> dict:
    """Consume one official base/plus verdict per sanitized task, never pass_at_k."""
    _validate_sanitized(records, original, sanitized)
    if not isinstance(result, dict) or not isinstance(result.get("eval"), dict):
        raise ScoringError("Missing official EvalPlus per-task results")
    if set(result["eval"]) != {record["task_id"] for record in records}:
        raise ScoringError("EvalPlus task set mismatch")
    by_task = {}
    for record, sample in zip(records, sanitized):
        grades = result["eval"][record["task_id"]]
        if not isinstance(grades, list) or len(grades) != 1 or not isinstance(grades[0], dict):
            raise ScoringError("EvalPlus requires exactly one result per task")
        grade = grades[0]
        if grade.get("task_id") != record["task_id"] or grade.get("solution") != sample["solution"]:
            raise ScoringError("EvalPlus result is not bound to sanitized solution")
        if grade.get("error", "") != "":
            raise ScoringError("Official EvalPlus scorer reported an error; retain raw artifact")
        statuses = (grade.get("base_status"), grade.get("plus_status"))
        if any(status not in ("pass", "fail", "timeout") for status in statuses):
            raise ScoringError("Missing or unknown EvalPlus base/plus status")
        base_correct = statuses[0] == "pass"
        plus_correct = statuses[1] == "pass"
        by_task[record["task_id"]] = {
            "correct": base_correct and plus_correct,
            "base_correct": base_correct,
            "plus_correct": plus_correct,
            "finish_reason": record["finish_reason"],
        }
    return by_task


def _math_inputs(records: list[dict], problems: list[dict]) -> list[dict]:
    rows = []
    for record in records:
        if record["dataset"] != "math_500":
            raise ScoringError("Non-math record in math scorer")
        index = int(record["task_id"].split("/")[1])
        if index >= len(problems):
            raise ScoringError("Math task absent from frozen dataset")
        problem = problems[index]
        if not isinstance(problem, dict) or not isinstance(problem.get("answer"), str):
            raise ScoringError("Invalid math gold schema")
        if "task_id" in problem and problem["task_id"] != record["task_id"]:
            raise ScoringError("Math dataset identity mismatch")
        rows.append({
            "task_id": record["task_id"],
            "answer": record["content"] or "NO_FINAL_ANSWER",
            "gold": "$" + problem["answer"] + "$",
        })
    return rows


def _parse_math(
    records: list[dict], inputs: list[dict], outputs: list[dict], problems: list[dict]
) -> dict:
    """Bind official rows by ordinal and answer/gold; upstream emits no task_id."""
    _validate_records(records)
    if inputs != _math_inputs(records, problems):
        raise ScoringError("Math input does not match records and frozen gold")
    if len(outputs) != len(inputs):
        raise ScoringError("Math output denominator mismatch")
    required = {"original_answer", "gold_answer", "extracted_answer", "extracted_gold", "is_correct"}
    by_task = {}
    for record, source, grade in zip(records, inputs, outputs):
        if not isinstance(grade, dict) or not required.issubset(grade):
            raise ScoringError("Invalid official math output schema")
        if grade["original_answer"] != source["answer"] or grade["gold_answer"] != source["gold"]:
            raise ScoringError("Math output row does not match input answer/gold")
        if "task_id" in grade and grade["task_id"] != record["task_id"]:
            raise ScoringError("Math output task identity mismatch")
        if grade.get("error", "") != "":
            raise ScoringError("Official math scorer reported an error; retain raw artifact")
        verdict = grade["is_correct"]
        if not isinstance(verdict, str) or verdict.lower() not in ("true", "false"):
            raise ScoringError("Missing or invalid official math verdict")
        by_task[record["task_id"]] = {
            "correct": verdict.lower() == "true",
            "base_correct": None,
            "plus_correct": None,
            "finish_reason": record["finish_reason"],
        }
    return by_task


def _summarize(records: list[dict], by_task: dict) -> dict:
    _validate_records(records)
    if set(by_task) != {record["task_id"] for record in records}:
        raise ScoringError("Normalized score denominator mismatch")
    datasets = {}
    for dataset in DATASETS:
        selected = [record for record in records if record["dataset"] == dataset]
        if not selected:
            continue
        grades = [by_task[record["task_id"]] for record in selected]
        if any(type(grade.get("correct")) is not bool for grade in grades):
            raise ScoringError("Missing normalized correctness measurement")
        datasets[dataset] = {
            "raw_correct": sum(grade["correct"] for grade in grades),
            "normal_correct": sum(grade["correct"] and grade["finish_reason"] == "stop" for grade in grades),
            "denominator": len(selected),
            "finish_counts": dict(Counter(record["finish_reason"] for record in selected)),
        }
    return {"by_task": by_task, "datasets": datasets}


def _json_bytes(value) -> bytes:
    try:
        return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise ScoringError("Scoring identity must contain finite JSON values") from None


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _unique_object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ScoringError("Duplicate JSON key in scoring artifact")
        result[key] = value
    return result


def _reject_constant(value):
    raise ScoringError("Nonfinite JSON value in scoring artifact")


def _decode_json(content: bytes):
    try:
        return json.loads(content, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (ValueError, UnicodeError):
        raise ScoringError("Invalid or ambiguous JSON scoring artifact") from None


def _read_bytes(path: Path) -> bytes:
    try:
        if path.is_symlink() or not path.is_file():
            raise ScoringError(f"Required scoring file is not a regular file: {path}")
        return path.read_bytes()
    except OSError:
        raise ScoringError(f"Cannot read required scoring file: {path}") from None


def _read_json(path: Path):
    return _decode_json(_read_bytes(path))


def _decode_jsonl(content: bytes) -> list[dict]:
    rows = [_decode_json(line) for line in content.splitlines() if line.strip()]
    if any(not isinstance(row, dict) for row in rows):
        raise ScoringError("JSONL scoring rows must be objects")
    return rows


def _read_csv(path: Path) -> list[dict]:
    try:
        text = _read_bytes(path).decode("utf-8")
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        headers = reader.fieldnames
        if not headers or len(headers) != len(set(headers)):
            raise ScoringError("Missing or duplicate CSV columns")
        rows = list(reader)
        if any(None in row or any(value is None for value in row.values()) for row in rows):
            raise ScoringError("Missing or extra CSV cells")
        return rows
    except (csv.Error, UnicodeError):
        raise ScoringError("Invalid CSV scoring artifact") from None


def _write_new(path: Path, content: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(content)


def _prepare_inputs(root: Path, records: list[dict]) -> tuple[dict, dict, list[dict]]:
    prepared = {}
    source_hashes = {}
    math_problems = []

    def source(relative: str) -> bytes:
        content = _read_bytes(root / relative)
        source_hashes[relative] = _digest(content)
        return content

    code = [record for record in records if record["dataset"] == "humaneval_plus"]
    maths = [record for record in records if record["dataset"] == "math_500"]
    if code:
        problems = _decode_jsonl(source("data/humaneval_plus.jsonl"))
        if any(not isinstance(problem.get("task_id"), str) for problem in problems):
            raise ScoringError("Missing HumanEval dataset identity")
        by_task = {problem["task_id"]: problem for problem in problems}
        if len(by_task) != len(problems) or any(record["task_id"] not in by_task for record in code):
            raise ScoringError("Missing or duplicate HumanEval dataset task")
        prepared["problems.jsonl"] = b"".join(_json_bytes(by_task[record["task_id"]]) for record in code)
        prepared["samples.jsonl"] = b"".join(_json_bytes({"task_id": record["task_id"], "solution": record["content"]}) for record in code)
        prepared["mbpp-plus-v0.2.0.jsonl"] = source("upstream/mbpp-plus-v0.2.0.jsonl")
    if maths:
        math_problems = _decode_jsonl(source("data/math500.jsonl"))
        rows = _math_inputs(maths, math_problems)
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=("task_id", "answer", "gold"), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        prepared["math-input.csv"] = stream.getvalue().encode("utf-8")
        prepared["math-verify-evaluate.py"] = source("upstream/math-verify-evaluate.py")
    return prepared, source_hashes, math_problems


def _inspect_image(image: str) -> str:
    if not isinstance(image, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/@:+-]*", image):
        raise ScoringError("Invalid local scoring image reference")
    try:
        result = subprocess.run(
            [*DOCKER, "image", "inspect", "--format", "{{.Id}}", image],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ScoringError("Cannot inspect local scoring image; no image will be pulled") from None
    image_id = result.stdout.strip()
    if result.returncode or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise ScoringError("Local scoring image is unavailable or has no immutable ID")
    return image_id


def _mount(source: Path, destination: str, readonly: bool = False) -> str:
    stream = io.StringIO(newline="")
    fields = ["type=bind", "src=" + str(source.resolve()), "dst=" + destination]
    if readonly:
        fields.append("readonly")
    csv.writer(stream, lineterminator="").writerow(fields)
    return stream.getvalue()


def _input_path(work: Path, filename: str) -> Path:
    if filename in ("math-verify-evaluate.py", "mbpp-plus-v0.2.0.jsonl"):
        return work.parent / "inputs" / filename
    return work / filename


def _container_prefix(work: Path, readonly_names: tuple, image_id: str, run_id: str, name: str) -> list[str]:
    prefix = [
        *DOCKER, "run", "--rm", "--pull", "never", "--name", name,
        "--network", "none", "--read-only", "--label", "dflash.run=" + run_id,
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--pids-limit", "512",
        "--memory", "8g", "--cpus", "8", "--user", "1000:1000", "--workdir", "/work",
        "--tmpfs", "/tmp:rw,nosuid,nodev,size=2g,mode=1777",
        "--mount", _mount(work, "/work"),
    ]
    for filename in readonly_names:
        upstream = filename in ("math-verify-evaluate.py", "mbpp-plus-v0.2.0.jsonl")
        destination = ("/upstream/" if upstream else "/work/") + filename
        prefix.extend(["--mount", _mount(_input_path(work, filename), destination, readonly=True)])
    return prefix + [
        "--env", "HUMANEVAL_OVERRIDE_PATH=/work/problems.jsonl",
        "--env", "MBPP_OVERRIDE_PATH=/upstream/mbpp-plus-v0.2.0.jsonl",
        "--env", "XDG_CACHE_HOME=/tmp/cache", "--env", "HOME=/tmp",
        "--env", "PYTHONDONTWRITEBYTECODE=1", image_id,
    ]


def _remove_container(name: str, log: Path) -> None:
    try:
        result = subprocess.run(
            [*DOCKER, "rm", "--force", name], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30,
        )
        _write_new(log, result.stdout)
    except (OSError, subprocess.TimeoutExpired):
        raise ScoringError(f"Scoring failed and owned-container cleanup is unconfirmed: {log}") from None
    if result.returncode and b"No such container" not in result.stdout:
        raise ScoringError(f"Scoring failed and owned-container cleanup is unconfirmed: {log}")


def _run_container(work: Path, readonly_names: tuple, image_id: str, run_id: str,
                   argv: list[str], log: Path, timeout: int = 1800) -> None:
    name = "qwen38-scoring-" + uuid.uuid4().hex
    command = _container_prefix(work, readonly_names, image_id, run_id, name) + argv
    receipt = {"argv": command, "timeout_seconds": timeout, "returncode": None}
    try:
        with log.open("xb") as output:
            try:
                result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=output,
                                        stderr=subprocess.STDOUT, timeout=timeout)
            except (OSError, subprocess.TimeoutExpired):
                _remove_container(name, log.with_suffix(log.suffix + ".cleanup.log"))
                raise ScoringError(f"Scoring command did not complete; log={log}") from None
            except BaseException:
                _remove_container(name, log.with_suffix(log.suffix + ".cleanup.log"))
                raise
            receipt["returncode"] = result.returncode
            if result.returncode:
                _remove_container(name, log.with_suffix(log.suffix + ".cleanup.log"))
                raise ScoringError(f"Scoring command failed rc={result.returncode}; log={log}")
    finally:
        _write_new(log.with_suffix(log.suffix + ".command.json"), _json_bytes(receipt))


def _packages(records: list[dict]) -> list[str]:
    datasets = {record["dataset"] for record in records}
    return (["evalplus"] if "humaneval_plus" in datasets else []) + (
        ["math-verify", "pandas", "sympy"] if "math_500" in datasets else [])


def _validate_tool_versions(tools: dict, records: list[dict]) -> None:
    if not isinstance(tools, dict) or not isinstance(tools.get("python"), str) or not tools["python"]:
        raise ScoringError("Missing scoring Python version")
    packages = tools.get("packages")
    if not isinstance(packages, dict) or set(packages) != set(_packages(records)):
        raise ScoringError("Missing official grader package versions")
    if any(not isinstance(version, str) or not version for version in packages.values()):
        raise ScoringError("Invalid official grader package version")


def _consume(work: Path, records: list[dict], math_problems: list[dict]) -> tuple[dict, dict]:
    by_task = {}
    bindings = []
    code = [record for record in records if record["dataset"] == "humaneval_plus"]
    maths = [record for record in records if record["dataset"] == "math_500"]
    if code:
        original = _decode_jsonl(_read_bytes(work / "samples.jsonl"))
        sanitized = _decode_jsonl(_read_bytes(work / "samples-sanitized.jsonl"))
        result = _read_json(work / "evalplus-results.json")
        by_task.update(_parse_evalplus(code, original, sanitized, result))
        for index, record in enumerate(code):
            bindings.append({
                "task_id": record["task_id"], "dataset": record["dataset"], "input_row": index,
                "record_sha256": _digest(_json_bytes(record)),
                "input_row_sha256": _digest(_json_bytes(original[index])),
                "sanitized_row_sha256": _digest(_json_bytes(sanitized[index])),
                "official_row_sha256": _digest(_json_bytes(result["eval"][record["task_id"]][0])),
            })
    if maths:
        inputs = _read_csv(work / "math-input.csv")
        outputs = _read_csv(work / "math-scores.csv")
        by_task.update(_parse_math(maths, inputs, outputs, math_problems))
        for index, record in enumerate(maths):
            bindings.append({
                "task_id": record["task_id"], "dataset": record["dataset"], "input_row": index,
                "official_output_row": index, "record_sha256": _digest(_json_bytes(record)),
                "input_row_sha256": _digest(_json_bytes(inputs[index])),
                "official_row_sha256": _digest(_json_bytes(outputs[index])),
            })
    return _summarize(records, by_task), {
        "math_identity_method": "input ordinal plus exact original_answer and gold_answer; no upstream task_id",
        "rows": bindings,
    }


def _check_inputs(work: Path, prepared: dict) -> None:
    if any(_read_bytes(_input_path(work, name)) != content for name, content in prepared.items()):
        raise ScoringError("Bound scoring input or output changed during or after grading")


def _artifact_hashes(attempt: Path) -> dict:
    hashes = {}
    for path in sorted(attempt.rglob("*")):
        if path.is_symlink():
            raise ScoringError("Scoring artifact tree contains a symbolic link")
        if path.is_file():
            hashes[path.relative_to(attempt).as_posix()] = _digest(_read_bytes(path))
        elif not path.is_dir():
            raise ScoringError("Scoring artifacts contain a nonregular filesystem object")
    return hashes


def score_group(root: Path, group_dir: Path, records: list[dict], image: str, run_id: str) -> dict:
    """Score unique completed tasks through offline official CLI containers.

    Resume verifies immutable image/code/data/ordered-record identities and every
    artifact, then reparses official verdicts. Incomplete attempts are retained;
    identical inputs may retry in a new attempt directory. A stale .scoring.lock
    requires the caller to confirm no owned container remains before removal.
    This module never prints answers or forwards request credentials to graders.
    """
    _validate_records(records)
    record_bytes = _json_bytes(records)
    records = _decode_json(record_bytes)
    if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", run_id):
        raise ScoringError("Invalid scoring run identity")
    root, group_dir = Path(root).resolve(), Path(group_dir).resolve()
    prepared, sources, math_problems = _prepare_inputs(root, records)
    identity = {
        "schema_version": 1, "run_id": run_id, "records_sha256": _digest(record_bytes),
        "protocol_hash": records[0]["protocol_hash"], "image_reference": image,
        "image_id": _inspect_image(image), "scoring_py_sha256": _digest(_read_bytes(Path(__file__))),
        "source_sha256": sources,
        "prepared_sha256": {name: _digest(content) for name, content in prepared.items()},
    }
    scores = group_dir / "scores"
    scores.mkdir(parents=True, exist_ok=True)
    lock = scores / ".scoring.lock"
    try:
        lock.mkdir()
    except FileExistsError:
        raise ScoringError(f"Scoring lock exists; verify owning process before recovery: {lock}") from None
    try:
        manifest = scores / "input-binding.json"
        marker = scores / "score-summary.json"
        if manifest.exists():
            if _read_json(manifest) != identity:
                raise ScoringError("Scoring inputs or tool identity changed; previous artifacts are preserved")
        else:
            if any(path != lock for path in scores.iterdir()):
                raise ScoringError("Existing scoring artifacts have no verified input binding")
            _write_new(manifest, _json_bytes(identity))
        if marker.exists():
            previous = _read_json(marker)
            if (not isinstance(previous, dict) or previous.get("identity") != identity
                    or previous.get("input_sha256") != identity["records_sha256"]):
                raise ScoringError("Cached scoring identity mismatch")
            attempt_name = previous.get("attempt", "")
            if not isinstance(attempt_name, str) or not re.fullmatch(r"attempt-[0-9a-f]{32}", attempt_name):
                raise ScoringError("Invalid cached scoring artifact path")
            attempt = scores / attempt_name
            if attempt.is_symlink() or _artifact_hashes(attempt) != previous.get("artifacts"):
                raise ScoringError("Cached official scoring artifacts changed or are missing")
            _check_inputs(attempt / "work", prepared)
            tools = _read_json(attempt / "tool-versions.json")
            _validate_tool_versions(tools, records)
            normalized, bindings = _consume(attempt / "work", records, math_problems)
            if (tools != previous.get("tool_versions") or _read_json(attempt / "bindings.json") != bindings
                    or any(previous.get(key) != value for key, value in normalized.items())):
                raise ScoringError("Cached scores do not reconcile with official artifacts")
            return {**previous, "scores_dir": str(scores)}

        attempt = scores / ("attempt-" + uuid.uuid4().hex)
        attempt.mkdir()
        work = attempt / "work"
        work.mkdir()
        work.chmod(0o777)
        (attempt / "inputs").mkdir()
        for name, content in prepared.items():
            path = _input_path(work, name)
            _write_new(path, content)
            path.chmod(0o644)
        readonly_names = tuple(prepared)
        image_id = identity["image_id"]
        version_code = (
            "import importlib.metadata as metadata, json, platform; "
            "print(json.dumps({'python': platform.python_version(), 'packages': "
            "{name: metadata.version(name) for name in " + repr(_packages(records)) + "}}))"
        )
        _run_container(work, readonly_names, image_id, run_id, ["python", "-c", version_code],
                       attempt / "tool-versions.json", timeout=60)
        tools = _read_json(attempt / "tool-versions.json")
        _validate_tool_versions(tools, records)
        code = [record for record in records if record["dataset"] == "humaneval_plus"]
        frozen_outputs = {}
        if code:
            _run_container(work, readonly_names, image_id, run_id,
                           ["evalplus.sanitize", "--samples", "/work/samples.jsonl"], attempt / "sanitize.log")
            original = _decode_jsonl(_read_bytes(work / "samples.jsonl"))
            frozen_outputs["samples-sanitized.jsonl"] = _read_bytes(work / "samples-sanitized.jsonl")
            sanitized = _decode_jsonl(frozen_outputs["samples-sanitized.jsonl"])
            _validate_sanitized(code, original, sanitized)
            _run_container(work, readonly_names + ("samples-sanitized.jsonl",), image_id, run_id,
                           ["evalplus.evaluate", "--dataset", "humaneval", "--samples", "/work/samples-sanitized.jsonl",
                            "--parallel", "4", "--output-file", "/work/evalplus-results.json"], attempt / "evalplus.log")
            frozen_outputs["evalplus-results.json"] = _read_bytes(work / "evalplus-results.json")
            _check_inputs(work, {**prepared, **frozen_outputs})
            _parse_evalplus(code, original, sanitized, _decode_json(frozen_outputs["evalplus-results.json"]))
        if any(record["dataset"] == "math_500" for record in records):
            _run_container(work, readonly_names + tuple(frozen_outputs), image_id, run_id,
                           ["python", "/upstream/math-verify-evaluate.py", "--input_csv", "/work/math-input.csv",
                            "--output_csv", "/work/math-scores.csv"], attempt / "math-verify.log")
        _check_inputs(work, {**prepared, **frozen_outputs})
        normalized, bindings = _consume(work, records, math_problems)
        _write_new(attempt / "bindings.json", _json_bytes(bindings))
        summary = {
            **normalized, "input_sha256": identity["records_sha256"], "identity": identity,
            "tool_versions": tools, "attempt": attempt.name, "scores_dir": str(scores),
            "artifacts": _artifact_hashes(attempt),
        }
        _write_new(marker, _json_bytes(summary))
        return summary
    finally:
        lock.rmdir()
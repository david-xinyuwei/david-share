"""Score each answer by running the exercise's own unit tests offline in Docker.

Extraction follows Aider's whole-file format: a file path line, then the
complete file in a fenced block. Test files always come from the pristine
exercise; only solution files are replaced. A run passes when the test
command exits 0 (Aider's pass_rate_1 rule, first attempt only).
"""
import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

IMAGE = os.environ.get("JUDGE_IMAGE", "polyglot-judge:1")
POLYGLOT = Path(os.environ.get("POLYGLOT_DIR", Path.home() / "polyglot-benchmark"))
TIMEOUT_S = 180  # Aider run_unit_tests timeout
COMMANDS = {
    "python": "pytest -q -p no:cacheprovider",
    "rust": "cargo test --offline -q -- --include-ignored",
    "go": "GOFLAGS=-mod=mod GOPROXY=off GOCACHE=/tmp/gocache go test ./...",
    "javascript": "/judge/npm-test.sh",
    "cpp": "/judge/cpp-test.sh",
    "java": "./gradlew test --offline --no-daemon -q",
}
OPEN_FENCE = re.compile(r"^\s*```[\w+#.\-]*\s*$")
CLOSE_FENCE = re.compile(r"^\s*```\s*$")
TERMINAL = {"COMPLETED", "BUDGET_STOP", "FAILED", "STOPPED"}


def clean_name(line):
    name = line.strip().lstrip("#").strip().strip("*`").strip()
    name = re.sub(r"^(file|filename|path)\s*:\s*", "", name, flags=re.IGNORECASE)
    return name.rstrip(":").strip().strip("`*").strip()


def extract_files(text, solution_files):
    lines = (text or "").split("\n")
    blocks, index = [], 0
    while index < len(lines):
        if OPEN_FENCE.match(lines[index]):
            previous = index - 1
            while previous >= 0 and not lines[previous].strip():
                previous -= 1
            name = clean_name(lines[previous]) if previous >= 0 else ""
            end = index + 1
            while end < len(lines) and not CLOSE_FENCE.match(lines[end]):
                end += 1
            blocks.append((name, "\n".join(lines[index + 1:end]) + "\n", end < len(lines)))
            index = end + 1
            continue
        index += 1
    by_base = {Path(path).name: path for path in solution_files}
    found, unnamed = {}, []
    for name, content, closed in blocks:
        if name in solution_files:
            found[name] = content
        elif Path(name).name in by_base and name:
            found[by_base[Path(name).name]] = content
        else:
            unnamed.append(content)
    if not found and len(solution_files) == 1 and len(unnamed) == 1:
        found[solution_files[0]] = unnamed[0]
    return found, {"blocks": len(blocks), "unclosed": sum(1 for b in blocks if not b[2]),
                   "files_found": sorted(found), "missing": sorted(set(solution_files) - set(found))}


def run_tests(problem, files, image=IMAGE):
    """Copy the pristine exercise, write `files` over its solution files and run its tests."""
    root = Path("/tmp/judge")
    root.mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="j-", dir=root))
    # Exercism CMakeLists derive the target name from the directory name.
    exercise = work / problem["name"]
    shutil.copytree(POLYGLOT / problem["path"], exercise)
    for relative, content in files.items():
        target = exercise / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    for relative in problem["test_files"]:
        if relative.endswith(".java"):
            path = exercise / relative
            path.write_text(re.sub(r"@Disabled\([^)]*\)\s*\n", "", path.read_text(encoding="utf-8")), encoding="utf-8")
    name = "judge-" + uuid.uuid4().hex[:12]
    inside = f"/work/{problem['name']}"
    inner = (f"timeout {TIMEOUT_S} bash -c {shlex.quote(COMMANDS[problem['language']])}; rc=$?; "
             f"chown -R {os.getuid()}:{os.getgid()} {inside}; exit $rc")
    command = ["docker", "run", "--rm", "--name", name, "--network", "none", "--cpus", "1.5",
               "--memory", "3g", "--pids-limit", "512", "-v", f"{exercise}:{inside}", "-w", inside,
               image, "bash", "-c", inner]
    started = time.time()
    try:
        process = subprocess.run(command, capture_output=True, text=True, timeout=TIMEOUT_S + 90,
                                 encoding="utf-8", errors="replace")
        returncode, output = process.returncode, process.stdout + process.stderr
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        returncode, output = 124, "judge wall-clock timeout"
    duration = round(time.time() - started, 2)
    shutil.rmtree(work, ignore_errors=True)
    return {"passed": returncode == 0, "returncode": returncode, "timed_out": returncode == 124,
            "duration_s": duration, "output_tail": output[-3000:]}


def is_final(record):
    """A throttled (429) attempt is re-sent by the runner; only the final attempt is scored."""
    return record.get("final", record.get("http_status") != 429)


def attempt_key(row):
    return f"{row['task_id']}#{row.get('attempt', 1)}"


def judge_record(problem, record):
    found, extraction = extract_files(record.get("text"), problem["solution_files"])
    row = {key: record.get(key) for key in ("task_id", "attempt", "model", "cell_id", "mode", "effort",
                                            "problem_id", "language", "repeat")}
    row["response_status"] = record.get("status")
    row["extraction"] = extraction
    if not found:
        row.update({"passed": False, "returncode": None, "timed_out": False, "duration_s": 0.0,
                    "output_tail": "", "verdict": "no_code"})
    else:
        result = run_tests(problem, found)
        row.update(result)
        row["verdict"] = "pass" if result["passed"] else ("test_timeout" if result["timed_out"] else "fail")
    row["judged_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return row


def read_jsonl(path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # a line still being written; picked up on the next pass
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--problems", required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--watch", action="store_true")
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    problems = {p["id"]: p for p in json.loads(Path(args.problems).read_text(encoding="utf-8"))["problems"]}
    judged_path = run_dir / "judged.jsonl"
    lock = threading.Lock()
    while True:
        done = {attempt_key(row) for row in read_jsonl(judged_path)}
        pending = [r for path in sorted(run_dir.glob("responses_*.jsonl")) for r in read_jsonl(path)
                   if r.get("kind") == "measured" and is_final(r) and attempt_key(r) not in done]

        def work(record):
            row = judge_record(problems[record["problem_id"]], record)
            with lock:
                with judged_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            return row

        if pending:
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                for row in pool.map(work, pending):
                    print(row["task_id"], row["verdict"], row.get("duration_s"), flush=True)
        if not args.watch:
            break
        state_path = run_dir / "run.json"
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        if state.get("status") in TERMINAL and not pending:
            break
        time.sleep(30)


if __name__ == "__main__":
    main()

"""Author-run DFlash quality regression with public datasets and official graders."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time
import traceback
from urllib.request import Request, urlopen


ROOT = Path(os.environ.get("DFLASH_RUN_ROOT", Path(__file__).resolve().parent.parent))
CACHE = Path(os.environ.get("DFLASH_CACHE_ROOT", ROOT / "cache"))
PYTHON = CACHE / "venv/bin/python"
BASE_URL = "http://127.0.0.1:18080"
MODEL_ID = "Qwen/Qwen3.6-27B"
IMAGE = "dflash-quality-eval:20260905"
STOP = threading.Event()


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def state(phase, **fields):
    value = {"run_id": "dflash-quality-20260905", "phase": phase, "updated_utc": utcnow(), **fields}
    write_json(ROOT / "state/suite.json", value)
    print(json.dumps(value, ensure_ascii=False), flush=True)


def command(argv, log, timeout=1800):
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("ab") as output:
        output.write((json.dumps({"utc": utcnow(), "argv": [str(value) for value in argv]}) + "\n").encode())
        output.flush()
        result = subprocess.run([str(value) for value in argv], stdout=output, stderr=subprocess.STDOUT, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"Command failed rc={result.returncode}; evidence={log}")


def json_get(path):
    with urlopen(BASE_URL + path, timeout=10) as response:
        return json.load(response)


def request_payload(task, temperature=0.0, seed=20260905, streaming=False):
    payload = {
        "model": MODEL_ID,
        "messages": task["messages"],
        "temperature": temperature,
        "top_p": 1.0 if temperature == 0 else 0.9,
        "top_k": -1,
        "seed": seed,
        "max_tokens": task["max_tokens"],
        "stream": streaming,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    if streaming:
        payload["stream_options"] = {"include_usage": True}
    return payload


def run_request(task, destination, protocol_hash, temperature=0.0, seed=20260905, streaming=False):
    if destination.is_file():
        previous = json.loads(destination.read_text(encoding="utf-8"))
        if previous.get("protocol_hash") != protocol_hash or previous.get("status") != "COMPLETE":
            raise ValueError(f"Unverified existing response: {destination}")
        return previous
    payload = request_payload(task, temperature, seed, streaming)
    started = utcnow()
    begin = time.perf_counter()
    first_any = None
    first_content = None
    chunks = []
    content = []
    reasoning = []
    usage = None
    finish_reason = None
    request = Request(BASE_URL + "/v1/chat/completions", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=600) as response:
        if not streaming:
            raw = json.loads(response.read())
            message = raw["choices"][0]["message"]
            content.append(message.get("content") or "")
            reasoning.append(message.get("reasoning") or message.get("reasoning_content") or "")
            usage = raw.get("usage")
            finish_reason = raw["choices"][0].get("finish_reason")
        else:
            done = False
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                value = line[5:].strip()
                if value == "[DONE]":
                    done = True
                    break
                chunk = json.loads(value)
                chunks.append(chunk)
                if chunk.get("usage"):
                    usage = chunk["usage"]
                for choice in chunk.get("choices", []):
                    delta = choice.get("delta", {})
                    text = delta.get("content") or ""
                    thought = delta.get("reasoning") or delta.get("reasoning_content") or ""
                    if (text or thought) and first_any is None:
                        first_any = time.perf_counter() - begin
                    if text and first_content is None:
                        first_content = time.perf_counter() - begin
                    content.append(text)
                    reasoning.append(thought)
                    if choice.get("finish_reason"):
                        finish_reason = choice["finish_reason"]
            if not done:
                raise RuntimeError("Streaming response ended without [DONE]")
            raw = {"chunks": chunks}
    elapsed = time.perf_counter() - begin
    if not usage or usage.get("completion_tokens", 0) <= 0:
        raise ValueError("No authoritative completion token count")
    if not finish_reason:
        raise ValueError("Missing finish_reason")
    record = {
        "status": "COMPLETE",
        "task_id": task["task_id"],
        "dataset": task["dataset"],
        "protocol_hash": protocol_hash,
        "started_utc": started,
        "ended_utc": utcnow(),
        "request": payload,
        "response": raw,
        "content": "".join(content),
        "reasoning": "".join(reasoning),
        "finish_reason": finish_reason,
        "usage": usage,
        "total_s": elapsed,
        "ttft_any_s": first_any,
        "ttft_content_s": first_content,
        "output_tps_e2e": usage["completion_tokens"] / elapsed,
    }
    write_json(destination, record)
    return record


def safe_task_name(task):
    return task["task_id"].replace("/", "_") + ".json"


def run_group(route, label, tasks, protocol_hash, concurrency=1, repeats=1, streaming=False, temperature=0.0, seeds=None):
    directory = ROOT / "results" / route / label
    directory.mkdir(parents=True, exist_ok=True)
    records = []
    seeds = seeds or [20260905] * repeats
    started = time.perf_counter()
    for repetition in range(repeats):
        selected_seed = seeds[repetition]
        def execute(task):
            output = directory / f"repeat-{repetition}" / safe_task_name(task)
            return run_request(task, output, protocol_hash, temperature, selected_seed, streaming)
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            for completed, record in enumerate(pool.map(execute, tasks), 1):
                records.append(record)
                if completed % 10 == 0 or completed == len(tasks):
                    state("RUNNING", route=route, group=label, repetition=repetition, completed=completed, expected=len(tasks))
    elapsed = time.perf_counter() - started
    summary = {
        "route": route, "group": label, "requests": len(records), "expected": len(tasks) * repeats,
        "concurrency": concurrency, "elapsed_wall_s": elapsed,
        "finish_counts": {reason: sum(record["finish_reason"] == reason for record in records) for reason in sorted({record["finish_reason"] for record in records})},
        "empty_content": sum(not record["content"].strip() for record in records),
        "completion_tokens": sum(record["usage"]["completion_tokens"] for record in records),
    }
    if summary["requests"] != summary["expected"]:
        raise ValueError("Incomplete response denominator")
    write_json(directory / "group-summary.json", summary)
    return records


def metrics_snapshot(route, label):
    with urlopen(BASE_URL + "/metrics", timeout=15) as response:
        content = response.read()
    path = ROOT / "results" / route / f"metrics-{label}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def container_prefix(directory):
    return [
        "sudo", "-n", "docker", "run", "--rm", "--network", "none", "--read-only",
        "--label", "dflash.run=dflash-quality-20260905",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--pids-limit", "512",
        "--memory", "8g", "--cpus", "8", "--user", "1000:1000",
        "--tmpfs", "/tmp:rw,nosuid,nodev,size=2g,mode=1777",
        "--mount", f"type=bind,src={directory},dst=/work",
        "--mount", f"type=bind,src={ROOT / 'upstream'},dst=/upstream,readonly",
        "--env", "HUMANEVAL_OVERRIDE_PATH=/work/problems.jsonl",
        "--env", "MBPP_OVERRIDE_PATH=/upstream/mbpp-plus-v0.2.0.jsonl",
        "--env", "XDG_CACHE_HOME=/tmp/cache", IMAGE,
    ]


def score_records(route, label, records, code_problems, math_problems):
    directory = ROOT / "results" / route / (label + "-scores")
    directory.mkdir(parents=True, exist_ok=True)
    signature = hashlib.sha256(json.dumps([(record["task_id"],record["content"],record["finish_reason"]) for record in records], ensure_ascii=False).encode()).hexdigest()
    marker = directory / "score-summary.json"
    if marker.is_file():
        previous = json.loads(marker.read_text(encoding="utf-8"))
        if previous.get("input_sha256") == signature:
            return previous
        raise ValueError("Scoring input changed in the same output directory")
    summary = {"input_sha256": signature}
    code_records = [record for record in records if record["dataset"] == "humaneval_plus"]
    math_records = [record for record in records if record["dataset"] == "math_500"]
    if code_records:
        task_ids = list(dict.fromkeys(record["task_id"] for record in code_records))
        (directory / "problems.jsonl").write_text("".join(json.dumps(code_problems[task_id]) + "\n" for task_id in task_ids), encoding="utf-8")
        samples = [{"task_id": record["task_id"], "solution": record["content"]} for record in code_records]
        (directory / "samples.jsonl").write_text("".join(json.dumps(sample) + "\n" for sample in samples), encoding="utf-8")
        prefix = container_prefix(directory)
        command(prefix + ["evalplus.sanitize", "--samples", "/work/samples.jsonl"], directory / "sanitize.log")
        sanitized = [json.loads(line) for line in (directory / "samples-sanitized.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        if Counter(sample["task_id"] for sample in sanitized) != Counter(sample["task_id"] for sample in samples):
            raise ValueError("Official sanitizer changed the task/sample denominator")
        write_json(directory / "sanitizer-provenance.json", {
            "producer": "EvalPlus official sanitize CLI",
            "original_sha256": file_hash(directory / "samples.jsonl"),
            "sanitized_sha256": file_hash(directory / "samples-sanitized.jsonl"),
            "samples": len(samples),
            "task_multiset_preserved": True,
        })
        command(prefix + ["evalplus.evaluate", "--dataset", "humaneval", "--samples", "/work/samples-sanitized.jsonl", "--parallel", "4", "--output-file", "/work/evalplus-results.json"], directory / "evalplus.log")
        grade = json.loads((directory / "evalplus-results.json").read_text())
        if set(grade["eval"]) != set(task_ids):
            raise ValueError("EvalPlus task set mismatch")
        summary["code"] = {"tasks": len(task_ids), "samples": len(code_records), "pass_at_k": grade["pass_at_k"]}
    if math_records:
        with (directory / "math-input.csv").open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=["task_id","answer","gold"])
            writer.writeheader()
            for record in math_records:
                problem = math_problems[int(record["task_id"].split("/")[1])]
                writer.writerow({"task_id": record["task_id"], "answer": record["content"] or "NO_FINAL_ANSWER", "gold": "$" + problem["answer"] + "$"})
        command(container_prefix(directory) + ["python", "/upstream/math-verify-evaluate.py", "--input_csv", "/work/math-input.csv", "--output_csv", "/work/math-scores.csv"], directory / "math-verify.log")
        with (directory / "math-scores.csv").open(encoding="utf-8", newline="") as source:
            grades = list(csv.DictReader(source))
        if len(grades) != len(math_records):
            raise ValueError("Math-Verify row count mismatch")
        correct = sum(row["is_correct"].lower() == "true" for row in grades)
        summary["math"] = {"correct": correct, "denominator": len(math_records), "accuracy": correct / len(math_records), "scoring_errors": sum(bool(row.get("error")) for row in grades)}
    write_json(marker, summary)
    return summary


class Server:
    def __init__(self, route):
        self.route = route
        self.process = None
        self.log = None

    def __enter__(self):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1",18080)) == 0:
                raise RuntimeError("Port 18080 is already owned by another process")
        argv = [str(PYTHON), "-m", "vllm.entrypoints.openai.api_server", "--model", os.environ.get("DFLASH_TARGET_PATH", str(CACHE / "target")), "--served-model-name", MODEL_ID, "--host", "127.0.0.1", "--port", "18080", "--dtype", "bfloat16", "--max-model-len", "40960", "--max-num-seqs", "16", "--max-num-batched-tokens", "8192", "--gpu-memory-utilization", "0.9", "--generation-config", "vllm", "--reasoning-parser", "qwen3", "--seed", "20260905", "--no-enable-prefix-caching", "--limit-mm-per-prompt", '{"image":0,"video":0}']
        if self.route != "baseline":
            config = {"method": "mtp" if self.route == "mtp5" else "dflash", "num_speculative_tokens": 15 if self.route == "dflash15" else 5, "rejection_sample_method": "standard"}
            if self.route.startswith("dflash"):
                config["model"] = str(CACHE / "draft")
            argv += ["--speculative-config", json.dumps(config)]
        env = dict(os.environ)
        env.update({"HF_HOME": str(CACHE / "hf"), "HF_HUB_OFFLINE": "1", "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1", "VLLM_DEEP_GEMM_WARMUP": "skip", "PYTHONUNBUFFERED": "1"})
        stamp = datetime.now(timezone.utc).strftime("%H%M%S")
        path = ROOT / "logs" / f"server-{self.route}-{stamp}.log"
        self.log = path.open("wb")
        write_json(path.with_suffix(".command.json"), {"argv": argv, "environment": {key:env[key] for key in ("HF_HOME","HF_HUB_OFFLINE","VLLM_DEEP_GEMM_WARMUP")}, "started_utc": utcnow()})
        state("SERVER_STARTING", route=self.route, log=str(path))
        self.process = subprocess.Popen(argv, env=env, stdout=self.log, stderr=subprocess.STDOUT, start_new_session=True)
        deadline = time.monotonic() + 1800
        try:
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeError(f"Server exited rc={self.process.returncode}; log={path}")
                try:
                    models = json_get("/v1/models")
                    if any(model["id"] == MODEL_ID for model in models.get("data", [])):
                        write_json(ROOT / "metadata" / f"models-{self.route}.json", models)
                        state("SERVER_READY", route=self.route, pid=self.process.pid, log=str(path))
                        return self
                except (OSError, ValueError):
                    pass
                STOP.wait(5)
            raise TimeoutError(f"Server readiness timed out; log={path}")
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_):
        if self.process and self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait(timeout=30)
        if self.log:
            self.log.close()


def select_prefix(tasks, count):
    return [task for dataset in ("humaneval_plus","math_500") for task in [entry for entry in tasks if entry["dataset"] == dataset][:count]]


def build_long_tasks():
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(CACHE / "target", local_files_only=True)
    tasks = []
    for target in (4096,16384,32768):
        filler = "Reference row: the category is ordinary and the value is unavailable.\n"
        count = target // len(tokenizer.encode(filler, add_special_tokens=False))
        for position in range(4):
            lines = [filler] * count
            insertion = int((count - 1) * (0.1,0.4,0.7,0.95)[position])
            answer = f"DFLASH-CHECK-{target}-{position}"
            lines[insertion] = f"Special record: the lookup code is {answer}.\n"
            text = "Read the reference records below.\n" + "".join(lines) + "\nReturn only the lookup code from the Special record."
            messages = [{"role":"user","content":text}]
            actual = len(tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, enable_thinking=False))
            tasks.append({"task_id":f"long/{target}-{position}","dataset":"synthetic_retrieval","messages":messages,"max_tokens":128,"expected":answer,"actual_input_tokens":actual,"nominal_input_tokens":target})
    write_json(ROOT / "data/long-context-tasks.json", tasks)
    return tasks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("canary","full"), required=True)
    parser.add_argument("--route", choices=("baseline","mtp5","dflash15","dflash5"))
    args = parser.parse_args()
    contract = ROOT / "src/experiment.json"
    protocol_hash = file_hash(contract)
    inputs = json.loads((ROOT / "metadata/inputs.json").read_text())
    if inputs["manifest_sha256"] != file_hash(ROOT / "data/tasks.jsonl"):
        raise ValueError("Task manifest changed after preparation")
    tasks = [json.loads(line) for line in (ROOT / "data/tasks.jsonl").read_text().splitlines()]
    code_problems = {problem["task_id"]:problem for problem in map(json.loads,(ROOT / "data/humaneval_plus.jsonl").read_text().splitlines())}
    math_problems = list(map(json.loads,(ROOT / "data/math500.jsonl").read_text().splitlines()))
    routes = [args.route] if args.route else ["baseline","mtp5","dflash15"]
    telemetry_file = (ROOT / "logs" / f"gpu-{args.phase}-{args.route or 'all'}.csv").open("wb")
    telemetry = subprocess.Popen(["nvidia-smi", "--query-gpu=timestamp,name,memory.used,memory.total,utilization.gpu,power.draw,temperature.gpu", "--format=csv", "--loop=2"],stdout=telemetry_file,stderr=subprocess.STDOUT)
    try:
        for route in routes:
            with Server(route):
                metrics_snapshot(route,args.phase + "-before")
                if args.phase == "canary":
                    selected = select_prefix(tasks,1)
                    records = run_group(route,"canary",selected,protocol_hash)
                    if any(not record["content"].strip() or record["finish_reason"] != "stop" for record in records):
                        raise ValueError("Canary did not produce complete final answers")
                    grades = score_records(route,"canary",records,code_problems,math_problems)
                    if grades["code"]["pass_at_k"]["base"]["pass@1"] == 0 and grades["math"]["correct"] == 0:
                        raise RuntimeError("Both canary tasks failed scoring; inspect outputs and scorer before full dispatch")
                    state("CANARY_COMPLETE",route=route,grades=grades)
                else:
                    primary_tasks = select_prefix(tasks,32) if route == "dflash5" else tasks
                    records = run_group(route,"matched-window" if route == "dflash5" else "primary",primary_tasks,protocol_hash)
                    label = "matched-window" if route == "dflash5" else "primary"
                    grades = score_records(route,label,records,code_problems,math_problems)
                    state("PRIMARY_COMPLETE",route=route,grades=grades)
                    if route != "dflash5":
                        subset = select_prefix(tasks,8)
                        repeated = run_group(route,"repeatability",subset,protocol_hash,repeats=3)
                        score_records(route,"repeatability",repeated,code_problems,math_problems)
                        streamed = run_group(route,"streaming",subset,protocol_hash,repeats=3,streaming=True)
                        score_records(route,"streaming",streamed,code_problems,math_problems)
                        for concurrency in (1,4,8):
                            concurrent = run_group(route,f"concurrency-{concurrency}",select_prefix(tasks,32),protocol_hash,concurrency=concurrency)
                            score_records(route,f"concurrency-{concurrency}",concurrent,code_problems,math_problems)
                        sampled = run_group(route,"sampling",subset,protocol_hash,repeats=3,temperature=0.7,seeds=[20260905,20260906,20260907])
                        score_records(route,"sampling",sampled,code_problems,math_problems)
                        long_tasks = build_long_tasks()
                        long_records = run_group(route,"long-context",long_tasks,protocol_hash)
                        write_json(ROOT / "results" / route / "long-context" / "correctness.json",[{"task_id":task["task_id"],"actual_input_tokens":task["actual_input_tokens"],"correct":record["content"].strip()==task["expected"]} for task,record in zip(long_tasks,long_records)])
                metrics_snapshot(route,args.phase + "-after")
            state("ROUTE_COMPLETE",route=route,stage=args.phase)
        state("COMPLETE",stage=args.phase,route=args.route or "all",protocol_hash=protocol_hash)
    finally:
        telemetry.terminate()
        telemetry.wait(timeout=15)
        telemetry_file.close()


def interrupted(signum, frame):
    raise RuntimeError(f"Interrupted by signal {signum}")


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, interrupted)
    try:
        main()
    except BaseException as error:
        diagnostic = ROOT / "logs/failure.txt"
        diagnostic.write_text(traceback.format_exc(), encoding="utf-8")
        state("FAILED",error_type=type(error).__name__,cause=str(error),diagnostic=str(diagnostic))
        raise
"""Bounded Windows CPU capacity measurements against real /v1/systemone requests."""
import argparse
import ctypes
import ctypes.wintypes as wt
import hashlib
import json
import math
import os
import platform
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from systemone_client import calibration_summary, request_body, score_answer
from try_ui import ProcessMonitor


class MemoryStatus(ctypes.Structure):
    _fields_ = [("length", wt.DWORD), ("load", wt.DWORD)] + [
        (name, ctypes.c_ulonglong) for name in
        ("physical_total", "physical_available", "commit_limit", "commit_available",
         "virtual_total", "virtual_available", "extended_available")]


class BasicLimits(ctypes.Structure):
    _fields_ = [("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
                ("flags", wt.DWORD), ("minimum_ws", ctypes.c_size_t),
                ("maximum_ws", ctypes.c_size_t), ("process_limit", wt.DWORD),
                ("affinity", ctypes.c_size_t), ("priority", wt.DWORD), ("scheduling", wt.DWORD)]


class IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in
               ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]


class ExtendedLimits(ctypes.Structure):
    _fields_ = [("basic", BasicLimits), ("io", IoCounters),
               ("process_memory_limit", ctypes.c_size_t), ("job_memory_limit", ctypes.c_size_t),
               ("peak_process_memory", ctypes.c_size_t), ("peak_job_memory", ctypes.c_size_t)]


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def system_memory():
    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise ctypes.WinError()
    return {"physical_total_mib": status.physical_total / 2**20,
            "physical_available_mib": status.physical_available / 2**20,
            "commit_limit_mib": status.commit_limit / 2**20,
            "commit_available_mib": status.commit_available / 2**20}


class ProcessBudget:
    def __init__(self, pid, limit_mib):
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wt.LPCWSTR]
        self.kernel.CreateJobObjectW.restype = wt.HANDLE
        self.kernel.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
        self.kernel.OpenProcess.restype = wt.HANDLE
        self.kernel.SetInformationJobObject.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD]
        self.kernel.QueryInformationJobObject.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD, ctypes.c_void_p]
        self.kernel.AssignProcessToJobObject.argtypes = [wt.HANDLE, wt.HANDLE]
        self.kernel.CloseHandle.argtypes = [wt.HANDLE]
        self.handle = self.kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimits()
        limits.basic.flags = 0x100 | 0x2000
        limits.process_memory_limit = int(limit_mib * 2**20)
        process_handle = None
        try:
            if not self.kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                raise ctypes.WinError(ctypes.get_last_error())
            process_handle = self.kernel.OpenProcess(0x100 | 0x1, False, pid)
            if not process_handle or not self.kernel.AssignProcessToJobObject(self.handle, process_handle):
                raise ctypes.WinError(ctypes.get_last_error())
            actual = ExtendedLimits()
            if not self.kernel.QueryInformationJobObject(self.handle, 9, ctypes.byref(actual), ctypes.sizeof(actual), None):
                raise ctypes.WinError(ctypes.get_last_error())
            if actual.process_memory_limit != limits.process_memory_limit or actual.basic.flags & limits.basic.flags != limits.basic.flags:
                raise RuntimeError("PROCESS_MEMORY_BUDGET_NOT_APPLIED")
        except BaseException:
            self.close()
            raise
        finally:
            if process_handle:
                self.kernel.CloseHandle(process_handle)

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def get_json(url, timeout=3):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=timeout) as response:
        return json.load(response)


def run_tier(options, requests, concurrency, root):
    directory = root / f"c{concurrency}-slots{concurrency}"
    directory.mkdir(exist_ok=False)
    result = {"client_concurrency": concurrency, "configured_slots": concurrency,
              "requested_questions": len(requests), "started_utc": timestamp(), "status": "RUNNING",
              "completed": 0, "answered": 0, "errors": 0, "process_limit_mib": options.process_limit_mib}
    save(directory / "result.json", result)
    arguments = [str(options.engine), "-m", str(options.model), "--alias", "kev-c-cloud-capacity",
                 "--host", "127.0.0.1", "--port", str(options.port), "-c", str(options.context * concurrency),
                 "-b", "2048", "-ub", "2048", "-ngl", "0", "--cache-ram", "0", "--offline",
                 "-np", str(concurrency), "--slots"]
    result["server_arguments"] = arguments
    process = None
    budget = None
    stop = threading.Event()
    guard_reason = []
    samples = []
    monitor_thread = None
    base_url = f"http://127.0.0.1:{options.port}"
    with (directory / "server.log").open("wb") as server_log:
        try:
            process = subprocess.Popen(arguments, stdout=server_log, stderr=subprocess.STDOUT)
            result["server_pid"] = process.pid
            budget = ProcessBudget(process.pid, options.process_limit_mib)
            result["process_budget_readback"] = "PASS"
            kernel = ctypes.windll.kernel32
            kernel.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
            kernel.OpenProcess.restype = wt.HANDLE
            kernel.CloseHandle.argtypes = [wt.HANDLE]
            kernel.GetProcessTimes.argtypes = [wt.HANDLE] + [ctypes.POINTER(wt.FILETIME)] * 4
            ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD]
            monitor = ProcessMonitor(options.port)
            monitor.pid = process.pid
            started = time.monotonic()

            def sample_memory():
                with (directory / "memory.jsonl").open("w", encoding="utf-8", newline="\n") as output:
                    while not stop.is_set():
                        try:
                            sample = {"timestamp_utc": timestamp(), **system_memory(), "process": monitor.sample()}
                            samples.append(sample)
                            output.write(json.dumps(sample) + "\n")
                            output.flush()
                            if min(sample["physical_available_mib"], sample["commit_available_mib"]) < options.reserve_mib:
                                guard_reason.append("SYSTEM_MEMORY_RESERVE")
                            if time.monotonic() - started > options.tier_seconds:
                                guard_reason.append("TIER_TIME_BUDGET")
                            if (root / "STOP").exists():
                                guard_reason.append("USER_STOP")
                        except Exception as error:
                            guard_reason.append("MONITOR_FAILURE:" + type(error).__name__)
                        if guard_reason:
                            if process.poll() is None:
                                process.terminate()
                            return
                        stop.wait(0.5)

            monitor_thread = threading.Thread(target=sample_memory, daemon=True)
            monitor_thread.start()
            deadline = time.monotonic() + 90
            ready = False
            while process.poll() is None and time.monotonic() < deadline and not guard_reason:
                try:
                    ready = get_json(base_url + "/health")["status"] == "ok"
                    if ready:
                        break
                except (OSError, ValueError):
                    stop.wait(0.25)
            if not ready:
                raise RuntimeError("SERVER_NOT_READY")
            server_log.flush()
            log_text = (directory / "server.log").read_text(encoding="utf-8", errors="replace")
            slots = re.search(r"n_slots\s*=\s*(\d+).*n_ctx_slot\s*=\s*(\d+)", log_text)
            if not slots or int(slots[1]) != concurrency or int(slots[2]) != options.context:
                raise RuntimeError("ACTUAL_SLOT_OR_CONTEXT_MISMATCH")
            result["actual_slots"] = int(slots[1])
            result["actual_context_per_slot"] = int(slots[2])
            initial_slots = get_json(base_url + "/slots")
            save(directory / "slots-before.json", initial_slots)
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            active_requests = 0
            peak_requests = 0
            request_lock = threading.Lock()
            first_wave = set()
            start_gate = None

            def ask(item):
                nonlocal active_requests, peak_requests
                request_id, record_index, question_id, record, question = item
                body = request_body({**record, "questions": {question_id: question}})
                row = {"id": request_id, "record_index": record_index, "question_id": question_id,
                       "request": body}
                request = urllib.request.Request(base_url + "/v1/systemone", data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                                 headers={"content-type": "application/json"}, method="POST")
                if start_gate is not None and request_id in first_wave:
                    start_gate.wait(timeout=30)
                with request_lock:
                    active_requests += 1
                    peak_requests = max(peak_requests, active_requests)
                row["started_utc"] = timestamp()
                begin = time.perf_counter()
                try:
                    with opener.open(request, timeout=options.request_timeout) as response:
                        payload = json.load(response)
                    row["latency_ms"] = (time.perf_counter() - begin) * 1000
                    row.update(status="ok", response=payload, score=score_answer(question, payload["answers"][question_id]))
                except Exception as error:
                    row.update(status="error", error={"type": type(error).__name__, "message": str(error)[:300]})
                    row["latency_ms"] = (time.perf_counter() - begin) * 1000
                finally:
                    with request_lock:
                        active_requests -= 1
                row["finished_utc"] = timestamp()
                return row

            warmups = []
            for item in requests[:2]:
                warmups.append(ask(item))
                save(directory / "warmup.json", warmups)
                if warmups[-1]["status"] != "ok":
                    raise RuntimeError("WARMUP_FAILED")
            peak_requests = 0
            first_wave = {item[0] for item in requests[:concurrency]}
            start_gate = threading.Barrier(concurrency)
            rows = []
            active_max = 0
            sampling_done = threading.Event()

            def sample_slots():
                nonlocal active_max
                with (directory / "slots.jsonl").open("w", encoding="utf-8", newline="\n") as output:
                    while not sampling_done.is_set() and process.poll() is None:
                        try:
                            slots_value = get_json(base_url + "/slots", timeout=2)
                            active = sum(bool(slot.get("is_processing")) for slot in slots_value)
                            active_max = max(active_max, active)
                            output.write(json.dumps({"timestamp_utc": timestamp(), "active": active, "slots": slots_value}) + "\n")
                            output.flush()
                        except (OSError, ValueError):
                            pass
                        sampling_done.wait(0.5)

            slot_thread = threading.Thread(target=sample_slots, daemon=True)
            slot_thread.start()
            wall_started = time.perf_counter()
            try:
                with ThreadPoolExecutor(max_workers=concurrency) as pool, (directory / "rows.jsonl").open("w", encoding="utf-8", newline="\n") as output:
                    futures = {pool.submit(ask, item): item[0] for item in requests}
                    for future in as_completed(futures):
                        row = future.result()
                        rows.append(row)
                        output.write(json.dumps(row, ensure_ascii=False) + "\n")
                        output.flush()
                        if len(rows) % 32 == 0 or len(rows) == len(requests):
                            print(json.dumps({"concurrency": concurrency, "completed": len(rows), "total": len(requests),
                                              "errors": sum(row["status"] != "ok" for row in rows)}), flush=True)
            finally:
                sampling_done.set()
                slot_thread.join(5)
            elapsed = time.perf_counter() - wall_started
            successful = [row for row in rows if row["status"] == "ok"]
            latencies = sorted(row["latency_ms"] for row in successful)
            scores = [row["score"] for row in successful]
            result.update(completed=len(rows), answered=len(successful), errors=len(rows) - len(successful),
                          wall_seconds=elapsed, requests_per_second=len(successful) / elapsed,
                          max_observed_processing_slots=active_max, max_observed_client_inflight=peak_requests,
                          accuracy=sum(score["ok"] for score in scores) / len(requests),
                          calibration=calibration_summary(scores),
                          latency_p50_ms=statistics.median(latencies) if latencies else None,
                          latency_p95_ms=latencies[math.ceil(0.95 * len(latencies)) - 1] if latencies else None)
            result["status"] = "PASS" if len(rows) == len(requests) and peak_requests == concurrency and not result["errors"] and not guard_reason else "FAIL"
        except Exception as error:
            result.update(status="FAIL", failure={"type": type(error).__name__, "message": str(error)[:300]})
        finally:
            stop.set()
            if monitor_thread:
                monitor_thread.join(5)
            if process is not None:
                result["server_exit_before_cleanup"] = process.poll()
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(15)
            if budget:
                budget.close()
    result["guard_reasons"] = guard_reason
    result["unrun_questions"] = len(requests) - result["completed"]
    result["finished_utc"] = timestamp()
    if samples:
        process_samples = [sample["process"] for sample in samples if sample["process"].get("available")]
        result["memory_samples"] = len(samples)
        result["minimum_available_ram_mib"] = min(sample["physical_available_mib"] for sample in samples)
        result["minimum_commit_headroom_mib"] = min(sample["commit_available_mib"] for sample in samples)
        result["peak_working_set_mib"] = max((sample["peak_working_set_mib"] for sample in process_samples), default=None)
        result["peak_sampled_private_mib"] = max((sample["private_mib"] for sample in process_samples), default=None)
        if not process_samples and result["status"] == "PASS":
            result.update(status="FAIL", failure={"type": "MonitoringError", "message": "NO_VALID_PROCESS_MEMORY_SAMPLES"})
    log_text = (directory / "server.log").read_text(encoding="utf-8", errors="replace")
    result["allocation_failure_lines"] = [line for line in log_text.splitlines()
                                          if re.search(r"out of memory|bad_alloc|failed to allocate|not enough memory", line, re.I)][-12:]
    if guard_reason:
        result["status"] = "PROTECTED_STOP"
    save(directory / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 2, 4, 8, 16, 32, 64, 128, 256])
    parser.add_argument("--records-per-set", type=int, default=32)
    parser.add_argument("--context", type=int, default=8192)
    parser.add_argument("--port", type=int, default=8127)
    parser.add_argument("--process-limit-mib", type=int, default=24576)
    parser.add_argument("--reserve-mib", type=int, default=8192)
    parser.add_argument("--tier-seconds", type=int, default=900)
    parser.add_argument("--request-timeout", type=int, default=180)
    options = parser.parse_args()
    if sys.platform != "win32":
        parser.error("this measurement uses Windows process and system memory counters")
    if min(options.concurrency + [options.records_per_set, options.context, options.process_limit_mib, options.reserve_mib]) < 1:
        parser.error("counts and budgets must be positive")
    if not options.engine.is_file() or not options.model.is_file():
        parser.error("the existing engine and model files are required")
    requests, sources = [], {}
    for dataset in ("test_support", "test_assistant", "ood_support", "ood_assistant"):
        path = options.data / f"{dataset}.jsonl"
        data = path.read_bytes()
        records = [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]
        sources[dataset] = {"input_sha256": hashlib.sha256(data).hexdigest(), "selected_records": min(len(records), options.records_per_set)}
        for record_index, record in enumerate(records[:options.records_per_set]):
            for question_id, question in record["questions"].items():
                requests.append((f"{dataset}/{record_index}/{question_id}", record_index, question_id, record, question))
    if max(options.concurrency) > len(requests):
        parser.error("each tier needs at least as many real requests as configured concurrency")
    root = options.out
    root.mkdir(parents=True, exist_ok=False)
    initial = system_memory()
    if min(initial["physical_available_mib"], initial["commit_available_mib"]) < options.process_limit_mib + options.reserve_mib:
        parser.error("insufficient current headroom for the process budget plus system reserve")
    frozen = root / "source"
    frozen.mkdir()
    for filename in (Path(__file__).name, "systemone_client.py", "try_ui.py", "vendor_policy.py"):
        shutil.copyfile(Path(__file__).parent / filename, frozen / filename)
    save(root / "inputs.json", [{"id": item[0], "record_index": item[1], "question_id": item[2],
                                "request": request_body({**item[3], "questions": {item[2]: item[4]}}), "label": item[4]["label"]}
                               for item in requests])
    environment = {"started_utc": timestamp(), "host": platform.node(), "platform": platform.platform(),
                   "python": sys.version, "process_pid": os.getpid(), "settings": {key: str(value) if isinstance(value, Path) else value for key, value in vars(options).items()},
                   "initial_memory": initial, "datasets": sources, "requests_per_tier": len(requests),
                   "source_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in frozen.iterdir()},
                   "engine_sha256": hashlib.sha256(options.engine.read_bytes()).hexdigest(),
                   "model_sha256": hashlib.sha256(options.model.read_bytes()).hexdigest(),
                   "scope": "Windows x64 CPU capacity diagnostic on a fixed subset, not Snapdragon results or a full accuracy benchmark"}
    save(root / "environment.json", environment)
    results = []
    for concurrency in options.concurrency:
        if (root / "STOP").exists():
            break
        save(root / "status.json", {"status": "RUNNING", "pid": os.getpid(), "current_concurrency": concurrency, "completed_tiers": len(results), "updated_utc": timestamp()})
        result = run_tier(options, requests, concurrency, root)
        results.append(result)
        save(root / "results.json", results)
        print(json.dumps({key: result.get(key) for key in ("client_concurrency", "actual_slots", "status", "errors", "peak_working_set_mib", "peak_sampled_private_mib", "latency_p50_ms", "latency_p95_ms", "guard_reasons")}), flush=True)
        if result["status"] != "PASS":
            break
    save(root / "status.json", {"status": "FINISHED", "pid": os.getpid(), "completed_tiers": len(results),
                              "highest_passed_setting": max((result["client_concurrency"] for result in results if result["status"] == "PASS"), default=None),
                              "first_nonpassing_tier": next((result["client_concurrency"] for result in results if result["status"] != "PASS"), None),
                              "updated_utc": timestamp(), "limit_claim": "highest tested success is not an unmeasured maximum; failures under a process budget are budget-scoped"})


if __name__ == "__main__":
    main()
"""Contract-driven C/G/S/F campaign; imports and --stage validate are offline.

Preparation owns runtime/models/engine-args metadata. This module never installs,
downloads, releases execution locks, or manages cloud resources. StreamMetrics
owns streaming accounting; scoring.score_group owns all correctness verdicts.
"""

import argparse
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import platform
import re
import signal
import socket
import statistics
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
import uuid

from stream_metrics import StreamMetrics, StreamProtocolError


DATASETS = ("humaneval_plus", "math_500")
ROUTES = ("baseline", "mtp7", "dflash2_7")
STAGES = ("C", "G", "S", "F")
MAX_RESPONSE_BYTES = 64 * 1024 * 1024
HISTOGRAMS = (
    "time_to_first_token_seconds", "request_time_per_output_token_seconds",
    "inter_token_latency_seconds", "e2e_request_latency_seconds",
    "request_queue_time_seconds", "request_prefill_time_seconds", "request_decode_time_seconds",
)
SPEC_COUNTERS = ("spec_decode_num_drafts_total", "spec_decode_num_draft_tokens_total",
                 "spec_decode_num_accepted_tokens_total")
CLIENT_METRICS = ("ttft_token_s", "ttft_visible_s", "time_to_first_final_answer_s", "tpot_s", "e2e_s")


class CampaignError(ValueError):
    """An unresolved measurement, never an incorrect model answer."""


class CampaignBlocked(CampaignError):
    """A contract or acceptance gate prevents further dispatch."""


class BudgetExceeded(CampaignBlocked):
    pass


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def digest(content):
    return hashlib.sha256(content).hexdigest()


def request_seed(base_seed, task_id):
    return int(digest(f"{base_seed}|{task_id}".encode("utf-8"))[:8], 16) % 2147483647


@dataclass(frozen=True)
class Group:
    group_id: str
    stage: str
    route: str
    concurrency: int
    base_seed: int
    repetition: int
    thinking: bool
    dataset: str
    tasks: tuple
    server_epoch: str


def validate_contract(contract):
    expected = [("baseline", None, 0), ("mtp7", "mtp", 7), ("dflash2_7", "dflash", 7)]
    actual = [(route["name"], route["method"], route["num_speculative_tokens"])
              for route in contract["routes"]]
    if actual != expected:
        raise CampaignBlocked("UNSUPPORTED_ROUTE_CONTRACT")
    if (not contract["target"]["model_id"].startswith("Qwen/")
            or "dflash" in contract["target"]["model_id"].lower()
            or contract["target"]["dtype"] != "bfloat16"):
        raise CampaignBlocked("OFFICIAL_TARGET_OR_DTYPE_MISMATCH")
    for role in ("target", "draft"):
        if not re.fullmatch(r"[0-9a-f]{40}", contract[role]["revision"]):
            raise CampaignBlocked("UNPINNED_MODEL_REVISION")
    if contract["draft"]["required_architecture"] != "DFlash2DraftModel":
        raise CampaignBlocked("DRAFT_ARCHITECTURE_CONTRACT_MISMATCH")
    serving = contract["serving"]
    if (serving["max_model_len"] != 32768 or serving["prefix_caching"] is not False
            or serving["runner_env"] != {"VLLM_USE_V2_MODEL_RUNNER": "1"}):
        raise CampaignBlocked("SHARED_ENGINE_POLICY_MISMATCH")
    datasets = contract["quality"]["datasets"]
    if [(item["name"], item["tasks"], item["max_tokens"]) for item in datasets] != [
            ("humaneval_plus", 164, 16384), ("math_500", 500, 16384)]:
        raise CampaignBlocked("UNSUPPORTED_DATASET_OR_OUTPUT_BUDGET")
    checks = contract["serving_checks"]
    if (len(checks["canary_task_ids"]) != 8 or checks["canary_concurrency"] != [1, 8]
            or checks["matched_concurrency"] != [1, 4, 8]
            or checks["matched_repeats"] != 3
            or checks["matched_base_seeds"] != [20260906, 20260907, 20260908]
            or contract["sampling"]["seed"] != checks["matched_base_seeds"][0]):
        raise CampaignBlocked("UNSUPPORTED_MATRIX_CONTRACT")
    if ("qwen38-plan-v1|20260906|dataset|task_id" not in checks["matched_subset"]
            or "qwen38-order-v1|stage|base_seed|dataset|task_id" not in checks["ordered_requests"]
            or "2147483647" not in checks["request_seed"]):
        raise CampaignBlocked("UNSUPPORTED_HASH_ALGORITHM_CONTRACT")
    diagnostic = checks["greedy_diagnostic"]
    if (len(diagnostic["task_ids"]) != 4 or diagnostic["concurrency"] != [1, 4]
            or diagnostic["thinking_modes"] != [False, True]
            or diagnostic["repeats"] != 3 or diagnostic["max_tokens"] != 512
            or diagnostic["stream"] is not False):
        raise CampaignBlocked("UNSUPPORTED_DIAGNOSTIC_CONTRACT")
    if contract["planned_measured_responses"] != 5904:
        raise CampaignBlocked("PLANNED_RESPONSE_COUNT_MISMATCH")


def _public_tasks(contract, tasks):
    result = []
    expected_counts = {item["name"]: item["tasks"] for item in contract["quality"]["datasets"]}
    for task in tasks:
        dataset = task.get("dataset")
        prefix = {"humaneval_plus": "HumanEval", "math_500": "MATH-500"}.get(dataset)
        task_id = task.get("task_id", "")
        if prefix is None or not re.fullmatch(prefix + r"/(0|[1-9][0-9]*)", task_id):
            raise CampaignError("INVALID_TASK_IDENTITY")
        messages = task.get("messages")
        if not isinstance(messages, list) or not messages:
            raise CampaignError("MISSING_TASK_MESSAGES")
        for message in messages:
            if (not isinstance(message, dict) or set(message) != {"role", "content"}
                    or message["role"] not in ("system", "user")
                    or not isinstance(message["content"], str)):
                raise CampaignError("TEXT_ONLY_INPUT_REQUIRED")
        if task.get("max_tokens") != 16384:
            raise CampaignError("TASK_OUTPUT_BUDGET_MISMATCH")
        if "input_tokens" in task:
            if (type(task["input_tokens"]) is not int or task["input_tokens"] < 0
                    or task["input_tokens"] + task["max_tokens"] > contract["serving"]["max_model_len"]):
                raise CampaignBlocked("INPUT_OUTPUT_CONTEXT_WINDOW_EXCEEDED")
        result.append({"task_id": task_id, "dataset": dataset,
                       "messages": deepcopy(messages), "max_tokens": task["max_tokens"]})
    if len({task["task_id"] for task in result}) != len(result):
        raise CampaignError("DUPLICATE_TASK_ID")
    if Counter(task["dataset"] for task in result) != expected_counts:
        raise CampaignError("TASK_DENOMINATOR_MISMATCH")
    for dataset, count in expected_counts.items():
        prefix = "HumanEval" if dataset == "humaneval_plus" else "MATH-500"
        if {task["task_id"] for task in result if task["dataset"] == dataset} != {
                f"{prefix}/{index}" for index in range(count)}:
            raise CampaignError("TASK_SET_MISMATCH")
    return result


def build_groups(contract, tasks):
    """Pure schedule: no answer, grade, previous run or filesystem influences it."""
    validate_contract(contract)
    tasks = _public_tasks(contract, tasks)
    by_id = {task["task_id"]: task for task in tasks}
    checks = contract["serving_checks"]
    first_seed = checks["matched_base_seeds"][0]
    groups = []

    def append(stage, route, concurrency, seed, repetition, thinking, dataset, selected, epoch):
        profile = "thinking" if thinking else "no-thinking"
        group_id = f"{stage}-{route}-c{concurrency}-s{seed}-r{repetition}-{profile}-{dataset}"
        groups.append(Group(group_id, stage, route, concurrency, seed, repetition,
                            thinking, dataset, tuple(selected), epoch))

    def listed(identities):
        if len(set(identities)) != len(identities) or any(identity not in by_id for identity in identities):
            raise CampaignError("INVALID_LISTED_TASK_IDS")
        return [by_id[identity] for identity in identities]

    def ordered(stage, seed, selected):
        return sorted(selected, key=lambda task: (
            digest(f"qwen38-order-v1|{stage}|{seed}|{task['dataset']}|{task['task_id']}".encode("utf-8")),
            task["dataset"], task["task_id"]))

    for route in ROUTES:
        for concurrency in checks["canary_concurrency"]:
            append("C", route, concurrency, first_seed, 1, True, "mixed",
                   listed(checks["canary_task_ids"]), "C-" + route)
    diagnostic = checks["greedy_diagnostic"]
    for route in ROUTES:
        epoch_number = 0
        for thinking in diagnostic["thinking_modes"]:
            for concurrency in diagnostic["concurrency"]:
                for repetition in range(1, diagnostic["repeats"] + 1):
                    if repetition == 3:
                        epoch_number += 1
                    epoch = f"G-{route}-{epoch_number}"
                    append("G", route, concurrency, first_seed, repetition, thinking, "mixed",
                           listed(diagnostic["task_ids"]), epoch)
    selected = []
    for dataset in DATASETS:
        candidates = [task for task in tasks if task["dataset"] == dataset]
        selected.extend(sorted(candidates, key=lambda task: (
            digest(f"qwen38-plan-v1|{first_seed}|{dataset}|{task['task_id']}".encode("utf-8")),
            task["task_id"]))[:32])
    for repeat_index, seed in enumerate(checks["matched_base_seeds"]):
        for route in checks["route_orders"][repeat_index]:
            for concurrency in checks["concurrency_orders"][repeat_index]:
                append("S", route, concurrency, seed, repeat_index + 1, True, "mixed",
                       ordered("S", seed, selected), f"S-{repeat_index + 1}-{route}")
    for concurrency in contract["quality"]["primary_concurrency_levels"]:
        for route in checks["full_route_orders_by_concurrency"][str(concurrency)]:
            for dataset in DATASETS:
                append("F", route, concurrency, first_seed, 1, True, dataset,
                       ordered("F", first_seed, [task for task in tasks if task["dataset"] == dataset]),
                       f"F-{concurrency}-{route}")
    counts = Counter()
    for group in groups:
        counts[group.stage] += len(group.tasks)
    if counts != {item["stage"]: item["responses"] for item in contract["planned_matrix"]}:
        raise CampaignError("BUILT_MATRIX_COUNT_MISMATCH")
    if len({group.group_id for group in groups}) != len(groups) or sum(counts.values()) != 5904:
        raise CampaignError("BUILT_MATRIX_IDENTITY_MISMATCH")
    return groups


def request_payload(contract, group, task, *, warmup=False):
    """Only public messages enter the API; gold and task metadata stay local."""
    payload = deepcopy(contract["sampling"])
    payload.update(model=contract["target"]["model_id"], messages=deepcopy(task["messages"]),
                   seed=request_seed(group.base_seed, task["task_id"]),
                   max_completion_tokens=512 if warmup else task["max_tokens"])
    payload["chat_template_kwargs"]["enable_thinking"] = group.thinking
    if group.stage == "G":
        diagnostic = contract["serving_checks"]["greedy_diagnostic"]
        for field in ("temperature", "top_p", "top_k", "stream", "return_token_ids",
                      "return_prompt_text", "logprobs", "top_logprobs"):
            payload[field] = diagnostic[field]
        payload["max_completion_tokens"] = diagnostic["max_tokens"]
        if not group.thinking:
            payload.pop("reasoning_effort", None)
    else:
        payload.update(deepcopy(contract["stream_measurement"]["request"]))
    if "max_tokens" in payload or "extra_body" in payload or any(value is None for value in payload.values()):
        raise CampaignError("AMBIGUOUS_REQUEST_PAYLOAD")
    return payload


class Budget:
    def __init__(self, start_epoch, stop_after_hours, *, now_epoch=None, monotonic=None):
        now_epoch = time.time() if now_epoch is None else now_epoch
        monotonic = time.monotonic() if monotonic is None else monotonic
        if (type(start_epoch) not in (int, float) or not math.isfinite(start_epoch)
                or start_epoch <= 0 or start_epoch > now_epoch
                or not 0 < stop_after_hours <= 11.5):
            raise CampaignBlocked("INVALID_BILLING_START_OR_DEADLINE")
        self.start_epoch = start_epoch
        self.deadline_epoch = start_epoch + stop_after_hours * 3600
        self.deadline_monotonic = monotonic + self.deadline_epoch - now_epoch

    def remaining(self):
        return min(self.deadline_epoch - time.time(), self.deadline_monotonic - time.monotonic())

    def check(self):
        if self.remaining() <= 0:
            raise BudgetExceeded("ABORTED_BUDGET: stop-new-work deadline reached")


class SSEDecoder:
    """SSE line grammar; UTF-8 decoding occurs only after a complete line."""

    def __init__(self):
        self.line = bytearray()
        self.data_lines = []
        self.after_cr = False
        self.first_line = True

    def _line(self):
        text = self.line.decode("utf-8")
        self.line.clear()
        if self.first_line:
            text = text.removeprefix("\ufeff")
            self.first_line = False
        if text == "":
            if not self.data_lines:
                return None
            data = "\n".join(self.data_lines)
            self.data_lines.clear()
            return data
        if not text.startswith(":"):
            name, separator, value = text.partition(":")
            if name == "data":
                self.data_lines.append(value.removeprefix(" ") if separator else "")
        return None

    def feed(self, content, received_ns):
        for octet in content:
            if self.after_cr:
                self.after_cr = False
                if octet == 10:
                    continue
            if octet in (10, 13):
                self.after_cr = octet == 13
                data = self._line()
                if data is not None:
                    yield data, received_ns
            else:
                self.line.append(octet)


class _SocketScope:
    def __init__(self):
        self.lock = threading.Lock()
        self.sockets = set()
        self.cancelled = False

    def remember(self, connection):
        with self.lock:
            if self.cancelled:
                connection.close()
                raise CampaignBlocked("HTTP_CANCELLED")
            self.sockets.add(connection)

    def cancel(self):
        with self.lock:
            self.cancelled = True
            for connection in self.sockets:
                try:
                    connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                # shutdown alone does not wake a blocked recv on Windows; closing the fd does.
                try:
                    connection._real_close()
                except (OSError, AttributeError):
                    connection.close()
            self.sockets.clear()


class _TrackedConnection(http.client.HTTPConnection):
    def __init__(self, host, *, scope, **kwargs):
        self.scope = scope
        super().__init__(host, **kwargs)

    def connect(self):
        super().connect()
        self.scope.remember(self.sock)


class _TrackedHandler(urllib.request.HTTPHandler):
    def __init__(self, scope):
        super().__init__()
        self.scope = scope

    def http_open(self, request):
        def factory(host, **kwargs):
            return _TrackedConnection(host, scope=self.scope, **kwargs)
        return self.do_open(factory, request)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        raise CampaignError("LOCAL_HTTP_REDIRECT_FORBIDDEN")


class LocalHTTP:
    """Loopback-only urllib transport, with cancellation of owned sockets."""

    def __init__(self, port, budget=None, stop=None):
        if type(port) is not int or not 0 < port < 65536:
            raise CampaignError("INVALID_LOCAL_PORT")
        self.base_url = f"http://127.0.0.1:{port}"
        self.budget = budget
        self.stop = stop if stop is not None else threading.Event()
        self.lock = threading.Lock()
        self.active = set()

    def check(self):
        if self.budget is not None:
            self.budget.check()
        if self.stop.is_set():
            raise CampaignBlocked("CAMPAIGN_CANCELLED")

    def cancel(self):
        self.stop.set()
        with self.lock:
            for scope in self.active:
                scope.cancel()

    @contextmanager
    def open(self, path, payload=None, timeout=600):
        self.check()
        if path not in ("/v1/chat/completions", "/v1/models", "/metrics", "/health"):
            raise CampaignError("UNEXPECTED_LOCAL_ENDPOINT")
        if self.budget is not None:
            timeout = min(timeout, max(0.001, self.budget.remaining()))
        scope = _SocketScope()
        with self.lock:
            self.check()
            self.active.add(scope)
        response = None
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                                 _TrackedHandler(scope), _NoRedirect())
            request = urllib.request.Request(self.base_url + path, data=payload,
                                             headers={"Content-Type": "application/json"})
            try:
                response = opener.open(request, timeout=timeout)
            except urllib.error.HTTPError as error:
                response = error
            yield response
        finally:
            scope.cancel()
            if response is not None:
                response.close()
            with self.lock:
                self.active.discard(scope)


@dataclass
class Capture:
    wire: bytearray = field(default_factory=bytearray)
    chunks: list = field(default_factory=list)
    events: list = field(default_factory=list)
    record: dict = field(default_factory=dict)
    buffered_bytes: int = 0
    overflow_bytes: int = 0

    def append(self, content, received_ns, maximum):
        available = max(0, maximum - self.buffered_bytes - 80)
        retained = content[:available]
        offset = len(self.wire)
        self.wire.extend(retained)
        self.chunks.append({"offset": offset, "length": len(retained), "received_ns": received_ns})
        self.buffered_bytes += len(retained) + 80
        self.overflow_bytes += len(content) - len(retained)
        if self.overflow_bytes:
            raise CampaignError("RESPONSE_BUFFER_LIMIT_EXCEEDED")

    def event(self, data, received_ns, maximum):
        size = len(data.encode("utf-8")) + 96
        if self.buffered_bytes + size > maximum:
            raise CampaignError("RESPONSE_BUFFER_LIMIT_EXCEEDED")
        self.buffered_bytes += size
        event = {"data": data, "received_ns": received_ns}
        self.events.append(event)
        return event


class RequestFailure(CampaignError):
    def __init__(self, capture, cause):
        self.capture = capture
        self.cause = cause
        super().__init__(f"{type(cause).__name__}: {cause}")


def _nonstream_result(raw, payload, started_ns, received_ns):
    if not isinstance(raw, dict) or raw.get("model") != payload["model"] or not raw.get("id"):
        raise StreamProtocolError("Diagnostic response identity mismatch")
    choices = raw.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or choices[0].get("index") != 0:
        raise StreamProtocolError("Diagnostic requires one index-0 choice")
    choice = choices[0]
    message = choice.get("message")
    if not isinstance(message, dict) or message.get("tool_calls") or message.get("function_call"):
        raise StreamProtocolError("Diagnostic message shape mismatch")
    content = message.get("content") or ""
    reasoning = message.get("reasoning") or message.get("reasoning_content") or ""
    if not isinstance(content, str) or not isinstance(reasoning, str):
        raise StreamProtocolError("Diagnostic text shape mismatch")
    usage = raw.get("usage")
    if not isinstance(usage, dict):
        raise StreamProtocolError("Diagnostic authoritative usage missing")
    token_ids = choice.get("token_ids")
    prompt_ids = raw.get("prompt_token_ids")
    for name, ids, limit in (("completion_tokens", token_ids, payload["max_completion_tokens"]),
                             ("prompt_tokens", prompt_ids, 32768)):
        if (not isinstance(ids, list) or any(type(token) is not int or token < 0 for token in ids)
                or type(usage.get(name)) is not int or not 0 <= usage[name] <= limit
                or len(ids) != usage[name]):
            raise StreamProtocolError("Diagnostic token IDs disagree with usage: " + name)
    if choice.get("finish_reason") not in ("stop", "length"):
        raise StreamProtocolError("Diagnostic finish reason missing")
    logprobs = choice.get("logprobs")
    if not isinstance(logprobs, dict) or not isinstance(logprobs.get("content"), list):
        raise CampaignBlocked("G_LOGPROB_RESPONSE_SCHEMA_UNVERIFIED")
    if len(logprobs["content"]) != len(token_ids):
        raise CampaignBlocked("G_LOGPROB_TOKEN_COVERAGE_UNVERIFIED")
    for observation in logprobs["content"]:
        if (not isinstance(observation, dict) or not isinstance(observation.get("top_logprobs"), list)
                or len(observation["top_logprobs"]) != payload["top_logprobs"]):
            raise CampaignBlocked("G_TOP5_LOGPROBS_UNVERIFIED")
        for candidate in [observation, *observation["top_logprobs"]]:
            if (not isinstance(candidate, dict) or not isinstance(candidate.get("token"), str)
                    or type(candidate.get("logprob")) not in (int, float) or not math.isfinite(candidate["logprob"])):
                raise CampaignBlocked("G_NONFINITE_OR_MALFORMED_LOGPROB")
    if token_ids and not logprobs["content"]:
        raise CampaignBlocked("G_LOGPROBS_MISSING")
    prompt_text = raw.get("prompt_text", raw.get("prompt"))
    if not isinstance(prompt_text, str) or not prompt_text:
        raise CampaignBlocked("G_RETURN_PROMPT_TEXT_RESPONSE_SCHEMA_UNVERIFIED")
    return {"response_id": raw["id"], "content": content, "reasoning": reasoning,
            "prompt_token_ids": prompt_ids, "token_ids": token_ids, "usage": usage,
            "finish_reason": choice["finish_reason"], "logprobs": logprobs, "prompt_text": prompt_text,
            "timestamps_ns": {"dispatch": started_ns, "response_received": received_ns},
            "e2e_s": (received_ns - started_ns) / 1e9, "ttft_token_s": None,
            "ttft_visible_s": None, "time_to_first_final_answer_s": None, "tpot_s": None,
            "tpot_status": "NONSTREAM_DIAGNOSTIC", "empty_final": not content.strip()}


def collect_request(transport, payload, *, wire_payload=None, clock=None,
                    max_bytes=MAX_RESPONSE_BYTES):
    """Receive once; callers must persist RequestFailure.capture before raising."""
    clock = time.monotonic_ns if clock is None else clock
    wire_payload = json_bytes(payload) if wire_payload is None else wire_payload
    capture = Capture()
    capture.record = {"started_utc": utcnow(), "status": "RUNNING"}
    started_ns = clock()
    metrics = StreamMetrics(payload["model"], started_ns, payload["max_completion_tokens"])
    decoder = SSEDecoder()
    last_received_ns = started_ns
    try:
        transport.check()
        with transport.open("/v1/chat/completions", wire_payload) as response:
            capture.record["http_status"] = response.status
            capture.record["content_type"] = response.headers.get("Content-Type", "")
            success = response.status == 200
            if success and payload["stream"] and "text/event-stream" not in capture.record["content_type"].lower():
                raise StreamProtocolError("Expected text/event-stream")
            while True:
                transport.check()
                content = response.read1(65536)
                received_ns = clock()
                if not content:
                    break
                last_received_ns = received_ns
                capture.append(content, received_ns, max_bytes)
                if success and payload["stream"]:
                    for data, event_ns in decoder.feed(content, received_ns):
                        event = capture.event(data, event_ns, max_bytes)
                        before = len(metrics.token_ids)
                        metrics.consume(data, event_ns)
                        event["generated_tokens"] = len(metrics.token_ids) - before
                    if metrics.done:
                        break
            if (transport.budget is not None
                    and last_received_ns > int(transport.budget.deadline_monotonic * 1e9)):
                raise BudgetExceeded("ABORTED_BUDGET: response arrived after deadline")
            if not success:
                raise CampaignError(f"HTTP_ERROR_{response.status}: raw body retained")
        result = (metrics.finalize() if payload["stream"] else
                  _nonstream_result(json.loads(capture.wire), payload, started_ns, last_received_ns))
        if result["usage"]["prompt_tokens"] + payload["max_completion_tokens"] > 32768:
            raise CampaignBlocked("ACTUAL_INPUT_OUTPUT_CONTEXT_WINDOW_EXCEEDED")
        capture.record.update(result, status="COMPLETE", ended_utc=utcnow(),
                              terminal_received_ns=result["timestamps_ns"].get("done", last_received_ns),
                              final_answer_status="MISSING_FINAL_CONTENT" if result["empty_final"] else "VALID")
        return capture
    except BaseException as error:
        if transport.budget is not None and transport.budget.remaining() <= 0:
            error = BudgetExceeded("ABORTED_BUDGET: received partial data retained")
        capture.record.update(status="ABORTED_BUDGET" if isinstance(error, BudgetExceeded) else "FAILED",
                              error_type=type(error).__name__, error=str(error), ended_utc=utcnow(),
                              terminal_received_ns=last_received_ns, overflow_bytes=capture.overflow_bytes,
                              timestamps_ns=dict(metrics.timestamps),
                              partial_content="".join(metrics.content_parts),
                              partial_reasoning="".join(metrics.reasoning_parts))
        raise RequestFailure(capture, error) from error


def parse_metrics(text, model, engine=None):
    from prometheus_client.parser import text_string_to_metric_families

    roots = {"vllm:" + name for name in (*HISTOGRAMS, *SPEC_COUNTERS,
             "generation_tokens_total", "prompt_tokens_total", "request_success_total",
             "num_requests_running", "num_requests_waiting")}
    selected = []
    for family in text_string_to_metric_families(text):
        for sample in family.samples:
            if (sample.labels.get("model_name") == model
                    and any(sample.name == name or sample.name in (name + "_sum", name + "_count", name + "_bucket")
                            for name in roots)):
                selected.append(sample)
    if not selected:
        raise CampaignError("METRICS_MODEL_SCOPE_MISSING")
    scopes = set()
    for sample in selected:
        keys = [key for key in ("engine", "engine_id") if key in sample.labels]
        if len(keys) != 1:
            raise CampaignError("METRICS_ENGINE_LABEL_MISSING_OR_AMBIGUOUS")
        scopes.add((keys[0], sample.labels[keys[0]]))
    if engine is not None:
        scopes = {scope for scope in scopes if scope[1] == str(engine)}
    if len(scopes) != 1:
        raise CampaignError("METRICS_ENGINE_SCOPE_MISSING_OR_AMBIGUOUS")
    engine_label, engine_id = next(iter(scopes))
    series = []
    seen = set()
    for sample in selected:
        if sample.labels.get(engine_label) != engine_id:
            continue
        key = (sample.name, tuple(sorted(sample.labels.items())))
        if key in seen or not math.isfinite(sample.value) or sample.value < 0:
            raise CampaignError("METRICS_DUPLICATE_OR_NONFINITE_SERIES")
        seen.add(key)
        series.append({"name": sample.name, "labels": dict(sample.labels), "value": sample.value})
    return {"model": model, "engine_label": engine_label, "engine": engine_id,
            "series": sorted(series, key=lambda row: (row["name"], sorted(row["labels"].items())))}


def _series_map(snapshot):
    return {(row["name"], tuple(sorted(row["labels"].items()))): row["value"] for row in snapshot["series"]}


def reconcile_metrics(before, after, records, route, elapsed_wall_s=None):
    for name in ("model", "engine_label", "engine", "server_instance"):
        if not before.get(name) or before.get(name) != after.get(name):
            raise CampaignError("METRICS_PROCESS_OR_SCOPE_CHANGED: " + name)
    previous, current = _series_map(before), _series_map(after)
    details = {}

    def delta(name, required=True):
        name = "vllm:" + name
        old = {key: value for key, value in previous.items() if key[0] == name}
        new = {key: value for key, value in current.items() if key[0] == name}
        if not old and not new and not required:
            return None
        if not old or old.keys() != new.keys():
            raise CampaignError("METRICS_MISSING_OR_CHANGED_SERIES: " + name)
        rows = []
        for key in sorted(old):
            if new[key] < old[key]:
                raise CampaignError("METRICS_COUNTER_RESET: " + name)
            rows.append({"labels": dict(key[1]), "before": old[key], "after": new[key],
                         "delta": new[key] - old[key]})
        details[name] = rows
        return math.fsum(row["delta"] for row in rows)

    completion = sum(record["usage"]["completion_tokens"] for record in records)
    prompt = sum(record["usage"]["prompt_tokens"] for record in records)
    generated = delta("generation_tokens_total")
    input_tokens = delta("prompt_tokens_total")
    if generated != completion or input_tokens != prompt:
        raise CampaignError(f"METRICS_USAGE_MISMATCH: output={generated}/{completion} input={input_tokens}/{prompt}")
    input_sources = details["vllm:prompt_tokens_total"]
    for row in input_sources:
        source = row["labels"].get("source", "")
        if row["delta"] > 0 and ("cache" in source.lower() or "transfer" in source.lower()):
            raise CampaignError("PREFIX_CACHE_DISABLED_BUT_CACHED_INPUT_RECORDED")
    finished = delta("request_success_total")
    expected_reasons = Counter(record["finish_reason"] for record in records)
    actual_reasons = Counter()
    for row in details["vllm:request_success_total"]:
        reason = row["labels"].get("finished_reason", row["labels"].get("finish_reason"))
        if reason is None:
            raise CampaignError("METRICS_FINISH_REASON_LABEL_MISSING")
        actual_reasons[reason] += row["delta"]
    if finished != len(records) or +actual_reasons != +expected_reasons:
        raise CampaignError("METRICS_FINISHED_REQUEST_COUNT_MISMATCH")
    for snapshot in (before, after):
        for row in snapshot["series"]:
            if row["name"] in ("vllm:num_requests_running", "vllm:num_requests_waiting") and row["value"] != 0:
                raise CampaignError("METRICS_REQUESTS_NOT_DRAINED")
    histograms = {}
    first_output_count = sum(record["usage"]["completion_tokens"] > 0 for record in records)
    for histogram in HISTOGRAMS:
        total = delta(histogram + "_sum")
        count = delta(histogram + "_count")
        delta(histogram + "_bucket")
        bucket_rows = details["vllm:" + histogram + "_bucket"]
        buckets = {}
        for row in bucket_rows:
            bound = row["labels"].get("le")
            if bound is None:
                raise CampaignError("HISTOGRAM_BUCKET_BOUND_MISSING")
            buckets[bound] = buckets.get(bound, 0) + row["delta"]
        ordered = sorted(buckets, key=float)
        values = [buckets[bound] for bound in ordered]
        if (not ordered or not math.isinf(float(ordered[-1])) or float(ordered[-1]) < 0
                or values[-1] != count or any(left > right for left, right in zip(values, values[1:]))):
            raise CampaignError("HISTOGRAM_BUCKET_COUNT_MISMATCH: " + histogram)
        if count != int(count) or (count == 0 and total != 0):
            raise CampaignError("HISTOGRAM_INVALID_OBSERVATION_COUNT: " + histogram)
        if histogram == "time_to_first_token_seconds":
            unit, expected_count = "request_reaching_first_output", first_output_count
        elif histogram == "inter_token_latency_seconds":
            unit, expected_count = "qualifying_engine_generation_output_update", None
        else:
            unit, expected_count = "finished_request", len(records)
        if expected_count is not None and count != expected_count:
            raise CampaignError("HISTOGRAM_POPULATION_MISMATCH: " + histogram)
        histograms[histogram] = {"sum_seconds": total, "count": count,
                                 "mean_seconds": total / count if count else None,
                                 "status": "VALID" if count else "NO_OBSERVATIONS",
                                 "observation_unit": unit, "buckets": buckets,
                                 "quantiles": "not computed; bucket estimates are not exact client percentiles"}
    speculation = {name: delta(name, required=route != "baseline") for name in SPEC_COUNTERS}
    if route == "baseline":
        if any(value is not None and value != 0 for value in speculation.values()):
            raise CampaignError("BASELINE_HAS_ACTIVE_SPECULATION")
        spec_status = "NOT_APPLICABLE_BASELINE"
    else:
        drafts, drafted, accepted = (speculation[name] for name in SPEC_COUNTERS)
        if not (drafts > 0 and drafted > 0 and accepted > 0 and accepted <= drafted):
            raise CampaignError("CANDIDATE_SPECULATION_NOT_OBSERVED_OR_INVALID")
        spec_status = "OBSERVED_ACTIVE_COUNTERS"
    wall_valid = elapsed_wall_s is not None and elapsed_wall_s > 0
    return {"status": "RECONCILED", "scope": {key: before[key] for key in ("model", "engine_label", "engine", "server_instance")},
            "generation_tokens": generated, "prompt_tokens": input_tokens, "finished_requests": finished,
            "generation_tokens_per_second": generated / elapsed_wall_s if wall_valid else None,
            "prompt_tokens_per_second": input_tokens / elapsed_wall_s if wall_valid else None,
            "input_source_rows": input_sources, "native_histograms": histograms,
            "native_tpot_output_le_one_count": sum(record["usage"]["completion_tokens"] <= 1 for record in records),
            "speculation": {"status": spec_status, "counters": speculation,
                            "acceptance_rate": (speculation[SPEC_COUNTERS[2]] / speculation[SPEC_COUNTERS[1]]
                                                if route != "baseline" else None),
                            "accepted_tokens_per_draft": (speculation[SPEC_COUNTERS[2]] / speculation[SPEC_COUNTERS[0]]
                                                          if route != "baseline" else None)},
            "original_series_and_deltas": details}


def summary_statistics(values):
    valid = [value for value in values if value is not None]
    if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0 for value in valid):
        raise CampaignError("INVALID_CLIENT_OBSERVATION")
    valid.sort()
    summary = {"valid_count": len(valid), "missing_count": len(values) - len(valid),
               "mean": statistics.fmean(valid) if valid else None,
               "stddev": statistics.pstdev(valid) if valid else None,
               "stddev_method": "population", "percentile_method": "linear interpolation"}
    for percentile in (50, 95, 99):
        value = None
        if valid:
            location = (len(valid) - 1) * percentile / 100
            lower, upper = math.floor(location), math.ceil(location)
            value = valid[lower] + (valid[upper] - valid[lower]) * (location - lower)
        summary["p" + str(percentile)] = value
    return summary


def describe_group(group):
    return {name: getattr(group, name) for name in ("group_id", "stage", "route", "concurrency",
            "base_seed", "repetition", "thinking", "dataset", "server_epoch")} | {
        "planned": len(group.tasks), "ordered_task_ids": [task["task_id"] for task in group.tasks]}


def summarize_group(group, records, scores, start_ns, end_ns, *, resumed=False):
    if [record["task_id"] for record in records] != [task["task_id"] for task in group.tasks]:
        raise CampaignError("GROUP_RECORD_ORDER_OR_DENOMINATOR_MISMATCH")
    if any(record.get("status") != "COMPLETE" for record in records):
        raise CampaignError("INCOMPLETE_RESPONSES_CANNOT_BE_SCORED")
    wall = (end_ns - start_ns) / 1e9 if start_ns is not None and end_ns is not None else None
    if not resumed and (wall is None or wall <= 0):
        raise CampaignError("INVALID_GROUP_WALL_CLOCK")
    throughput_status = "INVALID_RESUMED" if resumed else "VALID"
    wall = None if resumed else wall

    def latency(selected):
        result = {name: summary_statistics([record.get(name) for record in selected]) for name in CLIENT_METRICS}
        result["completion_tokens"] = summary_statistics([record["usage"]["completion_tokens"] for record in selected])
        result["tpot_status_counts"] = dict(Counter(record.get("tpot_status", "MISSING") for record in selected))
        result["missing_final_answer_count"] = sum(not record["content"].strip() for record in selected)
        return result

    output_tokens = sum(record["usage"]["completion_tokens"] for record in records)
    input_tokens = sum(record["usage"]["prompt_tokens"] for record in records)
    datasets = {}
    for dataset in DATASETS:
        selected = [record for record in records if record["dataset"] == dataset]
        if not selected:
            continue
        counts = scores["datasets"][dataset] if scores is not None else None
        if counts is not None and counts["denominator"] != len(selected):
            raise CampaignError("SCORE_DENOMINATOR_MISMATCH")
        datasets[dataset] = {
            "denominator": len(selected), "raw_correct": counts["raw_correct"] if counts else None,
            "normal_correct": counts["normal_correct"] if counts else None,
            "accuracy": counts["raw_correct"] / len(selected) if counts else None,
            "normal_completion_accuracy": counts["normal_correct"] / len(selected) if counts else None,
            "raw_correct_per_second": counts["raw_correct"] / wall if counts and wall else None,
            "normal_correct_per_second": counts["normal_correct"] / wall if counts and wall else None,
            "output_tokens_per_second": sum(record["usage"]["completion_tokens"] for record in selected) / wall if wall else None,
            "throughput_denominator": "entire_same_group_wall_time",
            "finish_counts": dict(Counter(record["finish_reason"] for record in selected)),
            "empty_final": sum(not record["content"].strip() for record in selected),
            "budget_censored": sum(record["finish_reason"] == "length" for record in selected) / len(selected) > 0.05,
        }
        if scores is not None and dataset == "humaneval_plus":
            for key in ("base_correct", "plus_correct"):
                datasets[dataset][key] = sum(scores["by_task"][record["task_id"]][key] for record in selected)
    return {**describe_group(group), "status": "COMPLETE", "completed": len(records),
            "throughput_status": throughput_status, "elapsed_wall_s": wall,
            "clock_start_ns": start_ns if not resumed else None, "clock_end_ns": end_ns if not resumed else None,
            "completion_tokens": output_tokens, "prompt_tokens": input_tokens,
            "output_tokens_per_second": output_tokens / wall if wall else None,
            "input_tokens_per_second": input_tokens / wall if wall else None,
            "requests_per_second": len(records) / wall if wall else None,
            "client": {"all": latency(records), "by_dataset": {
                dataset: latency([record for record in records if record["dataset"] == dataset])
                for dataset in datasets}}, "datasets": datasets, "scores": scores,
            "recorder_boundary": "receive timestamps precede parsing; final serialization and grading excluded; earlier per-request persistence delays remain in scheduling wall time"}


def canary_gate(group, records):
    if group.stage == "C":
        affected = [record["task_id"] for record in records
                    if not record["content"].strip() or record["finish_reason"] == "length"]
        if len(affected) >= 2:
            raise CampaignBlocked("CANARY_EMPTY_OR_LENGTH_DIAGNOSTIC_REQUIRED: " + group.group_id + " " + ",".join(affected))


def quality_regressions(results):
    arms = {(result["route"], result["concurrency"], result["base_seed"]): result
            for result in results if result["stage"] == "S" and result["status"] == "COMPLETE"}
    failures = []
    for (route, concurrency, seed), candidate in arms.items():
        baseline = arms.get(("baseline", concurrency, seed))
        if route == "baseline" or baseline is None:
            continue
        for dataset in DATASETS:
            reference = baseline["scores"]["datasets"][dataset]
            measured = candidate["scores"]["datasets"][dataset]
            if reference["denominator"] != 32 or measured["denominator"] != 32:
                raise CampaignError("S_REGRESSION_DENOMINATOR_MISMATCH")
            for metric in ("raw_correct", "normal_correct"):
                difference = reference[metric] - measured[metric]
                if difference >= 8:
                    failures.append({"route": route, "concurrency": concurrency, "base_seed": seed,
                                     "dataset": dataset, "metric": metric, "difference": difference,
                                     "baseline_group": baseline["group_id"], "candidate_group": candidate["group_id"]})
    return failures


def full_runway(contract, full_groups, slice_results, billing_start, now_epoch, safety=1.5):
    if safety < 1.5 or not math.isfinite(safety):
        raise CampaignError("RUNWAY_SAFETY_FACTOR_TOO_SMALL")
    estimates = []
    previous_route = None
    startup_seconds = 0.0
    for group in full_groups:
        if group.stage != "F":
            raise CampaignError("RUNWAY_EXPECTS_FULL_STAGE_GROUPS")
        selected = [result for result in slice_results if result["stage"] == "S"
                    and result["route"] == group.route and result["concurrency"] == group.concurrency]
        if (len(selected) != 3 or {result["base_seed"] for result in selected} != set(contract["serving_checks"]["matched_base_seeds"])
                or any(result["status"] != "COMPLETE" or result["throughput_status"] != "VALID" for result in selected)):
            raise CampaignBlocked("RUNWAY_REQUIRES_ALL_THREE_VALID_S_CALIBRATIONS")
        if group.concurrency == 1:
            means = [result["client"]["by_dataset"][group.dataset]["e2e_s"]["mean"] for result in selected]
            if any(value is None or value <= 0 for value in means):
                raise CampaignBlocked("RUNWAY_MISSING_DATASET_LATENCY")
            seconds = max(means) * len(group.tasks)
            method = "worst_seed_dataset_mean_request_latency_times_full_dataset_count"
        else:
            seconds = max(result["elapsed_wall_s"] / result["planned"] for result in selected) * len(group.tasks)
            method = "worst_seed_mixed_group_wall_per_request_times_full_dataset_count"
        overhead = max(result.get("nonmeasurement_wall_s", 0) for result in selected) * max(1, len(group.tasks) / 64)
        if group.route != previous_route:
            startup_seconds += max(result.get("server_startup_s", 0) for result in selected)
        previous_route = group.route
        estimates.append({"group_id": group.group_id, "planned": len(group.tasks), "method": method,
                          "generation_seconds": seconds, "overhead_seconds": overhead})
    projected = (math.fsum(row["generation_seconds"] + row["overhead_seconds"] for row in estimates) + startup_seconds) * safety
    deadline = billing_start + contract["resource"]["stop_new_work_after_hours"] * 3600
    remaining = deadline - now_epoch
    return {"status": "FIT" if projected <= remaining else "BLOCKED", "safety_factor": safety,
            "billing_start": billing_start, "stop_new_work_epoch": deadline,
            "remaining_seconds": remaining, "estimated_seconds_with_safety": projected,
            "server_startup_seconds": startup_seconds, "groups": estimates,
            "collection_reserve_seconds": contract["resource"]["collection_reserve_hours"] * 3600,
            "scope_reduced": False}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CampaignError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _reject_constant(value):
    raise CampaignError("NONFINITE_JSON_VALUE")


def decode_json(content):
    return json.loads(content, object_pairs_hook=_unique_object, parse_constant=_reject_constant)


def read_bytes(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise CampaignBlocked("REQUIRED_REGULAR_FILE_MISSING: " + str(path))
    return path.read_bytes()


def read_json(path):
    return decode_json(read_bytes(path))


def file_hash(path, guard=None):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise CampaignError("HASH_REQUIRES_REGULAR_FILE: " + str(path))
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while content := stream.read(1024 * 1024):
            if guard is not None:
                guard()
            value.update(content)
    return value.hexdigest()


def child_path(parent, relative):
    if not isinstance(relative, str) or "\\" in relative or Path(relative).is_absolute():
        raise CampaignError("INVALID_ARTIFACT_RELATIVE_PATH")
    if any(part in ("", ".", "..") for part in relative.split("/")):
        raise CampaignError("INVALID_ARTIFACT_RELATIVE_PATH")
    path = Path(parent) / relative
    if path.resolve() != path.absolute() or not path.resolve().is_relative_to(Path(parent).resolve()):
        raise CampaignError("ARTIFACT_PATH_ESCAPES_ROOT")
    return path


def write_new(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as output:
        output.write(content)
        output.flush()
        os.fsync(output.fileno())


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise CampaignError("STATE_FILE_SYMLINK_NOT_ALLOWED")
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    write_new(temporary, json_bytes(value))
    temporary.replace(path)


def freeze_file(path, content):
    if path.exists():
        if read_bytes(path) != content:
            raise CampaignBlocked("FROZEN_ARTIFACT_CHANGED: " + str(path))
    else:
        write_new(path, content)


def _replay_record(record, attempt, payload):
    wire = read_bytes(attempt / "response.wire")
    chunks = [decode_json(line) for line in read_bytes(attempt / "receive.jsonl").splitlines()]
    started_ns = record["timestamps_ns"]["dispatch"]
    metrics = StreamMetrics(payload["model"], started_ns, payload["max_completion_tokens"])
    decoder = SSEDecoder()
    offset = 0
    received_ns = started_ns
    replayed_events = []
    for chunk in chunks:
        if (chunk["offset"] != offset or type(chunk["length"]) is not int or chunk["length"] <= 0
                or offset + chunk["length"] > len(wire)
                or type(chunk["received_ns"]) is not int or chunk["received_ns"] < received_ns):
            raise CampaignError("RAW_RECEIVE_CHUNK_BINDING_MISMATCH")
        received_ns = chunk["received_ns"]
        content = wire[offset:offset + chunk["length"]]
        offset += chunk["length"]
        if payload["stream"]:
            for data, event_ns in decoder.feed(content, received_ns):
                previous_count = len(metrics.token_ids)
                metrics.consume(data, event_ns)
                replayed_events.append({"data": data, "received_ns": event_ns,
                                        "generated_tokens": len(metrics.token_ids) - previous_count})
    if offset != len(wire):
        raise CampaignError("RAW_RECEIVE_BYTES_MISSING")
    events = [decode_json(line) for line in read_bytes(attempt / "events.jsonl").splitlines()]
    if events != replayed_events:
        raise CampaignError("RAW_SSE_EVENT_BINDING_MISMATCH")
    result = (metrics.finalize() if payload["stream"] else
              _nonstream_result(decode_json(wire), payload, started_ns, received_ns))
    if any(record.get(key) != value for key, value in result.items()):
        raise CampaignError("RECORD_DIFFERS_FROM_RAW_RESPONSE")
    if record.get("terminal_received_ns") != result["timestamps_ns"].get("done", received_ns):
        raise CampaignError("RECORD_TERMINAL_TIME_MISMATCH")


class RequestStore:
    def __init__(self, directory, task, payload, protocol_hash, group_id, server_instance=None):
        self.directory = Path(directory)
        self.task = task
        self.payload = payload
        self.wire_payload = json_bytes(payload)
        self.request_hash = digest(self.wire_payload)
        self.protocol_hash = protocol_hash
        self.group_id = group_id
        self.server_instance = server_instance

    def attempts(self):
        if not self.directory.exists():
            return []
        attempts = []
        for path in sorted(self.directory.iterdir()):
            if path.name == "complete.json":
                continue
            if path.is_symlink() or not path.is_dir() or not re.fullmatch(r"attempt-[0-9a-f]{32}", path.name):
                raise CampaignError("UNRECOGNIZED_REQUEST_ARTIFACT")
            attempts.append(path)
        return attempts

    def verify(self, attempt):
        record = read_json(attempt / "record.json")
        if (record.get("protocol_hash") != self.protocol_hash or record.get("request_sha256") != self.request_hash
                or record.get("request") != self.payload or record.get("task_id") != self.task["task_id"]
                or record.get("dataset") != self.task["dataset"] or record.get("group_id") != self.group_id
                or read_bytes(attempt / "request.json") != self.wire_payload):
            raise CampaignError("RESTORED_PROTOCOL_OR_EXACT_REQUEST_HASH_MISMATCH")
        expected_files = {"request.json", "response.wire", "receive.jsonl", "events.jsonl"}
        if set(record.get("artifacts", {})) != expected_files:
            raise CampaignError("REQUEST_ARTIFACT_SET_MISMATCH")
        for relative, expected_hash in record["artifacts"].items():
            if file_hash(child_path(attempt, relative)) != expected_hash:
                raise CampaignError("REQUEST_RAW_ARTIFACT_HASH_MISMATCH")
        if record.get("status") == "COMPLETE":
            _replay_record(record, attempt, self.payload)
        return record

    def restore(self):
        marker = self.directory / "complete.json"
        if marker.exists():
            binding = read_json(marker)
            if binding.get("protocol_hash") != self.protocol_hash or binding.get("request_sha256") != self.request_hash:
                raise CampaignError("RESTORED_PROTOCOL_OR_EXACT_REQUEST_HASH_MISMATCH")
            attempt_name = binding.get("attempt", "")
            if not re.fullmatch(r"attempt-[0-9a-f]{32}", attempt_name):
                raise CampaignError("INVALID_COMPLETE_REQUEST_MARKER")
            attempt = child_path(self.directory, attempt_name)
            if file_hash(attempt / "record.json") != binding.get("record_sha256"):
                raise CampaignError("REQUEST_RECORD_HASH_MISMATCH")
            record = self.verify(attempt)
            if record["status"] != "COMPLETE":
                raise CampaignError("COMPLETE_MARKER_HAS_INCOMPLETE_RESPONSE")
            return record
        completed = []
        for attempt in self.attempts():
            if not (attempt / "record.json").is_file():
                raise CampaignBlocked("UNFINISHED_RECORDING_ATTEMPT_REQUIRES_ADJUDICATION: " + str(attempt))
            record = self.verify(attempt)
            if record["status"] == "COMPLETE":
                completed.append((attempt, record))
        if len(completed) > 1:
            raise CampaignError("DUPLICATED_COMPLETE_PRIMARY_RESPONSE")
        if completed:
            attempt, record = completed[0]
            self._mark_complete(attempt)
            return record
        return None

    def _mark_complete(self, attempt):
        freeze_file(self.directory / "complete.json", json_bytes({
            "attempt": attempt.name, "record_sha256": file_hash(attempt / "record.json"),
            "protocol_hash": self.protocol_hash, "request_sha256": self.request_hash}))

    def begin(self, reserve_retry=None):
        if self.restore() is not None:
            raise CampaignBlocked("COMPLETE_PRIMARY_RESPONSE_CANNOT_BE_DISPATCHED_AGAIN")
        attempts = self.attempts()
        if len(attempts) >= 2:
            raise CampaignBlocked("REQUEST_RETRY_LIMIT_REACHED")
        if attempts:
            if reserve_retry is None:
                raise CampaignBlocked("REQUEST_RETRY_REQUIRES_CAMPAIGN_RESERVE")
            reserve_retry()
        attempt = self.directory / ("attempt-" + uuid.uuid4().hex)
        write_new(attempt / "request.json", self.wire_payload)
        return attempt

    def persist(self, attempt, capture):
        persistence_started = time.monotonic_ns()
        artifacts = {"request.json": self.request_hash}
        for filename, content in (("response.wire", bytes(capture.wire)),
                                  ("receive.jsonl", b"".join(json_bytes(chunk) for chunk in capture.chunks)),
                                  ("events.jsonl", b"".join(json_bytes(event) for event in capture.events))):
            write_new(attempt / filename, content)
            artifacts[filename] = digest(content)
        record = {**capture.record, "task_id": self.task["task_id"], "dataset": self.task["dataset"],
                  "group_id": self.group_id, "protocol_hash": self.protocol_hash,
                  "request_sha256": self.request_hash, "request": self.payload, "artifacts": artifacts,
                  "server_instance": self.server_instance, "attempt": attempt.name,
                  "wire_bytes": len(capture.wire), "buffered_bytes": capture.buffered_bytes,
                  "pre_record_persistence_s": (time.monotonic_ns() - persistence_started) / 1e9}
        write_new(attempt / "record.json", json_bytes(record))
        if record["status"] == "COMPLETE":
            self._mark_complete(attempt)
        return record


class GroupStore:
    def __init__(self, root, group, contract, protocol_hash, identity):
        self.root, self.group = Path(root), group
        self.path = child_path(self.root, "results/" + group.group_id)
        self.path.mkdir(parents=True, exist_ok=True)
        self.protocol_hash = protocol_hash
        self.requests = []
        ordered = []
        for index, task in enumerate(group.tasks):
            payload = request_payload(contract, group, task)
            tag = f"{index:04d}-" + digest(task["task_id"].encode("utf-8"))[:16]
            store = RequestStore(self.path / "requests" / tag, task, payload, protocol_hash, group.group_id)
            self.requests.append(store)
            ordered.append({"task_id": task["task_id"], "dataset": task["dataset"], "request": payload,
                            "request_sha256": store.request_hash})
        content = json_bytes(ordered)
        self.binding = {"group": describe_group(group), "protocol_hash": protocol_hash,
                        "ordered_requests_sha256": digest(content), "identity": identity}
        freeze_file(self.path / "input-binding.json", json_bytes(self.binding))
        freeze_file(self.path / "ordered-requests.json", content)

    def restore(self):
        return {index: record for index, request in enumerate(self.requests) if (record := request.restore()) is not None}

    def load_complete(self):
        marker = self.path / "group-complete.json"
        if not marker.exists():
            return None
        binding = read_json(marker)
        if binding.get("input_binding") != self.binding:
            raise CampaignError("COMPLETE_GROUP_PROTOCOL_OR_REQUESTS_CHANGED")
        if not {"input-binding.json", "ordered-requests.json", "measurement.json", "group-summary.json"}.issubset(binding.get("artifacts", {})):
            raise CampaignError("COMPLETE_GROUP_ARTIFACT_REGISTRY_INCOMPLETE")
        for relative, expected_hash in binding["artifacts"].items():
            if file_hash(child_path(self.path, relative)) != expected_hash:
                raise CampaignError("COMPLETE_GROUP_ARTIFACT_CHANGED: " + relative)
        records = self.restore()
        if len(records) != len(self.requests):
            raise CampaignError("COMPLETE_GROUP_HAS_MISSING_RESPONSES")
        result = read_json(self.path / "group-summary.json")
        if result["completed"] != len(records) or result["status"] != "COMPLETE":
            raise CampaignError("COMPLETE_GROUP_MARKER_COUNT_MISMATCH")
        return result

    def finish(self, result):
        freeze_file(self.path / "group-summary.json", json_bytes(result))
        artifacts = {}
        for path in sorted(self.path.rglob("*")):
            if path.is_symlink():
                raise CampaignError("GROUP_ARTIFACT_SYMLINK_NOT_ALLOWED")
            if path.is_file() and path.name not in ("group-complete.json", "group-state.json"):
                artifacts[path.relative_to(self.path).as_posix()] = file_hash(path)
        freeze_file(self.path / "group-complete.json", json_bytes({
            "input_binding": self.binding, "artifacts": artifacts, "completed": result["completed"],
            "measurement_complete": result["throughput_status"] == "VALID"}))


def dispatch_requests(transport, requests, existing, concurrency, *, reserve_retry=None,
                      on_record=None, on_progress=None):
    """Fixed closed-loop slots; a slot is freed only after its raw record persists."""
    missing = [index for index in range(len(requests)) if index not in existing]
    if not missing:
        return {"records": [existing[index] for index in range(len(requests))], "new_records": [],
                "start_ns": None, "end_ns": None, "resumed": True}
    initial_count = min(concurrency, len(missing))
    barrier = threading.Barrier(initial_count + 1)
    completed = dict(existing)
    fresh = {}
    first_error = None
    pool = ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="campaign-http")

    def execute(index, initial=False):
        if initial:
            barrier.wait(timeout=30)
        transport.check()
        store = requests[index]
        attempt = store.begin(reserve_retry)
        try:
            capture = collect_request(transport, store.payload, wire_payload=store.wire_payload)
        except RequestFailure as error:
            store.persist(attempt, error.capture)
            raise
        record = store.persist(attempt, capture)
        if on_record is not None:
            on_record(record)
        return record

    pending = {}
    cursor = initial_count
    start_ns = None
    try:
        transport.check()
        for index in missing[:initial_count]:
            pending[pool.submit(execute, index, True)] = index
        start_ns = time.monotonic_ns()
        barrier.wait(timeout=30)
        while pending:
            transport.check()
            done, unused = wait(pending, timeout=0.2, return_when=FIRST_COMPLETED)
            for future in done:
                index = pending.pop(future)
                try:
                    record = future.result()
                    completed[index] = fresh[index] = record
                except BaseException as error:
                    first_error = first_error or error
            if first_error is not None:
                raise first_error
            if done and on_progress is not None:
                on_progress(len(completed), len(requests))
            for unused_future in done:
                if cursor < len(missing):
                    transport.check()
                    index = missing[cursor]
                    cursor += 1
                    pending[pool.submit(execute, index)] = index
    except BaseException:
        barrier.abort()
        transport.cancel()
        raise
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
    end_ns = max(record["terminal_received_ns"] for record in fresh.values())
    return {"records": [completed[index] for index in range(len(requests))],
            "new_records": [fresh[index] for index in sorted(fresh)], "start_ns": start_ns,
            "end_ns": end_ns, "resumed": bool(existing)}


def take_snapshot(transport, path, model, server_instance, engine=None):
    transport.check()
    started_ns, started_utc = time.monotonic_ns(), utcnow()
    content = bytearray()
    query_error = None
    status = None
    try:
        with transport.open("/metrics", timeout=30) as response:
            status = response.status
            while chunk := response.read1(65536):
                transport.check()
                if len(content) + len(chunk) > 16 * 1024 * 1024:
                    raise CampaignError("METRICS_BODY_LIMIT_EXCEEDED")
                content.extend(chunk)
            if status != 200:
                raise CampaignError("METRICS_HTTP_ERROR_" + str(status))
    except BaseException as error:
        query_error = error
    finally:
        ended_ns = time.monotonic_ns()
        write_new(path, bytes(content))
        receipt = {"started_ns": started_ns, "ended_ns": ended_ns, "query_time_s": (ended_ns - started_ns) / 1e9,
                   "started_utc": started_utc, "ended_utc": utcnow(), "http_status": status,
                   "sha256": digest(content), "server_instance": server_instance, "path": str(path)}
        write_new(path.with_suffix(".query.json"), json_bytes(receipt))
    if query_error is not None:
        raise query_error
    snapshot = parse_metrics(content.decode("utf-8"), model, engine)
    return {**snapshot, **receipt}


def load_inputs(root):
    root = Path(root).resolve()
    contract_bytes = read_bytes(child_path(root, "src/experiment.json"))
    contract = decode_json(contract_bytes.decode("utf-8-sig"))
    task_bytes = read_bytes(child_path(root, "data/tasks.jsonl"))
    inputs = read_json(child_path(root, "metadata/inputs.json"))
    if inputs.get("manifest_sha256") != digest(task_bytes):
        raise CampaignBlocked("INPUT_MANIFEST_SHA256_MISMATCH")
    tasks = [decode_json(line) for line in task_bytes.splitlines() if line.strip()]
    groups = build_groups(contract, tasks)
    code = {}
    for filename in ("campaign_runner.py", "stream_metrics.py", "scoring.py", "prepare_runtime.py"):
        code[filename] = file_hash(child_path(root, "src/" + filename))
    if file_hash(Path(__file__)) != code["campaign_runner.py"]:
        raise CampaignBlocked("RUNNER_NOT_BOUND_TO_ROOT_SRC_BYTES")
    return contract, tasks, groups, digest(contract_bytes), {
        "tasks_sha256": digest(task_bytes), "inputs_sha256": file_hash(root / "metadata/inputs.json"),
        "source_sha256": code}


def safe_environment(cache):
    allowed = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LD_LIBRARY_PATH",
               "CUDA_HOME", "CUDA_PATH", "CUDA_VISIBLE_DEVICES", "TMPDIR", "OMP_NUM_THREADS")
    environment = {name: os.environ[name] for name in allowed if name in os.environ}
    environment.update({"VLLM_USE_V2_MODEL_RUNNER": "1", "HF_HUB_OFFLINE": "1",
                        "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",
                        "HF_HUB_DISABLE_TELEMETRY": "1", "HF_HOME": str(Path(cache) / "hf"),
                        "VLLM_CACHE_ROOT": str(Path(cache) / "vllm-cache"),
                        "TORCHINDUCTOR_CACHE_DIR": str(Path(cache) / "torch-cache"),
                        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1",
                        "PYTHONNOUSERSITE": "1"})
    return environment


def cli_options(arguments):
    if not isinstance(arguments, list) or any(not isinstance(value, str) or "\x00" in value for value in arguments):
        raise CampaignBlocked("INVALID_PREPARED_CLI_ARGUMENTS")
    options = {}
    index = 0
    while index < len(arguments):
        option = arguments[index]
        if not option.startswith("--") or "=" in option or option in options:
            raise CampaignBlocked("AMBIGUOUS_PREPARED_CLI_ARGUMENT")
        if option == "--no-enable-prefix-caching":
            options[option] = True
            index += 1
        else:
            if index + 1 >= len(arguments) or arguments[index + 1].startswith("--"):
                raise CampaignBlocked("PREPARED_CLI_VALUE_MISSING")
            options[option] = arguments[index + 1]
            index += 2
    return options


@dataclass(frozen=True)
class RuntimePlan:
    python: str
    routes: dict
    models: dict
    environment: dict
    identity: dict
    engine_metadata: dict


def load_runtime_plan(root, cache, contract, *, guard=None, verify_weights=True):
    root, cache = Path(root).resolve(), Path(cache).resolve()
    metadata = root / "metadata"
    engine_path = metadata / "engine-args-preflight.json"
    if not engine_path.exists():
        engine_path = metadata / "engine-args.json"
    engine = read_json(engine_path)
    if (engine.get("status") != "ARGUMENT_PARSER_AND_CONSTRUCTOR_VALIDATED"
            or engine.get("vllm_version") != contract["serving"]["vllm_version"]
            or engine.get("runner_env") != contract["serving"]["runner_env"]
            or not isinstance(engine.get("routes"), dict) or set(engine["routes"]) != set(ROUTES)):
        raise CampaignBlocked("PREPARED_ENGINE_METADATA_CONTRACT_UNVERIFIED")
    runtime_path = metadata / "runtime.json"
    runtime = read_json(runtime_path) if runtime_path.exists() else {}
    python = Path(runtime.get("python") or cache / "venv/bin/python")
    if not python.is_absolute() or not python.is_file():
        raise CampaignBlocked("PREPARED_PYTHON_PATH_UNAVAILABLE")
    if runtime.get("wheel_verification", {}).get("matches") is not True:
        raise CampaignBlocked("OFFICIAL_RUNTIME_WHEEL_VERIFICATION_MISSING")
    sources = engine.get("sources")
    if not isinstance(sources, dict) or set(sources) != {"engine_args", "api_parser", "envs"}:
        raise CampaignBlocked("PREPARED_INSTALLED_SOURCE_IDENTITIES_MISSING")
    for label, source in sources.items():
        if (file_hash(metadata / ("source-" + label + ".py"), guard) != source["sha256"]
                or (verify_weights and file_hash(Path(source["installed_path"]), guard) != source["sha256"])):
            raise CampaignBlocked("PREPARED_INSTALLED_SOURCE_BYTES_CHANGED: " + label)
    inventories = read_json(metadata / "models.json")
    for role in ("target", "draft"):
        inventory = inventories.get(role, {})
        expected = contract[role]
        if inventory.get("model_id") != expected["model_id"] or inventory.get("revision") != expected["revision"]:
            raise CampaignBlocked("PREPARED_MODEL_IDENTITY_MISMATCH: " + role)
        directory = Path(inventory.get("path", ""))
        if not directory.is_absolute() or directory.resolve() != directory or not directory.is_relative_to(cache):
            raise CampaignBlocked("PREPARED_MODEL_PATH_OUTSIDE_CACHE: " + role)
        if role == "draft" and expected["required_architecture"] not in inventory.get("architectures", []):
            raise CampaignBlocked("PREPARED_DFLASH2_ARCHITECTURE_MISMATCH")
        files = inventory.get("files")
        if not isinstance(files, dict) or "config.json" not in files or not any(name.endswith(".safetensors") for name in files):
            raise CampaignBlocked("PREPARED_MODEL_FILE_INVENTORY_MISSING")
        if verify_weights:
            for relative, facts in files.items():
                if guard is not None:
                    guard()
                path = child_path(directory, relative)
                if path.stat().st_size != facts["bytes"] or file_hash(path, guard) != facts["sha256"]:
                    raise CampaignBlocked("PREPARED_MODEL_BYTES_CHANGED: " + role + "/" + relative)
    attention_field, ssm_field = engine.get("attention_field"), engine.get("ssm_field")
    if attention_field not in ("attention_backend", "attention_config") or not isinstance(ssm_field, str) or not re.fullmatch(r"[a-z_]*ssm_cache_dtype", ssm_field):
        raise CampaignBlocked("PREPARED_ATTENTION_OR_SSM_ENTRY_UNVERIFIED")
    shared = None
    routes = {}
    serving = contract["serving"]
    required = {"--model": inventories["target"]["path"], "--dtype": contract["target"]["dtype"],
                "--tensor-parallel-size": str(serving["tensor_parallel_size"]),
                "--max-model-len": str(serving["max_model_len"]), "--max-num-seqs": str(serving["max_num_seqs"]),
                "--max-num-batched-tokens": str(serving["max_num_batched_tokens"]),
                "--gpu-memory-utilization": str(serving["gpu_memory_utilization"]),
                "--no-enable-prefix-caching": True, "--kv-cache-dtype": "auto",
                "--reasoning-parser": serving["reasoning_parser"], "--stream-interval": str(serving["stream_interval"])}
    allowed = set(required) | {"--speculative-config", "--" + attention_field.replace("_", "-"),
                               "--" + ssm_field.replace("_", "-")}
    for route in contract["routes"]:
        arguments = engine["routes"][route["name"]].get("cli_arguments")
        options = cli_options(arguments)
        if set(options) - allowed or any(options.get(key) != value for key, value in required.items()):
            raise CampaignBlocked("PREPARED_ROUTE_COMMON_ARGUMENTS_MISMATCH: " + route["name"])
        expected_spec = None
        if route["method"] is not None:
            expected_spec = {"method": route["method"], "num_speculative_tokens": route["num_speculative_tokens"],
                             "rejection_sample_method": serving["rejection_sample_method"]}
            if route["method"] == "dflash":
                expected_spec["model"] = inventories["draft"]["path"]
        actual_spec = decode_json(options["--speculative-config"]) if "--speculative-config" in options else None
        if actual_spec != expected_spec:
            raise CampaignBlocked("PREPARED_SPECULATION_METHOD_OR_WINDOW_MISMATCH")
        common = {key: value for key, value in options.items() if key != "--speculative-config"}
        if any("--" + name.replace("_", "-") not in common for name in (attention_field, ssm_field)):
            raise CampaignBlocked("PREPARED_SHARED_POLICY_MISSING")
        if shared is not None and common != shared:
            raise CampaignBlocked("ROUTES_DO_NOT_SHARE_TARGET_AND_ENGINE_POLICY")
        shared = common
        routes[route["name"]] = list(arguments)
    help_path = metadata / "vllm-api-help.txt"
    help_text = read_bytes(help_path).decode("utf-8")
    for option in ("--served-model-name", "--host", "--port", "--generation-config", "--seed", "--limit-mm-per-prompt"):
        if option not in help_text:
            raise CampaignBlocked("APPENDED_RUNTIME_CLI_ENTRY_UNVERIFIED: " + option)
    preparation = read_json(metadata / "preparation-input.json")
    if preparation.get("contract_sha256") != file_hash(root / "src/experiment.json"):
        raise CampaignBlocked("PREPARATION_CONTRACT_HASH_MISMATCH")
    identity = {path.name: file_hash(path) for path in (engine_path, runtime_path, metadata / "models.json",
                metadata / "preparation-input.json", help_path, metadata / "runtime-artifact.json", metadata / "evaluator-image.json")}
    return RuntimePlan(str(python), routes, inventories, safe_environment(cache), identity, engine)


def server_command(plan, contract, route, port):
    if route not in ROUTES or type(port) is not int or not 0 < port < 65536:
        raise CampaignError("INVALID_SERVER_ROUTE_OR_PORT")
    return [plan.python, "-I", "-B", "-m", "vllm.entrypoints.openai.api_server", *plan.routes[route],
            "--served-model-name", contract["target"]["model_id"], "--host", "127.0.0.1", "--port", str(port),
            "--generation-config", "vllm", "--seed", str(contract["sampling"]["seed"]),
            "--limit-mm-per-prompt", json.dumps({"image": 0, "video": 0, "audio": 0}, separators=(",", ":"))]


def listening_inodes(port):
    inodes = set()
    for line in Path("/proc/net/tcp").read_text().splitlines()[1:]:
        fields = line.split()
        if fields[1].upper() == f"0100007F:{port:04X}" and fields[3] == "0A":
            inodes.add(fields[9])
    return inodes


def listener_owned(port, process_group):
    if sys.platform != "linux":
        raise CampaignBlocked("LISTENER_OWNERSHIP_REQUIRES_LINUX_PROCFS")
    inodes = listening_inodes(port)
    if not inodes:
        return False
    owners = set()
    for path in Path("/proc").iterdir():
        if not path.name.isdigit():
            continue
        try:
            group = os.getpgid(int(path.name))
            for descriptor in (path / "fd").iterdir():
                target = os.readlink(descriptor)
                if target.startswith("socket:[") and target[8:-1] in inodes:
                    owners.add(group)
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    return owners == {process_group}


class OwnedProcess:
    def __init__(self, argv, environment, log_path, *, cwd=None):
        self.argv, self.environment, self.log_path = argv, environment, Path(log_path)
        self.cwd, self.process, self.output = cwd, None, None
        self.instance = uuid.uuid4().hex
        self.started_ns = None

    def start(self):
        if sys.platform != "linux":
            raise CampaignBlocked("MODEL_AND_SCORER_EXECUTION_REQUIRES_LINUX")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.output = self.log_path.open("xb")
        self.started_ns = time.monotonic_ns()
        try:
            self.process = subprocess.Popen(self.argv, env=self.environment, cwd=self.cwd,
                                            stdin=subprocess.DEVNULL, stdout=self.output,
                                            stderr=subprocess.STDOUT, start_new_session=True)
            write_new(self.log_path.with_suffix(".command.json"), json_bytes({
                "argv": self.argv, "environment": self.environment, "cwd": str(self.cwd) if self.cwd else None,
                "server_instance": self.instance, "pid": self.process.pid, "process_group": self.process.pid,
                "started_ns": self.started_ns, "started_utc": utcnow()}))
            return self
        except BaseException:
            if self.process is None:
                self.output.close()
            raise

    def alive(self):
        if self.process is None:
            return False
        try:
            os.killpg(self.process.pid, 0)
            return True
        except ProcessLookupError:
            return False

    def send(self, signum):
        if self.process is not None:
            try:
                os.killpg(self.process.pid, signum)
            except ProcessLookupError:
                pass

    @staticmethod
    def stop_all(processes):
        processes = [process for process in processes if process is not None]
        waiter = threading.Event()
        remaining = list(processes)
        for signum, grace in ((signal.SIGTERM, 60), (signal.SIGKILL, 30)):
            for process in remaining:
                process.send(signum)
            deadline = time.monotonic() + grace
            while remaining and time.monotonic() < deadline:
                active = []
                for process in remaining:
                    if process.process is not None:
                        process.process.poll()
                    if process.alive():
                        active.append(process)
                remaining = active
                if remaining:
                    waiter.wait(min(0.2, max(0, deadline - time.monotonic())))
        receipts = []
        for process in processes:
            receipt = {"instance": process.instance, "pid": process.process.pid if process.process else None,
                       "returncode": process.process.poll() if process.process else None,
                       "status": "CLEANUP_UNCONFIRMED" if process in remaining else "STOPPED",
                       "finished_utc": utcnow(), "log": str(process.log_path),
                       "fallback_owner": "independent systemd RuntimeMaxSec and finalizer"}
            if process.output is not None:
                process.output.close()
            write_json(process.log_path.with_suffix(".exit.json"), receipt)
            receipts.append(receipt)
        return receipts


class Server:
    def __init__(self, root, plan, contract, port, transport, update):
        self.root, self.plan, self.contract = Path(root), plan, contract
        self.port, self.transport, self.update = port, transport, update
        self.owned = None
        self.route = None
        self.epoch = None
        self.model_readback = None
        self.startup_s = 0.0

    def ensure(self, group):
        restart = (self.owned is None or self.route != group.route
                   or (group.stage == "G" and group.repetition == 3)
                   or (group.stage == "S" and self.epoch != group.server_epoch))
        if not restart:
            self.check()
            self.epoch = group.server_epoch
            self.startup_s = 0.0
            return
        if self.owned is not None:
            receipts = OwnedProcess.stop_all([self.owned])
            if any(receipt["status"] != "STOPPED" for receipt in receipts):
                raise CampaignBlocked("PREVIOUS_OWNED_SERVER_CLEANUP_UNCONFIRMED")
        self.transport.check()
        # After the previous owned server exits, the kernel may hold the port
        # briefly (TIME_WAIT); only a real LISTEN socket is a foreign owner.
        deadline = time.monotonic() + 30
        while True:
            if sys.platform == "linux" and listening_inodes(self.port):
                raise CampaignBlocked("LOCAL_PORT_ALREADY_OWNED; existing listener untouched")
            with socket.socket() as probe:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    probe.bind(("127.0.0.1", self.port))
                    break
                except OSError as error:
                    if time.monotonic() >= deadline:
                        raise CampaignBlocked("LOCAL_PORT_NOT_RELEASED_WITHIN_30S") from error
            self.transport.stop.wait(0.5)
        path = self.root / "logs" / f"server-{group.route}-{uuid.uuid4().hex}.log"
        self.owned = OwnedProcess(server_command(self.plan, self.contract, group.route, self.port),
                                  self.plan.environment, path)
        self.route, self.epoch = group.route, group.server_epoch
        self.update("SERVER_STARTING", latest_route=group.route, latest_log=str(path))
        self.owned.start()
        deadline = time.monotonic() + 1800
        while time.monotonic() < deadline:
            self.check()
            try:
                with self.transport.open("/v1/models", timeout=5) as response:
                    content = response.read(1024 * 1024 + 1)
                    if len(content) > 1024 * 1024:
                        raise CampaignError("MODEL_READBACK_TOO_LARGE")
                    if response.status != 200:
                        raise urllib.error.URLError("model endpoint not ready")
                    models = decode_json(content)
                selected = [model for model in models.get("data", []) if model.get("id") == self.contract["target"]["model_id"]]
                if len(selected) != 1:
                    raise CampaignBlocked("SERVED_TARGET_IDENTITY_MISMATCH")
                if (selected[0].get("root") != self.plan.models["target"]["path"]
                        or selected[0].get("max_model_len") != self.contract["serving"]["max_model_len"]):
                    raise CampaignBlocked("SERVED_TARGET_ROOT_OR_CONTEXT_UNVERIFIED")
                if not listener_owned(self.port, self.owned.process.pid):
                    raise CampaignBlocked("LISTENER_NOT_OWNED_BY_THIS_SERVER_PROCESS_GROUP")
                self.check()
                self.model_readback = models
                write_new(self.root / "metadata" / f"served-models-{self.owned.instance}.json", content)
                self.startup_s = (time.monotonic_ns() - self.owned.started_ns) / 1e9
                self.update("SERVER_READY", latest_route=group.route, latest_log=str(path),
                            server_instance=self.owned.instance, server_pid=self.owned.process.pid)
                return
            except (urllib.error.URLError, ConnectionError, TimeoutError):
                self.transport.stop.wait(0.5)
        raise CampaignBlocked("SERVER_READINESS_DEADLINE_EXCEEDED: " + str(path))

    def check(self):
        self.transport.check()
        if self.owned is not None and self.owned.process is not None:
            returncode = self.owned.process.poll()
            if returncode is not None:
                raise CampaignError(f"SERVER_EXITED rc={returncode}; log={self.owned.log_path}")

    def loaded_evidence(self, engine_metrics):
        self.check()
        text = read_bytes(self.owned.log_path).decode("utf-8", errors="replace")
        patterns = {
            "weights_loaded": r"(?i)(model loading took|loading model weights took|loading weights took)",
            "v2_runner": r"(?i)(using (?:the )?(?:model runner v2|v2 model runner)|GPUModelRunnerV2|V2ModelRunner|ModelRunnerV2)",
            "target_bfloat16": r"(?i)(?:dtype[=: ]+['\"]?(?:torch\.)?bfloat16)",
            # vLLM 0.28 logs kv_cache_dtype=auto; auto resolves to the model dtype (bfloat16 here).
            "kv_cache_bfloat16": r"(?i)(?:kv[ _-]cache.{0,50}(?:dtype|type).{0,12}(?:torch\.)?bfloat16|kv_cache_dtype[=: ]+['\"]?(?:(?:torch\.)?bfloat16|auto)\b)",
        }
        matches = {name: [line for line in text.splitlines() if re.search(pattern, line)][:8]
                   for name, pattern in patterns.items()}
        if self.route == "dflash2_7":
            matches["draft_architecture"] = [line for line in text.splitlines() if "DFlash2DraftModel" in line][:8]
        evidence = {"server_instance": self.owned.instance, "route": self.route,
                    "model_readback": self.model_readback, "prepared_identity": self.plan.identity,
                    "log": str(self.owned.log_path), "matches": matches,
                    "active_speculation": engine_metrics["speculation"],
                    "status": "OBSERVED" if all(matches.values()) else "UNVERIFIED_RUNTIME_TRACE"}
        write_json(self.root / "metadata" / f"loaded-{self.owned.instance}.json", evidence)
        if not all(matches.values()):
            raise CampaignBlocked("ACTUAL_RUNTIME_TRACE_GATE: " + ",".join(name for name, lines in matches.items() if not lines))
        return evidence


def score_worker(root, group_dir, image, run_id):
    from scoring import score_group

    def interrupted(signum, frame):
        raise CampaignBlocked("SCORER_CANCELLED_SIGNAL_" + str(signum))

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    group_dir = Path(group_dir)
    records = read_json(group_dir / "records-for-scoring.json")
    result = score_group(Path(root), group_dir, records, image, run_id)
    freeze_file(group_dir / "scoring-result.json", json_bytes(result))


def greedy_diagnostics(groups, stores, results):
    diagnostic_groups = [group for group in groups if group.stage == "G"]
    rows = []
    for first in diagnostic_groups:
        if first.repetition != 1:
            continue
        matched = [group for group in diagnostic_groups if (group.route, group.concurrency, group.thinking) ==
                   (first.route, first.concurrency, first.thinking)]
        if len(matched) != 3 or any(group.group_id not in results for group in matched):
            raise CampaignBlocked("G_DIAGNOSTIC_REPETITIONS_INCOMPLETE")
        repetitions = [stores[group.group_id].restore() for group in matched]
        instances = []
        for records in repetitions:
            unique = {record["server_instance"] for record in records.values()}
            if len(unique) != 1 or not next(iter(unique)):
                raise CampaignBlocked("G_REPETITION_SPLIT_ACROSS_SERVER_PROCESSES")
            instances.append(next(iter(unique)))
        if instances[0] != instances[1] or instances[0] == instances[2]:
            raise CampaignBlocked("G_SAME_PROCESS_THEN_RESTART_CONTRACT_UNMET")
        for index, task in enumerate(first.tasks):
            records = [repetition[index] for repetition in repetitions]
            token_lists = [record["token_ids"] for record in records]

            def divergence(left, right):
                return next((position for position in range(max(len(left), len(right)))
                             if position >= len(left) or position >= len(right) or left[position] != right[position]), None)

            rows.append({"route": first.route, "concurrency": first.concurrency, "thinking": first.thinking,
                         "task_id": task["task_id"], "server_instances": instances,
                         "token_hashes": [digest(json_bytes(tokens)) for tokens in token_lists],
                         "logprob_hashes": [digest(json_bytes(record["logprobs"])) for record in records],
                         "same_process_tokens_equal": token_lists[0] == token_lists[1],
                         "restart_tokens_equal": token_lists[0] == token_lists[2],
                         "first_divergence_same_process": divergence(token_lists[0], token_lists[1]),
                         "first_divergence_restart": divergence(token_lists[0], token_lists[2]),
                         "attribution": "NOT_ESTABLISHED; API logprobs are not internal verifier tensors"})
    return {"status": "DIAGNOSTIC_RECORDED", "rows": rows, "accuracy_scored": False,
            "distribution_equivalence_proven": False}


class Campaign:
    def __init__(self, root, cache, contract, tasks, groups, protocol_hash, identity, plan, budget,
                 image="dflash-quality-eval:20260905", port=18080):
        self.root, self.cache = Path(root), Path(cache)
        self.contract, self.tasks, self.groups = contract, tasks, groups
        self.protocol_hash = protocol_hash
        self.identity = {**identity, "runtime_metadata_sha256": plan.identity, "image": image,
                         "environment": plan.environment}
        self.plan, self.budget, self.image = plan, budget, image
        self.transport = LocalHTTP(port, budget)
        self.stores, self.results, self.partial_counts = {}, {}, {}
        self.lock = threading.RLock()
        self.telemetry, self.scorer = None, None
        self.server = Server(root, plan, contract, port, self.transport, self.update)
        self.state = {"run_id": contract["run_id"], "status": "RUNNING", "phase": "RUNNING",
                      "stage": "INITIALIZING", "completed": 0, "total": contract["planned_measured_responses"],
                      "groups_completed": 0, "groups_total": len(groups), "latest_route": None,
                      "latest_group": None, "latest_log": None, "diagnostic_extra_responses": 0,
                      "billing_start": budget.start_epoch, "stop_new_work_epoch": budget.deadline_epoch,
                      "model_execution_status": "NOT_RUN", "protocol_hash": protocol_hash}
        self.prompt_lock = threading.Lock()
        self.prompt_bindings = {}

    def store(self, group):
        if group.group_id not in self.stores:
            self.stores[group.group_id] = GroupStore(self.root, group, self.contract, self.protocol_hash, self.identity)
        return self.stores[group.group_id]

    def update(self, event, **fields):
        with self.lock:
            self.state.update(fields, event=event, updated_utc=utcnow(), budget_remaining_s=self.budget.remaining())
            self.state["phase"] = self.state["status"]
            write_json(self.root / "state/campaign.json", self.state)
            with (self.root / "logs/campaign-events.jsonl").open("ab") as output:
                output.write(json_bytes(self.state))
                output.flush()
            print(json.dumps(self.state, ensure_ascii=True, allow_nan=False), flush=True)

    def reserve_retry(self):
        with self.lock:
            self.transport.check()
            if self.state["diagnostic_extra_responses"] >= self.contract["diagnostic_extra_response_cap"]:
                raise CampaignBlocked("CAMPAIGN_DIAGNOSTIC_RESERVE_EXHAUSTED")
            self.update("RESUMING_FAILED_MEASUREMENT_ONCE",
                        diagnostic_extra_responses=self.state["diagnostic_extra_responses"] + 1)

    def bind_prompt(self, record):
        payload = record["request"]
        identity = {key: payload[key] for key in ("model", "messages", "chat_template_kwargs")}
        identity["reasoning_effort"] = payload.get("reasoning_effort")
        key = digest(json_bytes(identity))
        binding = {"input": identity, "prompt_token_ids": record["prompt_token_ids"],
                   "target_revision": self.contract["target"]["revision"]}
        with self.prompt_lock:
            previous = self.prompt_bindings.get(key)
            if previous is not None and previous != binding:
                raise CampaignBlocked("ACTUAL_RENDERED_PROMPT_TOKEN_MISMATCH")
            freeze_file(self.root / "metadata/prompt-bindings" / (key + ".json"), json_bytes(binding))
            self.prompt_bindings[key] = binding

    def restore_completed(self):
        retries = 0
        for group in self.groups:
            self.transport.check()
            path = self.root / "results" / group.group_id
            if not path.exists():
                continue
            store = self.store(group)
            previous = store.load_complete()
            records = store.restore()
            self.partial_counts[group.group_id] = len(records)
            for record in records.values():
                self.bind_prompt(record)
            for request in store.requests:
                retries += max(0, len(request.attempts()) - 1)
            if previous is not None:
                self.results[group.group_id] = previous
        self.update("RESTORE_VALIDATED", diagnostic_extra_responses=retries,
                    completed=sum(self.partial_counts.values()), groups_completed=len(self.results))

    def warmup(self, group):
        self.server.check()
        by_id = {task["task_id"]: task for task in self.tasks}
        ids = self.contract["serving_checks"]["greedy_diagnostic"]["task_ids"]
        fixed = [by_id[ids[0]], by_id[ids[2]]]
        directory = self.store(group).path / "warmups" / ("attempt-" + uuid.uuid4().hex)
        started = time.monotonic()
        for wave in range(2 if group.stage == "G" else 1):
            self.transport.check()
            requests = []
            for index in range(group.concurrency):
                task = fixed[(index + wave) % len(fixed)]
                requests.append(RequestStore(directory / f"wave-{wave + 1}" / f"request-{index:02d}", task,
                    request_payload(self.contract, group, task, warmup=True), self.protocol_hash,
                    group.group_id + f"-warmup-{wave + 1}", self.server.owned.instance))
            self.update("WARMUP", latest_route=group.route, latest_group=group.group_id,
                        warmup_wave=wave + 1, warmup_requests=group.concurrency)
            dispatch_requests(self.transport, requests, {}, group.concurrency, on_record=self.bind_prompt)
        return time.monotonic() - started

    def score(self, store, records):
        self.transport.check()
        freeze_file(store.path / "records-for-scoring.json", json_bytes(records))
        argv = [sys.executable, "-B", "-c",
                "from campaign_runner import score_worker; import sys; score_worker(*sys.argv[1:])",
                str(self.root), str(store.path), self.image, self.contract["run_id"]]
        self.scorer = OwnedProcess(argv, self.plan.environment,
                                  self.root / "logs" / f"scorer-{store.group.group_id}-{uuid.uuid4().hex}.log",
                                  cwd=Path(__file__).resolve().parent)
        self.update("OFFICIAL_SCORING", latest_log=str(self.scorer.log_path))
        self.scorer.start()
        while self.scorer.process.poll() is None:
            self.transport.check()
            self.transport.stop.wait(0.2)
        if self.scorer.process.returncode:
            raise CampaignError(f"OFFICIAL_SCORER_FAILED rc={self.scorer.process.returncode}; log={self.scorer.log_path}")
        self.transport.check()
        result = read_json(store.path / "scoring-result.json")
        prepared_image = read_json(self.root / "metadata/evaluator-image.json")
        if result["identity"]["image_id"] != prepared_image.get("id") or prepared_image.get("image") != self.image:
            raise CampaignBlocked("OFFICIAL_SCORER_IMAGE_CHANGED_SINCE_PREPARATION")
        if set(result["by_task"]) != {record["task_id"] for record in records}:
            raise CampaignError("OFFICIAL_SCORE_TASK_SET_MISMATCH")
        for record in records:
            if result["by_task"][record["task_id"]]["finish_reason"] != record["finish_reason"]:
                raise CampaignError("OFFICIAL_SCORE_FINISH_BINDING_MISMATCH")
        receipts = OwnedProcess.stop_all([self.scorer])
        if any(receipt["status"] != "STOPPED" for receipt in receipts):
            raise CampaignBlocked("SCORER_CLEANUP_UNCONFIRMED")
        self.scorer = None
        return result

    def _g_pair_gate(self, group, existing):
        if group.stage != "G":
            return
        if existing and len(existing) != len(group.tasks):
            raise CampaignBlocked("G_PARTIAL_REPETITION_CANNOT_CHANGE_SERVER_PROCESS")
        if group.repetition != 2 or len(existing) == len(group.tasks):
            return
        first = next(candidate for candidate in self.groups if candidate.stage == "G"
                     and (candidate.route, candidate.concurrency, candidate.thinking, candidate.repetition) ==
                     (group.route, group.concurrency, group.thinking, 1))
        reference = self.results.get(first.group_id)
        if (reference is None or self.server.owned is None
                or reference.get("server_instance") != self.server.owned.instance):
            raise CampaignBlocked("G_REPEAT2_ORIGINAL_SERVER_NO_LONGER_AVAILABLE")

    def run_group(self, group):
        store = self.store(group)
        cached = store.load_complete()
        if cached is not None:
            return cached
        existing = store.restore()
        self._g_pair_gate(group, existing)
        self.partial_counts[group.group_id] = len(existing)
        before_group_completed = sum(value for key, value in self.partial_counts.items() if key != group.group_id)
        self.update("GROUP_START", stage=group.stage, latest_route=group.route, latest_group=group.group_id,
                    group_completed=len(existing), group_total=len(group.tasks),
                    completed=before_group_completed + len(existing), total=self.contract["planned_measured_responses"])
        group_started = time.monotonic()
        measurement_path = store.path / "measurement.json"
        try:
            if len(existing) < len(group.tasks):
                if measurement_path.exists():
                    raise CampaignError("PRIMARY_MEASUREMENT_EXISTS_BUT_RESPONSES_ARE_MISSING")
                self.server.ensure(group)
                for request in store.requests:
                    request.server_instance = self.server.owned.instance
                warmup_s = self.warmup(group)
                measurement_directory = store.path / "measurements" / ("attempt-" + uuid.uuid4().hex)
                before = take_snapshot(self.transport, measurement_directory / "metrics-before.txt",
                                       self.contract["target"]["model_id"], self.server.owned.instance)
                before["relative_path"] = (measurement_directory / "metrics-before.txt").relative_to(store.path).as_posix()
                log_offset = self.server.owned.log_path.stat().st_size

                def progress(completed, total):
                    self.server.check()
                    self.partial_counts[group.group_id] = completed
                    self.update("GROUP_PROGRESS", group_completed=completed, group_total=total,
                                completed=before_group_completed + completed)

                self.update("MEASURING", model_execution_status="IN_PROGRESS", latest_log=str(self.server.owned.log_path))
                measured = dispatch_requests(self.transport, store.requests, existing, group.concurrency,
                                             reserve_retry=self.reserve_retry, on_record=self.bind_prompt, on_progress=progress)
                self.server.check()
                log_end = self.server.owned.log_path.stat().st_size
                records = measured["records"]
                after = take_snapshot(self.transport, measurement_directory / "metrics-after.txt", self.contract["target"]["model_id"],
                                      self.server.owned.instance, before["engine"])
                after["relative_path"] = (measurement_directory / "metrics-after.txt").relative_to(store.path).as_posix()
                capture = {"records_sha256": digest(json_bytes(records)), "resumed": measured["resumed"],
                           "start_ns": measured["start_ns"], "end_ns": measured["end_ns"],
                           "new_task_ids": [record["task_id"] for record in measured["new_records"]],
                           "before": before, "after": after, "warmup_s": warmup_s,
                           "server_instance": self.server.owned.instance, "server_startup_s": self.server.startup_s}
                write_new(measurement_directory / "measurement-capture.json", json_bytes(capture))
                wall = None if measured["resumed"] else (measured["end_ns"] - measured["start_ns"]) / 1e9
                engine_metrics = reconcile_metrics(before, after, measured["new_records"], group.route, wall)
                engine_metrics["snapshot_interval_s"] = (after["started_ns"] - before["ended_ns"]) / 1e9
                engine_metrics["coverage"] = "resumed_segment_only" if measured["resumed"] else "entire_group"
                loaded = self.server.loaded_evidence(engine_metrics)
                with self.server.owned.log_path.open("rb") as source:
                    source.seek(log_offset)
                    log_slice = source.read(log_end - log_offset)
                write_new(store.path / "measured-server.log", log_slice)
                measurement = {**capture, "engine": engine_metrics, "loaded": loaded,
                               "cold_start_contamination": bool(re.search(rb"(?i)compil|cudagraph.*captur|\bJIT\b", log_slice))}
                write_new(measurement_path, json_bytes(measurement))
            else:
                records = [existing[index] for index in range(len(store.requests))]
                if not measurement_path.exists():
                    raise CampaignBlocked("COMPLETE_RESPONSES_NEED_ORIGINAL_METRICS_OR_RUNTIME_ADJUDICATION; no regeneration")
                measurement = read_json(measurement_path)
                if measurement["records_sha256"] != digest(json_bytes(records)):
                    raise CampaignError("ORIGINAL_MEASUREMENT_RESPONSE_HASH_MISMATCH")
                for name in ("before", "after"):
                    snapshot = measurement[name]
                    path = child_path(store.path, snapshot["relative_path"])
                    if file_hash(path) != snapshot["sha256"]:
                        raise CampaignError("ORIGINAL_METRIC_SNAPSHOT_HASH_MISMATCH")
                    parsed = parse_metrics(read_bytes(path).decode("utf-8"), snapshot["model"], snapshot["engine"])
                    if parsed["series"] != snapshot["series"]:
                        raise CampaignError("ORIGINAL_METRIC_SERIES_MISMATCH")
                if measurement["loaded"]["status"] != "OBSERVED":
                    raise CampaignBlocked("ORIGINAL_RUNTIME_ACTIVATION_UNVERIFIED")
            self.transport.check()
            scores = None if group.stage == "G" else self.score(store, records)
            result = summarize_group(group, records, scores, measurement["start_ns"], measurement["end_ns"],
                                     resumed=measurement["resumed"])
            result.update(engine=measurement["engine"], server_instance=measurement["server_instance"],
                          server_startup_s=measurement["server_startup_s"],
                          cold_start_contamination=measurement["cold_start_contamination"],
                          loaded=measurement["loaded"], protocol_hash=self.protocol_hash,
                          measurement_complete=not measurement["resumed"])
            result["nonmeasurement_wall_s"] = max(0, time.monotonic() - group_started - (result["elapsed_wall_s"] or 0))
            store.finish(result)
            self.results[group.group_id] = result
            self.partial_counts[group.group_id] = len(records)
            self.update("GROUP_END", group_completed=len(records), group_total=len(group.tasks),
                        completed=sum(self.partial_counts.values()), groups_completed=len(self.results),
                        latest_log=measurement["loaded"]["log"])
            canary_gate(group, records)
            regressions = quality_regressions(list(self.results.values()))
            if regressions:
                write_json(self.root / "results/quality-stop.json", {"status": "BLOCKED", "regressions": regressions,
                           "remaining_cells": [candidate.group_id for candidate in self.groups if candidate.group_id not in self.results]})
                raise CampaignBlocked("S_RAW_OR_NORMAL_REGRESSION_RESOURCE_GATE; entire campaign paused, not algorithm failure")
            if result["throughput_status"] != "VALID":
                raise CampaignBlocked("RESUMED_QUALITY_RETAINED_BUT_PRIMARY_THROUGHPUT_INVALID")
            return result
        except BaseException as error:
            recovery_error = None
            try:
                restored = store.restore()
                self.partial_counts[group.group_id] = len(restored)
            except (CampaignError, OSError, KeyError, ValueError) as restore_error:
                recovery_error = str(restore_error)
            write_json(store.path / "group-state.json", {"status": "FAILED", "group_id": group.group_id,
                       "completed": self.partial_counts.get(group.group_id, 0), "total": len(group.tasks),
                       "error_type": type(error).__name__, "error": str(error), "recovery_check_error": recovery_error,
                       "updated_utc": utcnow(), "quality_errors_imputed": False})
            raise

    def require_stages(self, stages):
        required = [group for group in self.groups if group.stage in stages]
        missing = [group.group_id for group in required if group.group_id not in self.results]
        if missing:
            raise CampaignBlocked("PREREQUISITE_GROUPS_NOT_COMPLETE: " + ",".join(missing))
        for group in required:
            result = self.results[group.group_id]
            if (result.get("throughput_status") != "VALID" or result.get("engine", {}).get("status") != "RECONCILED"
                    or result.get("loaded", {}).get("status") != "OBSERVED"):
                raise CampaignBlocked("PREREQUISITE_MEASUREMENT_OR_ACTIVATION_INCOMPLETE: " + group.group_id)
            if group.stage == "C":
                canary_gate(group, list(self.stores[group.group_id].restore().values()))
        if "G" in stages:
            diagnostics = greedy_diagnostics(self.groups, self.stores, self.results)
            freeze_file(self.root / "results/greedy-diagnostic.json", json_bytes(diagnostics))
        if quality_regressions(list(self.results.values())):
            raise CampaignBlocked("S_REGRESSION_REQUIRES_ADJUDICATION; no route removed from F")

    def before_stage(self, stage):
        previous = STAGES[:STAGES.index(stage)]
        self.require_stages(previous)
        if stage == "F":
            remaining = [group for group in self.groups if group.stage == "F" and group.group_id not in self.results]
            runway = full_runway(self.contract, remaining, list(self.results.values()), self.budget.start_epoch, time.time())
            write_json(self.root / "state/full-runway.json", runway)
            if runway["status"] != "FIT":
                raise CampaignBlocked("FULL_MATRIX_DOES_NOT_FIT_BILLING_RUNWAY; denominator unchanged")

    def run(self, stage):
        freeze_file(self.root / "metadata/campaign-plan.json", json_bytes({
            "protocol_hash": self.protocol_hash, "identity": self.identity,
            "groups": [describe_group(group) for group in self.groups], "planned_measured_responses": 5904}))
        self.update("CAMPAIGN_START", requested_stage=stage)
        self.restore_completed()
        selected = [group for group in self.groups if stage == "all" or group.stage == stage]
        active_stage = None
        for group in selected:
            self.transport.check()
            if active_stage != group.stage:
                self.before_stage(group.stage)
                active_stage = group.stage
            if group.group_id in self.results:
                continue
            if self.telemetry is None:
                self.telemetry = OwnedProcess([
                    "nvidia-smi", "--query-gpu=timestamp,name,memory.used,memory.total,utilization.gpu,power.draw,temperature.gpu",
                    "--format=csv", "--loop=2"], self.plan.environment,
                    self.root / "logs" / ("gpu-" + uuid.uuid4().hex + ".csv"))
                self.telemetry.start()
            if self.telemetry.process.poll() is not None:
                raise CampaignError("GPU_TELEMETRY_PROCESS_EXITED: " + str(self.telemetry.log_path))
            self.run_group(group)
        self.require_stages(tuple({group.stage for group in selected}))
        all_complete = len(self.results) == len(self.groups)
        if all_complete:
            self.require_stages(STAGES)
            checked = [self.store(group).load_complete() for group in self.groups]
            if any(result is None for result in checked) or sum(result["completed"] for result in checked) != 5904:
                raise CampaignError("FINAL_GROUP_MARKER_OR_5904_RESPONSE_RECONCILIATION_FAILED")
            self.update("ALL_GROUPS_RECONCILED", status="COMPLETE", completed=5904, groups_completed=len(self.groups),
                        model_execution_status="COMPLETE", remaining_groups=[], campaign_complete=True)
        else:
            self.update("REQUESTED_STAGE_COMPLETE", status="BLOCKED", requested_stage_complete=True,
                        campaign_complete=False, block_reason="AWAITING_UNREQUESTED_STAGES",
                        remaining_groups=[group.group_id for group in self.groups if group.group_id not in self.results])
        return 0

    def close(self):
        self.transport.cancel()
        receipts = OwnedProcess.stop_all([self.scorer, self.server.owned, self.telemetry])
        self.scorer = self.telemetry = self.server.owned = None
        write_json(self.root / "state/process-cleanup.json", {"processes": receipts, "finished_utc": utcnow()})
        if any(receipt["status"] != "STOPPED" for receipt in receipts):
            self.update("CLEANUP_UNCONFIRMED", status="BLOCKED", campaign_complete=False,
                        block_reason="independent systemd RuntimeMaxSec and finalizer must finish owned-process cleanup")
            return False
        return True


def make_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--stage", choices=(*STAGES, "all", "validate"), default="all")
    parser.add_argument("--image", default="dflash-quality-eval:20260905")
    parser.add_argument("--port", type=int, default=18080)
    return parser


def main(argv=None):
    args = make_parser().parse_args(argv)
    root, cache = args.root.resolve(), args.cache.resolve()
    campaign = None
    lock_file = None
    previous_signals = {}
    exit_code = 1
    try:
        contract, tasks, groups, protocol_hash, identity = load_inputs(root)
        if args.stage == "validate":
            report = {"status": "STATIC_VALIDATED", "model_execution_status": "NOT_RUN",
                      "groups": len(groups), "responses": sum(len(group.tasks) for group in groups),
                      "protocol_hash": protocol_hash, "identity": identity,
                      "execution_lock_released": contract["execution_lock"].get("allow_model_execution") is True,
                      "pending_runtime_gates": ["actual model/V2/BF16 KV-cache activation", "C/G response and grader semantics",
                                                "owned Linux listener", "group-local native counters", "S quality and F runway",
                                                "independent systemd RuntimeMaxSec and finalizer"]}
            try:
                plan = load_runtime_plan(root, cache, contract, verify_weights=False)
                report["runtime_metadata_identity"] = plan.identity
                report["weight_byte_verification"] = "NOT_RUN_BY_VALIDATE"
            except (CampaignError, OSError, KeyError, TypeError) as error:
                report.update(status="BLOCKED", gate=str(error), error_type=type(error).__name__)
            print(json.dumps(report, ensure_ascii=True, allow_nan=False), flush=True)
            return 0 if report["status"] == "STATIC_VALIDATED" else 3
        if contract["execution_lock"].get("allow_model_execution") is not True:
            raise CampaignBlocked("MODEL_EXECUTION_AUTHORIZATION_LOCK_CLOSED")
        if sys.platform != "linux" or platform.machine() != "x86_64":
            raise CampaignBlocked("CAMPAIGN_EXECUTION_REQUIRES_LINUX_X86_64")
        if str(root) != contract["resource"]["remote_root"] or root.name != contract["run_id"] or str(cache) != contract["resource"]["cache_root"]:
            raise CampaignBlocked("NEW_ROOT_OR_CACHE_DOES_NOT_MATCH_CONTRACT")
        for name in ("logs", "state", "metadata", "results"):
            child_path(root, name).mkdir(parents=True, exist_ok=True)
        import fcntl

        lock_file = child_path(root, "state/campaign.lock").open("a+b")
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({"status": "BLOCKED", "gate": "CAMPAIGN_ALREADY_OWNED; active state untouched"}), flush=True)
            return 3
        billing = read_json(child_path(root, "state/billing.json"))
        budget = Budget(billing["start"], contract["resource"]["stop_new_work_after_hours"])
        budget.check()
        plan = load_runtime_plan(root, cache, contract, guard=budget.check)
        evaluator = read_json(root / "metadata/evaluator-image.json")
        if evaluator.get("image") != args.image or not re.fullmatch(r"sha256:[0-9a-f]{64}", evaluator.get("id", "")):
            raise CampaignBlocked("PREPARED_EVALUATOR_IMAGE_IDENTITY_MISMATCH")
        campaign = Campaign(root, cache, contract, tasks, groups, protocol_hash, identity, plan, budget, args.image, args.port)

        def interrupted(signum, frame):
            campaign.state["interrupted_signal"] = signum
            campaign.transport.cancel()

        for signum in (signal.SIGTERM, signal.SIGINT):
            previous_signals[signum] = signal.signal(signum, interrupted)
        exit_code = campaign.run(args.stage)
    except BaseException as error:
        trace = traceback.format_exc()
        cause = error.cause if isinstance(error, RequestFailure) else error
        status = "BLOCKED" if isinstance(cause, CampaignBlocked) else "FAILED"
        if args.stage != "validate":
            diagnostic = child_path(root, "logs/campaign-failure.txt")
            diagnostic.parent.mkdir(parents=True, exist_ok=True)
            with diagnostic.open("a", encoding="utf-8") as output:
                output.write(utcnow() + "\n" + trace + "\n")
            if campaign is not None:
                campaign.update("CAMPAIGN_FAILURE", status=status, error_type=type(cause).__name__,
                                error=str(cause), latest_log=str(diagnostic), completed=sum(campaign.partial_counts.values()),
                                remaining_groups=[group.group_id for group in campaign.groups if group.group_id not in campaign.results])
            else:
                write_json(child_path(root, "state/campaign.json"), {"status": status, "phase": status,
                           "event": "PREFLIGHT_FAILED", "model_execution_status": "NOT_RUN", "completed": 0,
                           "total": 5904, "error_type": type(cause).__name__, "error": str(cause), "latest_log": str(diagnostic)})
        print(json.dumps({"status": status, "error_type": type(cause).__name__, "error": str(cause)},
                 ensure_ascii=True), file=sys.stderr)
        exit_code = 3 if isinstance(cause, CampaignBlocked) else 1
    finally:
        if campaign is not None:
            try:
                if not campaign.close():
                    exit_code = 3
            except BaseException:
                with (root / "logs/campaign-failure.txt").open("a", encoding="utf-8") as output:
                    output.write(utcnow() + "\n" + traceback.format_exc() + "\n")
                campaign.update("CLEANUP_FAILED", status="BLOCKED", campaign_complete=False,
                                block_reason="independent systemd RuntimeMaxSec and finalizer must finish cleanup")
                exit_code = 3
        for signum, handler in previous_signals.items():
            signal.signal(signum, handler)
        if lock_file is not None:
            lock_file.close()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
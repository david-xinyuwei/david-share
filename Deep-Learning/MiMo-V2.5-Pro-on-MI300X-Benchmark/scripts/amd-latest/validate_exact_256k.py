#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


FATAL_RE = re.compile(
    r"Traceback \(most recent call last\)|OutOfMemoryError|ClientPayloadError|"
    r"No available .*worker|Engine is dead|Segmentation fault|Memory access fault|"
    r"HSA_STATUS_ERROR_MEMORY_APERTURE_VIOLATION|Fatal Python error|"
    r"longer than the model['’]s context length|exceeds the maximum allowed length|"
    r"Health check failed|_watchdog_thread",
    re.IGNORECASE,
)


def metric(text: str, label: str, cast: type[int] | type[float]) -> int | float:
    match = re.search(rf"{re.escape(label)}:\s+([0-9.]+)", text)
    if not match:
        raise SystemExit(f"Missing client metric: {label}")
    return cast(match.group(1))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("client_log", type=Path)
    parser.add_argument("--prefill-info", type=Path, required=True)
    parser.add_argument("--decode-info", type=Path, required=True)
    parser.add_argument("--service-logs", nargs=3, type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    client_text = args.client_log.read_text(encoding="utf-8", errors="replace")
    service_rows = []
    for path in args.service_logs:
        text = path.read_text(encoding="utf-8", errors="replace")
        service_rows.append({"path": str(path), "fatal_count": len(FATAL_RE.findall(text))})

    worker_rows = []
    for role, path in (("prefill", args.prefill_info), ("decode", args.decode_info)):
        payload = json.loads(path.read_text(encoding="utf-8"))
        worker_rows.append(
            {
                "role": role,
                "context_length": payload["context_length"],
                "max_req_input_len": payload["max_req_input_len"],
                "version": payload.get("version"),
            }
        )

    evidence = {
        "tokenize_prompt": "tokenize_prompt=True" in client_text,
        "successful_requests": metric(client_text, "Successful requests", int),
        "retokenized_outputs": metric(
            client_text, "Total generated tokens (retokenized)", int
        ),
        "total_input_tokens": metric(client_text, "Total input tokens", int),
        "benchmark_duration_s": metric(client_text, "Benchmark duration (s)", float),
        "input_tok_s": metric(client_text, "Input token throughput (tok/s)", float),
        "workers": worker_rows,
        "service_logs": service_rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, sort_keys=True))

    if not evidence["tokenize_prompt"]:
        raise SystemExit("Client did not use --tokenize-prompt")
    if evidence["successful_requests"] != 16 or evidence["retokenized_outputs"] != 16:
        raise SystemExit("Expected 16/16 successful and retokenized outputs")
    if evidence["total_input_tokens"] != 4_194_304:
        raise SystemExit("Expected exactly 16 * 262144 input tokens")
    if any(row["context_length"] != 262151 for row in worker_rows):
        raise SystemExit("Expected context_length=262151 on both workers")
    if any(row["max_req_input_len"] < 262145 for row in worker_rows):
        raise SystemExit("Insufficient max_req_input_len")
    if any(row["fatal_count"] for row in service_rows):
        raise SystemExit("Service logs contain fatal/context markers")


if __name__ == "__main__":
    main()
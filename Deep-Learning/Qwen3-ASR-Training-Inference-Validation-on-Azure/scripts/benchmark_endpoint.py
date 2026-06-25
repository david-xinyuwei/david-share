#!/usr/bin/env python3
"""Benchmark an ASR HTTP endpoint with audio files.

The endpoint contract is intentionally simple and explicit:
- POST multipart/form-data with field name `file` by default.
- Response may be JSON or text.
- The script measures wall-clock latency and computes RTF from ffprobe duration.

It does not assume vLLM, SGLang, TensorRT-LLM, Whisper, or Azure Speech. Use the
headers option to adapt it to customer-controlled endpoints.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class RequestResult:
    file: str
    audio_seconds: float
    status: int | None
    latency_seconds: float
    rtf: float | None
    response_bytes: int
    error: str | None


def audio_duration_seconds(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def parse_headers(values: list[str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for value in values:
        if ":" not in value:
            raise ValueError(f"Header must be in 'Name: value' format: {value}")
        key, raw = value.split(":", 1)
        headers[key.strip()] = raw.strip()
    return headers


def build_multipart(field_name: str, file_path: Path) -> tuple[bytes, str]:
    boundary = f"----asr-eval-boundary-{time.time_ns()}"
    body = bytearray()
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(
        f'Content-Disposition: form-data; name="{field_name}"; filename="{file_path.name}"\r\n'.encode()
    )
    body.extend(b"Content-Type: application/octet-stream\r\n\r\n")
    body.extend(file_path.read_bytes())
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    return bytes(body), boundary


def post_audio(url: str, file_path: Path, field_name: str, headers: dict[str, str], timeout: float) -> RequestResult:
    duration = audio_duration_seconds(file_path)
    body, boundary = build_multipart(field_name, file_path)
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    for key, value in headers.items():
        request.add_header(key, value)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
            latency = time.perf_counter() - started
            return RequestResult(
                file=str(file_path),
                audio_seconds=duration,
                status=response.status,
                latency_seconds=latency,
                rtf=latency / duration if duration else None,
                response_bytes=len(payload),
                error=None,
            )
    except urllib.error.HTTPError as error:
        payload = error.read()
        latency = time.perf_counter() - started
        return RequestResult(
            str(file_path),
            duration,
            error.code,
            latency,
            latency / duration if duration else None,
            len(payload),
            str(error),
        )
    except Exception as error:
        latency = time.perf_counter() - started
        return RequestResult(str(file_path), duration, None, latency, latency / duration if duration else None, 0, repr(error))


def percentile(values: list[float], percent: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    index = min(len(values) - 1, max(0, round((percent / 100) * (len(values) - 1))))
    return values[index]


def summarize(results: list[RequestResult]) -> dict[str, object]:
    latencies = [item.latency_seconds for item in results]
    rtfs = [item.rtf for item in results if item.rtf is not None]
    successes = [item for item in results if item.error is None and item.status and 200 <= item.status < 300]
    audio_seconds = sum(item.audio_seconds for item in results)
    wall_seconds = sum(item.latency_seconds for item in results)
    return {
        "requests": len(results),
        "successes": len(successes),
        "failures": len(results) - len(successes),
        "audio_seconds_total": audio_seconds,
        "latency_p50_seconds": percentile(latencies, 50),
        "latency_p95_seconds": percentile(latencies, 95),
        "rtf_p50": percentile(rtfs, 50),
        "rtf_p95": percentile(rtfs, 95),
        "audio_hours_per_wall_hour_sum_latency": (audio_seconds / wall_seconds) if wall_seconds else None,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark an ASR HTTP endpoint with audio files.")
    parser.add_argument("--url", required=True, help="Endpoint URL to POST audio to.")
    parser.add_argument("--audio", nargs="+", type=Path, required=True, help="Audio files to send.")
    parser.add_argument("--field-name", default="file", help="Multipart file field name. Default: file")
    parser.add_argument("--header", action="append", default=[], help="HTTP header in 'Name: value' format. Repeatable.")
    parser.add_argument("--concurrency", type=int, default=1, help="Number of concurrent requests.")
    parser.add_argument("--timeout", type=float, default=600.0, help="Per-request timeout seconds.")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    headers = parse_headers(args.header)
    for audio in args.audio:
        if not audio.exists():
            raise FileNotFoundError(audio)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [
            executor.submit(post_audio, args.url, audio, args.field_name, headers, args.timeout)
            for audio in args.audio
        ]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]

    payload = {"summary": summarize(results), "results": [asdict(item) for item in results]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

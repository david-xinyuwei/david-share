"""Parse and validate the official Azure Context Cache demo transcript."""

from __future__ import annotations

import argparse
import json
import re
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path


ROW_RE = re.compile(
    r"^\s*(?P<call>\d+)\s+"
    r"(?P<input_name>\S+\.diff)\s+"
    r"(?P<latency_ms>\d+)\s+"
    r"(?P<input_tokens>\d+)\s+"
    r"(?P<cached_tokens>\d+)\s+"
    r"(?P<output_tokens>\d+)\s+"
    r"(?P<hit_percent>\d+)%\s*$",
    re.MULTILINE,
)
ERROR_RE = re.compile(
    r"(?:HTTP\s+[45]\d\d|transport error:|Demo exited with code\s+[1-9]\d*|"
    r"Traceback \(most recent call last\)|UnicodeEncodeError)",
    re.IGNORECASE,
)


class ValidationError(RuntimeError):
    """The transcript does not prove the requested validation contract."""


@dataclass(frozen=True)
class CallResult:
    call: int
    input_name: str
    latency_ms: int
    input_tokens: int
    cached_tokens: int
    output_tokens: int
    hit_percent: int


def parse_rows(text: str) -> list[CallResult]:
    if ERROR_RE.search(text):
        raise ValidationError("the transcript contains an HTTP or transport error")
    return [
        CallResult(
            call=int(match["call"]),
            input_name=match["input_name"],
            latency_ms=int(match["latency_ms"]),
            input_tokens=int(match["input_tokens"]),
            cached_tokens=int(match["cached_tokens"]),
            output_tokens=int(match["output_tokens"]),
            hit_percent=int(match["hit_percent"]),
        )
        for match in ROW_RE.finditer(text)
    ]


def summarize(
    rows: list[CallResult],
    *,
    expected_runs: int = 6,
    min_warm_hit_ratio: float = 0.6,
) -> dict[str, object]:
    if len(rows) != expected_runs:
        raise ValidationError(f"expected {expected_runs} call rows, found {len(rows)}")
    if [row.call for row in rows] != list(range(1, expected_runs + 1)):
        raise ValidationError("call numbers are missing, duplicated, or out of order")
    if not 0.0 <= min_warm_hit_ratio <= 1.0:
        raise ValidationError("minimum warm hit ratio must be between 0 and 1")
    for row in rows:
        if row.input_tokens <= 0:
            raise ValidationError(f"call {row.call} has no input tokens")
        if row.output_tokens <= 0:
            raise ValidationError(f"call {row.call} has no output tokens")
        if not 0 <= row.cached_tokens <= row.input_tokens:
            raise ValidationError(f"call {row.call} has impossible cached token counts")
        expected_percent = 100.0 * row.cached_tokens / row.input_tokens
        if not 0 <= row.hit_percent <= 100 or abs(row.hit_percent - expected_percent) > 0.51:
            raise ValidationError(f"call {row.call} has inconsistent cache percentage")

    warm_rows = rows[1:]
    if not warm_rows:
        raise ValidationError("at least two calls are required")
    warm_hits = [row for row in warm_rows if row.cached_tokens > 0]
    warm_hit_ratio = len(warm_hits) / len(warm_rows)
    if warm_hit_ratio < min_warm_hit_ratio:
        raise ValidationError(
            f"warm cache hit ratio {warm_hit_ratio:.3f} is below {min_warm_hit_ratio:.3f}"
        )

    warm_mean_latency = statistics.mean(row.latency_ms for row in warm_rows)
    first_to_warm_speedup = rows[0].latency_ms / warm_mean_latency
    return {
        "schemaVersion": 1,
        "runCount": len(rows),
        "firstCallColdObserved": rows[0].cached_tokens == 0,
        "warm": {
            "calls": len(warm_rows),
            "hits": len(warm_hits),
            "hitRatio": round(warm_hit_ratio, 6),
            "meanLatencyMs": round(warm_mean_latency, 3),
            "cachedTokens": {
                "min": min(row.cached_tokens for row in warm_rows),
                "max": max(row.cached_tokens for row in warm_rows),
                "mean": round(statistics.mean(row.cached_tokens for row in warm_rows), 3),
            },
        },
        "firstCallLatencyMs": rows[0].latency_ms,
        "firstToWarmSpeedup": round(first_to_warm_speedup, 6),
        "calls": [asdict(row) for row in rows],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transcript", type=Path)
    parser.add_argument("--stderr", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-runs", type=int, default=6)
    parser.add_argument("--min-warm-hit-ratio", type=float, default=0.6)
    args = parser.parse_args()

    try:
        text = args.transcript.read_text(encoding="utf-8")
        if args.stderr:
            text = f"{text}\n--- STDERR ---\n{args.stderr.read_text(encoding='utf-8')}"
        summary = summarize(
            parse_rows(text),
            expected_runs=args.expected_runs,
            min_warm_hit_ratio=args.min_warm_hit_ratio,
        )
    except (OSError, UnicodeError, ValidationError) as error:
        parser.error(str(error))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(
        "VALIDATION_PASS "
        f"runs={summary['runCount']} "
        f"warm_hits={summary['warm']['hits']}/{summary['warm']['calls']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
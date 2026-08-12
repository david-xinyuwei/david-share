"""Extract per-step GRPO metrics from a captured verl job log into the evidence/ directory.

The source log is the console stream of a managed training job: UTF-16LE (PowerShell 5.1
`*>` redirection writes UTF-16), several tens of MB, and tqdm progress bars separated by
carriage returns rather than newlines. Both facts break naive line-oriented parsing, so
they are handled explicitly here.

Environment identifiers are redacted on the way out. No numeric value is altered, so the
published evidence can be diffed against a rerun on other hardware.

    python tools/extract_training_evidence.py --log <job-log> --out evidence/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

STEP_RE = re.compile(r"^step:(\d+)\s+-\s+(.*)$")
PROGRESS_RE = re.compile(
    r"Training Progress:\s*(\d+)%\|[^|]*\|\s*(\d+)/(\d+)\s*\[([^<]+)<([^,]+),\s*([\d.]+)s/it\]"
)
PAIR_RE = re.compile(r"([A-Za-z0-9_/@.-]+):(.+)")
NUMERIC_RE = re.compile(r"^(?:np\.(?:float64|float32|int32|int64)\()?(-?[\d.eE+-]+)\)?$")

REDACTIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"/scratch/azureml/cr/j/[0-9a-f]{16,}"), "/scratch/<run-id>"),
    (re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"), "<guid>"),
    (re.compile(r"\b[a-z0-9]+\.azurecr\.io\b"), "<registry>"),
    (re.compile(r"\bverl-rft-[a-z0-9]+-[0-9a-f]{4}\b"), "<job>"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "<ip>"),
]


def redact(text: str) -> str:
    for pattern, replacement in REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def parse_value(raw: str) -> float | int | str:
    raw = raw.strip()
    match = NUMERIC_RE.match(raw)
    if not match:
        return redact(raw)
    literal = match.group(1)
    try:
        return int(literal) if re.fullmatch(r"-?\d+", literal) else float(literal)
    except ValueError:
        return redact(raw)


def parse_metric_line(payload: str) -> dict[str, float | int | str]:
    """Split a ` - `-joined run of `key:value` pairs into a dict."""
    metrics: dict[str, float | int | str] = {}
    for chunk in payload.split(" - "):
        pair = PAIR_RE.match(chunk.strip())
        if pair:
            metrics[pair.group(1)] = parse_value(pair.group(2))
    return metrics


def read_records(log_path: Path) -> tuple[list[str], str]:
    """Return logical records, splitting on carriage returns so tqdm frames separate."""
    raw = log_path.read_bytes()
    encoding = "utf-16-le" if b"\x00" in raw[:200] else "utf-8"
    text = raw.decode(encoding, errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n"), encoding


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path, help="evidence/ directory")
    parser.add_argument("--total-steps", type=int, default=None)
    args = parser.parse_args()

    if not args.log.is_file():
        raise SystemExit(f"log not found: {args.log}")

    digest = hashlib.sha256(args.log.read_bytes()).hexdigest()
    records, encoding = read_records(args.log)

    steps: dict[int, dict] = {}
    validation: list[dict] = []
    progress: dict[int, dict] = {}
    total_steps = args.total_steps

    for record in records:
        step_match = STEP_RE.match(record.strip())
        if step_match:
            index = int(step_match.group(1))
            metrics = parse_metric_line(step_match.group(2))
            # A step that triggers evaluation emits training and validation metrics on the
            # same line; both must be kept, so split rather than classify the whole line.
            val_metrics = {k: v for k, v in metrics.items() if k.startswith("val-")}
            train_metrics = {k: v for k, v in metrics.items() if not k.startswith("val-")}
            if val_metrics:
                validation.append({"afterStep": index, "metrics": val_metrics})
            if train_metrics:
                steps[index] = train_metrics
            continue

        for progress_match in PROGRESS_RE.finditer(record):
            completed = int(progress_match.group(2))
            total_steps = total_steps or int(progress_match.group(3))
            if completed == 0:
                continue
            progress[completed] = {
                "elapsed": progress_match.group(4).strip(),
                "remainingEstimate": progress_match.group(5).strip(),
                "secondsPerStep": float(progress_match.group(6)),
            }

    args.out.mkdir(parents=True, exist_ok=True)

    metrics_path = args.out / "training-metrics.jsonl"
    with metrics_path.open("w", encoding="utf-8", newline="\n") as handle:
        for index in sorted(steps):
            row: dict[str, object] = {"step": index}
            row.update(progress.get(index, {}))
            row.update(steps[index])
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    validation_path = args.out / "validation-baseline.json"
    validation_path.write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )

    manifest = {
        "extractedAtUtc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sourceLog": {
            "sha256": digest,
            "bytes": args.log.stat().st_size,
            "records": len(records),
            "encoding": encoding,
        },
        "run": {
            "totalStepsPlanned": total_steps,
            "stepsCaptured": sorted(steps),
            "validationPasses": [entry["afterStep"] for entry in validation],
        },
        "extractor": "tools/extract_training_evidence.py",
        "note": (
            "Metrics are copied verbatim from the job log. Environment identifiers "
            "(run GUIDs, registry, job name, IPs) are redacted; no numeric value is altered."
        ),
    }
    manifest_path = args.out / "run-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )

    print(f"SOURCE_SHA256={digest}")
    print(f"RECORDS={len(records)}")
    print(f"STEPS_CAPTURED={sorted(steps)}")
    print(f"TOTAL_STEPS_PLANNED={total_steps}")
    print(f"VALIDATION_PASSES={[entry['afterStep'] for entry in validation]}")
    for path in (metrics_path, validation_path, manifest_path):
        print(f"WROTE={path.name} bytes={path.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

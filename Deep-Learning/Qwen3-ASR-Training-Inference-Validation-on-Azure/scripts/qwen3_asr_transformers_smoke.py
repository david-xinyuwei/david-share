#!/usr/bin/env python3
"""Run a Qwen3-ASR transformers-backend smoke test.

This script is intentionally small: it validates that the model can load on a
GPU and transcribe one audio input. It is not a benchmark by itself; use
`benchmark_endpoint.py` for serving latency tests and `eval_asr_metrics.py` for
WER/CER once ground truth is available.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Qwen3-ASR transformers backend smoke test.")
    parser.add_argument("--model", default="Qwen/Qwen3-ASR-0.6B", help="Qwen3-ASR model name or local path.")
    parser.add_argument("--audio", required=True, help="Audio path or URL.")
    parser.add_argument("--language", default=None, help="Optional language hint, e.g. Chinese or English.")
    parser.add_argument("--max-new-tokens", type=int, default=1024, help="Maximum generated tokens.")
    parser.add_argument("--batch-size", type=int, default=1, help="Max inference batch size.")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    import torch  # noqa: PLC0415 - late import so --help works without GPU deps
    from qwen_asr import Qwen3ASRModel  # noqa: PLC0415

    started = time.perf_counter()
    model = Qwen3ASRModel.from_pretrained(
        args.model,
        dtype=torch.bfloat16,
        device_map="cuda:0",
        max_inference_batch_size=args.batch_size,
        max_new_tokens=args.max_new_tokens,
    )
    loaded = time.perf_counter()
    results = model.transcribe(audio=args.audio, language=args.language)
    finished = time.perf_counter()
    payload = {
        "model": args.model,
        "audio": args.audio,
        "language_hint": args.language,
        "load_seconds": loaded - started,
        "transcribe_seconds": finished - loaded,
        "results": [
            {
                "language": item.language,
                "text": item.text,
            }
            for item in results
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
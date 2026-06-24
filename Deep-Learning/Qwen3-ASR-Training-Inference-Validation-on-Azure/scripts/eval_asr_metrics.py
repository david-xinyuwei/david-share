#!/usr/bin/env python3
"""Evaluate ASR output with WER, CER, and optional hotword recall.

This script intentionally does not call any model or cloud service. It compares
existing reference and hypothesis text files so it can run in customer-controlled
environments without moving audio or transcripts out of their boundary.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class AsrMetrics:
    reference_chars: int
    hypothesis_chars: int
    reference_words: int
    hypothesis_words: int
    wer: float
    cer: float
    hotword_recall: float | None
    hotwords_total: int
    hotwords_hit: int


def normalize_text(text: str, keep_spaces: bool = True) -> str:
    text = text.strip().lower()
    text = re.sub(r"[\u3000\s]+", " ", text)
    text = re.sub(r"[，。！？、；：,.!?;:\"'()\[\]{}<>《》“”‘’]", "", text)
    if not keep_spaces:
        text = text.replace(" ", "")
    return text.strip()


def tokenize_words(text: str) -> list[str]:
    normalized = normalize_text(text, keep_spaces=True)
    if " " in normalized:
        return [token for token in normalized.split(" ") if token]
    return list(normalized)


def tokenize_chars(text: str) -> list[str]:
    return list(normalize_text(text, keep_spaces=False))


def edit_distance(reference: list[str], hypothesis: list[str]) -> int:
    rows = len(reference) + 1
    cols = len(hypothesis) + 1
    previous = list(range(cols))
    for row in range(1, rows):
        current = [row] + [0] * (cols - 1)
        for col in range(1, cols):
            substitution_cost = 0 if reference[row - 1] == hypothesis[col - 1] else 1
            current[col] = min(
                previous[col] + 1,
                current[col - 1] + 1,
                previous[col - 1] + substitution_cost,
            )
        previous = current
    return previous[-1]


def error_rate(reference: list[str], hypothesis: list[str]) -> float:
    if not reference:
        return 0.0 if not hypothesis else 1.0
    return edit_distance(reference, hypothesis) / len(reference)


def hotword_recall(reference_text: str, hypothesis_text: str, hotwords: list[str]) -> tuple[float | None, int, int]:
    if not hotwords:
        return None, 0, 0
    reference_normalized = normalize_text(reference_text, keep_spaces=False)
    hypothesis_normalized = normalize_text(hypothesis_text, keep_spaces=False)
    expected = []
    for hotword in hotwords:
        normalized = normalize_text(hotword, keep_spaces=False)
        if normalized and normalized in reference_normalized:
            expected.append(normalized)
    if not expected:
        return None, 0, 0
    hits = sum(1 for word in expected if word in hypothesis_normalized)
    return hits / len(expected), len(expected), hits


def load_hotwords(path: Path | None) -> list[str]:
    if path is None:
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def evaluate(reference_text: str, hypothesis_text: str, hotwords: list[str]) -> AsrMetrics:
    reference_words = tokenize_words(reference_text)
    hypothesis_words = tokenize_words(hypothesis_text)
    reference_chars = tokenize_chars(reference_text)
    hypothesis_chars = tokenize_chars(hypothesis_text)
    recall, hotwords_total, hotwords_hit = hotword_recall(reference_text, hypothesis_text, hotwords)
    return AsrMetrics(
        reference_chars=len(reference_chars),
        hypothesis_chars=len(hypothesis_chars),
        reference_words=len(reference_words),
        hypothesis_words=len(hypothesis_words),
        wer=error_rate(reference_words, hypothesis_words),
        cer=error_rate(reference_chars, hypothesis_chars),
        hotword_recall=recall,
        hotwords_total=hotwords_total,
        hotwords_hit=hotwords_hit,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate ASR transcript quality.")
    parser.add_argument("--reference", type=Path, required=True, help="Ground-truth transcript text file.")
    parser.add_argument("--hypothesis", type=Path, required=True, help="ASR output transcript text file.")
    parser.add_argument("--hotwords", type=Path, default=None, help="Optional newline-delimited hotword file.")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    reference_text = args.reference.read_text(encoding="utf-8")
    hypothesis_text = args.hypothesis.read_text(encoding="utf-8")
    metrics = evaluate(reference_text, hypothesis_text, load_hotwords(args.hotwords))
    payload = asdict(metrics)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
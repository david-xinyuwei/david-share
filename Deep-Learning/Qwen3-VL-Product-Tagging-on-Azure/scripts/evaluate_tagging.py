#!/usr/bin/env python3
"""Evaluate JSON validity and tag-level scores for product tagging predictions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


TAG_FIELDS = ("colors", "materials", "patterns", "style_tags")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", required=True, help="Gold JSONL product records with tags object.")
    parser.add_argument("--predictions", required=True, help="Prediction JSONL from batch_infer_openai_compatible.py.")
    parser.add_argument("--output", default="reports/tagging_eval.json")
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as input_file:
        for line in input_file:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def parse_prediction(text: str | None) -> dict[str, Any] | None:
    if not text:
        return None
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(stripped[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None


def normalize_list(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {value.strip().lower()} if value.strip() else set()
    if isinstance(value, list):
        return {str(item).strip().lower() for item in value if str(item).strip()}
    return {str(value).strip().lower()} if str(value).strip() else set()


def prf(true_items: set[str], pred_items: set[str]) -> dict[str, float]:
    true_positive = len(true_items & pred_items)
    precision = true_positive / len(pred_items) if pred_items else 0.0
    recall = true_positive / len(true_items) if true_items else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def main() -> None:
    args = parse_args()
    gold_rows = read_jsonl(Path(args.gold))
    prediction_rows = read_jsonl(Path(args.predictions))
    if len(gold_rows) != len(prediction_rows):
        raise ValueError(f"Gold rows ({len(gold_rows)}) and prediction rows ({len(prediction_rows)}) differ.")

    valid_predictions: list[dict[str, Any] | None] = [parse_prediction(row.get("prediction")) for row in prediction_rows]
    schema_validity = sum(pred is not None for pred in valid_predictions) / len(valid_predictions) if valid_predictions else 0.0

    field_scores: dict[str, list[dict[str, float]]] = {field: [] for field in TAG_FIELDS}
    category_matches = 0
    category_total = 0

    for gold, pred in zip(gold_rows, valid_predictions):
        if pred is None:
            for field in TAG_FIELDS:
                field_scores[field].append({"precision": 0.0, "recall": 0.0, "f1": 0.0})
            continue
        gold_tags = gold.get("tags", {})
        category_total += 1
        if str(gold.get("category", "")).lower() == str(pred.get("category", "")).lower():
            category_matches += 1
        for field in TAG_FIELDS:
            field_scores[field].append(prf(normalize_list(gold_tags.get(field)), normalize_list(pred.get(field))))

    summary = {
        "n": len(gold_rows),
        "schema_validity": schema_validity,
        "category_accuracy": category_matches / category_total if category_total else 0.0,
        "fields": {},
    }
    for field, scores in field_scores.items():
        summary["fields"][field] = {
            metric: sum(score[metric] for score in scores) / len(scores) if scores else 0.0
            for metric in ("precision", "recall", "f1")
        }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(summary, output_file, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

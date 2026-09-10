#!/usr/bin/env python3
"""Build a disjoint fine-tuning split and a held-out evaluation prompt set.

The two files produced here are the only data used by the re-adaptation experiment:

* ``train.jsonl``        - supervised fine-tuning records for the target model.
* ``eval_prompts.jsonl`` - held-out prompts used to measure acceptance length.

The split is deterministic: the dataset is shuffled with a fixed seed and the two
slices are taken from non-overlapping index ranges, so the evaluation prompts are
never seen during fine-tuning. Both files are hashed so a later run can prove it
used the same data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from datasets import load_dataset


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_prompt(record: dict, question_field: str, instruction_field: str | None) -> str:
    question = record[question_field].strip()
    if instruction_field and record.get(instruction_field):
        return f"{record[instruction_field].strip()}\n\n{question}"
    return question


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="lavita/ChatDoctor-HealthCareMagic-100k")
    parser.add_argument("--config", default=None, help="dataset config name, e.g. 'en'")
    parser.add_argument("--split", default="train")
    parser.add_argument("--question-field", default="input")
    parser.add_argument("--response-field", default="output")
    parser.add_argument("--instruction-field", default="instruction",
                        help="optional field prefixed to the question; pass '' to disable")
    parser.add_argument("--train-size", type=int, default=2000)
    parser.add_argument("--eval-size", type=int, default=40)
    parser.add_argument("--seed", type=int, default=20260908)
    parser.add_argument("--max-output-chars", type=int, default=1600)
    parser.add_argument("--out-dir", default="data")
    args = parser.parse_args()
    instruction_field = args.instruction_field or None

    dataset = load_dataset(args.dataset, args.config, split=args.split)
    dataset = dataset.shuffle(seed=args.seed)

    needed = args.train_size + args.eval_size
    if needed > len(dataset):
        raise ValueError(f"dataset has {len(dataset)} rows, need {needed}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    train_path = out_dir / "train.jsonl"
    eval_path = out_dir / "eval_prompts.jsonl"

    with train_path.open("w", encoding="utf-8") as handle:
        for index in range(args.train_size):
            record = dataset[index]
            payload = {
                "id": f"train-{index}",
                "prompt": build_prompt(record, args.question_field, instruction_field),
                "response": record[args.response_field].strip()[: args.max_output_chars],
            }
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    with eval_path.open("w", encoding="utf-8") as handle:
        for offset in range(args.eval_size):
            index = args.train_size + offset
            record = dataset[index]
            payload = {
                "id": f"eval-{offset}",
                "prompt": build_prompt(record, args.question_field, instruction_field),
                "reference": record[args.response_field].strip()[: args.max_output_chars],
            }
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    summary = {
        "dataset": args.dataset,
        "config": args.config,
        "split": args.split,
        "fields": {"question": args.question_field, "response": args.response_field,
                   "instruction": instruction_field},
        "seed": args.seed,
        "shuffled": True,
        "train_index_range": [0, args.train_size - 1],
        "eval_index_range": [args.train_size, args.train_size + args.eval_size - 1],
        "disjoint": True,
        "train_file": str(train_path),
        "train_rows": args.train_size,
        "train_sha256": sha256_of(train_path),
        "eval_file": str(eval_path),
        "eval_rows": args.eval_size,
        "eval_sha256": sha256_of(eval_path),
    }
    (out_dir / "split_manifest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    print("PREPARE_DATA=PASS", flush=True)


if __name__ == "__main__":
    main()

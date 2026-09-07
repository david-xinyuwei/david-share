"""Freeze public evaluation tasks without exposing gold answers to generation."""

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args()
    os.environ["EVALPLUS_CACHE_DIR"] = str(args.root / "data" / "evalplus-cache")
    from evalplus.data import get_human_eval_plus
    from evalplus.provider.base import DecoderBase

    code = get_human_eval_plus()
    if len(code) != 164:
        raise ValueError("HumanEval+ task count differs from the frozen denominator")
    math = [json.loads(line) for line in (args.root / "data/math500.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(math) != 500:
        raise ValueError("MATH-500 task count differs from the frozen denominator")
    records = []
    prefix = "Please provide a self-contained Python script that solves the following problem in a markdown code block:"
    for task_id in sorted(code, key=lambda value: int(value.split("/")[1])):
        problem = code[task_id]
        records.append({
            "task_id": task_id,
            "dataset": "humaneval_plus",
            "messages": [{"role": "user", "content": prefix + "\n```python\n" + problem["prompt"].strip() + "\n```"}],
            "max_tokens": 4096,
            "entry_point": problem["entry_point"],
        })
    for index, problem in enumerate(math):
        records.append({
            "task_id": "MATH-500/" + str(index),
            "dataset": "math_500",
            "messages": [{"role": "user", "content": problem["problem"] + "\nPlease reason carefully and put your final answer within \\boxed{}."}],
            "max_tokens": 8192,
            "source_unique_id": problem.get("unique_id", str(index)),
        })
    manifest = args.root / "data/tasks.jsonl"
    manifest.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records), encoding="utf-8")
    code_path = args.root / "data/humaneval_plus.jsonl"
    code_path.write_text("".join(json.dumps(problem, ensure_ascii=False) + "\n" for problem in code.values()), encoding="utf-8")
    metadata = {
        "tasks": len(records),
        "manifest_sha256": sha256(manifest),
        "math500_sha256": sha256(args.root / "data/math500.jsonl"),
        "humaneval_plus_sha256": sha256(code_path),
        "human_eval_plus_version": "v0.1.10",
        "packages": {name: importlib.metadata.version(name) for name in ("vllm", "torch", "transformers", "evalplus", "math-verify", "pandas", "huggingface-hub")},
        "artifacts": [],
    }
    for role in ("target", "draft"):
        for path in sorted((args.cache / role).iterdir()):
            if path.is_file() and path.suffix in (".json", ".jinja", ".safetensors"):
                metadata["artifacts"].append({"role": role, "name": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)})
    (args.root / "metadata/inputs.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"tasks": len(records), "manifest_sha256": metadata["manifest_sha256"], "packages": metadata["packages"]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
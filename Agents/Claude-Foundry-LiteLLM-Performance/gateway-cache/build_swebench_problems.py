"""Pick long coding problems from SWE-bench Lite (BM25 13K) for the cached coding matrix.

The dataset's `text` column is the full prompt: an issue plus the repository files
that BM25 retrieved, capped at 13,000 cl100k tokens of code. It is split the way the
official SWE-bench inference script splits it for Claude (swebench/inference/run_api.py,
call_anthropic_v2): first line = system prompt, the rest = user message.
"""
import argparse
import hashlib
import json
import random
import urllib.request
from pathlib import Path

DATASET = "princeton-nlp/SWE-bench_Lite_bm25_13K"


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify_manifest(spec, manifest):
    if spec["source"] != manifest["source"] or spec["system_prompt_sha256"] != manifest["system_prompt_sha256"]:
        raise ValueError("Dataset source or system prompt differs from the frozen manifest")
    fields = ("id", "repo", "base_commit", "user_message_sha256", "user_message_chars")
    actual = [{key: problem[key] for key in fields} for problem in spec["problems"]]
    expected = [{key: problem[key] for key in fields} for problem in manifest["problems"]]
    if actual != expected:
        raise ValueError("Selected problems, order or prompt hashes differ from the frozen manifest")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--seed", default="20261026")
    parser.add_argument("--manifest", type=Path, help="rebuild the frozen revision and problem order instead of sampling latest")
    args = parser.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8")) if args.manifest else None
    if manifest:
        if manifest["source"]["dataset"] != DATASET:
            raise ValueError("Manifest identifies another dataset")
        revision, dataset_file = manifest["source"]["revision"], manifest["source"]["file"]
    else:
        meta = json.load(urllib.request.urlopen(f"https://huggingface.co/api/datasets/{DATASET}", timeout=60))
        tests = [item["rfilename"] for item in meta["siblings"] if item["rfilename"].endswith(".parquet") and "test" in item["rfilename"]]
        if len(tests) != 1:
            raise SystemExit(f"expected one test parquet, found {tests}")
        revision, dataset_file = meta["sha"], tests[0]
    raw = urllib.request.urlopen(f"https://huggingface.co/datasets/{DATASET}/resolve/{revision}/{dataset_file}", timeout=300).read()
    if manifest and hashlib.sha256(raw).hexdigest() != manifest["source"]["parquet_sha256"]:
        raise ValueError("Downloaded parquet differs from the frozen manifest")
    import pyarrow.parquet as pq

    parquet = out.with_suffix(".test.parquet")
    parquet.write_bytes(raw)
    rows = {r["instance_id"]: r for r in pq.read_table(parquet).to_pylist()}
    chosen = [problem["id"] for problem in manifest["problems"]] if manifest else random.Random(args.seed).sample(sorted(rows), args.count)
    systems, problems = set(), []
    for instance_id in chosen:
        row = rows[instance_id]
        system, user = row["text"].split("\n", 1)
        systems.add(system)
        problems.append({"id": instance_id, "repo": row["repo"], "base_commit": row["base_commit"],
                         "language": "python", "user_message": user, "user_message_sha256": sha(user),
                         "user_message_chars": len(user)})
    if len(systems) != 1:
        raise SystemExit("the selected instances do not share one system line")
    system = systems.pop()
    spec = {"source": {"dataset": DATASET, "revision": revision, "file": dataset_file, "rows": len(rows),
                       "parquet_sha256": hashlib.sha256(raw).hexdigest()},
            "selection": manifest["selection"] if manifest else f"random.Random('{args.seed}').sample(sorted(test instance_ids), {args.count})",
            "split_rule": "first line of text = system, rest = user (SWE-bench run_api.py call_anthropic_v2)",
            "system_prompt": system, "system_prompt_sha256": sha(system), "problems": problems}
    if manifest:
        verify_manifest(spec, manifest)
    out.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print(json.dumps({"status": "PASS", "revision": revision, "rows": len(rows), "chosen": chosen,
                      "chars": [p["user_message_chars"] for p in problems], "system": system}, ensure_ascii=False))


if __name__ == "__main__":
    main()

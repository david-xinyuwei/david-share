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

import pyarrow.parquet as pq

DATASET = "princeton-nlp/SWE-bench_Lite_bm25_13K"


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--seed", default="20261026")
    args = parser.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    meta = json.load(urllib.request.urlopen(f"https://huggingface.co/api/datasets/{DATASET}", timeout=60))
    tests = [s["rfilename"] for s in meta["siblings"] if s["rfilename"].endswith(".parquet") and "test" in s["rfilename"]]
    if len(tests) != 1:
        raise SystemExit(f"expected one test parquet, found {tests}")
    revision = meta["sha"]
    raw = urllib.request.urlopen(f"https://huggingface.co/datasets/{DATASET}/resolve/{revision}/{tests[0]}", timeout=300).read()
    parquet = out.with_suffix(".test.parquet")
    parquet.write_bytes(raw)
    rows = {r["instance_id"]: r for r in pq.read_table(parquet).to_pylist()}
    chosen = random.Random(args.seed).sample(sorted(rows), args.count)
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
    spec = {"source": {"dataset": DATASET, "revision": revision, "file": tests[0], "rows": len(rows),
                       "parquet_sha256": hashlib.sha256(raw).hexdigest()},
            "selection": f"random.Random('{args.seed}').sample(sorted(test instance_ids), {args.count})",
            "split_rule": "first line of text = system, rest = user (SWE-bench run_api.py call_anthropic_v2)",
            "system_prompt": system, "system_prompt_sha256": sha(system), "problems": problems}
    out.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print(json.dumps({"status": "PASS", "revision": revision, "rows": len(rows), "chosen": chosen,
                      "chars": [p["user_message_chars"] for p in problems], "system": system}, ensure_ascii=False))


if __name__ == "__main__":
    main()

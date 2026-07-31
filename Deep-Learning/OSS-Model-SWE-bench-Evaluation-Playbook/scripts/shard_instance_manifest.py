#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path

from swebench_outcomes import sha256


def union_sha256(instance_ids: list[str]) -> str:
    payload = "".join(f"{instance_id}\n" for instance_id in sorted(instance_ids))
    return hashlib.sha256(payload.encode()).hexdigest()


def atomic_write_tsv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Split a frozen SWE-bench instance manifest into deterministic disjoint shards."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--shards", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--prefix", default="shard")
    args = parser.parse_args()

    if args.shards < 1:
        raise SystemExit("--shards must be positive")
    with args.manifest.open(newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if not reader.fieldnames or "instance_id" not in reader.fieldnames:
            raise SystemExit("Manifest must be TSV with an instance_id column")
        fieldnames = list(reader.fieldnames)
        rows = list(reader)
    instance_ids = [row.get("instance_id", "") for row in rows]
    if not instance_ids or any(not instance_id for instance_id in instance_ids):
        raise SystemExit("Manifest contains no instances or an empty instance_id")
    if len(instance_ids) != len(set(instance_ids)):
        raise SystemExit("Manifest contains duplicate instance IDs")
    if args.shards > len(rows):
        raise SystemExit("--shards cannot exceed the number of instances")

    sorted_rows = sorted(rows, key=lambda row: row["instance_id"])
    shards = [[] for _ in range(args.shards)]
    for index, row in enumerate(sorted_rows):
        shards[index % args.shards].append(row)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = args.output_dir / "sharding-summary.json"
    targets = [
        args.output_dir / f"{args.prefix}-{index:03d}.tsv"
        for index in range(args.shards)
    ]
    existing = [path for path in [*targets, summary_path] if path.exists()]
    if existing:
        raise SystemExit(f"Refusing to overwrite existing shard outputs: {existing}")

    shard_summaries = []
    emitted_ids = []
    for index, (path, shard_rows) in enumerate(zip(targets, shards)):
        atomic_write_tsv(path, fieldnames, shard_rows)
        shard_ids = [row["instance_id"] for row in shard_rows]
        emitted_ids.extend(shard_ids)
        shard_summaries.append(
            {
                "index": index,
                "path": path.name,
                "count": len(shard_ids),
                "instance_ids_sha256": union_sha256(shard_ids),
                "file_sha256": sha256(path),
            }
        )

    if sorted(emitted_ids) != sorted(instance_ids):
        raise RuntimeError("Internal error: shard union differs from source manifest")
    summary = {
        "schema_version": 1,
        "strategy": "sorted_round_robin",
        "source_manifest_sha256": sha256(args.manifest),
        "source_count": len(instance_ids),
        "shard_count": args.shards,
        "union_instance_ids_sha256": union_sha256(instance_ids),
        "shards": shard_summaries,
    }
    temporary = summary_path.with_suffix(summary_path.suffix + ".tmp")
    temporary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, summary_path)
    print(
        f"SHARD_MANIFEST=PASS cases={len(instance_ids)} shards={args.shards} "
        f"counts={','.join(str(len(shard)) for shard in shards)}"
    )


if __name__ == "__main__":
    main()
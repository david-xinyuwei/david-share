"""Cross-check the retained full-text answers against the numerical evidence.

Proves, offline and without calling any model, that every ``response_text`` in
``outputs/raw_fulltext/direct_<run>.jsonl`` hashes to the ``response_sha256``
stored in the numerical record with the same (arm, question_id, iteration) key,
and that the numerical fields of both files agree.

Usage:
    python scripts/verify_fulltext.py

Author: Xinyu Wei (魏新宇)
"""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = "20260909_120534"
OUTPUT = ROOT / "outputs"
KEY = ("arm", "question_id", "iteration")
IGNORED = {"response_text", "response_preview", "response_sha256", "cost_usd",
           "total_tokens", "visible_output_tokens_estimate"}


def load(path: Path) -> dict:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    keyed = {tuple(r[k] for k in KEY): r for r in rows}
    if len(keyed) != len(rows):
        raise ValueError(f"{path.name}: duplicate matrix cells")
    return keyed


def main() -> None:
    redaction_path = OUTPUT / "public_redaction.json"
    redaction = json.loads(redaction_path.read_text(encoding="utf-8")) if redaction_path.exists() else None
    withheld_ids = set(redaction["withheld_question_ids"]) if redaction else set()
    marker = redaction["marker"] if redaction else None
    numeric = load(OUTPUT / f"direct_{RUN}.metrics.jsonl")
    fulltext = load(OUTPUT / f"raw_fulltext/direct_{RUN}.jsonl")
    if set(numeric) != set(fulltext) or len(numeric) != 748:
        raise ValueError("Full-text and numerical files do not cover the same 748 cells.")
    mismatched_hash, mismatched_fields, withheld = [], [], 0
    for key, record in numeric.items():
        answer = fulltext[key]
        if key[1] in withheld_ids:
            if answer["response_text"] != marker:
                raise ValueError(f"withheld cell {key} does not carry the public-redaction marker")
            withheld += 1
        elif hashlib.sha256(answer["response_text"].encode()).hexdigest() != record["response_sha256"]:
            mismatched_hash.append(key)
        for field, value in record.items():
            if field not in IGNORED and answer.get(field) != value:
                mismatched_fields.append((key, field))
    if mismatched_hash or mismatched_fields:
        raise ValueError(f"hash mismatches={mismatched_hash[:5]} field mismatches={mismatched_fields[:5]}")
    chars = sum(len(a["response_text"]) for k, a in fulltext.items() if k[1] not in withheld_ids)
    note = f"; {withheld} answers to {sorted(withheld_ids)} withheld in the public copy (numbers and hashes kept)" if withheld else ""
    print(f"VERIFIED: {748 - withheld} answers match their SHA256 and numerical fields; {chars:,} characters of model output retained{note}.")


if __name__ == "__main__":
    main()

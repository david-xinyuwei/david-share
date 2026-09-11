"""Cross-check the retained Task B full-text answers against the numerical evidence.

Proves, offline and without calling any model, that every ``response_text`` in
``outputs/raw_fulltext/router_<run>.jsonl`` hashes to the ``response_sha256``
stored in ``outputs/router_<run>.metrics.jsonl`` for the same
(arm, question_id, iteration) cell, and that the numerical fields agree.

Usage:
    python scripts/verify_router_fulltext.py

Author: Xinyu Wei (魏新宇)
"""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = "20260909_223737"
EXPECTED = 1880
OUTPUT = ROOT / "outputs"
KEY = ("arm", "question_id", "iteration")
# Fields the builder adds or derives; they do not exist in the raw harness output.
IGNORED = {"response_text", "response_preview", "response_sha256", "cost_usd",
           "total_tokens", "visible_output_tokens_estimate", "category", "source"}


def load(path: Path) -> dict:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    keyed = {tuple(r[k] for k in KEY): r for r in rows}
    if len(keyed) != len(rows):
        raise ValueError(f"{path.name}: duplicate matrix cells")
    return keyed


def main() -> None:
    provenance = json.loads((OUTPUT / f"provenance_router_{RUN}.json").read_text(encoding="utf-8"))
    redaction_path = OUTPUT / "public_redaction.json"
    redaction = json.loads(redaction_path.read_text(encoding="utf-8")) if redaction_path.exists() else None
    withheld_ids = set(redaction["withheld_question_ids"]) if redaction else set()
    marker = redaction["marker"] if redaction else None

    def accepted(rel: str, *expected: str) -> set:
        """Hashes a file may legitimately carry: the recorded ones plus the public-redaction hash if recorded."""
        values = {e for e in expected if e}
        if redaction and rel in redaction["files"] and redaction["files"][rel]["original_sha256"] in values:
            values.add(redaction["files"][rel]["redacted_sha256"])
        return values

    raw_path = OUTPUT / f"raw_fulltext/router_{RUN}.jsonl"
    raw_digest = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    if raw_digest not in accepted(f"outputs/raw_fulltext/router_{RUN}.jsonl", provenance.get("retained_raw_sha256"), provenance["raw_sha256"]):
        raise ValueError("Full-text file SHA256 differs from provenance.")
    quality_path = OUTPUT / f"raw_fulltext/quality_{RUN}.jsonl"
    if hashlib.sha256(quality_path.read_bytes()).hexdigest() not in accepted(f"outputs/raw_fulltext/quality_{RUN}.jsonl", provenance["quality_sha256"]):
        raise ValueError("Raw quality file SHA256 differs from the VM export.")
    if load(quality_path) != load(OUTPUT / f"quality_router_{RUN}.jsonl"):
        raise ValueError("Retained judge scores differ from the generated quality file.")
    numeric = load(OUTPUT / f"router_{RUN}.metrics.jsonl")
    fulltext = load(raw_path)
    if set(numeric) != set(fulltext) or len(numeric) != EXPECTED:
        raise ValueError(f"Full-text and numerical files do not cover the same {EXPECTED} cells.")
    mismatched_hash, mismatched_fields, withheld = [], [], 0
    for key, record in numeric.items():
        answer = fulltext[key]
        if key[1] in withheld_ids:
            if answer.get("response_text") != marker:
                raise ValueError(f"withheld cell {key} does not carry the public-redaction marker")
            withheld += 1
        elif hashlib.sha256((answer.get("response_text") or "").encode()).hexdigest() != record["response_sha256"]:
            mismatched_hash.append(key)
        for field, value in record.items():
            if field not in IGNORED and answer.get(field) != value:
                mismatched_fields.append((key, field))
    if mismatched_hash or mismatched_fields:
        raise ValueError(f"hash mismatches={mismatched_hash[:5]} field mismatches={mismatched_fields[:5]}")
    chars = sum(len(a["response_text"]) for k, a in fulltext.items() if k[1] not in withheld_ids)
    served = sum(1 for a in fulltext.values() if a.get("served_model_family") == "gpt-5.6-sol")
    note = f"; {withheld} answers to {sorted(withheld_ids)} withheld in the public copy (numbers and hashes kept)" if withheld else ""
    print(f"VERIFIED: {EXPECTED - withheld} answers match their SHA256 and numerical fields; "
          f"{chars:,} characters of model output retained; {served} answers were served by gpt-5.6-sol{note}.")


if __name__ == "__main__":
    main()

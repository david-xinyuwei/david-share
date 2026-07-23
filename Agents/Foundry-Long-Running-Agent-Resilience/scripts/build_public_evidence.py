#!/usr/bin/env python3
"""Build the public matrix and manifest from sanitized run attestations."""

from __future__ import annotations

import json
from pathlib import Path

from lra_resilience.evidence import build_evidence_schema, validate_matrix
from lra_resilience.manifest import build_manifest


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "evidence" / "sanitized-runs"
MATRIX_PATH = ROOT / "data" / "validation-matrix.json"
SCHEMA_PATH = ROOT / "data" / "evidence-contract.schema.json"
MANIFEST_PATH = ROOT / "evidence" / "manifest.json"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    scenarios = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(RUNS.glob("*.json"))]
    matrix = {
        "schema_version": 2,
        "disclosure": "public-sanitized-attestation",
        "scope": "eight-main-documented-scenarios",
        "validation_date": "2026-07-23",
        "raw_evidence_disclosed": False,
        "scenarios": scenarios,
        "summary": {
            "passed": sum(scenario.get("status") == "passed" for scenario in scenarios),
            "total": len(scenarios),
            "all_main_scenarios_passed": all(scenario.get("status") == "passed" for scenario in scenarios),
        },
    }
    errors = validate_matrix(matrix)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    write_json(MATRIX_PATH, matrix)
    write_json(SCHEMA_PATH, build_evidence_schema())
    write_json(MANIFEST_PATH, build_manifest(ROOT))
    print(f"Built {len(scenarios)} sanitized attestations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

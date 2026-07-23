#!/usr/bin/env python3
"""Validate the committed evidence matrix and manifest."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from lra_resilience.evidence import build_evidence_schema, validate_matrix
from lra_resilience.manifest import load_manifest, validate_manifest


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    matrix = json.loads((root / "data" / "validation-matrix.json").read_text(encoding="utf-8"))
    committed_schema = json.loads(
        (root / "data" / "evidence-contract.schema.json").read_text(encoding="utf-8")
    )
    errors = validate_matrix(matrix)
    if committed_schema != build_evidence_schema():
        errors.append("committed JSON Schema differs from the authoritative Python contract")
    errors.extend(
        f"JSON Schema: {error.json_path}: {error.message}"
        for error in Draft202012Validator(
            committed_schema,
            format_checker=FormatChecker(),
        ).iter_errors(matrix)
    )
    errors.extend(validate_manifest(root, load_manifest(root / "evidence" / "manifest.json")))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print(
        f"PASS: {matrix['summary']['passed']}/{matrix['summary']['total']} sanitized scenarios "
        f"and {len(load_manifest(root / 'evidence' / 'manifest.json')['artifacts'])} artifacts verified"
    )

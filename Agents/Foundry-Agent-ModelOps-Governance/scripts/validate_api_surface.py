#!/usr/bin/env python3
"""Validate and print the Foundry API-surface evidence matrix."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = {
    "name",
    "example",
    "package_or_api",
    "client_or_resource",
    "operation",
    "resource_shape",
    "purpose",
    "governance_plane",
}


def load_matrix(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def validate_matrix(matrix: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    surfaces = matrix.get("surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        errors.append("matrix.surfaces must be a non-empty list")
        return errors

    names = set()
    operations = set()
    packages = set()
    for index, surface in enumerate(surfaces, start=1):
        missing = sorted(REQUIRED_FIELDS - set(surface))
        if missing:
            errors.append(f"surface {index} missing fields: {', '.join(missing)}")
            continue
        name = surface["name"]
        operation = surface["operation"]
        package = surface["package_or_api"]
        if name in names:
            errors.append(f"duplicate surface name: {name}")
        names.add(name)
        operations.add(operation)
        packages.add(package)

    if len(operations) != len(surfaces):
        errors.append("operations must be distinct; otherwise the matrix does not prove specialized operation surfaces")
    if len(packages) < 3:
        errors.append("expected at least three distinct package/API families")
    if matrix.get("conclusion") != "unified_context_specialized_operations":
        errors.append("matrix.conclusion must be unified_context_specialized_operations")
    return errors


def print_markdown(matrix: dict[str, Any]) -> None:
    print("| Surface | Package/API | Operation | Resource shape | Purpose |")
    print("|---|---|---|---|---|")
    for surface in matrix["surfaces"]:
        print(
            "| {name} | {package_or_api} | {operation} | {resource_shape} | {purpose} |".format(
                **surface
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the Foundry API-surface evidence matrix.")
    parser.add_argument(
        "--matrix",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "api-surfaces.json",
        help="Path to api-surfaces.json.",
    )
    parser.add_argument("--check", action="store_true", help="Validate the matrix and print a concise result.")
    parser.add_argument("--format", choices=["json", "markdown"], default="json", help="Output format.")
    args = parser.parse_args()

    matrix = load_matrix(args.matrix)
    errors = validate_matrix(matrix)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    if args.check:
        print(f"Validated {len(matrix['surfaces'])} API surfaces.")
        print(f"Governance-plane conclusion: {matrix['conclusion']}")
        return 0

    if args.format == "markdown":
        print_markdown(matrix)
    else:
        print(json.dumps(matrix, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

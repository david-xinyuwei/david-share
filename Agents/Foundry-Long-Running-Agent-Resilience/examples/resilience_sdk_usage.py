#!/usr/bin/env python3
"""Minimal executable use of the public AgentServer resilience SDK.

The handler is valid runtime code, but this file is not a complete Hosted Agent
deployment. Run it after installing requirements-validation.txt:

    python examples/resilience_sdk_usage.py --check

The check imports the pinned public package and registers the @task handler. It
does not call Azure or invent an endpoint, identity, model, or deployment.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any, Sequence

try:
    from resilience_handler import resilience_api_usage
except ModuleNotFoundError as error:
    raise SystemExit(
        "The public AgentServer SDK is required. Install it with:\n"
        "    python -m pip install -r requirements-validation.txt"
    ) from error


EXPECTED_CORE_VERSION = "2.0.0"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load and validate the public resilience SDK handler example."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the pinned package import and @task registration",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format (default: text)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="write the report to this path instead of stdout",
    )
    args = parser.parse_args(argv)
    if not args.check:
        parser.error("--check is required; the Hosted Agent runtime invokes the handler")
    return args


def collect_report() -> dict[str, Any]:
    installed = version("azure-ai-agentserver-core")
    checks = [
        {
            "name": "azure-ai-agentserver-core version",
            "passed": installed == EXPECTED_CORE_VERSION,
            "detail": f"installed={installed}; expected={EXPECTED_CORE_VERSION}",
        },
        {
            "name": "@task handler registered",
            "passed": (
                type(resilience_api_usage).__name__ == "Task"
                and resilience_api_usage.name == "resilience-api-usage"
            ),
            "detail": (
                f"type={type(resilience_api_usage).__name__}; "
                f"name={resilience_api_usage.name}"
            ),
        },
    ]
    return {
        "schema_version": 1,
        "evidence_type": "public-resilience-sdk-usage",
        "scenario_type": "dynamic-runtime",
        "claim_scope": (
            "Installed-package import and real @task decorator registration; "
            "not handler execution, durable-write acknowledgement, or live "
            "Hosted Agent recovery."
        ),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(
            timespec="milliseconds"
        ),
        "expected_core_version": EXPECTED_CORE_VERSION,
        "installed_core_version": installed,
        "registered_task_type": type(resilience_api_usage).__name__,
        "registered_task_name": resilience_api_usage.name,
        "checks": checks,
        "passed": all(item["passed"] for item in checks),
    }


def render(report: dict[str, Any], output_format: str) -> str:
    if output_format == "json":
        return json.dumps(
            report, ensure_ascii=False, indent=2, sort_keys=True
        ) + "\n"
    if report["passed"]:
        return (
            "PASS: imported azure.ai.agentserver.core.tasks and registered "
            f"{report['registered_task_type']} "
            f"'{report['registered_task_name']}' with core "
            f"{report['installed_core_version']}\n"
        )
    failed = [item["detail"] for item in report["checks"] if not item["passed"]]
    return "FAIL: " + "; ".join(failed) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = collect_report()
    content = render(report, args.format)
    if args.output is None:
        print(content, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Verify the documented recovery contract against the public AgentServer SDK.

This is an offline API-surface check. It does not claim that a live Hosted
Agent survived a process interruption.
"""

from __future__ import annotations

import argparse
import inspect
import json
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any, Sequence

SCHEMA_VERSION = 1
EXPECTED_VERSIONS = {
    "azure-ai-agentserver-core": "2.0.0",
    "azure-ai-agentserver-invocations": "1.0.0",
    "azure-ai-agentserver-responses": "2.0.0",
}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="verify_public_resilience_api.py",
        description=(
            "Check that the installed public Azure AI AgentServer packages "
            "expose the long-running recovery contract described in this "
            "repository."
        ),
        epilog=(
            "This is an offline API-contract check, not a live-service recovery "
            "test. Exit codes: 0 = every check passed, 1 = at least one failed."
        ),
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="print only the text summary; SDK warnings may still use stderr",
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
    if args.quiet and args.format != "text":
        parser.error("--quiet is valid only with --format text")
    return args


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def collect_report() -> dict[str, Any]:
    # Imports stay here so --help works before dependencies are installed.
    from azure.ai.agentserver.core.tasks import (
        EntryMode,
        RetryPolicy,
        TaskContext,
        TaskMetadata,
        resilient_tasks_enabled,
        task,
    )
    from azure.ai.agentserver.responses import (
        ExitForRecoverySignal,
        ResponseExitForRecovery,
    )

    checks: list[dict[str, Any]] = []

    def check(name: str, condition: bool, detail: object = "") -> None:
        checks.append(
            {
                "name": name,
                "passed": bool(condition),
                "detail": str(detail) if detail else "",
            }
        )

    installed_versions = {
        package: version(package) for package in EXPECTED_VERSIONS
    }
    for package, expected in EXPECTED_VERSIONS.items():
        installed = installed_versions[package]
        check(
            f"{package} version",
            installed == expected,
            f"installed={installed}; expected={expected}",
        )

    modes = set(EntryMode.__args__)
    check("EntryMode exposes recovered re-entry", "recovered" in modes, sorted(modes))

    context_members = {
        member for member in dir(TaskContext) if not member.startswith("_")
    }
    check(
        "entry_mode and retry_attempt are separate fields",
        {"entry_mode", "retry_attempt"} <= context_members,
    )
    check(
        "recovery_count is separate from retry_attempt",
        {"recovery_count", "retry_attempt"} <= context_members,
    )
    check("task_id (work identity) is exposed", "task_id" in context_members)
    check("input_id (input identity) is exposed", "input_id" in context_members)

    metadata_operations = {
        member for member in dir(TaskMetadata) if not member.startswith("_")
    }
    check(
        "metadata exposes checkpoint operations",
        {"get", "set", "increment", "append", "flush"} <= metadata_operations,
        "API surface only; flush return is not a durable-write acknowledgement",
    )
    check("cooperative shutdown is exposed", "shutdown" in context_members)
    check("exit-for-recovery is exposed", "exit_for_recovery" in context_members)
    check(
        "steering is exposed",
        {"is_steered_turn", "pending_input_count"} <= context_members,
    )
    check("RetryPolicy is public", inspect.isclass(RetryPolicy))
    check(
        "resilient-task enablement is queryable",
        isinstance(resilient_tasks_enabled(), bool),
        f"enabled={resilient_tasks_enabled()}",
    )
    check(
        "Responses recovery signals are public",
        inspect.isclass(ExitForRecoverySignal)
        and inspect.isclass(ResponseExitForRecovery),
    )

    async def typed_handler(ctx):
        return ctx.input

    typed_handler.__annotations__ = {"ctx": TaskContext[str], "return": str}
    typed_task = task(
        name="verify-work", timeout=None, retry=RetryPolicy()
    )(typed_handler)
    check("@task accepts name, timeout, and retry", typed_task is not None)

    async def wrong_name_handler(context):
        return context.input

    wrong_name_handler.__annotations__ = {
        "context": TaskContext[str],
        "return": str,
    }
    try:
        task(name="invalid-parameter-name")(wrong_name_handler)
    except TypeError as error:
        check(
            "handler first argument must be named ctx",
            "must be named `ctx`" in str(error),
            error,
        )
    else:
        check("handler first argument must be named ctx", False, "wrong name accepted")

    async def bare_handler(ctx):
        return str(ctx.input)

    bare_handler.__annotations__ = {"ctx": TaskContext, "return": str}
    try:
        task(name="invalid-bare-context")(bare_handler)
    except TypeError as error:
        check(
            "handler requires TaskContext[Input]",
            "TaskContext[Input]" in str(error),
            error,
        )
    else:
        check(
            "handler requires TaskContext[Input]",
            False,
            "bare TaskContext accepted",
        )

    passed = sum(item["passed"] for item in checks)
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_type": "public-sdk-contract",
        "scenario_type": "dynamic-runtime",
        "claim_scope": (
            "Offline installed-package probe; not live Hosted Agent recovery evidence."
        ),
        "generated_at_utc": utc_now(),
        "expected_versions": EXPECTED_VERSIONS,
        "installed_versions": installed_versions,
        "checks": checks,
        "summary": {
            "passed": passed,
            "failed": len(checks) - passed,
            "total": len(checks),
        },
        "passed": passed == len(checks),
    }


def render_text(report: dict[str, Any], *, quiet: bool) -> str:
    lines: list[str] = []
    if not quiet:
        width = max(len(item["name"]) for item in report["checks"])
        for item in report["checks"]:
            status = "PASS" if item["passed"] else "FAIL"
            suffix = f"  <- {item['detail']}" if item["detail"] else ""
            lines.append(f"  [{status}] {item['name'].ljust(width)}{suffix}")
        lines.append("")
    summary = report["summary"]
    lines.append(
        f"{summary['passed']}/{summary['total']} checks passed against the public SDK"
    )
    return "\n".join(lines) + "\n"


def render(report: dict[str, Any], *, output_format: str, quiet: bool) -> str:
    if output_format == "json":
        return json.dumps(
            report, ensure_ascii=False, indent=2, sort_keys=True
        ) + "\n"
    return render_text(report, quiet=quiet)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = collect_report()
    content = render(report, output_format=args.format, quiet=args.quiet)
    if args.output is None:
        print(content, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

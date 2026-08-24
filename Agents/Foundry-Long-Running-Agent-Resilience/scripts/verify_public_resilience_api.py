"""Verify the documented recovery contract against the public AgentServer SDK.

This offline check verifies the installed public API surface. It does not claim
that a live Hosted Agent survived a process interruption.
"""

import argparse
import inspect
from importlib.metadata import version


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="verify_public_resilience_api.py",
        description=(
            "Check that the installed public Azure AI AgentServer packages expose the "
            "long-running recovery contract described in this repository's article: "
            "durable work and input identity, recovery re-entry that is distinct from "
            "retry, a durable metadata checkpoint index, cooperative shutdown, "
            "exit-for-recovery, and steering."
        ),
        epilog=(
            "This is an offline API-contract check, not a live-service test. It cannot "
            "prove that Foundry replaced a host or reclaimed a lease. "
            "Exit codes: 0 = every check passed, 1 = at least one check failed."
        ),
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="drop the per-check result lines and print only the summary",
    )
    return parser.parse_args()


# Arguments are parsed before the SDK imports so that --help works on a machine
# where the packages are not installed yet.
args = parse_args()

from azure.ai.agentserver.core.tasks import (  # noqa: E402
    EntryMode,
    RetryPolicy,
    TaskContext,
    TaskMetadata,
    resilient_tasks_enabled,
    task,
)
from azure.ai.agentserver.responses import (  # noqa: E402
    ExitForRecoverySignal,
    ResponseExitForRecovery,
)


EXPECTED_VERSIONS = {
    "azure-ai-agentserver-core": "2.0.0",
    "azure-ai-agentserver-invocations": "1.0.0",
    "azure-ai-agentserver-responses": "2.0.0",
}

results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: object = "") -> None:
    results.append((name, bool(condition), str(detail) if detail else ""))


for package, expected in EXPECTED_VERSIONS.items():
    installed = version(package)
    check(f"{package} version", installed == expected, f"installed={installed}")

modes = set(EntryMode.__args__)
check("EntryMode exposes recovered re-entry", "recovered" in modes, sorted(modes))

context_members = {member for member in dir(TaskContext) if not member.startswith("_")}
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
    "metadata supports a durable checkpoint index",
    {"get", "set", "increment", "append", "flush"} <= metadata_operations,
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


@task(name="verify-work", timeout=None, retry=RetryPolicy())
async def typed_handler(ctx: TaskContext[str]) -> str:
    return ctx.input


check("@task accepts name, timeout, and retry", typed_handler is not None)


async def wrong_name_handler(context: TaskContext[str]) -> str:
    return context.input


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


async def bare_handler(ctx: TaskContext) -> str:
    return str(ctx.input)


try:
    task(name="invalid-bare-context")(bare_handler)
except TypeError as error:
    check(
        "handler requires TaskContext[Input]",
        "TaskContext[Input]" in str(error),
        error,
    )
else:
    check("handler requires TaskContext[Input]", False, "bare TaskContext accepted")

width = max(len(name) for name, _, _ in results)
failures = 0
for name, passed, detail in results:
    status = "PASS" if passed else "FAIL"
    failures += not passed
    if not args.quiet:
        suffix = f"  <- {detail}" if detail else ""
        print(f"  [{status}] {name.ljust(width)}{suffix}")

if not args.quiet:
    print()
print(f"{len(results) - failures}/{len(results)} checks passed against the public SDK")
raise SystemExit(1 if failures else 0)

#!/usr/bin/env python3
"""Run an executable reference model of the documented recovery contract.

This is a public-safe test fixture, not Microsoft Foundry service source and
not a live-service recovery test. It uses only the Python standard library:

* SQLite persists work, input, lease, checkpoint, and phase results.
* Worker A commits one or more phases and then exits with ``os._exit(9)``.
* Worker B is a separate OS process that reclaims the expired lease.
* Every durable write is fenced by lease owner and generation.
* Phase commits and their idempotency keys are recorded atomically.

The demo emits a JSON summary and can write a structured JSONL event log.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

SCHEMA_VERSION = 1
INJECTED_EXIT_CODE = 9


class DemoError(RuntimeError):
    """Base class for explicit demo failures."""


class ExistingWorkError(DemoError):
    """Raised when a demo tries to overwrite existing durable work."""


class WorkUnavailableError(DemoError):
    """Raised when work cannot be claimed in its current state."""


class LeaseLostError(DemoError):
    """Raised when a stale or expired worker attempts a durable write."""


class ConflictingCommitError(DemoError):
    """Raised when one phase key is reused for different durable content."""


@dataclass(frozen=True)
class Lease:
    work_id: str
    owner: str
    generation: int
    entry_mode: str
    expires_at: float


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def phase_result(payload: str, phase: int) -> dict[str, Any]:
    """Produce deterministic work output that varies with payload and phase."""
    return {
        "phase": phase,
        "payload_sha256": sha256_text(payload),
        "result_sha256": sha256_text(f"{payload}\0{phase}"),
    }


class DurableWorkStore:
    """SQLite implementation of the public-safe recovery reference model."""

    def __init__(self, database: Path) -> None:
        self.database = database

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS work (
                    work_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'completed')),
                    checkpoint INTEGER NOT NULL DEFAULT 0 CHECK (checkpoint >= 0),
                    lease_owner TEXT,
                    lease_generation INTEGER NOT NULL DEFAULT 0 CHECK (lease_generation >= 0),
                    lease_expires_at REAL
                );

                CREATE TABLE IF NOT EXISTS phase_commits (
                    work_id TEXT NOT NULL REFERENCES work(work_id),
                    phase INTEGER NOT NULL CHECK (phase > 0),
                    idempotency_key TEXT NOT NULL UNIQUE,
                    result_json TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    lease_generation INTEGER NOT NULL,
                    PRIMARY KEY (work_id, phase)
                );

                CREATE TABLE IF NOT EXISTS events (
                    event_index INTEGER PRIMARY KEY AUTOINCREMENT,
                    schema_version INTEGER NOT NULL,
                    timestamp_utc TEXT NOT NULL,
                    event TEXT NOT NULL,
                    work_id TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    process_id INTEGER NOT NULL,
                    lease_generation INTEGER NOT NULL,
                    entry_mode TEXT,
                    phase INTEGER,
                    checkpoint INTEGER,
                    details_json TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _append_event(
        connection: sqlite3.Connection,
        *,
        event: str,
        work_id: str,
        worker_id: str,
        generation: int,
        entry_mode: str | None = None,
        phase: int | None = None,
        checkpoint: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO events (
                schema_version, timestamp_utc, event, work_id, worker_id,
                process_id, lease_generation, entry_mode, phase, checkpoint,
                details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                SCHEMA_VERSION,
                utc_now(),
                event,
                work_id,
                worker_id,
                os.getpid(),
                generation,
                entry_mode,
                phase,
                checkpoint,
                json.dumps(details or {}, sort_keys=True),
            ),
        )

    def create_work(self, work_id: str, payload: str) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute(
                "SELECT 1 FROM work WHERE work_id = ?", (work_id,)
            ).fetchone():
                raise ExistingWorkError(f"work already exists: {work_id}")
            connection.execute(
                """
                INSERT INTO work (
                    work_id, payload, payload_sha256, status, checkpoint,
                    lease_generation
                ) VALUES (?, ?, ?, 'pending', 0, 0)
                """,
                (work_id, payload, sha256_text(payload)),
            )
            self._append_event(
                connection,
                event="work_created",
                work_id=work_id,
                worker_id="controller",
                generation=0,
                checkpoint=0,
                details={"payload_sha256": sha256_text(payload)},
            )

    def claim_work(
        self, work_id: str, *, worker_id: str, lease_seconds: float
    ) -> Lease:
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            # The lock wait can be longer than a short lease. Start the lease
            # clock only after this transaction owns the SQLite write lock.
            now = time.time()
            row = connection.execute(
                "SELECT * FROM work WHERE work_id = ?", (work_id,)
            ).fetchone()
            if row is None:
                raise WorkUnavailableError(f"work not found: {work_id}")

            is_fresh = row["status"] == "pending"
            is_expired = (
                row["status"] == "running"
                and row["lease_expires_at"] is not None
                and float(row["lease_expires_at"]) <= now
            )
            if not (is_fresh or is_expired):
                raise WorkUnavailableError(
                    f"work {work_id!r} is {row['status']!r} and not claimable"
                )

            generation = int(row["lease_generation"]) + 1
            entry_mode = "fresh" if is_fresh else "recovered"
            expires_at = now + lease_seconds
            connection.execute(
                """
                UPDATE work
                SET status = 'running',
                    lease_owner = ?,
                    lease_generation = ?,
                    lease_expires_at = ?
                WHERE work_id = ?
                """,
                (worker_id, generation, expires_at, work_id),
            )
            self._append_event(
                connection,
                event="handler_entry",
                work_id=work_id,
                worker_id=worker_id,
                generation=generation,
                entry_mode=entry_mode,
                checkpoint=int(row["checkpoint"]),
                details={"lease_seconds": lease_seconds},
            )
            return Lease(
                work_id=work_id,
                owner=worker_id,
                generation=generation,
                entry_mode=entry_mode,
                expires_at=expires_at,
            )

    @staticmethod
    def _require_active_lease(
        connection: sqlite3.Connection, lease: Lease
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM work WHERE work_id = ?", (lease.work_id,)
        ).fetchone()
        if row is None:
            raise LeaseLostError(f"work not found: {lease.work_id}")
        if (
            row["status"] != "running"
            or row["lease_owner"] != lease.owner
            or int(row["lease_generation"]) != lease.generation
            or row["lease_expires_at"] is None
            or float(row["lease_expires_at"]) <= time.time()
        ):
            raise LeaseLostError(
                f"worker {lease.owner!r} no longer owns generation "
                f"{lease.generation} of {lease.work_id!r}"
            )
        return row

    def commit_phase(
        self,
        lease: Lease,
        *,
        phase: int,
        idempotency_key: str,
        result: dict[str, Any],
        lease_seconds: float,
    ) -> bool:
        result_json = json.dumps(result, sort_keys=True)
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._require_active_lease(connection, lease)
            existing = connection.execute(
                """
                SELECT idempotency_key, result_json
                FROM phase_commits
                WHERE work_id = ? AND phase = ?
                """,
                (lease.work_id, phase),
            ).fetchone()
            if existing is not None:
                if (
                    existing["idempotency_key"] != idempotency_key
                    or existing["result_json"] != result_json
                ):
                    raise ConflictingCommitError(
                        f"phase {phase} was already committed with different content"
                    )
                self._append_event(
                    connection,
                    event="phase_replay_deduplicated",
                    work_id=lease.work_id,
                    worker_id=lease.owner,
                    generation=lease.generation,
                    entry_mode=lease.entry_mode,
                    phase=phase,
                    checkpoint=int(row["checkpoint"]),
                )
                return False

            expected_phase = int(row["checkpoint"]) + 1
            if phase != expected_phase:
                raise ConflictingCommitError(
                    f"expected phase {expected_phase}, received {phase}"
                )

            connection.execute(
                """
                INSERT INTO phase_commits (
                    work_id, phase, idempotency_key, result_json, worker_id,
                    lease_generation
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    lease.work_id,
                    phase,
                    idempotency_key,
                    result_json,
                    lease.owner,
                    lease.generation,
                ),
            )
            connection.execute(
                """
                UPDATE work
                SET checkpoint = ?, lease_expires_at = ?
                WHERE work_id = ?
                """,
                (phase, time.time() + lease_seconds, lease.work_id),
            )
            self._append_event(
                connection,
                event="phase_committed",
                work_id=lease.work_id,
                worker_id=lease.owner,
                generation=lease.generation,
                entry_mode=lease.entry_mode,
                phase=phase,
                checkpoint=phase,
                details={
                    "idempotency_key": idempotency_key,
                    "result_sha256": sha256_text(result_json),
                },
            )
            return True

    def record_injected_loss(self, lease: Lease, *, phase: int) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._require_active_lease(connection, lease)
            self._append_event(
                connection,
                event="process_loss_injected",
                work_id=lease.work_id,
                worker_id=lease.owner,
                generation=lease.generation,
                entry_mode=lease.entry_mode,
                phase=phase,
                checkpoint=int(row["checkpoint"]),
                details={"exit_code": INJECTED_EXIT_CODE},
            )

    def complete_work(self, lease: Lease, *, expected_phases: int) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._require_active_lease(connection, lease)
            if int(row["checkpoint"]) != expected_phases:
                raise ConflictingCommitError(
                    f"cannot complete at checkpoint {row['checkpoint']}; "
                    f"expected {expected_phases}"
                )
            connection.execute(
                """
                UPDATE work
                SET status = 'completed',
                    lease_owner = NULL,
                    lease_expires_at = NULL
                WHERE work_id = ?
                """,
                (lease.work_id,),
            )
            self._append_event(
                connection,
                event="work_completed",
                work_id=lease.work_id,
                worker_id=lease.owner,
                generation=lease.generation,
                entry_mode=lease.entry_mode,
                checkpoint=expected_phases,
            )

    def snapshot(self, work_id: str) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            work = connection.execute(
                "SELECT * FROM work WHERE work_id = ?", (work_id,)
            ).fetchone()
            if work is None:
                raise WorkUnavailableError(f"work not found: {work_id}")
            phases = connection.execute(
                """
                SELECT phase, idempotency_key, result_json, worker_id,
                       lease_generation
                FROM phase_commits
                WHERE work_id = ?
                ORDER BY phase
                """,
                (work_id,),
            ).fetchall()
            return {
                "work_id": work["work_id"],
                "payload_sha256": work["payload_sha256"],
                "status": work["status"],
                "checkpoint": int(work["checkpoint"]),
                "lease_owner": work["lease_owner"],
                "lease_generation": int(work["lease_generation"]),
                "lease_expires_at": work["lease_expires_at"],
                "phases": [
                    {
                        "phase": int(row["phase"]),
                        "idempotency_key": row["idempotency_key"],
                        "result": json.loads(row["result_json"]),
                        "worker_id": row["worker_id"],
                        "lease_generation": int(row["lease_generation"]),
                    }
                    for row in phases
                ],
            }

    def events(self, work_id: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM events
                WHERE work_id = ?
                ORDER BY event_index
                """,
                (work_id,),
            ).fetchall()
            return [
                {
                    "event_index": int(row["event_index"]),
                    "schema_version": int(row["schema_version"]),
                    "timestamp_utc": row["timestamp_utc"],
                    "event": row["event"],
                    "work_id": row["work_id"],
                    "worker_id": row["worker_id"],
                    "process_id": int(row["process_id"]),
                    "lease_generation": int(row["lease_generation"]),
                    "entry_mode": row["entry_mode"],
                    "phase": row["phase"],
                    "checkpoint": row["checkpoint"],
                    "details": json.loads(row["details_json"]),
                }
                for row in rows
            ]


def validate_config(
    *, work_id: str, payload: str, phases: int, crash_after: int, lease_seconds: float
) -> None:
    if not work_id.strip() or len(work_id) > 128:
        raise ValueError("work_id must contain 1-128 non-whitespace characters")
    if not payload:
        raise ValueError("payload must not be empty")
    if phases < 2:
        raise ValueError("phases must be at least 2")
    if crash_after < 1 or crash_after >= phases:
        raise ValueError("crash_after must be between 1 and phases - 1")
    if not 0.2 <= lease_seconds <= 60:
        raise ValueError("lease_seconds must be between 0.2 and 60")


def run_worker(
    *,
    database: Path,
    work_id: str,
    worker_id: str,
    phases: int,
    crash_after: int | None,
    lease_seconds: float,
) -> int:
    store = DurableWorkStore(database)
    store.initialize()
    lease = store.claim_work(
        work_id, worker_id=worker_id, lease_seconds=lease_seconds
    )
    snapshot = store.snapshot(work_id)
    payload = _read_payload(database, work_id)

    for phase in range(int(snapshot["checkpoint"]) + 1, phases + 1):
        store.commit_phase(
            lease,
            phase=phase,
            idempotency_key=f"{work_id}:phase:{phase}",
            result=phase_result(payload, phase),
            lease_seconds=lease_seconds,
        )
        if crash_after == phase:
            store.record_injected_loss(lease, phase=phase)
            os._exit(INJECTED_EXIT_CODE)

    store.complete_work(lease, expected_phases=phases)
    return 0


def _read_payload(database: Path, work_id: str) -> str:
    with closing(sqlite3.connect(database)) as connection:
        row = connection.execute(
            "SELECT payload FROM work WHERE work_id = ?", (work_id,)
        ).fetchone()
        if row is None:
            raise WorkUnavailableError(f"work not found: {work_id}")
        return str(row[0])


def _worker_command(
    *,
    database: Path,
    work_id: str,
    worker_id: str,
    phases: int,
    crash_after: int | None,
    lease_seconds: float,
) -> list[str]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "_worker",
        "--database",
        str(database),
        "--work-id",
        work_id,
        "--worker-id",
        worker_id,
        "--phases",
        str(phases),
        "--lease-seconds",
        str(lease_seconds),
    ]
    if crash_after is not None:
        command.extend(["--crash-after", str(crash_after)])
    return command


def _run_worker_process(command: Sequence[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _wait_for_lease_expiry(store: DurableWorkStore, work_id: str) -> None:
    expires_at = store.snapshot(work_id)["lease_expires_at"]
    if expires_at is None:
        raise LeaseLostError("crashed worker left no lease expiry")
    remaining = float(expires_at) - time.time()
    if remaining > 0:
        time.sleep(remaining + 0.02)


def run_demo(
    state_dir: Path,
    *,
    work_id: str,
    payload: str,
    phases: int,
    crash_after: int,
    lease_seconds: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    validate_config(
        work_id=work_id,
        payload=payload,
        phases=phases,
        crash_after=crash_after,
        lease_seconds=lease_seconds,
    )
    state_dir.mkdir(parents=True, exist_ok=True)
    database = state_dir / "recovery-contract.sqlite3"
    if database.exists():
        raise ExistingWorkError(
            f"state database already exists; choose an empty directory: {database}"
        )

    store = DurableWorkStore(database)
    store.initialize()
    store.create_work(work_id, payload)

    worker_a = _run_worker_process(
        _worker_command(
            database=database,
            work_id=work_id,
            worker_id="worker-a",
            phases=phases,
            crash_after=crash_after,
            lease_seconds=lease_seconds,
        ),
        timeout=30,
    )
    if worker_a.returncode != INJECTED_EXIT_CODE:
        raise DemoError(
            f"worker A returned {worker_a.returncode}, expected "
            f"{INJECTED_EXIT_CODE}; stderr={worker_a.stderr.strip()!r}"
        )

    _wait_for_lease_expiry(store, work_id)
    worker_b = _run_worker_process(
        _worker_command(
            database=database,
            work_id=work_id,
            worker_id="worker-b",
            phases=phases,
            crash_after=None,
            lease_seconds=lease_seconds,
        ),
        timeout=30,
    )
    if worker_b.returncode != 0:
        raise DemoError(
            f"worker B returned {worker_b.returncode}; "
            f"stderr={worker_b.stderr.strip()!r}"
        )

    snapshot = store.snapshot(work_id)
    events = store.events(work_id)
    committed_phases = [item["phase"] for item in snapshot["phases"]]
    phase_workers = {
        str(item["phase"]): item["worker_id"] for item in snapshot["phases"]
    }
    phase_result_sha256s = [
        item["result"]["result_sha256"] for item in snapshot["phases"]
    ]
    entry_modes = [
        event["entry_mode"]
        for event in events
        if event["event"] == "handler_entry"
    ]
    checks = {
        "worker_a_hard_exit_observed": worker_a.returncode == INJECTED_EXIT_CODE,
        "worker_b_completed": worker_b.returncode == 0,
        "same_work_recovered": len({event["work_id"] for event in events}) == 1,
        "fresh_then_recovered": entry_modes == ["fresh", "recovered"],
        "generation_advanced": snapshot["lease_generation"] == 2,
        "checkpoint_complete": snapshot["checkpoint"] == phases,
        "phase_domain_complete": committed_phases == list(range(1, phases + 1)),
        "no_duplicate_phase_commit": len(committed_phases)
        == len(set(committed_phases)),
        "original_worker_stopped_at_injected_phase": all(
            worker == ("worker-a" if phase <= crash_after else "worker-b")
            for phase, worker in (
                (int(phase), owner) for phase, owner in phase_workers.items()
            )
        ),
        "payload_affected_every_result": all(
            item["result"] == phase_result(payload, item["phase"])
            for item in snapshot["phases"]
        ),
    }
    summary = {
        "schema_version": SCHEMA_VERSION,
        "scenario_type": "test-fixture",
        "claim_scope": (
            "Executable local reference model; not Foundry service source "
            "and not live-service recovery evidence."
        ),
        "work_id": work_id,
        "payload_sha256": sha256_text(payload),
        "configuration": {
            "phases": phases,
            "crash_after": crash_after,
            "lease_seconds": lease_seconds,
        },
        "worker_a_exit_code": worker_a.returncode,
        "worker_b_exit_code": worker_b.returncode,
        "entry_modes": entry_modes,
        "lease_generation": snapshot["lease_generation"],
        "checkpoint": snapshot["checkpoint"],
        "committed_phases": committed_phases,
        "phase_workers": phase_workers,
        "phase_result_sha256s": phase_result_sha256s,
        "checks": checks,
        "passed": all(checks.values()),
    }
    return summary, events


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, events: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for event in events:
            stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Execute a real two-process SQLite recovery reference model. "
            "This is a test fixture, not Microsoft Foundry service code."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo = subparsers.add_parser("demo", help="run the crash/recovery demonstration")
    demo.add_argument("--state-dir", type=Path)
    demo.add_argument("--work-id", default="recovery-contract-demo")
    demo.add_argument("--payload", default="public-safe synthetic workload")
    demo.add_argument("--phases", type=int, default=5)
    demo.add_argument("--crash-after", type=int, default=1)
    demo.add_argument("--lease-seconds", type=float, default=0.5)
    demo.add_argument("--summary-file", type=Path)
    demo.add_argument("--events-file", type=Path)

    worker = subparsers.add_parser(
        "_worker", help=argparse.SUPPRESS, description="internal worker entry point"
    )
    worker.add_argument("--database", type=Path, required=True)
    worker.add_argument("--work-id", required=True)
    worker.add_argument("--worker-id", required=True)
    worker.add_argument("--phases", type=int, required=True)
    worker.add_argument("--crash-after", type=int)
    worker.add_argument("--lease-seconds", type=float, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "_worker":
        return run_worker(
            database=args.database,
            work_id=args.work_id,
            worker_id=args.worker_id,
            phases=args.phases,
            crash_after=args.crash_after,
            lease_seconds=args.lease_seconds,
        )

    if args.state_dir is not None:
        summary, events = run_demo(
            args.state_dir,
            work_id=args.work_id,
            payload=args.payload,
            phases=args.phases,
            crash_after=args.crash_after,
            lease_seconds=args.lease_seconds,
        )
    else:
        with tempfile.TemporaryDirectory(prefix="lra-recovery-contract-") as temp:
            summary, events = run_demo(
                Path(temp),
                work_id=args.work_id,
                payload=args.payload,
                phases=args.phases,
                crash_after=args.crash_after,
                lease_seconds=args.lease_seconds,
            )

    if args.summary_file is not None:
        write_json(args.summary_file, summary)
    if args.events_file is not None:
        write_jsonl(args.events_file, events)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

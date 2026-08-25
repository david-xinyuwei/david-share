from __future__ import annotations

import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from recovery_contract_demo import (  # noqa: E402
    ConflictingCommitError,
    DurableWorkStore,
    ExistingWorkError,
    LeaseLostError,
    phase_result,
    run_demo,
)


class RecoveryContractDemoTests(unittest.TestCase):
    def test_lease_clock_starts_after_sqlite_lock_is_acquired(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = DurableWorkStore(Path(temp) / "state.sqlite3")
            store.initialize()
            store.create_work("lock-wait", "payload")
            blocker = sqlite3.connect(store.database)
            blocker.execute("BEGIN IMMEDIATE")
            with ThreadPoolExecutor(max_workers=1) as executor:
                claim = executor.submit(
                    store.claim_work,
                    "lock-wait",
                    worker_id="worker-a",
                    lease_seconds=0.2,
                )
                time.sleep(0.25)
                blocker.commit()
                lease = claim.result(timeout=5)
            blocker.close()

        # If the lease clock started before the 250 ms lock wait, it would
        # already be expired here. Keep margin for Windows process scheduling.
        self.assertGreater(lease.expires_at - time.time(), 0.05)

    def test_existing_state_is_not_silently_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            state_dir = Path(temp)
            run_demo(
                state_dir,
                work_id="existing-state",
                payload="alpha",
                phases=3,
                crash_after=1,
                lease_seconds=0.5,
            )
            with self.assertRaises(ExistingWorkError):
                run_demo(
                    state_dir,
                    work_id="existing-state",
                    payload="beta",
                    phases=3,
                    crash_after=1,
                    lease_seconds=0.5,
                )

    def test_real_process_loss_recovery_completes_without_duplicate_phase(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            summary, events = run_demo(
                Path(temp),
                work_id="process-loss",
                payload="alpha",
                phases=4,
                crash_after=1,
                lease_seconds=0.5,
            )

        self.assertTrue(summary["passed"])
        self.assertEqual(summary["worker_a_exit_code"], 9)
        self.assertEqual(summary["entry_modes"], ["fresh", "recovered"])
        self.assertEqual(summary["committed_phases"], [1, 2, 3, 4])
        self.assertEqual(summary["phase_workers"]["1"], "worker-a")
        self.assertEqual(summary["phase_workers"]["4"], "worker-b")
        self.assertIn("process_loss_injected", [event["event"] for event in events])

    def test_stale_generation_cannot_commit_after_reclaim(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = DurableWorkStore(Path(temp) / "state.sqlite3")
            store.initialize()
            store.create_work("fence", "payload")
            stale = store.claim_work(
                "fence", worker_id="worker-a", lease_seconds=0.2
            )
            time.sleep(0.25)
            current = store.claim_work(
                "fence", worker_id="worker-b", lease_seconds=1
            )

            with self.assertRaises(LeaseLostError):
                store.commit_phase(
                    stale,
                    phase=1,
                    idempotency_key="fence:phase:1",
                    result=phase_result("payload", 1),
                    lease_seconds=1,
                )

            self.assertEqual(current.generation, stale.generation + 1)

    def test_replay_is_idempotent_but_conflicting_content_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = DurableWorkStore(Path(temp) / "state.sqlite3")
            store.initialize()
            store.create_work("idempotency", "payload")
            lease = store.claim_work(
                "idempotency", worker_id="worker-a", lease_seconds=1
            )
            result = phase_result("payload", 1)

            first = store.commit_phase(
                lease,
                phase=1,
                idempotency_key="idempotency:phase:1",
                result=result,
                lease_seconds=1,
            )
            replay = store.commit_phase(
                lease,
                phase=1,
                idempotency_key="idempotency:phase:1",
                result=result,
                lease_seconds=1,
            )

            self.assertTrue(first)
            self.assertFalse(replay)
            with self.assertRaises(ConflictingCommitError):
                store.commit_phase(
                    lease,
                    phase=1,
                    idempotency_key="idempotency:phase:1",
                    result={"phase": 1, "result_sha256": "different"},
                    lease_seconds=1,
                )

    def test_materially_different_payloads_change_durable_results(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first, _ = run_demo(
                Path(first_dir),
                work_id="differential-a",
                payload="alpha",
                phases=3,
                crash_after=1,
                lease_seconds=0.5,
            )
            second, _ = run_demo(
                Path(second_dir),
                work_id="differential-b",
                payload="beta",
                phases=3,
                crash_after=1,
                lease_seconds=0.5,
            )

        self.assertNotEqual(first["payload_sha256"], second["payload_sha256"])
        self.assertNotEqual(
            first["phase_result_sha256s"], second["phase_result_sha256s"]
        )
        self.assertTrue(first["passed"])
        self.assertTrue(second["passed"])


if __name__ == "__main__":
    unittest.main()

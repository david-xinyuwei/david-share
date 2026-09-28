"""Evidence: recomputation semantics, fail-closed checks and the committed measurements."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_evidence as ev  # noqa: E402


def row(minute, proc=0, users="", util=0.0, sm=0.0, computer="vm-a", gpu=0):
    return {"Minute": minute, "Computer": computer, "GpuId": gpu, "ProcCount": proc, "Users": users,
            "GpuUtil": util, "SmActive": sm}


class SemanticsTests(unittest.TestCase):
    def test_allocated_busy_effective_idle(self):
        hb = [{"Minute": m, "Computer": "vm-a"} for m in range(4)]
        gpu = [row(0), row(1, proc=1, users="a", util=50, sm=0.5), row(2, util=9, sm=0.2), row(3, proc=1, users="a")]
        s = ev.recompute(gpu, hb)["summary"]
        self.assertAlmostEqual(s["AllocatedGpuHours"], 4 / 60)
        self.assertAlmostEqual(s["BusyGpuHours"], 3 / 60)  # process present, or util >= 5 without a process
        self.assertAlmostEqual(s["EffectiveGpuHours"], 0.7 / 60)
        self.assertAlmostEqual(s["IdleGpuHours"], 1 / 60)

    def test_shared_minute_is_split_between_owners(self):
        hb = [{"Minute": m, "Computer": "vm-a"} for m in range(2)]
        gpu = [row(0, proc=1, users="a", sm=1.0, util=100), row(1, proc=2, users="a,b", sm=1.0, util=100)]
        users = {u["User"]: u for u in ev.recompute(gpu, hb)["per_user"]}
        self.assertAlmostEqual(users["a"]["BusyGpuHours"], 1.5 / 60)
        self.assertAlmostEqual(users["b"]["BusyGpuHours"], 0.5 / 60)
        self.assertAlmostEqual(sum(u["BusyGpuHours"] for u in users.values()), 2 / 60)

    def test_gpus_multiply_allocated_time(self):
        hb = [{"Minute": 0, "Computer": "vm-a"}]
        gpu = [row(0, gpu=g) for g in range(8)]
        self.assertAlmostEqual(ev.recompute(gpu, hb)["per_vm"][0]["AllocatedGpuHours"], 8 / 60)

    def test_minute_classes(self):
        self.assertEqual(ev.classify(row(0)), "idle")
        self.assertEqual(ev.classify(row(0, proc=1)), "held")
        self.assertEqual(ev.classify(row(0, proc=1, util=50, sm=0.35)), "partial")
        self.assertEqual(ev.classify(row(0, proc=1, util=100, sm=0.96)), "full")
        self.assertEqual(ev.classify(row(0, util=60, sm=0.34)), "partial")  # busy without a visible owner


class FailClosedTests(unittest.TestCase):
    def test_committed_measurements_are_current(self):
        self.assertEqual(ev.main(["--check"]), 0)

    def test_changed_evidence_row_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            shutil.copytree(ev.RUNS, runs)
            path = runs / "validation-1" / "gpu-metrics.jsonl"
            path.write_text(path.read_text(encoding="utf-8").replace('"SmActive": 0.9413', '"SmActive": 0.5', 1),
                            encoding="utf-8", newline="\n")
            original = ev.RUNS
            try:
                ev.RUNS = runs
                with self.assertRaises(SystemExit) as ctx:
                    ev.build()
            finally:
                ev.RUNS = original
            self.assertIn("HASH_MISMATCH", str(ctx.exception))

    def test_kql_that_disagrees_with_python_is_rejected(self):
        run = ev.RUNS / "validation-1"
        gpu, hb = ev._read_jsonl(run / "gpu-metrics.jsonl"), ev._read_jsonl(run / "heartbeat.jsonl")
        kql = json.loads((run / "kql-results.json").read_text(encoding="utf-8"))
        kql["summary"][0]["BusyGpuHours"] += 0.01
        with self.assertRaises(SystemExit) as ctx:
            ev._agreement(ev.recompute(gpu, hb), kql)
        self.assertIn("KQL_PYTHON_MISMATCH", str(ctx.exception))

    def test_public_rows_carry_no_timestamps_or_identifiers(self):
        for path in ev.RUNS.rglob("*.jsonl"):
            first = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
            with self.subTest(file=path.name):
                self.assertNotIn("TimeGenerated", first)
                self.assertNotIn("VmResourceId", first)
                self.assertNotIn("GpuUuid", first)
                self.assertRegex(first["Computer"], r"^gpu-vm-\d+$")


if __name__ == "__main__":
    unittest.main()

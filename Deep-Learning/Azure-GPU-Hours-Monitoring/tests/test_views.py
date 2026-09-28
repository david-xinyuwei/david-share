"""Views in kql/ and the reference client that sends them."""
import re
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))
import gpu_hours_client as client  # noqa: E402

LET = re.compile(r"^let (\w+) = (.*;)", re.M)


def _text(view: str) -> str:
    return (ROOT / "kql" / f"{view}.kql").read_text(encoding="utf-8")


class ViewTests(unittest.TestCase):
    def test_every_view_file_exists(self):
        self.assertEqual(sorted(p.stem for p in (ROOT / "kql").glob("*.kql")), sorted(client.VIEWS))

    def test_shared_let_lines_are_identical(self):
        seen: dict[str, tuple[str, str]] = {}
        for view in client.VIEWS:
            for name, body in LET.findall(_text(view)):
                if name == "per_vm":
                    continue  # multi-line; compared in the next test
                if name in seen:
                    self.assertEqual(body, seen[name][1], f"let {name} differs between {seen[name][0]} and {view}")
                else:
                    seen[name] = (view, body)
        self.assertIn("IdlePct", seen)

    def test_summary_sums_per_vm(self):
        def normalize(s: str) -> str:
            return re.sub(r"\s+", " ", s).strip()
        per_vm = _text("per_vm")
        body = per_vm[per_vm.index("heartbeat\n| summarize"):per_vm.index("| order by")]
        summary = _text("summary")
        let_body = summary[summary.index("let per_vm = heartbeat") + len("let per_vm = "):summary.index(";\nper_vm")]
        self.assertEqual(normalize(let_body), normalize(body))

    def test_window_comes_from_the_timespan(self):
        for view in client.VIEWS:
            with self.subTest(view=view):
                text = _text(view)
                self.assertNotRegex(text, r"ago\(|TimeGenerated\s+(between|>)|\{[A-Za-z]+\}")


class ClientTests(unittest.TestCase):
    def test_overrides_replace_exactly_one_let(self):
        q = client.build_query("per_hour", idle_pct=10, tz_offset_hours=-5, computers=["vm-a", "vm-b"])
        self.assertIn("let IdlePct = 10;", q)
        self.assertIn("let TzOffset = -5h;", q)
        self.assertIn('let Computers = dynamic(["vm-a", "vm-b"]);', q)
        self.assertNotIn("let IdlePct = 5;", q)

    def test_override_of_a_missing_default_fails(self):
        with self.assertRaises(ValueError):
            client.build_query("per_vm", tz_offset_hours=8)
        with self.assertRaises(ValueError):
            client.build_query("no_such_view")

    def test_query_sends_the_window_as_timespan(self):
        from azure.monitor.query import LogsQueryStatus

        class Table:
            columns = ["Computer", "Last"]
            rows = [["vm-a", datetime(2000, 1, 1, 8, tzinfo=timezone.utc)]]

        class Result:
            status = LogsQueryStatus.SUCCESS
            tables = [Table()]

        calls = []

        class FakeLogs:
            def query_workspace(self, ws, kql, timespan):
                calls.append((ws, kql, timespan))
                return Result()

        start = datetime(2000, 1, 1, tzinfo=timezone.utc)
        end = datetime(2000, 1, 2, tzinfo=timezone.utc)
        rows = client.GpuHoursClient("ws-guid", logs_client=FakeLogs()).query_view("per_vm", start, end, idle_pct=7)
        self.assertEqual(rows, [{"Computer": "vm-a", "Last": "2000-01-01T08:00:00Z"}])
        ws, kql, timespan = calls[0]
        self.assertEqual((ws, timespan), ("ws-guid", (start, end)))
        self.assertIn("let IdlePct = 7;", kql)

    def test_partial_result_raises(self):
        class Result:
            status = "PartialError"
            partial_error = "boom"

        class FakeLogs:
            def query_workspace(self, *a, **k):
                return Result()

        with self.assertRaises(RuntimeError):
            client.GpuHoursClient("ws", logs_client=FakeLogs()).run_kql("x", datetime.now(timezone.utc), datetime.now(timezone.utc))


if __name__ == "__main__":
    unittest.main()

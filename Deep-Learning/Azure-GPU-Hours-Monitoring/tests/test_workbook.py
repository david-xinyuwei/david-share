"""azure/workbook.json: built from kql/ and azure/workbook/, and bound to the workbook parameters."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_workbook as wb  # noqa: E402


def panels() -> dict[str, dict]:
    return {n["name"]: n for n in wb.walk(wb.items()) if n["type"] == 3}


class WorkbookTests(unittest.TestCase):
    def test_committed_template_is_current(self):
        self.assertEqual(wb.main(["--check"]), 0)

    def test_template_embeds_the_built_items(self):
        template = json.loads(wb.OUT.read_text(encoding="utf-8"))
        data = json.loads(template["variables"]["data"])
        self.assertEqual(data["items"], json.loads(json.dumps(wb.items())))
        resource = template["resources"][0]
        self.assertEqual(resource["type"], "Microsoft.Insights/workbooks")
        self.assertEqual(resource["tags"]["hidden-title"], "[parameters('displayName')]")
        self.assertIn("guid(parameters('workspaceResourceId')", resource["name"])

    def test_every_hour_view_is_the_kql_file_with_bound_defaults(self):
        p = panels()
        for view in ("per_vm", "per_hour", "per_day", "per_user", "per_job", "per_submitter", "live"):
            with self.subTest(view=view):
                source = (ROOT / "kql" / f"{view}.kql").read_text(encoding="utf-8")
                expected = wb.LET_COMPUTERS.sub(wb.BOUND_COMPUTERS, wb.LET_IDLE.sub(wb.BOUND_IDLE, source)).rstrip()
                self.assertTrue(p[view]["content"]["query"].startswith(expected), view)
                self.assertIn("{Computer}", p[view]["content"]["query"])
        self.assertTrue(p["summary_tiles"]["content"]["query"].startswith(wb.bind("summary").rstrip()))

    def test_unbound_view_fails(self):
        original = wb.LET_COMPUTERS
        try:
            wb.LET_COMPUTERS = __import__("re").compile(r"^no such line$", __import__("re").M)
            with self.assertRaises(SystemExit):
                wb.bind("per_vm")
        finally:
            wb.LET_COMPUTERS = original

    def test_coverage_columns_reach_the_tiles(self):
        tiles = panels()["summary_tiles"]["content"]["query"]
        for column in ("ObservedGpuHours", "UnknownGpuHours", "TelemetryCoveragePct"):
            self.assertIn(column, tiles)

    def test_job_views_show_only_when_job_tracking_exists(self):
        groups = {n["name"]: n for n in wb.walk(wb.items()) if n["type"] in (1, 12)}
        self.assertEqual(groups["jobs"]["conditionalVisibility"]["value"], "yes")
        self.assertEqual(groups["jobs_off"]["conditionalVisibility"]["comparison"], "isNotEqualTo")
        for needle in ("'RunId'", "AzureActivity", "AmlRunStatusChangedEvent"):
            self.assertIn(needle, wb.HAS_JOBS)

    def test_operational_panels_come_from_files(self):
        p = panels()
        for name in ("sampling_window", "sampling_status", "trend_utilization", "trend_memory", "trend_power",
                     "recent_15m", "idle_60m"):
            with self.subTest(panel=name):
                self.assertEqual(p[name]["content"]["query"], wb.panel(name))
        self.assertEqual({p.stem for p in wb.PANELS.glob("*.kql")},
                         {"sampling_window", "sampling_status", "trend_utilization", "trend_memory", "trend_power",
                          "recent_15m", "idle_60m"})

    def test_every_panel_targets_the_workspace_placeholder(self):
        for name, node in panels().items():
            with self.subTest(panel=name):
                self.assertEqual(node["content"]["crossComponentResources"], [wb.WS])


if __name__ == "__main__":
    unittest.main()

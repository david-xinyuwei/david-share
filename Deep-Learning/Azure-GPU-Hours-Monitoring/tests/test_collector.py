"""Collector tests: dcgmi dmon parsing, per-minute averaging and the JSON-line contract."""
import json
import re
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vm"))
import gpu_collector as c  # noqa: E402

# Verbatim `dcgmi dmon -e 1001,1002,1005` output on the measured VM (DCGM 3.3.9): profiling fields read
# N/A for the first sample after the host engine starts, then report values.
REAL_DMON_3_FIELDS = (
    "#Entity   GRACT        SMACT        DRAMA        \n"
    "ID                                               \n"
    "GPU 0     N/A          N/A          N/A          \n"
    "GPU 0     0.000        0.000        0.000        \n"
)
# A line with the collector's nine fields, in the same column layout.
FULL_LINE = "GPU 3     100               0.966        0.941        0.916        0.131        21618             95830             397.637           64"
META = {"VmName": "vm-a", "VmSize": "Standard_NC40ads_H100_v5", "VmResourceId": "/x", "Tags": ""}
GPU = {"GpuUuid": "GPU-0", "GpuName": "NVIDIA H100 NVL"}


class ParseTests(unittest.TestCase):
    def test_real_output_headers_skipped_and_na_parsed(self):
        original = c.FIELDS
        try:
            c.FIELDS = [(1001, "GrActive"), (1002, "SmActive"), (1005, "DramActive")]
            parsed = [c.parse_dmon_line(line) for line in REAL_DMON_3_FIELDS.splitlines()]
        finally:
            c.FIELDS = original
        self.assertEqual(parsed, [None, None, (0, [None, None, None]), (0, [0.0, 0.0, 0.0])])

    def test_nine_field_line(self):
        gpu, values = c.parse_dmon_line(FULL_LINE)
        self.assertEqual(gpu, 3)
        self.assertEqual(len(values), len(c.FIELDS))
        self.assertAlmostEqual(values[[k for _, k in c.FIELDS].index("SmActive")], 0.941)

    def test_foreign_lines_ignored(self):
        for line in ("", "GPU", "GPU x 1 2 3 4 5 6 7 8 9", "Error: unable to establish a connection to the specified host"):
            with self.subTest(line=line):
                self.assertIsNone(c.parse_dmon_line(line))

    def test_command_samples_every_10_seconds(self):
        self.assertEqual(c.SAMPLE_MS, 10000)
        self.assertEqual([f for f, _ in c.FIELDS], [203, 1001, 1002, 1004, 1005, 252, 250, 155, 150])


class AggregateTests(unittest.TestCase):
    def test_minute_average_skips_missing_samples(self):
        agg = c.Aggregator()
        agg.add(0, [100.0] * len(c.FIELDS))
        agg.add(0, [None] * (len(c.FIELDS) - 1) + [70.0])
        data = agg.drain()
        self.assertEqual(agg.drain(), {})
        rec = c.build_record(datetime(2000, 1, 1, tzinfo=timezone.utc), META, 0, GPU, data[0], [("u2", "python3"), ("u1", "python3")])
        self.assertEqual(rec["GpuUtil"], 100.0)
        self.assertEqual(rec["TempC"], 85.0)
        self.assertEqual(rec["Samples"], 2)
        self.assertEqual((rec["ProcCount"], rec["Users"], rec["Processes"]), (2, "u1,u2", "python3"))

    def test_empty_minute_gives_null_metrics(self):
        rec = c.build_record(datetime(2000, 1, 1, tzinfo=timezone.utc), META, 1, GPU, {}, [])
        self.assertIsNone(rec["SmActive"])
        self.assertEqual((rec["Samples"], rec["ProcCount"], rec["Users"]), (0, 0, ""))


class ContractTests(unittest.TestCase):
    def _record(self):
        agg = c.Aggregator()
        agg.add(0, c.parse_dmon_line(FULL_LINE.replace("GPU 3", "GPU 0"))[1])
        return c.build_record(datetime(2000, 1, 1, tzinfo=timezone.utc), META, 0, GPU, agg.drain()[0], [("u1", "python3")])

    def test_json_line_matches_rule_stream_and_table(self):
        rule = json.loads((ROOT / "azure" / "dcr-rule.json").read_text(encoding="utf-8"))
        stream = {col["name"]: col["type"] for col in rule["properties"]["streamDeclarations"]["Custom-Json-GpuMetrics"]["columns"]}
        script = (ROOT / "scripts" / "setup-workspace.sh").read_text(encoding="utf-8")
        table = dict(re.findall(r"\b(\w+)=(datetime|string|int|real)\b", script.split("COLUMNS=(", 1)[1].split(")", 1)[0]))
        self.assertEqual(table, stream, "table columns in setup-workspace.sh differ from the rule's stream")
        rec = self._record()
        # the agent fills Computer and FilePath; everything else comes from the collector
        self.assertEqual(set(rec) | {"Computer", "FilePath"}, set(stream))
        for key, kind in stream.items():
            if key in rec and rec[key] is not None:
                expected = {"datetime": str, "string": str, "int": int, "real": (int, float)}[kind]
                self.assertIsInstance(rec[key], expected, key)

    def test_rule_reads_the_collector_directory(self):
        rule = json.loads((ROOT / "azure" / "dcr-rule.json").read_text(encoding="utf-8"))["properties"]
        self.assertEqual(rule["dataSources"]["logFiles"][0]["filePatterns"], ["/var/log/gpumon/*.json"])
        self.assertEqual(c.LOG_DIR, "/var/log/gpumon")
        self.assertEqual(rule["dataFlows"][0]["outputStream"], "Custom-GpuMetrics_CL")


if __name__ == "__main__":
    unittest.main()

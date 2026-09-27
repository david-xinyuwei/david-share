"""Tests for tools/bench_log.py (projection and parsing of sglang.bench_serving output)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import bench_log  # noqa: E402

FIXTURE = (ROOT / "tests" / "fixtures" / "bench_serving_raw_sample.log").read_text(encoding="utf-8")


class ProjectionTests(unittest.TestCase):
    def test_projection_keeps_workload_and_result_block(self):
        projected = bench_log.project(FIXTURE)
        self.assertIn("# args: ", projected)
        self.assertIn("max_concurrency=64", projected)
        self.assertIn("Output token throughput (tok/s):", projected)

    def test_projection_drops_private_paths_and_hosts(self):
        projected = bench_log.project(FIXTURE)
        self.assertNotIn("/srv/private", projected)
        self.assertNotIn("dataset_path", projected)
        self.assertNotIn("model=", projected)

    def test_projection_fails_closed_on_private_content_inside_block(self):
        poisoned = FIXTURE.replace("Backend:                                 sglang",
                                   "Backend:                                 /data/secret/sglang")
        with self.assertRaises(bench_log.ProjectionError):
            bench_log.project(poisoned)

    def test_projection_rejects_each_private_shape(self):
        probes = ["/srv/private/x", "/workspace/a/b", "C:\\Users\\me", "\\\\fileserver\\share", "10.1.2.3",
                  "fe80::1:2:3", "person@internal-host"]
        for probe in probes:
            with self.subTest(probe=probe):
                poisoned = FIXTURE.replace("Backend:                                 sglang",
                                           "Backend:                                 " + probe)
                with self.assertRaises(bench_log.ProjectionError):
                    bench_log.project(poisoned)

    def test_projection_requires_arguments_before_block(self):
        no_args = "\n".join(l for l in FIXTURE.splitlines() if "Namespace(" not in l)
        with self.assertRaises(bench_log.ProjectionError):
            bench_log.project(no_args)

    def test_unterminated_block_is_rejected(self):
        truncated = FIXTURE.split("==================================================")[0]
        with self.assertRaises(bench_log.ProjectionError):
            bench_log.project(truncated)


class ParseTests(unittest.TestCase):
    def test_parse_reads_metrics_and_types(self):
        run = bench_log.parse(bench_log.project(FIXTURE))[0]
        self.assertEqual(run["args"]["random_input_len"], 8192)
        self.assertEqual(run["metrics"]["successful_requests"], 256)
        self.assertAlmostEqual(run["metrics"]["output_tok_s"], 1234.5)
        self.assertAlmostEqual(run["metrics"]["mean_tpot_ms"], 12.25)

    def test_every_committed_projection_parses(self):
        for path in sorted((ROOT / "evidence" / "raw").glob("*.txt")):
            with self.subTest(path=path.name):
                runs = bench_log.parse(path.read_text(encoding="utf-8"))
                for run in runs:
                    self.assertIn("output_tok_s", run["metrics"])
                    self.assertEqual(run["metrics"]["successful_requests"], run["args"]["num_prompts"])


if __name__ == "__main__":
    unittest.main()

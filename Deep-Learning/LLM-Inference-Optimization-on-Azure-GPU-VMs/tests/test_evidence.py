"""Tests for the evidence chain: projected logs -> measurements.json -> README numbers."""
import hashlib
import json
import statistics
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_evidence  # noqa: E402


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.m = load("evidence/measurements.json")
        self.runs = load("evidence/runs.json")

    def test_committed_measurements_equal_a_fresh_build(self):
        self.assertEqual(json.dumps(build_evidence.build(), indent=2) + "\n",
                         (ROOT / "evidence/measurements.json").read_text(encoding="utf-8"))

    def test_manifest_hashes_match_projected_files(self):
        manifest = load("evidence/raw-manifest.json")
        on_disk = {p.name for p in (ROOT / "evidence/raw").iterdir() if p.is_file()}
        self.assertEqual(on_disk, {f["projected_file"] for f in manifest["files"]})
        for item in manifest["files"]:
            data = (ROOT / "evidence/raw" / item["projected_file"]).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), item["projected_sha256"], item["projected_file"])
            self.assertRegex(item["raw_log_sha256"], r"^[0-9a-f]{64}$")

    def test_tampered_projection_fails_the_build(self):
        target = ROOT / "evidence/raw/stage-20260713-tuned-moe__prefill-8192-c4.txt"
        original = target.read_bytes()
        try:
            target.write_bytes(original.replace(b"20780.79", b"29780.79"))
            with self.assertRaises(SystemExit):
                build_evidence.build()
        finally:
            target.write_bytes(original)

    def test_stage_deltas_recompute_from_absolute_values(self):
        for row in self.m["tuned_moe_stage"]["prefill"]:
            expected = round((row["after_input_tok_s"] - row["before_input_tok_s"]) / row["before_input_tok_s"] * 100, 2)
            self.assertEqual(row["input_tok_s_delta_pct"], expected)
        for row in self.m["tuned_moe_stage"]["decode"]:
            expected = round((row["after_output_tok_s"] - row["before_output_tok_s"]) / row["before_output_tok_s"] * 100, 2)
            self.assertEqual(row["output_tok_s_delta_pct"], expected)

    def test_context_overflow_point_is_excluded_not_compared(self):
        stage = self.m["tuned_moe_stage"]
        self.assertEqual([e["input_tokens"] for e in stage["excluded"]], [262144])
        self.assertNotIn(262144, [r["input_tokens"] for r in stage["prefill"]])

    def test_ab_means_recompute_from_samples(self):
        raw = load("evidence/raw/" + self.runs["runs"]["ab-20260718-64k-bs16"]["raw"][0])
        base = statistics.fmean(statistics.fmean(s) for s in raw["baseline"]["runs"])
        opt = statistics.fmean(statistics.fmean(s) for s in raw["optimized"]["runs"])
        ab = self.m["ab_ck_unified_verify_64k"]
        self.assertAlmostEqual(ab["baseline_mean_tok_s"], round(base, 2))
        self.assertAlmostEqual(ab["optimized_mean_tok_s"], round(opt, 2))
        self.assertAlmostEqual(ab["throughput_delta_pct"], round((opt - base) / base * 100, 2))
        self.assertLess(abs(ab["baseline_repeatability_pct"]), 1.0)
        self.assertLess(abs(ab["optimized_repeatability_pct"]), 1.0)

    def test_stage_pair_uses_identical_scripts(self):
        before = self.runs["runs"]["stage-20260707-ck"]["script_sha256"]
        after = self.runs["runs"]["stage-20260713-tuned-moe"]["script_sha256"]
        for key in ("prefill_launch", "router_launch", "decode_benchmark", "prefill_benchmark"):
            self.assertEqual(before[key], after[key], key)

    def test_no_numbers_from_other_hardware_or_vendors(self):
        self.assertNotIn("vendor_reported", self.runs)
        self.assertNotIn("public_upstream_reported", self.runs)
        for path in (ROOT / "evidence").rglob("*"):
            if path.is_file():
                self.assertNotRegex(path.read_text(encoding="utf-8"), r"(?i)gfx950|mi350", path.name)

    def test_every_run_names_only_manifest_sources(self):
        listed = {f["projected_file"] for f in load("evidence/raw-manifest.json")["files"]}
        for name, run in self.runs["runs"].items():
            with self.subTest(run=name):
                self.assertTrue(run["raw"])
                self.assertLessEqual(set(run["raw"]), listed)

    def test_unlisted_raw_file_fails_the_build(self):
        stray = ROOT / "evidence/raw/stray.txt"
        try:
            stray.write_text("stray", encoding="utf-8")
            with self.assertRaises(SystemExit):
                build_evidence.build()
        finally:
            stray.unlink()

    def test_cumulative_factors_recompute_from_absolute_values(self):
        cu = self.m["cumulative"]
        g = cu["graph_capture"]
        self.assertEqual(g["output_tok_s_factor"], round(g["on_output_tok_s"] / g["off_output_tok_s"], 2))
        for row in cu["prefill"]:
            self.assertEqual(row["factor"], round(row["late_input_tok_s"] / row["early_input_tok_s"], 2))
        for row in cu["decode"]:
            self.assertEqual(row["real_tpot_factor"], round(row["early_mean_tpot_ms"] / row["real_mean_tpot_ms"], 2))
            self.assertEqual(row["fixed_tpot_factor"], round(row["early_mean_tpot_ms"] / row["fixed_mean_tpot_ms"], 2))
            self.assertEqual(row["real_output_factor"], round(row["real_output_tok_s"] / row["early_output_tok_s"], 2))

    def test_cumulative_shows_real_acceptance_next_to_fixed(self):
        """The favorable fixed-acceptance factor must never appear without the real-acceptance one."""
        for row in self.m["cumulative"]["decode"]:
            self.assertLess(row["real_tpot_factor"], row["fixed_tpot_factor"])
        real = self.runs["runs"]["realacc-20260714"]
        self.assertIn("no SGLANG_SIMULATE_ACC_", real["server_env"])
        for name in real["raw"]:
            self.assertNotIn("SIMULATE", (ROOT / "evidence" / "raw" / name).read_text(encoding="utf-8"))

    def test_cumulative_workload_difference_is_recorded(self):
        cu = self.m["cumulative"]
        self.assertEqual(cu["early_decode_workload"]["input_tokens"], 16384)
        self.assertEqual(cu["late_decode_workload"]["input_tokens"], 8192)
        for row in cu["prefill"]:
            self.assertIn(row["early_run"], self.runs["runs"])
            self.assertIn(row["late_run"], self.runs["runs"])

    def test_every_comparison_is_mi300x_only(self):
        self.assertIn("MI300X with MI300X", self.runs["compared_objects"]["comparison_rule"])
        for rel in ("evidence/runs.json", "evidence/measurements.json"):
            self.assertNotRegex((ROOT / rel).read_text(encoding="utf-8"), r"(?i)h200|vs_h|h20\b")


if __name__ == "__main__":
    unittest.main()

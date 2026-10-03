"""GPT-6.1 Sol in the console: catalog, ordering and the follow-up replay pack (2026-10-03 run)."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import bench_core  # noqa: E402
import server  # noqa: E402

STUDY_CONFIG = ROOT.parent / "production-readiness" / "config"
RUN_DIR = ROOT.parent / "scenario-model-benchmark" / "outputs" / "gpt61-sol-20261003"


class Gpt61SolCatalog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.arms = {a["deployment"]: a for a in bench_core.catalog()["arms"]}

    def test_gpt61_sol_is_an_offered_study_model(self):
        arm = self.arms["gpt-6.1-sol"]
        self.assertTrue(arm["is_study_model"])
        self.assertTrue(arm["verified"])
        self.assertEqual(arm["region"], "swedencentral")
        self.assertEqual(arm["api"], "responses")
        # the model rejects `none`; the registry entry in the run folder records what the probe found
        self.assertEqual(arm["supported_efforts"], ["low", "medium", "high", "xhigh", "max"])
        self.assertEqual(arm["default_effort"], "low")

    def test_gpt61_sol_is_priced_from_its_run_folder(self):
        arm = self.arms["gpt-6.1-sol"]
        folder_prices = json.loads((RUN_DIR / "pricing.json").read_text(encoding="utf-8"))["models"]["gpt-6.1-sol"]
        self.assertEqual((arm["price_input"], arm["price_cached"], arm["price_output"], arm["price_cache_write"]),
                         (folder_prices["input"], folder_prices["cached"], folder_prices["output"],
                          folder_prices["cache_write"]))
        self.assertEqual((arm["price_input"], arm["price_output"]), (2.0, 10.0))

    def test_second_follow_up_does_not_rewrite_the_first_or_the_pinned_entries(self):
        pinned_prices = json.loads((STUDY_CONFIG / "pricing.json").read_text(encoding="utf-8"))["models"]
        self.assertEqual(self.arms["gpt-5.6-luna"]["price_input"], pinned_prices["gpt-5.6-luna"]["input"])
        # gpt-6-luna also appears in the 2026-10-03 folder; the 2026-09-26 record stays authoritative
        self.assertEqual(self.arms["gpt-6-luna"]["price_input"], 0.10)
        self.assertEqual(self.arms["gpt-6-luna"]["default_effort"], "none")

    def test_gpt61_sol_sorts_after_gpt6_luna(self):
        arms = ["gpt-6.1-sol@high", "gpt-6-luna@max", "gpt-6.1-sol@low", "gpt-4o-mini-bench", "gpt-6-luna@none"]
        self.assertEqual(sorted(arms, key=bench_core.arm_order_key), [
            "gpt-4o-mini-bench", "gpt-6-luna@none", "gpt-6-luna@max", "gpt-6.1-sol@low", "gpt-6.1-sol@high"])


class Gpt61SolReplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = server.load_replay()

    def test_follow_up_run_is_merged_after_the_luna_run(self):
        ids = [run["id"] for run in self.pack["runs"]]
        self.assertEqual(ids[-1], "gpt61-sol-follow-up")
        self.assertGreater(ids.index("gpt61-sol-follow-up"), ids.index("gpt6-luna-same-session"))

    def test_follow_up_run_covers_the_three_arms_in_effort_order(self):
        run = next(r for r in self.pack["runs"] if r["id"] == "gpt61-sol-follow-up")
        arms = [s["arm"] for s in run["summaries"]]
        self.assertEqual(arms, [f"gpt-6.1-sol@{e}" for e in ("low", "medium", "high")])
        self.assertEqual(run["records"], 153)

    def test_replay_catalog_offers_gpt61_sol_last(self):
        catalog = self.pack["catalog"]
        self.assertIn("gpt-6.1-sol", {a["deployment"] for a in catalog["arms"]})
        self.assertEqual(catalog["study_models"][-1], "gpt-6.1-sol")


if __name__ == "__main__":
    unittest.main()

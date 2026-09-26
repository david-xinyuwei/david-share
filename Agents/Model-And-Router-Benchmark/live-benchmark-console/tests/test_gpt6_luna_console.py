"""GPT-6 Luna in the console: catalog, ordering and the follow-up replay pack (2026-09-26 run)."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import bench_core  # noqa: E402
import server  # noqa: E402

STUDY_CONFIG = ROOT.parent / "production-readiness" / "config"


class Gpt6LunaCatalog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.arms = {a["deployment"]: a for a in bench_core.catalog()["arms"]}

    def test_gpt6_luna_is_an_offered_study_model(self):
        arm = self.arms["gpt-6-luna"]
        self.assertTrue(arm["is_study_model"])
        self.assertTrue(arm["verified"])
        self.assertEqual(arm["region"], "swedencentral")
        self.assertEqual(arm["api"], "responses")
        self.assertEqual(arm["supported_efforts"], ["none", "low", "medium", "high", "xhigh", "max"])

    def test_gpt6_luna_is_priced_from_its_run_folder(self):
        arm = self.arms["gpt-6-luna"]
        self.assertEqual((arm["price_input"], arm["price_cached"], arm["price_output"], arm["price_cache_write"]),
                         (0.10, 0.01, 0.50, 0.125))

    def test_follow_up_never_rewrites_a_pinned_entry(self):
        pinned_prices = json.loads((STUDY_CONFIG / "pricing.json").read_text(encoding="utf-8"))["models"]
        luna = self.arms["gpt-5.6-luna"]
        self.assertEqual(luna["price_input"], pinned_prices["gpt-5.6-luna"]["input"])
        self.assertEqual(luna["price_output"], pinned_prices["gpt-5.6-luna"]["output"])
        # the follow-up record names a region for this deployment; the pinned record does not
        self.assertIsNone(luna["region"])

    def test_gpt6_luna_sorts_after_the_earlier_study_models(self):
        arms = ["gpt-6-luna@high", "gpt-5.6-luna@none", "gpt-6-luna@none", "gpt-4o-mini-bench", "gpt-6-luna@max"]
        self.assertEqual(sorted(arms, key=bench_core.arm_order_key), [
            "gpt-4o-mini-bench", "gpt-5.6-luna@none", "gpt-6-luna@none", "gpt-6-luna@high", "gpt-6-luna@max"])


class Gpt6LunaReplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = server.load_replay()

    def test_follow_up_run_is_merged_after_the_pinned_runs(self):
        ids = [run["id"] for run in self.pack["runs"]]
        self.assertEqual(ids[-1], "gpt6-luna-same-session")
        self.assertIn("scenario-matrix", ids)

    def test_follow_up_run_covers_every_arm_in_model_then_effort_order(self):
        run = next(r for r in self.pack["runs"] if r["id"] == "gpt6-luna-same-session")
        arms = [s["arm"] for s in run["summaries"]]
        self.assertEqual(len(arms), 17)
        self.assertEqual(arms, sorted(arms, key=bench_core.arm_order_key))
        self.assertEqual(arms[-6:], [f"gpt-6-luna@{e}" for e in ("none", "low", "medium", "high", "xhigh", "max")])
        self.assertEqual(run["records"], 867)

    def test_replay_catalog_offers_gpt6_luna(self):
        catalog = self.pack["catalog"]
        self.assertIn("gpt-6-luna", {a["deployment"] for a in catalog["arms"]})
        self.assertEqual(catalog["study_models"][-1], "gpt-6-luna")


if __name__ == "__main__":
    unittest.main()

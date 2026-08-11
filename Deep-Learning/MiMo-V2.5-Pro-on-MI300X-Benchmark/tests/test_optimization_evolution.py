from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_optimization_evolution import (
    validate_claims,
    validate_order_rules,
    validate_parallelism_axes,
    validate_sources,
    validate_stages,
)


class OptimizationEvolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = json.loads((ROOT / "data/optimization-evolution.json").read_text(encoding="utf-8"))

    def test_current_data_passes(self) -> None:
        validate_sources(self.data["sources"])
        validate_claims(self.data["claims"], self.data["sources"])
        validate_stages(self.data["stages"], self.data["sources"], self.data["claims"])
        validate_order_rules(self.data["order_rules"])
        validate_parallelism_axes(self.data["parallelism_axes"], self.data["sources"])

    def test_forward_dependency_is_rejected(self) -> None:
        stages = copy.deepcopy(self.data["stages"])
        stages[1]["depends_on"] = [stages[2]["id"]]
        with self.assertRaises(AssertionError):
            validate_stages(stages, self.data["sources"], self.data["claims"])

    def test_unknown_source_is_rejected(self) -> None:
        stages = copy.deepcopy(self.data["stages"])
        stages[0]["source_refs"] = ["missing-source"]
        with self.assertRaises(AssertionError):
            validate_stages(stages, self.data["sources"], self.data["claims"])

    def test_sequence_gap_is_rejected(self) -> None:
        stages = copy.deepcopy(self.data["stages"])
        stages[3]["sequence"] = 99
        with self.assertRaises(AssertionError):
            validate_stages(stages, self.data["sources"], self.data["claims"])

    def test_claim_source_union_mismatch_is_rejected(self) -> None:
        stages = copy.deepcopy(self.data["stages"])
        stages[0]["source_refs"] = ["mimo_model_card"]
        with self.assertRaises(AssertionError):
            validate_stages(stages, self.data["sources"], self.data["claims"])

    def test_parallelism_axis_order_is_rejected(self) -> None:
        axes = copy.deepcopy(self.data["parallelism_axes"])
        axes[0], axes[1] = axes[1], axes[0]
        with self.assertRaises(AssertionError):
            validate_parallelism_axes(axes, self.data["sources"])


if __name__ == "__main__":
    unittest.main()
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "paired-prefix-follow-up.json"
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "validate_repo", SCRIPTS / "validate_repo.py"
)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class PairedPrefixEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = json.loads(EVIDENCE.read_text(encoding="utf-8"))

    def test_warm_phase_proves_two_independent_cacheable_prefixes(self) -> None:
        self.assertEqual(self.data["status"], "warm-pass-verify-pending")
        self.assertTrue(self.data["contract"]["linkedArmHasContainerBinding"])
        self.assertFalse(self.data["contract"]["controlArmHasContainerBinding"])
        self.assertTrue(self.data["isolation"]["prefixesAreDistinct"])
        self.assertTrue(self.data["isolation"]["markersHaveEqualLength"])
        self.assertTrue(self.data["isolation"]["firstDifferenceIsWithinTheLeadingMarker"])
        self.assertTrue(self.data["isolation"]["markersPrecedeTheOriginalPrompt"])
        self.assertEqual(self.data["warm"]["linkedCachedTokensByCall"], [0, 2304])
        self.assertEqual(self.data["warm"]["controlCachedTokensByCall"], [0, 2304])
        self.assertEqual(self.data["isolation"]["inputTokensPerCallBothArms"], 2513)

    def test_pending_verify_cannot_contain_a_result(self) -> None:
        verify = self.data["verify"]
        self.assertEqual(verify["status"], "pending")
        self.assertGreaterEqual(self.data["contract"]["minimumVerifyHours"], 26)
        self.assertIsNone(verify["linkedCachedTokens"])
        self.assertIsNone(verify["controlCachedTokens"])

    def test_verdict_matrix_is_frozen_before_verify(self) -> None:
        self.assertEqual(
            self.data["verdictMatrix"],
            {
                "linkedHitControlMiss": "context-cache-incremental-retention-observed",
                "linkedMissControlMiss": "context-cache-incremental-retention-not-observed",
                "linkedHitControlHit": "attribution-ambiguous-both-retained",
                "linkedMissControlHit": "unexpected-control-only-hit",
            },
        )

    def test_bilingual_shape_detects_an_extra_table_row(self) -> None:
        matched = "| Column A | Column B |\n|---|---|\n| one | two |\n"
        drifted = matched + "| extra | row |\n"

        self.assertNotEqual(
            VALIDATOR.markdown_shape(matched),
            VALIDATOR.markdown_shape(drifted),
        )


if __name__ == "__main__":
    unittest.main()

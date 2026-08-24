from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
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
        self.assertEqual(
            self.data["status"],
            "complete-incremental-retention-not-observed",
        )
        self.assertTrue(self.data["contract"]["linkedArmHasContainerBinding"])
        self.assertFalse(self.data["contract"]["controlArmHasContainerBinding"])
        self.assertTrue(self.data["isolation"]["prefixesAreDistinct"])
        self.assertTrue(self.data["isolation"]["markersHaveEqualLength"])
        self.assertTrue(self.data["isolation"]["firstDifferenceIsWithinTheLeadingMarker"])
        self.assertTrue(self.data["isolation"]["markersPrecedeTheOriginalPrompt"])
        self.assertEqual(self.data["warm"]["linkedCachedTokensByCall"], [0, 2304])
        self.assertEqual(self.data["warm"]["controlCachedTokensByCall"], [0, 2304])
        self.assertEqual(self.data["isolation"]["inputTokensPerCallBothArms"], 2513)

    def test_completed_verify_records_the_frozen_negative_verdict(self) -> None:
        verify = self.data["verify"]
        self.assertEqual(verify["status"], "complete")
        self.assertGreaterEqual(self.data["contract"]["minimumVerifyHours"], 26)
        self.assertGreater(verify["idleHours"], 24)
        self.assertTrue(verify["allHttp200"])
        self.assertEqual(verify["inputTokensPerCallBothArms"], 2512)
        self.assertEqual(verify["linkedCachedTokens"], 0)
        self.assertEqual(verify["controlCachedTokens"], 0)
        self.assertEqual(
            verify["verdict"],
            self.data["verdictMatrix"]["linkedMissControlMiss"],
        )

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

    def test_manifest_hashes_canonical_lf_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.json"
            path.write_bytes(b'{\r\n  "status": "pending"\r\n}\r\n')

            self.assertEqual(
                VALIDATOR.canonical_text_bytes(path),
                b'{\n  "status": "pending"\n}\n',
            )


if __name__ == "__main__":
    unittest.main()

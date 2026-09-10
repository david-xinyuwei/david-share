"""Reject drift in the drafter-adaptation evidence and its README table."""

import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import analyze_results
import validate_report


ROOT = Path(__file__).resolve().parent
TOPIC = ROOT.parent.parent


class AdaptationEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "topic" / "experiments" / ROOT.name
        self.topic = self.root.parent.parent
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns("__pycache__"))
        for filename in validate_report.READMES:
            shutil.copyfile(TOPIC / filename, self.topic / filename)

    def mutate_json(self, relative, mutate):
        path = self.root / relative
        content = json.loads(path.read_text(encoding="utf-8"))
        mutate(content)
        path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")

    def test_recorded_evidence_passes(self):
        validate_report.validate(self.root)

    def test_summary_is_recomputed_not_copied(self):
        published = json.loads((self.root / "data/summary.json").read_text(encoding="utf-8"))
        self.assertEqual(published, analyze_results.summarize(self.root))

    def test_paired_bootstrap_refuses_different_target_text(self):
        record = self.root / "results/round4/agreement/ftzh_ours.json"
        content = json.loads(record.read_text(encoding="utf-8"))
        content["per_request"][0]["completion_ids_sha256"] = "0" * 64
        reference = json.loads((self.root / "results/round4/agreement/ftzh_released.json").read_text(encoding="utf-8"))
        result = analyze_results.paired_agreement(reference, content)
        self.assertEqual(result["status"], "NOT_PAIRED")
        self.assertEqual(result["prompts_with_identical_text"], 199)

    def test_round3_marginals_are_not_multiplied_into_a_joint_length(self):
        summary = json.loads((self.root / "data/summary.json").read_text(encoding="utf-8"))
        for entry in summary["round3"]["agreement"].values():
            self.assertIsNone(entry["joint_prefix_acceptance_length"])
        for entry in summary["round3"]["agreement_paired"].values():
            self.assertEqual(entry["status"], "NOT_PAIRED")

    def test_round4_joint_prefix_matches_recorded_value(self):
        record = json.loads((self.root / "results/round4/agreement/ftzh_ours.json").read_text(encoding="utf-8"))
        runs = [value for row in record["per_request"] for value in row["prefix_lengths"]]
        self.assertAlmostEqual(1.0 + sum(runs) / len(runs), record["teacher_forced_acceptance_length"], places=9)

    def test_changed_hit_count_is_rejected(self):
        self.mutate_json("results/round4/agreement/ftzh_ours.json", lambda value: value["per_request"][0]["hits"].__setitem__(0, 0))
        with self.assertRaisesRegex(ValueError, "AGREEMENT_MARGINAL_MISMATCH"):
            analyze_results.summarize(self.root)

    def test_changed_vllm_tokens_are_rejected(self):
        self.mutate_json("results/round4/vllm/dflash_ours.json", lambda value: value["levels"][0].update(completion_tokens=1))
        with self.assertRaisesRegex(ValueError, "VLLM_TOKEN_MISMATCH"):
            analyze_results.summarize(self.root)

    def test_changed_acceptance_length_is_rejected(self):
        self.mutate_json("results/round3/acceptance/v3_selector.json", lambda value: value.update(macro_mean_acceptance_length=9.0))
        with self.assertRaisesRegex(ValueError, "ACCEPTANCE_MACRO_MISMATCH"):
            analyze_results.summarize(self.root)

    def test_gate_verdict_must_match_rows(self):
        self.mutate_json("results/round4/gates/target_zh.json", lambda value: value["verdict"].update(loop_prompts=0))
        with self.assertRaisesRegex(ValueError, "GATE_LOOP_MISMATCH"):
            analyze_results.summarize(self.root)

    def test_readme_table_drift_is_rejected(self):
        for filename in validate_report.READMES:
            with self.subTest(filename=filename):
                path = self.topic / filename
                original = path.read_text(encoding="utf-8")
                self.assertIn("97.1 / 106.0", original)
                path.write_text(original.replace("97.1 / 106.0", "97.1 / 116.0", 1), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "REPORT_DATA_DRIFT:ADAPTATION_TABLE"):
                    validate_report.validate(self.root)
                path.write_text(original, encoding="utf-8")

    def test_private_marker_in_public_file_is_rejected(self):
        path = self.root / "results/round4/vllm/baseline.json"
        content = json.loads(path.read_text(encoding="utf-8"))
        for leaked in ("served from 10.0.0.4", "cache at /home/operator/run", "sub 12345678-1234-1234-1234-123456789abc"):
            with self.subTest(leaked=leaked):
                content["note"] = leaked
                path.write_text(json.dumps(content), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "PRIVATE_MARKER_IN_PUBLIC_FILE"):
                    validate_report.verify_provenance(self.root)

    def test_edited_source_snapshot_is_rejected(self):
        source = self.root / "source/round4/train_drafter.py"
        source.write_bytes(source.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "PUBLISHED_FILE_HASH_OR_SET_MISMATCH"):
            validate_report.verify_manifest(self.root)

    def test_tampered_published_prompts_are_rejected(self):
        prompts = self.root / "inputs/round4/eval_prompts_zh200.jsonl"
        prompts.write_bytes(prompts.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "INPUT_HASH_MISMATCH:eval_prompts_zh200.jsonl"):
            analyze_results.summarize(self.root)

    def test_server_acceptance_is_derived_from_logged_totals(self):
        summary = json.loads((self.root / "data/summary.json").read_text(encoding="utf-8"))
        for round_name in ("round3", "round4"):
            for route, entry in summary[round_name]["vllm_server_acceptance"].items():
                with self.subTest(round=round_name, route=route):
                    self.assertEqual(entry["drafted_tokens"], entry["verification_steps"] * 7)
                    self.assertAlmostEqual(entry["derived_mean_acceptance_length"],
                                           1.0 + entry["accepted_tokens"] / entry["verification_steps"], places=4)

    def test_forged_rule_record_is_rejected(self):
        self.mutate_json(validate_report.RULES, lambda value: value["checks"].append({"id": "extra", "status": "PASS", "evidence": []}))
        with self.assertRaisesRegex(ValueError, "VALIDATION_RECORD_DRIFT"):
            validate_report.validate(self.root)

    def test_replay_entry_required_in_both_readmes(self):
        for filename in validate_report.READMES:
            with self.subTest(filename=filename):
                path = self.topic / filename
                original = path.read_text(encoding="utf-8")
                path.write_text(original.replace(f"python experiments/{ROOT.name}/validate_report.py", "omitted", 1), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "REPLAY_ENTRY_MISSING"):
                    validate_report.validate(self.root)
                path.write_text(original, encoding="utf-8")

    def test_bootstrap_is_deterministic(self):
        reference = json.loads((self.root / "results/round4/agreement/ftzh_released.json").read_text(encoding="utf-8"))
        candidate = json.loads((self.root / "results/round4/agreement/ftzh_ours.json").read_text(encoding="utf-8"))
        first = analyze_results.paired_agreement(reference, candidate)
        second = analyze_results.paired_agreement(copy.deepcopy(reference), copy.deepcopy(candidate))
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "PAIRED")
        self.assertEqual(first["first_offset_hit_rate"]["interpretation"], "positive")


if __name__ == "__main__":
    unittest.main()

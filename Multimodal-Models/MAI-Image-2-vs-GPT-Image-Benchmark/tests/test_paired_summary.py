import csv
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import summarize_paired_run as summary


class PairedSummaryTests(unittest.TestCase):
    def usage(self):
        return {"input_tokens": 8, "input_tokens_details": {"text_tokens": 8, "image_tokens": 0},
                "output_tokens": 196, "output_tokens_details": {"image_tokens": 196, "text_tokens": 0},
                "total_tokens": 204}

    def test_incomplete_run_cannot_be_final_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "5way_v2_results.json").write_text(json.dumps({"state": "WARMUP"}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "terminal state"):
                summary.summarize(root, root / "prompts.csv")


class CompleteMatrixTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        report = Path(__file__).resolve().parents[1]
        prompts_bytes = (report / "prompts.csv").read_bytes()
        self.prompts_path = self.root / "prompts.csv"
        self.prompts_path.write_bytes(prompts_bytes)
        with self.prompts_path.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.reader(source)
            next(reader)
            prompts = [row[0].strip() for row in reader if row and row[0].strip()]
        (self.root / "source").mkdir()
        (self.root / "source" / "prompts.csv").write_bytes(prompts_bytes)
        source_bytes = b"offline fixture; never executed\n"
        (self.root / "source" / "benchmark_5way_v2.py").write_bytes(source_bytes)
        self.image = (report / "images" / "mai-image-2" / "r1" / "01_test.png").read_bytes()
        (self.root / "fixture.png").write_bytes(self.image)
        self.image_hash = hashlib.sha256(self.image).hexdigest()
        self.record = {
            "state": "COMPLETED", "started_at_utc": "2026-01-01T00:00:00+00:00",
            "ended_at_utc": "2026-01-01T00:04:00+00:00", "environment": {"fixture": True},
            "script_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "config": {"groups": list(summary.GROUPS), "rounds": 2, "resolution": "1024x1024",
                       "concurrency": 1, "inter_call_wait": 5, "formal_sample_count": 88,
                       "prompts_sha256": hashlib.sha256(prompts_bytes).hexdigest(),
                       "group_configurations": [
                           {"id": group, "quality": None if group == summary.GROUPS[0] else group.rsplit("-", 1)[1],
                            "provider": "mai" if group == summary.GROUPS[0] else "gpt",
                            "model": "MAI-Image-2.6" if group == summary.GROUPS[0] else "gpt-image-2",
                            "deployment_sku": "GlobalStandard"} for group in summary.GROUPS]},
            "warmup": [], "raw_data": [],
        }
        self.attempts = []
        for group in summary.GROUPS:
            tokens = self.add_attempt(group, "blue circle", "warmup-" + group, "warmup")
            (self.root / ("warmup-" + group + ".png")).write_bytes(self.image)
            self.record["warmup"].append({"group": group, "ok": True, "time": 0.25,
                                           "attempt_count": 1, "token_info": tokens})
        start = datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc)
        for round_number in (1, 2):
            for prompt_index, prompt in enumerate(prompts, 1):
                for group in (summary.GROUPS if round_number == 1 else reversed(summary.GROUPS)):
                    tokens = self.add_attempt(group, prompt, f"{group}-r{round_number}-p{prompt_index}",
                                              "formal", round_number, prompt_index)
                    began = start + timedelta(seconds=len(self.record["raw_data"]) * 2)
                    self.record["raw_data"].append({
                        "round": round_number, "prompt_idx": prompt_index, "group": group,
                        "quality": None if group == summary.GROUPS[0] else group.rsplit("-", 1)[1],
                        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                        "ok": True, "attempt_count": 1, "first_attempt_ok": True, "time": 0.25,
                        "logical_request_seconds": 0.3, "image": "fixture.png", "image_sha256": self.image_hash,
                        "size_bytes": len(self.image), "token_info": tokens,
                        "started_at_utc": began.isoformat(), "ended_at_utc": (began + timedelta(seconds=1)).isoformat(),
                    })

    def add_attempt(self, group, prompt, sample_id, phase, round_number=None, prompt_index=None):
        is_mai = group == summary.GROUPS[0]
        usage = ({"num_input_text_tokens": 8, "num_input_image_tokens": 0, "num_output_tokens": 1024}
                 if is_mai else PairedSummaryTests().usage())
        metadata = {"data": [{}], "usage": usage}
        (self.root / "responses").mkdir(exist_ok=True)
        metadata_path = "responses/" + sample_id + ".json"
        (self.root / metadata_path).write_text(json.dumps(metadata), encoding="utf-8")
        request = ({"model": "MAI-Image-2.6", "prompt": prompt, "width": 1024, "height": 1024} if is_mai else
                   {"prompt": prompt, "n": 1, "size": "1024x1024", "quality": group.rsplit("-", 1)[1]})
        self.attempts.append({"phase": phase, "group": group, "round": round_number, "prompt_idx": prompt_index,
                              "sample_id": sample_id, "attempt": 1, "ok": True, "request_seconds": 0.25,
                              "http_status": 200, "request": request, "width": 1024, "height": 1024,
                              "image_sha256": self.image_hash, "image_bytes": len(self.image),
                              "response_metadata": metadata_path})
        return {"usage": usage}

    def calculate(self):
        (self.root / "5way_v2_results.json").write_text(json.dumps(self.record), encoding="utf-8")
        (self.root / "attempts.jsonl").write_text("\n".join(json.dumps(row) for row in self.attempts), encoding="utf-8")
        return summary.summarize(self.root, self.prompts_path)

    def test_complete_matrix_excludes_four_warmups(self):
        result = self.calculate()
        self.assertEqual(result["formal_samples"], 88)
        self.assertEqual(result["warmup_samples"], 4)
        self.assertEqual([group["planned_samples"] for group in result["groups"]], [22] * 4)
        self.assertEqual(len(result["images"]), 92)
        self.assertTrue(all(group["successful_request_latency"]["mean_seconds"] == 0.25 for group in result["groups"]))
        self.assertNotRegex(json.dumps(result).lower(), r"price|cost|usd")

    def test_failed_high_sample_stays_in_denominator(self):
        failed = self.record["raw_data"][3]
        failed.update({"ok": False, "first_attempt_ok": False, "time": 0, "token_info": {},
                       "image": None, "image_sha256": None, "size_bytes": 0})
        self.attempts[7].update({"ok": False, "http_status": 503})
        self.record["state"] = "COMPLETED_WITH_FAILURES"
        result = self.calculate()
        high = result["groups"][3]
        self.assertEqual(high["planned_samples"], 22)
        self.assertEqual(high["successful_samples"], 21)
        self.assertEqual(result["failed_samples"], 1)
        self.assertEqual(high["unsuccessful_http_attempts"], 1)
        self.assertEqual(high["unsuccessful_attempt_seconds"], 0.25)
        self.assertEqual(len(result["unsuccessful_attempts"]), 1)
        self.assertEqual(result["unsuccessful_attempts"][0]["sample_id"], self.attempts[7]["sample_id"])

    def test_warmup_usage_must_match_original_response(self):
        self.record["warmup"][1]["token_info"]["usage"]["output_tokens"] += 1
        with self.assertRaisesRegex(ValueError, "Warmup usage"):
            self.calculate()

    def test_wrong_provider_is_rejected(self):
        self.record["config"]["group_configurations"][1]["provider"] = "mai"
        with self.assertRaisesRegex(ValueError, "provider/model"):
            self.calculate()

    def test_nonfinite_duration_is_rejected(self):
        self.record["raw_data"][0]["logical_request_seconds"] = float("nan")
        with self.assertRaisesRegex(ValueError, "finite"):
            self.calculate()

    def test_round_two_order_cannot_be_silently_changed(self):
        rows = self.record["raw_data"]
        rows[44], rows[45] = rows[45], rows[44]
        with self.assertRaisesRegex(ValueError, "ordered 88-sample"):
            self.calculate()

    def test_changed_source_without_provenance_is_rejected(self):
        (self.root / "source" / "benchmark_5way_v2.py").write_text("changed fixture\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "snapshot hash"):
            self.calculate()

    def test_public_projection_requires_both_current_hashes(self):
        path = self.root / "source" / "benchmark_5way_v2.py"
        path.write_text("redacted fixture\n", encoding="utf-8")
        result_path = self.root / "5way_v2_results.json"
        result_path.write_text(json.dumps(self.record), encoding="utf-8")
        projection = {"kind": "financial-metadata-removal", "original_script_sha256": self.record["script_sha256"],
                      "published_script_sha256": summary.digest(path), "published_result_sha256": summary.digest(result_path)}
        provenance = self.root / "provenance.json"
        provenance.write_text(json.dumps({"publication_redaction": projection}), encoding="utf-8")
        summary.validate_source_snapshot(self.root, self.record)
        path.write_text("unrecorded change\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "projection"):
            summary.validate_source_snapshot(self.root, self.record)


if __name__ == "__main__":
    unittest.main()
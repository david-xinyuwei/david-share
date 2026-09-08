import base64
import hashlib
import importlib.util
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("benchmark_runner", ROOT / "scripts" / "benchmark_5way_v2.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class RequestEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)
        self.output_patch = patch.object(runner, "OUT_BASE", self.output)
        self.output_patch.start()
        self.addCleanup(self.output_patch.stop)
        self.image = (ROOT / "images" / "mai-image-2" / "r1" / "01_test.png").read_bytes()
        runner.REQUEST_CONTEXT.clear()
        runner.LAST_ATTEMPTS.clear()

    def response(self, usage):
        content = {"created": 1, "data": [{"b64_json": base64.b64encode(self.image).decode("ascii")}],
                   "usage": usage}
        response = Mock(status_code=200, headers={"apim-request-id": "offline-contract-test"})
        response.content = json.dumps(content).encode("utf-8")
        response.json.return_value = content
        return response

    def test_all_gpt_quality_requests_preserve_usage_and_attempts(self):
        usage = {"input_tokens": 43, "output_tokens": 100,
                 "input_tokens_details": {"text_tokens": 43, "image_tokens": 0},
                 "total_tokens": 143}
        for quality in ("low", "medium", "high"):
            with self.subTest(quality=quality):
                runner.REQUEST_CONTEXT.update({"sample_id": "offline-" + quality, "group": "gpt-image-2-" + quality})
                with patch.object(runner.requests, "post", return_value=self.response(usage)) as post:
                    succeeded, duration, image, tokens = runner.generate_gpt("original prompt", quality)
                self.assertTrue(succeeded)
                self.assertGreaterEqual(duration, 0)
                self.assertEqual(image, self.image)
                self.assertEqual(post.call_args.kwargs["json"],
                                 {"prompt": "original prompt", "n": 1, "size": "1024x1024", "quality": quality})
                self.assertEqual(post.call_args.kwargs["timeout"], 300)
                self.assertEqual(tokens["usage"], usage)
                self.assertEqual(len(runner.LAST_ATTEMPTS), 1)
                self.assertEqual(runner.LAST_ATTEMPTS[0]["image_sha256"], hashlib.sha256(self.image).hexdigest())
                metadata = json.loads((self.output / runner.LAST_ATTEMPTS[0]["response_metadata"]).read_text("utf-8"))
                self.assertEqual(metadata["usage"], usage)
                self.assertNotIn("b64_json", metadata["data"][0])

    def test_mai_request_has_no_quality_parameter(self):
        usage = {"num_input_text_tokens": 43, "num_input_image_tokens": 0, "num_output_tokens": 1024}
        runner.REQUEST_CONTEXT.update({"sample_id": "offline-mai", "group": "mai-image-2.6"})
        with patch.object(runner.requests, "post", return_value=self.response(usage)) as post:
            succeeded, _, image, tokens = runner.generate_mai("MAI-Image-2.6", "original prompt", None)
        self.assertTrue(succeeded)
        self.assertEqual(image, self.image)
        self.assertEqual(post.call_args.kwargs["json"],
                         {"model": "MAI-Image-2.6", "prompt": "original prompt", "width": 1024, "height": 1024})
        self.assertEqual(tokens["usage"], usage)
        self.assertEqual(len(runner.LAST_ATTEMPTS), 1)

    def test_mai_grounding_pair_changes_only_grounding(self):
        requests_sent = []
        for grounding in (False, True):
            with self.subTest(web_grounding=grounding):
                group = {"type": "mai", "model": "MAI-Image-2.6", "web_grounding": grounding}
                with patch.object(runner.requests, "post", return_value=self.response({})) as post:
                    succeeded, _, image, _ = runner.call_group(group, "identical prompt", None)
                self.assertTrue(succeeded)
                self.assertEqual(image, self.image)
                payload = post.call_args.kwargs["json"]
                self.assertIs(payload["web_grounding"], grounding)
                self.assertIs(payload["auto_aspect_ratio"], False)
                self.assertEqual(runner.LAST_ATTEMPTS[0]["request"], payload)
                requests_sent.append(payload)
        self.assertEqual({key: value for key, value in requests_sent[0].items() if key != "web_grounding"},
                         {key: value for key, value in requests_sent[1].items() if key != "web_grounding"})

    def test_mai_grounding_rejects_string_boolean(self):
        with patch.object(runner.requests, "post") as post:
            with self.assertRaises(ValueError):
                runner.generate_mai("MAI-Image-2.6", "prompt", None, web_grounding="false")
        post.assert_not_called()

    def test_gpt_rate_limit_is_recorded_before_success(self):
        limited = Mock(status_code=429, headers={"retry-after": "1"}, content=b"rate limited")
        with patch.object(runner.requests, "post", side_effect=[limited, self.response({})]), \
                patch.object(runner.time, "sleep") as sleep:
            succeeded, _, _, _ = runner.generate_gpt("prompt", "low")
        self.assertTrue(succeeded)
        self.assertEqual([attempt["http_status"] for attempt in runner.LAST_ATTEMPTS], [429, 200])
        self.assertFalse(runner.LAST_ATTEMPTS[0]["ok"])
        self.assertEqual(runner.LAST_ATTEMPTS[0]["retry_wait_seconds"], 6)
        sleep.assert_called_once_with(6)

    def test_invalid_image_dimensions_cannot_be_successful(self):
        invalid = self.image[:16] + struct.pack(">II", 2048, 1024) + self.image[24:]
        response = self.response({})
        content = response.json.return_value
        content["data"][0]["b64_json"] = base64.b64encode(invalid).decode("ascii")
        with patch.object(runner.requests, "post", return_value=response):
            succeeded, _, image, _ = runner.generate_gpt("prompt", "medium", max_retries=1)
        self.assertFalse(succeeded)
        self.assertIsNone(image)
        self.assertFalse(runner.LAST_ATTEMPTS[0]["ok"])

    def test_two_key_providers_do_not_fetch_entra_token(self):
        with patch.object(runner, "GROUPS", [{"type": "mai"}, {"type": "gpt"}]), \
                patch.object(runner, "MAI_API_KEY", "offline-key"), \
                patch.object(runner.subprocess, "run") as command:
            self.assertIsNone(runner.get_entra_token())
        command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
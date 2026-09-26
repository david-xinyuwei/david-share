"""Fail-closed checks for outputs/gpt6-luna-20260926 (the GPT-6 Luna same-session follow-up)."""

import hashlib
import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("gpt6_report", ROOT / "scripts" / "build_gpt6_luna_report.py")
REPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPORT)
RUN_DIR = REPORT.RUN_DIR
MARKER = json.loads((ROOT / "outputs" / "public_redaction.json").read_text(encoding="utf-8"))["marker"]
# SHA-256 of lower-cased tokens that must never appear (customer, people in the withheld transcript, real
# resource names, subscription IDs, VM address). Stored as hashes so this file does not publish them itself.
SENSITIVE_SHA256 = {
    "0d3a77d2f4bad2330000262b8a8a4b018be6ef570b53e3d62096fb121e05800b",
    "0d53224e68dfaa495e15ac4d02eeb4cbccb770e8d05c1cdc60f6a5981ed60232",
    "176b1a548facbefbaab85e66a2cf98ef6ac0f8c53b9be03bd7573be926d9bca0",
    "320c52971eb158416d2a4cebada12592ea43f6a0bc5ac64ff81f135d584792d7",
    "498fdb55b8fbdf97cd8e2b1f3ee1fe5e0f200887b16842dafb4c15af8b75bb80",
    "502b058ffec835b396ac5a6cef1c6acb678cf7fefd6c9b6f42ec37dfe135774d",
    "52f1e281766542887930bd9d1ce3d897eae826a57c33572359ac441628c5835e",
    "56018fe135c84cb3af995473a79669e46d0a02b12b8b3141aba2d2ad19d66f70",
    "585a18898b0dc32773c4e82f5b5e8da53456131f2cc586a4a961f5058419a0f7",
    "6f9b3c70fcd44fe58bb465581698eba82143f57d556d8e15893d3b036d06551c",
    "7f7d20914b30eb642fb1570a9246d704d095291d28a9c518f516e7cd95c330ca",
    "83711b30d714ef00b98a68bc2ef22193de662eeb8494e83c96869ae729178c22",
    "bca679a1aa9b724a5e8bad61fc0aeba5311f0bb8b0564e3d7d486ad943aa4489",
    "d9f31c9e0c7880bb43858ba6e183e741df498eaa7ee604fdac7ee1e032fed1ac",
    "da792133688e3db30f3015add74da185f999bc04ea72c2c7dcfeae8f77b24c8a",
}
TOKEN = re.compile(r"[a-z0-9][a-z0-9._-]*")


def rows(name):
    return REPORT.load_jsonl(RUN_DIR / name)


class Gpt6LunaRunTests(unittest.TestCase):
    def test_evidence_is_complete(self):
        records = rows(f"direct_{REPORT.RUN}.metrics.jsonl")
        paired = rows(f"{REPORT.PAIRED}.jsonl")
        summary = json.loads((RUN_DIR / f"{REPORT.PAIRED}.summary.json").read_text(encoding="utf-8"))
        q55 = REPORT.quality(RUN_DIR / f"quality_opus55_{REPORT.RUN}.jsonl")
        q46 = REPORT.quality(RUN_DIR / f"quality_opus46_{REPORT.RUN}.jsonl")
        self.assertEqual(REPORT.validate(records, paired, q55, q46, summary), [])

    def test_readme_matches_evidence(self):
        self.assertEqual((RUN_DIR / "README.md").read_text(encoding="utf-8"), REPORT.render())

    def test_metrics_carry_no_answer_text(self):
        for r in rows(f"direct_{REPORT.RUN}.metrics.jsonl"):
            self.assertNotIn("response_text", r)
            self.assertNotIn("response_preview", r)
            self.assertRegex(r["response_sha256"], r"^[0-9a-f]{64}$")

    def test_fulltext_hashes_and_withheld_prompts(self):
        metrics = {(r["arm"], r["question_id"], r["iteration"]): r["response_sha256"]
                   for r in rows(f"direct_{REPORT.RUN}.metrics.jsonl")}
        full = rows(f"raw_fulltext/direct_{REPORT.RUN}.jsonl")
        self.assertEqual(len(full), len(metrics))
        for r in full:
            key = (r["arm"], r["question_id"], r["iteration"])
            self.assertEqual(r["response_sha256"], metrics[key])
            if r["question_id"] in REPORT.WITHHELD:
                self.assertEqual(r["response_text"], MARKER)
            else:
                self.assertEqual(hashlib.sha256(r["response_text"].encode("utf-8")).hexdigest(), r["response_sha256"])

    def test_withheld_justifications(self):
        for name in (f"quality_opus55_{REPORT.RUN}.jsonl", f"quality_opus46_{REPORT.RUN}.jsonl"):
            for r in rows(name):
                if r["question_id"] in REPORT.WITHHELD:
                    self.assertEqual(r["justification"], MARKER, name)

    def test_no_sensitive_strings_in_published_files(self):
        for path in list(RUN_DIR.rglob("*")) + [ROOT / "scripts" / "paired_direct.py",
                                                ROOT / "scripts" / "build_gpt6_luna_report.py"]:
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace").lower()
            # whole tokens catch addresses and IDs; alphanumeric runs catch names inside file names
            tokens = {t.strip("._-") for t in TOKEN.findall(text)} | set(re.findall(r"[a-z0-9]+", text))
            hits = {t for t in tokens if hashlib.sha256(t.encode("utf-8")).hexdigest() in SENSITIVE_SHA256}
            self.assertFalse(hits, f"{path.name}: {len(hits)} sensitive token(s)")


if __name__ == "__main__":
    unittest.main()

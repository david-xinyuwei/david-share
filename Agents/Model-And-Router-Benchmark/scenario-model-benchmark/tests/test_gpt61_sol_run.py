"""Fail-closed checks for outputs/gpt61-sol-20261003 (the GPT-6.1 Sol follow-up)."""

import hashlib
import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


REPORT = module("gpt61_report", "scripts/build_gpt61_sol_report.py")
# the sensitive-token list is owned by the 2026-09-26 test; reuse it rather than copy it
SENSITIVE_SHA256 = module("gpt6_luna_test", "tests/test_gpt6_luna_run.py").SENSITIVE_SHA256
RUN_DIR = REPORT.RUN_DIR
MARKER = json.loads((ROOT / "outputs" / "public_redaction.json").read_text(encoding="utf-8"))["marker"]
TOKEN = re.compile(r"[a-z0-9][a-z0-9._-]*")


def rows(name):
    return REPORT.load_jsonl(RUN_DIR / name)


class Gpt61SolRunTests(unittest.TestCase):
    def test_evidence_is_complete(self):
        records = rows(f"direct_{REPORT.RUN}.metrics.jsonl")
        paired = rows(f"{REPORT.PAIRED}.jsonl")
        summary = json.loads((RUN_DIR / f"{REPORT.PAIRED}.summary.json").read_text(encoding="utf-8"))
        q46 = REPORT.quality(RUN_DIR / f"quality_opus46_{REPORT.RUN}.jsonl")
        cache_rows = rows("prompt_cache_check.metrics.jsonl")
        cache_summary = json.loads((RUN_DIR / "prompt_cache_check.summary.json").read_text(encoding="utf-8"))
        self.assertEqual(REPORT.validate(records, paired, q46, summary, REPORT.probe_files(), cache_rows,
                                         cache_summary), [])

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
        for r in rows(f"quality_opus46_{REPORT.RUN}.jsonl"):
            if r["question_id"] in REPORT.WITHHELD:
                self.assertEqual(r["justification"], MARKER)

    def test_probe_records_classify_without_a_wrong_answer_on_the_base_run(self):
        base = json.loads((RUN_DIR / "exact_answer_probe.json").read_text(encoding="utf-8"))
        outcomes = [REPORT.probe_outcome(r, 40_000) for r in base["records"]]
        self.assertEqual(len(outcomes), 9)
        self.assertNotIn("wrong", outcomes)
        self.assertNotIn("error", outcomes)

    def test_provenance_hashes_match_committed_files(self):
        prov = json.loads((RUN_DIR / "provenance.json").read_text(encoding="utf-8"))
        for relative, digest in prov["committed_sha256"].items():
            path = RUN_DIR / relative
            self.assertTrue(path.is_file(), relative)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest, relative)

    def test_no_sensitive_strings_in_published_files(self):
        for path in list(RUN_DIR.rglob("*")) + [ROOT / "scripts" / "build_gpt61_sol_report.py", Path(__file__)]:
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace").lower()
            tokens = {t.strip("._-") for t in TOKEN.findall(text)} | set(re.findall(r"[a-z0-9]+", text))
            hits = {t for t in tokens if hashlib.sha256(t.encode("utf-8")).hexdigest() in SENSITIVE_SHA256}
            self.assertFalse(hits, f"{path.name}: {len(hits)} sensitive token(s)")


if __name__ == "__main__":
    unittest.main()

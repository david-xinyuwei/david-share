"""Tests for the pinned upstream patches and the code excerpts quoted in the READMEs."""
import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_readme  # noqa: E402

LOCK = json.loads((ROOT / "upstream/SOURCES.lock.json").read_text(encoding="utf-8"))


class UpstreamTests(unittest.TestCase):
    def test_every_patch_matches_its_lock_entry(self):
        files = {p.name for p in (ROOT / "upstream/patches").glob("*.patch")}
        self.assertEqual(files, {e["file"] for e in LOCK["patches"]})
        for e in LOCK["patches"]:
            raw = (ROOT / "upstream/patches" / e["file"]).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), e["sha256"], e["file"])
            self.assertEqual(len(raw), e["bytes"], e["file"])
            self.assertTrue(raw.startswith(f"From {e['commit']} ".encode()), e["file"])
            self.assertEqual(e["url"], f"https://github.com/{e['repository']}/commit/{e['commit']}")
            self.assertIn(e["license"], {"Apache-2.0", "MIT"})

    def test_later_commits_are_marked_outside_the_pinned_runtime(self):
        status = {e["commit"][:7]: e["in_pinned_head"] for e in LOCK["patches"]}
        self.assertFalse(status["1f9bb2b"])
        self.assertTrue(status["c99d5cd"])
        self.assertTrue(status["d725746"])

    def test_technique_catalog_only_references_locked_patches(self):
        catalog = json.loads((ROOT / "profiles/techniques.json").read_text(encoding="utf-8"))
        locked = {e["file"] for e in LOCK["patches"]}
        for t in catalog["techniques"]:
            for patch in t["patches"]:
                self.assertIn(patch, locked, t["id"])

    def test_readme_excerpts_are_byte_identical_to_the_patch(self):
        spec = json.loads((ROOT / "tools/excerpts.json").read_text(encoding="utf-8"))["excerpts"]
        for lang, path in build_readme.READMES.items():
            text = path.read_text(encoding="utf-8")
            for name, e in spec.items():
                lines = (ROOT / "upstream/patches" / e["patch"]).read_text(encoding="utf-8").split("\n")
                start = lines.index(e["start"])
                body = "\n".join(lines[start:start + e["lines"]])
                with self.subTest(lang=lang, excerpt=name):
                    self.assertIn("```diff\n" + body + "\n```", text)

    def test_tuned_moe_csv_in_patch_is_the_file_that_was_served(self):
        served = json.loads((ROOT / "evidence/runs.json").read_text(encoding="utf-8"))["runs"]["stage-20260713-tuned-moe"]["runtime"]["tuned_fmoe_csv_sha256"]
        text = (ROOT / "upstream/patches/sammysun0711__aiter__d725746.patch").read_text(encoding="utf-8")
        section = text.split("b/aiter/configs/model_configs/mimo_v2_5_pro_b16_tuned_fmoe.csv\n", 2)[2].split("diff --git", 1)[0]
        body = "\n".join(l[1:] for l in section.split("\n") if l.startswith("+") and not l.startswith("+++")) + "\n"
        self.assertEqual(hashlib.sha256(body.encode()).hexdigest(), served)

    def test_dockerfile_pins_the_locked_heads(self):
        docker = (ROOT / "docker/Dockerfile").read_text(encoding="utf-8")
        args = dict(re.findall(r"^ARG (\w+)=(\S+)$", docker, re.M))
        self.assertEqual(args["SGLANG_COMMIT"], LOCK["pinned_heads"]["sammysun0711/sglang"]["commit"])
        self.assertEqual(args["AITER_COMMIT"], LOCK["pinned_heads"]["sammysun0711/aiter"]["commit"])
        self.assertEqual(args["FLYDSL_KERNELS_COMMIT"], LOCK["pinned_heads"]["sammysun0711/FlyDSL"]["commit"])
        self.assertRegex(args["FLYDSL_WHEEL_SHA256"], r"^[0-9a-f]{64}$")
        self.assertIn("sha256sum -c", docker)
        self.assertRegex(docker, r"FROM rocm/sgl-dev@sha256:[0-9a-f]{64}")

    def test_stack_status_separates_measured_from_pinned(self):
        status = {e["commit"][:7]: e["stack_status"] for e in LOCK["patches"]}
        self.assertEqual(status["2f9b9ae"], "measured_run")
        self.assertEqual(status["d725746"], "measured_run")
        self.assertEqual(status["c99d5cd"], "pinned_runtime_not_throughput_tested")
        self.assertEqual(status["1f9bb2b"], "later_branch")


if __name__ == "__main__":
    unittest.main()

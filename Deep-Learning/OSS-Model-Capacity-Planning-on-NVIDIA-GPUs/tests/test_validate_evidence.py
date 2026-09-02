"""Fail-closed tests for tools/validate_evidence.py.

Each test copies this repository subtree into a temporary two-level tree
(``<tmp>/david-share/Deep-Learning/<subtree>``) so that the ``../../LICENSE``
badge link still resolves, applies exactly one tampering, and asserts that
the validator exits non-zero with the expected message. The untampered copy
must pass. No GPU, credentials, or network are required.

Run from the subtree root:

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SUBTREE = Path(__file__).resolve().parents[1]
REAL_WORKLOADS = Path("evidence/runs/qwen3-235b-h100-vllm-real-workloads")
CODING_LOG = REAL_WORKLOADS / "logs/coding-agent-16gpu.log"
CODING_CSV = REAL_WORKLOADS / "results/coding-agent-16gpu/disagg/best_config_topn.csv"
CODING_32_CSV = REAL_WORKLOADS / "results/coding-agent-32gpu/disagg/best_config_topn.csv"
MANIFEST = REAL_WORKLOADS / "run-manifest.json"
IGNORE = shutil.ignore_patterns(".venv", "run-output", "__pycache__", ".git", "*.pyc")


class ValidatorCopy:
    """A disposable copy of the subtree with helpers for one tampering."""

    def __init__(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="capacity-validator-"))
        repo_root = self.tmp / "david-share"
        self.root = repo_root / "Deep-Learning" / SUBTREE.name
        shutil.copytree(SUBTREE, self.root, ignore=IGNORE)
        (repo_root / "LICENSE").write_text("MIT License placeholder for link resolution\n", encoding="utf-8")

    def cleanup(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def read(self, relative: Path | str) -> str:
        return (self.root / relative).read_text(encoding="utf-8")

    def write(self, relative: Path | str, text: str) -> None:
        (self.root / relative).write_text(text, encoding="utf-8", newline="\n")

    def replace_once(self, relative: Path | str, old: str, new: str) -> None:
        text = self.read(relative)
        if text.count(old) < 1:
            raise AssertionError(f"tampering target {old!r} not found in {relative}")
        self.write(relative, text.replace(old, new, 1))

    def forge_manifest_entry(self, relative_to_run: str) -> None:
        """Rewrite the manifest hash and byte count so a tampered file looks published."""
        target = self.root / REAL_WORKLOADS / relative_to_run
        manifest_path = self.root / MANIFEST
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in manifest["files"]:
            if entry["path"] == relative_to_run:
                entry["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
                entry["bytes"] = target.stat().st_size
                break
        else:
            raise AssertionError(f"{relative_to_run} not in manifest")
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    def run_validator(self) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        return subprocess.run(
            [sys.executable, str(self.root / "tools" / "validate_evidence.py")],
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            check=False,
        )


class ValidatorFailsClosed(unittest.TestCase):
    def setUp(self) -> None:
        self.copy = ValidatorCopy()
        self.addCleanup(self.copy.cleanup)

    def assert_rejected(self, message: str) -> None:
        result = self.copy.run_validator()
        self.assertNotEqual(result.returncode, 0, f"validator accepted tampered tree:\n{result.stdout}")
        self.assertIn(message, result.stderr, f"unexpected rejection reason:\n{result.stderr}")

    def test_untampered_copy_passes(self) -> None:
        result = self.copy.run_validator()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("EVIDENCE_VALIDATION=PASS RUNS=3 PUBLIC_BOUNDARY=PASS", result.stdout)

    def test_flipped_log_byte_is_rejected_by_hash(self) -> None:
        self.copy.replace_once(CODING_LOG, "Experiment agg completed with 211 results.", "Experiment agg completed with 2l1 results.")
        self.assert_rejected("SHA-256 mismatch")

    def test_forged_hash_does_not_hide_numeric_drift(self) -> None:
        self.copy.replace_once(CODING_CSV, ",120.146,", ",121.146,")
        self.copy.forge_manifest_entry("results/coding-agent-16gpu/disagg/best_config_topn.csv")
        self.assert_rejected("tokens/s/gpu drift")

    def test_forged_hash_does_not_hide_inflated_cluster_metric(self) -> None:
        # Pretend the 24-GPU replica used all 32 GPUs by copying tokens/s/gpu into tokens/s/gpu_cluster.
        self.copy.replace_once(CODING_32_CSV, ",99.39375000000001", ",132.525")
        self.copy.forge_manifest_entry("results/coding-agent-32gpu/disagg/best_config_topn.csv")
        self.assert_rejected("does not equal tokens/s/gpu x 24/32")

    def test_readme_ratio_drift_is_rejected(self) -> None:
        self.copy.write("README.md", self.copy.read("README.md").replace("4.75x", "4.8x"))
        self.assert_rejected("English walkthrough token missing: 4.75x")

    def test_selected_layout_token_drift_is_rejected(self) -> None:
        self.copy.write("README.md", self.copy.read("README.md").replace("tp1pp1dp8etp1ep8", "tp1pp1dp8etp8ep1"))
        self.assert_rejected("English walkthrough token missing: tp1pp1dp8etp1ep8")

    def test_missing_chinese_log_link_is_rejected(self) -> None:
        link = "evidence/runs/qwen3-235b-h100-vllm-50rps/logs/04-cpu-memory-profile.log"
        self.copy.write("README-CN.md", self.copy.read("README-CN.md").replace(link, "evidence/README.md"))
        self.assert_rejected(f"Chinese full-log link missing: {link}")

    def test_bilingual_command_block_drift_is_rejected(self) -> None:
        self.copy.replace_once("README-CN.md", "--top-n 5 \\", "--top-n 6 \\")
        self.assert_rejected("Bilingual Bash/PowerShell command blocks drifted")

    def test_retired_chinese_phrase_is_rejected(self) -> None:
        self.copy.write("README-CN.md", self.copy.read("README-CN.md") + "\n工作负载形态\n")
        self.assert_rejected("Retired Chinese phrase found")

    def test_private_path_in_log_is_rejected_even_with_forged_hash(self) -> None:
        self.copy.write(CODING_LOG, self.copy.read(CODING_LOG) + "saved to /root/private/results\n")
        self.copy.forge_manifest_entry("logs/coding-agent-16gpu.log")
        self.assert_rejected("private-linux-root found")


if __name__ == "__main__":
    unittest.main()

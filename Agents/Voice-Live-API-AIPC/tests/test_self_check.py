from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"


def test_self_check_contains_no_live_or_mutating_calls() -> None:
    module = ast.parse(APP.read_text(encoding="utf-8"))
    function = next(
        node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "_self_check"
    )
    source = ast.unparse(function)

    for forbidden in ("signed_in_user", "get_power_timeouts", "_ensure_hibernate_visible"):
        assert forbidden not in source


def test_source_self_check_passes_without_creating_runtime_logs() -> None:
    report = ROOT / "self_check.txt"
    report.unlink(missing_ok=True)
    try:
        completed = subprocess.run(
            [sys.executable, str(APP), "--self-check"],
            cwd=ROOT,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        text = report.read_text(encoding="utf-8")
        assert "SELF_CHECK=PASS" in text
        assert "Graph 已授权账号" not in text
        assert not (ROOT / "logs").exists()
    finally:
        report.unlink(missing_ok=True)

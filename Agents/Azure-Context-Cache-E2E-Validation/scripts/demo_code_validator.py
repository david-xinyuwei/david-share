"""Static authenticity gate for the Azure Context Cache live path."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_FILES = (
    ROOT / "scripts" / "run_official_e2e.ps1",
    ROOT / "scripts" / "verify_upstream.py",
    ROOT / "scripts" / "parse_demo_output.py",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    runner = RUNTIME_FILES[0].read_text(encoding="utf-8")
    combined = "\n".join(path.read_text(encoding="utf-8") for path in RUNTIME_FILES)
    manifest = json.loads((ROOT / "scenario-manifest.json").read_text(encoding="utf-8"))

    for marker in (
        "scripts/quickstart.ps1",
        "verify_upstream.py",
        "parse_demo_output.py",
        "ProcessStartInfo",
        "OpenAI.ContextCacheAllowed",
        "AZURE_CONFIG_DIR",
        "SupportsShouldProcess",
    ):
        require(marker in runner, f"runner missing real-path marker: {marker}")
    for forbidden in (
        "tests/fixtures",
        "az login",
        "feature register",
        "AOAI_API_KEY",
        "Start-Sleep",
        "fallback to mock",
    ):
        require(forbidden not in combined, f"forbidden runtime fallback: {forbidden}")

    classifications = {item["classification"] for item in manifest["scenarios"]}
    require(
        classifications == {"dynamic-runtime", "test-fixture", "architecture-explainer"},
        "scenario classifications changed",
    )
    require(len(manifest["forbiddenFallbacks"]) >= 5, "forbidden fallbacks are incomplete")
    print("DEMO_CODE_GATE=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, KeyError, TypeError, ValueError, RuntimeError) as error:
        print(f"DEMO_CODE_GATE=FAIL: {error}")
        raise SystemExit(1) from error
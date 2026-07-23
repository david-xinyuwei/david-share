"""Build the byte-for-byte classic-versus-managed parity manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

BASELINE_COMMIT = "667357dac6ee2dc30102d572c458c77861112bea"
SHARED_FILES = (
    "src/meeting_agent/models.py",
    "src/meeting_agent/session.py",
    "src/meeting_agent/draft.py",
    "src/meeting_agent/hosted_models.py",
    "src/meeting_agent/hosted_pipeline.py",
    "ui/src/input.ts",
    "ui/src/mind-map-export.ts",
    "ui/server/outlook.mjs",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--classic-root", type=Path, required=True)
    parser.add_argument("--managed-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "evidence"
        / "managed-live"
        / "parity-manifest.json",
    )
    args = parser.parse_args()

    entries = []
    for relative in SHARED_FILES:
        baseline_path = args.classic_root / relative
        managed_path = args.managed_root / relative
        baseline_hash = sha256(baseline_path)
        managed_hash = sha256(managed_path)
        if baseline_hash != managed_hash:
            raise RuntimeError(f"Parity mismatch: {relative}")
        entries.append(
            {
                "baseline_path": f"Agents/Meeting-Agent/{relative}",
                "managed_path": f"Agents/Meeting-Agent/managed-agent/{relative}",
                "sha256": baseline_hash,
            }
        )

    manifest = {
        "schema_version": 1,
        "baseline_repository": "https://github.com/david-xinyuwei/david-share",
        "baseline_commit": BASELINE_COMMIT,
        "validated_at_utc": datetime.now(UTC).isoformat(),
        "comparison": "byte-for-byte SHA-256 equality",
        "entries": entries,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"PARITY_MANIFEST_PASS entries={len(entries)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Summarize Q0 quantization smoke JSON artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        return {"label": path.stem.replace("_smoke", ""), "status": "read_error", "error": repr(error)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    rows = []
    for path in sorted(input_dir.glob("*_smoke.json")):
        data = load_json(path)
        rows.append(
            {
                "label": data.get("label", path.stem.replace("_smoke", "")),
                "status": data.get("status"),
                "http_status": data.get("http_status"),
                "latency_ms": data.get("latency_ms"),
                "schema_valid": data.get("schema_valid"),
                "image_observed": data.get("image_observed"),
                "error": data.get("error") or data.get("reason"),
            }
        )

    summary = {"n": len(rows), "rows": rows}
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
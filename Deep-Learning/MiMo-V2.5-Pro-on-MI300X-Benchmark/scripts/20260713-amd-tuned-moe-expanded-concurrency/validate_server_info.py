#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import urlopen


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="Direct worker /server_info URL")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--context-length", type=int, default=262151)
    parser.add_argument("--min-request-input", type=int, default=262145)
    args = parser.parse_args()

    with urlopen(args.url, timeout=10) as response:
        payload = json.load(response)
    evidence = {
        "context_length": payload["context_length"],
        "max_req_input_len": payload["max_req_input_len"],
        "version": payload.get("version"),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, sort_keys=True))

    if evidence["context_length"] != args.context_length:
        raise SystemExit(f"Unexpected context_length: {evidence}")
    if evidence["max_req_input_len"] < args.min_request_input:
        raise SystemExit(f"Insufficient max_req_input_len: {evidence}")


if __name__ == "__main__":
    main()
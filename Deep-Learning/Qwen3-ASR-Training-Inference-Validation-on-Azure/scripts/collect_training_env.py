#!/usr/bin/env python3
"""Collect training environment facts for ASR troubleshooting."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path


COMMANDS = {
    "nvidia_smi": ["nvidia-smi"],
    "nvidia_smi_query": ["nvidia-smi", "--query-gpu=index,name,driver_version,memory.total,memory.used,utilization.gpu", "--format=csv,noheader"],
    "python_version": ["python3", "--version"],
    "pip_freeze_selected": ["python3", "-m", "pip", "show", "torch", "transformers", "accelerate", "deepspeed", "trl", "vllm", "sglang"],
    "disk_root": ["df", "-h", "/"],
    "memory": ["free", "-h"],
}


def run_command(command: list[str]) -> dict[str, object]:
    if shutil.which(command[0]) is None:
        return {"available": False, "returncode": None, "stdout": "", "stderr": f"{command[0]} not found"}
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    return {
        "available": True,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def collect() -> dict[str, object]:
    return {
        "host": platform.node(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cwd": str(Path.cwd()),
        "env": {
            key: os.environ.get(key)
            for key in [
                "CUDA_VISIBLE_DEVICES",
                "NCCL_DEBUG",
                "NCCL_SOCKET_IFNAME",
                "TRANSFORMERS_CACHE",
                "HF_HOME",
                "HF_HUB_ENABLE_HF_TRANSFER",
                "ACCELERATE_CONFIG_FILE",
            ]
            if os.environ.get(key) is not None
        },
        "commands": {name: run_command(command) for name, command in COMMANDS.items()},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect ASR training environment facts.")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = collect()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
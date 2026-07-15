"""Foundry Hosted Agent entry point."""

from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path


def main() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    hosted = import_module("meeting_agent.hosted")
    hosted.main()


if __name__ == "__main__":
    main()
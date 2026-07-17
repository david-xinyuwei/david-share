"""Test-only Hosted Agent process with an explicitly injected fixture analyzer."""

from __future__ import annotations

from meeting_agent import hosted
from tests.support import DeterministicTestAnalyzer


def main() -> None:
    hosted._get_analyzer = lambda: DeterministicTestAnalyzer()
    hosted.main()


if __name__ == "__main__":
    main()
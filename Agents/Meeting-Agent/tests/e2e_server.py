"""Test-only Hosted Agent process with an explicitly injected fixture analyzer."""

from __future__ import annotations

from itertools import cycle

from meeting_agent import hosted
from tests.support import StaticFixtureAnalyzer, sample_analysis

ANALYSES = cycle(
    (
        sample_analysis("product-planning"),
        sample_analysis("operations-review"),
    )
)


def _test_analyzer() -> StaticFixtureAnalyzer:
    return StaticFixtureAnalyzer(
        next(ANALYSES),
        response_id="test-fixture-response",
        deltas=('{"fixture":true}',),
    )


def main() -> None:
    hosted._get_analyzer = _test_analyzer
    hosted.main()


if __name__ == "__main__":
    main()
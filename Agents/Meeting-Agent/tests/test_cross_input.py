from pathlib import Path

from meeting_agent.analyzers import OfflineContractAnalyzer
from meeting_agent.session import load_jsonl

ROOT = Path(__file__).resolve().parents[1]


def test_two_meetings_produce_materially_different_analysis() -> None:
    analyzer = OfflineContractAnalyzer()
    product = analyzer.analyze(load_jsonl(ROOT / "examples" / "product-planning.jsonl"))
    operations = analyzer.analyze(load_jsonl(ROOT / "examples" / "operations-review.jsonl"))

    assert product.title != operations.title
    assert product.summary != operations.summary
    assert product.mind_map.model_dump() != operations.mind_map.model_dump()
    assert "pilot" in product.summary.casefold()
    assert "database" in operations.summary.casefold()


def test_offline_contract_analyzer_is_deterministic() -> None:
    session = load_jsonl(ROOT / "examples" / "product-planning.jsonl")
    analyzer = OfflineContractAnalyzer()

    assert analyzer.analyze(session) == analyzer.analyze(session)
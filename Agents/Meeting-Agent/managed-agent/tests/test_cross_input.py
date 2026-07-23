from tests.support import StaticFixtureAnalyzer, sample_analysis


def test_committed_sample_fixtures_are_materially_different() -> None:
    product = sample_analysis("product-planning")
    operations = sample_analysis("operations-review")

    assert product.title != operations.title
    assert product.summary != operations.summary
    assert product.mind_map.model_dump() != operations.mind_map.model_dump()
    assert "pilot" in product.summary.casefold()
    assert "database" in operations.summary.casefold()


def test_static_fixture_analyzer_returns_the_supplied_analysis() -> None:
    product = sample_analysis("product-planning")
    analyzer = StaticFixtureAnalyzer(product)

    assert analyzer.analyze(None) == product
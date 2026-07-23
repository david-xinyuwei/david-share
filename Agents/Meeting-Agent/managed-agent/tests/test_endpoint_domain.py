from meeting_agent.analyzers import FOUNDRY_HOST_SUFFIX


def test_foundry_host_suffix_is_fixed() -> None:
    assert FOUNDRY_HOST_SUFFIX == ".services.ai.azure.com"

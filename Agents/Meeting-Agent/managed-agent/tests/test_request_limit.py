from meeting_agent.hosted import MAX_REQUEST_BYTES


def test_request_limit_is_two_mib() -> None:
    assert MAX_REQUEST_BYTES == 2_097_152

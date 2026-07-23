from meeting_agent.hosted import MAX_CONCURRENT_RUNS, MAX_REQUEST_BYTES


def test_backend_admission_limits_are_bounded() -> None:
    assert MAX_REQUEST_BYTES == 2 * 1024 * 1024
    assert MAX_CONCURRENT_RUNS == 2

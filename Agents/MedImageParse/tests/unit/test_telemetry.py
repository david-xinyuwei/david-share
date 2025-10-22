"""
Unit tests for telemetry module
"""
from src.telemetry import get_correlation_id, reset_correlation_id, TelemetryLogger


def test_correlation_id_generation():
    """Test correlation ID generation"""
    correlation_id = get_correlation_id()
    assert correlation_id is not None
    assert len(correlation_id) > 0
    
    # Should return same ID on subsequent calls
    correlation_id2 = get_correlation_id()
    assert correlation_id == correlation_id2


def test_correlation_id_reset():
    """Test correlation ID reset"""
    id1 = get_correlation_id()
    id2 = reset_correlation_id()
    
    assert id1 != id2
    assert get_correlation_id() == id2


def test_telemetry_logger_initialization():
    """Test TelemetryLogger initialization"""
    logger = TelemetryLogger(name="test")
    assert logger is not None
    assert logger.logger.name == "test"


def test_telemetry_logger_methods():
    """Test TelemetryLogger logging methods"""
    logger = TelemetryLogger(name="test")
    
    # These should not raise exceptions
    logger.info("Test info message")
    logger.warning("Test warning message")
    logger.error("Test error message")
    logger.track_event("test_event", {"key": "value"})

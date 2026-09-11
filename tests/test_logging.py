import logging
from app.logging_config import setup_logging

def test_logging_setup():
    """Test that logging is configured."""
    logger = setup_logging("DEBUG")
    assert logger.level == logging.DEBUG

    # Verify secret filter is applied
    handler = logger.handlers[0]
    assert any(f.name == "SecretFilter" for f in handler.filters)

def test_secret_filter_redacts():
    """Test that secrets are redacted from logs."""
    from app.logging_config import SecretFilter

    filter = SecretFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="cookie: abc123secret",
        args=(),
        exc_info=None
    )

    # Filter should allow the record but the filter logic will redact
    assert filter.filter(record) is True
    assert record.msg == "cookie: [REDACTED]"

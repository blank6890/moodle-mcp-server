import logging
import sys
from typing import Optional

class SecretFilter(logging.Filter):
    """Filter that redacts sensitive fields from log records."""

    name = "SecretFilter"

    SENSITIVE_FIELDS = {"cookie", "token", "session", "authorization", "password", "csrf"}

    def __init__(self):
        super().__init__(name="SecretFilter")

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact sensitive fields from the log message."""
        if record.msg:
            msg_str = str(record.msg)
            for field in self.SENSITIVE_FIELDS:
                # Simple replacement: "field: value" → "field: [REDACTED]"
                import re
                pattern = rf"({field})\s*:\s*\S+"
                msg_str = re.sub(pattern, rf"\1: [REDACTED]", msg_str, flags=re.IGNORECASE)
            record.msg = msg_str
        return True

def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure logging with secret redaction."""
    logger = logging.getLogger("moodle_agent")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)

    # Add secret filter
    handler.addFilter(SecretFilter())

    # Add handler to logger
    if logger.handlers:
        logger.handlers.clear()
    logger.addHandler(handler)

    return logger

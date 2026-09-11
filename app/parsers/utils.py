import logging
from dateutil.parser import parse as parse_date

logger = logging.getLogger(__name__)


def parse_date_to_iso(date_str: str) -> tuple[str | None, str]:
    """Parse Moodle date string to ISO 8601 and raw fallback.

    Args:
        date_str: Date string from HTML (e.g., "15 September 2026")

    Returns:
        Tuple of (iso_8601_string or None, raw_string)
    """
    raw = date_str.strip()
    try:
        dt = parse_date(date_str, dayfirst=True)
        iso = dt.isoformat()
        return iso, raw
    except Exception as e:
        logger.debug(f"Could not parse date '{date_str}': {e}")
        return None, raw


def parse_date_to_iso_date(date_str: str) -> tuple[str | None, str]:
    """Parse Moodle date string to ISO date (without time).

    Args:
        date_str: Date string from HTML

    Returns:
        Tuple of (iso_date_string or None, raw_string)
    """
    raw = date_str.strip()
    try:
        dt = parse_date(date_str, dayfirst=True)
        iso = dt.date().isoformat()
        return iso, raw
    except Exception as e:
        logger.debug(f"Could not parse date '{date_str}': {e}")
        return None, raw

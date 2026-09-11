import logging
from bs4 import BeautifulSoup
from dateutil.parser import parse as parse_date
from app.models import Announcement

logger = logging.getLogger(__name__)

def _parse_date_to_iso(date_str: str) -> tuple[str | None, str]:
    """Parse date string to ISO 8601."""
    raw = date_str.strip()
    try:
        dt = parse_date(date_str, dayfirst=True)
        iso = dt.isoformat()
        return iso, raw
    except Exception:
        return None, raw

def parse_announcements(html: str) -> list[Announcement]:
    """Parse announcements (forum posts) → list of Announcement models.

    CALIBRATE: Update selectors from real course Discussions section HTML.
    """
    soup = BeautifulSoup(html, "html.parser")
    announcements = []

    # CALIBRATE: Find real selectors for forum posts
    post_elements = soup.select(".forum-post, [data-post-id]")

    for elem in post_elements:
        try:
            title_elem = elem.find(class_="post-title") or elem.find("a")
            title = title_elem.get_text(strip=True) if title_elem else ""
            url = title_elem.get("href", "") if title_elem and title_elem.name == "a" else ""

            author_elem = elem.find(class_="post-author")
            author = author_elem.get_text(strip=True) if author_elem else ""

            content_elem = elem.find(class_="post-content")
            content = content_elem.get_text(strip=True)[:200] if content_elem else ""

            date_elem = elem.find(class_="post-date")
            date_str = date_elem.get_text(strip=True) if date_elem else ""
            date, date_raw = _parse_date_to_iso(date_str)

            announcements.append(Announcement(
                course="",  # CALIBRATE: extract course name if present
                title=title,
                content_preview=content,
                author=author,
                date=date,
                date_raw=date_raw,
                url=url
            ))
        except Exception as e:
            logger.warning(f"Failed to parse announcement: {e}")

    logger.info(f"Parsed {len(announcements)} announcements")
    return announcements

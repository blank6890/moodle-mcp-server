import logging
from bs4 import BeautifulSoup
from app.models import CalendarEvent
from app.parsers.utils import parse_date_to_iso_date

logger = logging.getLogger(__name__)

def parse_calendar(html: str) -> list[CalendarEvent]:
    """Parse calendar page → list of CalendarEvent models.

    CALIBRATE: Update selectors from real /calendar/view.php?view=upcoming HTML.
    """
    soup = BeautifulSoup(html, "html.parser")
    events = []

    # CALIBRATE: Find real selectors for events
    event_elements = soup.select(".event, [data-event-id]")

    for elem in event_elements:
        try:
            title_elem = elem.find(class_="event-title") or elem.find("a")
            title = title_elem.get_text(strip=True) if title_elem else ""
            url = title_elem.get("href", "") if title_elem and title_elem.name == "a" else ""

            date_elem = elem.find(class_="event-date") or elem.find(class_="date")
            date_str = date_elem.get_text(strip=True) if date_elem else ""
            date, date_raw = parse_date_to_iso_date(date_str)

            event_type = "course_event"  # CALIBRATE: detect from content
            course = ""  # CALIBRATE: extract if present

            events.append(CalendarEvent(
                title=title,
                date=date,
                date_raw=date_raw,
                course=course,
                event_type=event_type,
                url=url
            ))
        except Exception as e:
            logger.warning(f"Failed to parse event element: {e}")

    logger.info(f"Parsed {len(events)} calendar events")
    return events

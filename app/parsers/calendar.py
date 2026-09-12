import logging
import html as html_lib
import re
from bs4 import BeautifulSoup
from app.models import CalendarEvent
from app.parsers.utils import parse_date_to_iso_date

logger = logging.getLogger(__name__)

def parse_calendar(html: str) -> list[CalendarEvent]:
    """Parse calendar page → list of CalendarEvent models."""
    soup = BeautifulSoup(html, "html.parser")
    events = []

    # Get event blocks in Moodle 4 calendar
    event_elements = soup.find_all('div', class_='event')

    for elem in event_elements:
        try:
            # Title from data attribute or fallback
            title = elem.get('data-event-title', '')
            if not title:
                title_elem = elem.find('h3', class_='name')
                title = title_elem.get_text(strip=True) if title_elem else "Unknown Event"
            title = html_lib.unescape(title)

            # Date
            date_elem = elem.find('span', class_='date')
            date_str = date_elem.get_text(strip=True) if date_elem else ""
            date, date_raw = parse_date_to_iso_date(date_str)

            # Course - look for the graduation-cap icon row
            course = ""
            cap_icon = elem.find('i', class_='fa-graduation-cap')
            if cap_icon:
                course_col = cap_icon.find_parent('div').find_next_sibling('div')
                if course_col:
                    course = course_col.get_text(strip=True)

            # Event Type
            event_type = elem.get('data-event-eventtype', 'course_event')

            # URL - usually in card-footer
            url = ""
            footer = elem.find('div', class_='card-footer')
            if footer:
                link = footer.find('a', class_='card-link')
                if link:
                    url = link.get('href', "")

            events.append(CalendarEvent(
                title=title,
                date=date,
                date_raw=date_raw or date_str,
                course=course,
                event_type=event_type,
                url=url
            ))
        except Exception as e:
            logger.warning(f"Failed to parse event element: {e}")

    logger.info(f"Parsed {len(events)} calendar events")
    return events

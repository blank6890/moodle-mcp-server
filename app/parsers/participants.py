import logging
from bs4 import BeautifulSoup
from app.models import Participant

logger = logging.getLogger(__name__)

def parse_participants(html: str) -> list[Participant]:
    """Parse participants page → list of Participant models.

    CALIBRATE: Update selectors from real course participants HTML.
    """
    soup = BeautifulSoup(html, "html.parser")
    participants = []

    # CALIBRATE: Find real selectors for participant rows
    row_elements = soup.select(".userlist table tbody tr, [data-user-id]")

    for row in row_elements:
        try:
            name_elem = row.find(class_="username") or row.find("a")
            name = name_elem.get_text(strip=True) if name_elem else ""
            profile_url = name_elem.get("href", "") if name_elem and name_elem.name == "a" else ""

            role_elem = row.find(class_="role") or row.select_one("td:nth-of-type(4)")
            role = role_elem.get_text(strip=True).lower() if role_elem else "student"

            if name:
                participants.append(Participant(
                    name=name,
                    role=role,
                    profile_url=profile_url
                ))
        except Exception as e:
            logger.warning(f"Failed to parse participant: {e}")

    logger.info(f"Parsed {len(participants)} participants")
    return participants

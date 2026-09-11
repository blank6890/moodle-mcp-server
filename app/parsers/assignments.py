import logging
from bs4 import BeautifulSoup
from app.models import Assignment
from app.parsers.utils import parse_date_to_iso

logger = logging.getLogger(__name__)

def parse_assignments(html: str) -> list[Assignment]:
    """Parse assignment lists → list of Assignment models.

    CALIBRATE: Update selectors from real /mod/assign/index.php or timeline HTML.
    """
    soup = BeautifulSoup(html, "html.parser")
    assignments = []

    # CALIBRATE: Find real selectors
    assignment_elements = soup.select(".assignment-item, [data-assignment-id]")

    for elem in assignment_elements:
        try:
            name = elem.find(class_="name") or elem.find("a")
            if not name:
                continue

            name_text = name.get_text(strip=True)
            url = name.get("href", "") if name.name == "a" else ""

            due_date_elem = elem.find(class_="due-date") or elem.find(class_="duedate")
            due_date_str = due_date_elem.get_text(strip=True) if due_date_elem else ""
            due_date, due_date_raw = parse_date_to_iso(due_date_str)

            status_elem = elem.find(class_="status")
            status = status_elem.get_text(strip=True) if status_elem else "unknown"

            assignments.append(Assignment(
                course="",  # Will be filled by orchestrator
                name=name_text,
                due_date=due_date,
                due_date_raw=due_date_raw,
                status=status,
                url=url
            ))
        except Exception as e:
            logger.warning(f"Failed to parse assignment element: {e}")

    logger.info(f"Parsed {len(assignments)} assignments")
    return assignments

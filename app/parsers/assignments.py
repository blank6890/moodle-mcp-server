import logging
import html as html_lib
import re
from bs4 import BeautifulSoup
from app.models import Assignment
from app.parsers.utils import parse_date_to_iso

logger = logging.getLogger(__name__)

def parse_assignments(html: str) -> list[Assignment]:
    """Parse assignment lists → list of Assignment models."""
    soup = BeautifulSoup(html, "html.parser")
    assignments = []

    # Select assignment rows from Moodle 4 assign index table
    assignment_links = soup.find_all('a', class_='activityname')

    for link in assignment_links:
        try:
            name_text = html_lib.unescape(link.get_text(strip=True))
            url = link.get("href", "")

            # The parent tr contains the due date and submission status
            row = link.find_parent('tr')
            if not row:
                continue

            cells = row.find_all('td')
            # Depending on Moodle configuration, cells could be:
            # [0] Name, [1] Due Date, [2] Status or similar
            if len(cells) >= 3:
                # Often the submission status is the last cell, and due date is the second to last.
                due_date_str = cells[-2].get_text(strip=True)
                status_raw = cells[-1].get_text(strip=True)
            elif len(cells) == 2:
                # Sometimes only 2 columns: Name, Due Date
                due_date_str = cells[-1].get_text(strip=True)
                status_raw = "unknown"
            else:
                due_date_str = ""
                status_raw = "unknown"

            due_date, due_date_raw = parse_date_to_iso(due_date_str)

            assignments.append(Assignment(
                course="",  # Orchestrator handles mapping or this is returned directly
                name=name_text,
                due_date=due_date,
                due_date_raw=due_date_raw or due_date_str,
                status=status_raw,
                url=url
            ))
        except Exception as e:
            logger.warning(f"Failed to parse assignment element: {e}")

    logger.info(f"Parsed {len(assignments)} assignments")
    return assignments

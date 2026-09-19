import logging
import html as html_lib
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

    # Moodle's assign index table shows a different set of optional
    # columns per course (Grade, Time remaining, Last modified, Comments),
    # so "due date" is not reliably the second-to-last column. Locate it
    # by reading the table header instead of guessing a fixed position.
    due_col_index = None
    status_col_index = None
    table = None
    if assignment_links:
        first_row = assignment_links[0].find_parent('tr')
        table = first_row.find_parent('table') if first_row else None
    if table is not None:
        header_cells = table.select("thead th") or table.select("tr:first-child th")
        for idx, th in enumerate(header_cells):
            header_text = th.get_text(strip=True).lower()
            if "due date" in header_text or header_text == "due":
                due_col_index = idx
            elif "submission" in header_text or "status" in header_text:
                status_col_index = idx

    for link in assignment_links:
        try:
            name_text = html_lib.unescape(link.get_text(strip=True))
            url = link.get("href", "")

            # The parent tr contains the due date and submission status
            row = link.find_parent('tr')
            if not row:
                continue

            cells = row.find_all('td')

            due_date_str = ""
            status_raw = "unknown"

            if due_col_index is not None and due_col_index < len(cells):
                due_date_str = cells[due_col_index].get_text(strip=True)
            elif len(cells) >= 3:
                # Fallback to the old heuristic if headers weren't found
                due_date_str = cells[-2].get_text(strip=True)
            elif len(cells) == 2:
                due_date_str = cells[-1].get_text(strip=True)

            if status_col_index is not None and status_col_index < len(cells):
                status_raw = cells[status_col_index].get_text(strip=True)
            elif len(cells) >= 3:
                status_raw = cells[-1].get_text(strip=True)

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

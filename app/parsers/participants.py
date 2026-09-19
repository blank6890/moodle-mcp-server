import logging
from bs4 import BeautifulSoup
from app.models import Participant

logger = logging.getLogger(__name__)

def parse_participants(html: str) -> list[Participant]:
    """Parse participants page → list of Participant models.

    Moodle's participants table (id="participants") pads its <tbody> with
    empty placeholder rows (class="emptyrow") up to whatever `perpage` was
    requested, and puts the name cell in a <th scope="row"> rather than a
    <td> — a plain `row.find_all('td')` silently drops that column, which
    shifts every later cell index by one. The optional columns shown (ID
    number, Email, Groups, Last access, ...) also vary by course, so
    "Roles" is not reliably at a fixed position either. We read the
    header row to find it, and read each row with find_all(['td', 'th'])
    so cell indices line up with the header regardless of which optional
    columns are present or whether the name cell is a th.
    """
    soup = BeautifulSoup(html, "html.parser")
    participants = []

    table = (
        soup.select_one("table#participants")
        or soup.select_one("table.participants")
        or soup.select_one(".userlist table")
    )
    if table is None:
        logger.warning("Participants table not found in HTML")
        return participants

    # Find which column index holds "Roles" by reading the header row.
    header_cells = table.select("thead th") or table.select("tr:first-child th")
    role_col_index = None
    for idx, th in enumerate(header_cells):
        if "role" in th.get_text(strip=True).lower():
            role_col_index = idx
            break

    body = table.select_one("tbody") or table
    row_elements = [
        row for row in body.select("tr")
        if "emptyrow" not in (row.get("class") or [])
    ]

    for row in row_elements:
        try:
            name_elem = row.find(class_="username") or row.find(
                "a", href=lambda h: h and ("user/view.php" in h or "user/profile.php" in h)
            )
            if name_elem is None:
                continue  # not a real participant row

            # Drop the avatar-initials span (e.g. "K.") so it doesn't get
            # glued onto the start of the name with no separator.
            initials = name_elem.find(class_="userinitials")
            if initials is not None:
                initials.extract()

            name = name_elem.get_text(strip=True)
            profile_url = (
                name_elem.get("href")
                if name_elem.name == "a"
                else None
            )

            # Use td AND th so the index lines up with the header row even
            # when the name cell is a <th> rather than a <td>.
            cells = row.find_all(["td", "th"])
            role_cell = None
            if role_col_index is not None and role_col_index < len(cells):
                role_cell = cells[role_col_index]
            if role_cell is None:
                role_cell = (
                    row.select_one('td[data-label*="Role" i]')
                    or row.find(class_="role")
                )

            role = "student"
            if role_cell is not None:
                role_text = role_cell.get_text(separator=", ", strip=True)
                if role_text:
                    role = role_text.lower()

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

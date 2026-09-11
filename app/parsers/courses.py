import logging
from bs4 import BeautifulSoup
from app.models import Course

logger = logging.getLogger(__name__)

def parse_courses(html: str) -> list[Course]:
    """Parse /my/courses.php → list of Course models.

    CALIBRATE: Find actual selectors after inspecting real HTML.
    """
    soup = BeautifulSoup(html, "html.parser")
    courses = []

    # CALIBRATE: Update with real selectors from courses page
    # Expected: course cards/list items with id, name, url
    course_elements = soup.select(".course-card, [data-course-id]")

    for elem in course_elements:
        try:
            course_id = elem.get("data-course-id") or elem.get("data-id")
            course_name = elem.get_text(strip=True)
            course_url = elem.find("a")

            if course_id and course_name and course_url:
                courses.append(Course(
                    id=str(course_id),
                    name=course_name,
                    url=course_url.get("href", "")
                ))
        except Exception as e:
            logger.warning(f"Failed to parse course element: {e}")

    logger.info(f"Parsed {len(courses)} courses")
    return courses

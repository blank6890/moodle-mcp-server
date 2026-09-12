import logging
import urllib.parse
import html as html_lib
from bs4 import BeautifulSoup
from app.models import Course

logger = logging.getLogger(__name__)

def parse_courses(html: str) -> list[Course]:
    """Parse /my/courses.php → list of Course models."""
    soup = BeautifulSoup(html, "html.parser")
    courses = []

    # Moodle 4.x dashboard course links
    course_links = soup.find_all('a', class_='coursename')

    for link in course_links:
        try:
            url = link.get("href", "")
            if not url:
                continue

            # Extract course ID from URL query parameters
            query = urllib.parse.urlparse(url).query
            params = urllib.parse.parse_qs(query)
            course_id = params.get('id', [None])[0]

            if not course_id:
                continue

            # Try to get the name from the multiline span, fallback to cleaning up the text
            name_span = link.find('span', class_='multiline')
            if name_span:
                # get text from the visible part or title attribute
                course_name = name_span.get('title')
                if not course_name:
                    course_name = name_span.get_text(strip=True)
            else:
                # fallback text extraction if structure differs
                course_name = link.get_text(strip=True)
                course_name = course_name.replace('Course is starred', '').replace('Course name', '').strip()

            courses.append(Course(
                id=str(course_id),
                name=html_lib.unescape(course_name),
                url=url
            ))
        except Exception as e:
            logger.warning(f"Failed to parse course element: {e}")

    logger.info(f"Parsed {len(courses)} courses")
    return courses

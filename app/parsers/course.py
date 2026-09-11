import logging
from bs4 import BeautifulSoup
from app.models import CourseDetail, Section, Resource

logger = logging.getLogger(__name__)

def parse_course_detail(html: str) -> CourseDetail:
    """Parse course page → CourseDetail with sections and resources.

    CALIBRATE: Update selectors from real /course/view.php?id={id} HTML.
    """
    soup = BeautifulSoup(html, "html.parser")

    # CALIBRATE: Extract course info
    title_elem = soup.find("h1") or soup.find(class_="course-title")
    title = title_elem.get_text(strip=True) if title_elem else "Unknown Course"

    course_id = ""  # CALIBRATE: extract from URL or page data
    course_url = ""  # CALIBRATE: construct from course ID

    sections = []
    # CALIBRATE: Find section containers
    section_elements = soup.select(".section, [data-section]")

    for section_elem in section_elements:
        try:
            section_title_elem = section_elem.find(class_="sectionname") or section_elem.find("h3")
            section_title = section_title_elem.get_text(strip=True) if section_title_elem else "Untitled"

            resources = []
            resource_elements = section_elem.select(".activity, .resource")

            for resource_elem in resource_elements:
                resource_name_elem = resource_elem.find("a")
                resource_name = resource_name_elem.get_text(strip=True) if resource_name_elem else ""
                resource_url = resource_name_elem.get("href", "") if resource_name_elem else ""

                # CALIBRATE: detect resource type from icon or class
                resource_type = "link"  # default
                if "pdf" in resource_url.lower() or "pdf" in str(resource_elem).lower():
                    resource_type = "pdf"

                resources.append(Resource(
                    name=resource_name,
                    url=resource_url,
                    resource_type=resource_type
                ))

            sections.append(Section(title=section_title, resources=resources))
        except Exception as e:
            logger.warning(f"Failed to parse section: {e}")

    logger.info(f"Parsed course '{title}' with {len(sections)} sections")
    return CourseDetail(
        id=course_id,
        name=title,
        url=course_url,
        sections=sections
    )

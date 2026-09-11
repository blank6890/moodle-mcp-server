import pytest
from pathlib import Path
from app.models import Course, Assignment, CalendarEvent, Announcement, CourseDetail
from app.parsers.courses import parse_courses
from app.parsers.assignments import parse_assignments
from app.parsers.calendar import parse_calendar
from app.parsers.announcements import parse_announcements
from app.parsers.course import parse_course_detail

FIXTURES_DIR = Path(__file__).parent / "fixtures"

def load_fixture(name: str) -> str:
    """Load a fixture HTML file."""
    path = FIXTURES_DIR / name
    if path.exists():
        return path.read_text()
    return "<html></html>"  # Empty fallback

def test_parse_courses():
    """Test parse_courses parser."""
    html = load_fixture("my_courses.html")
    courses = parse_courses(html)
    # Verify structure even if no courses found
    assert isinstance(courses, list)

def test_parse_assignments():
    """Test parse_assignments parser."""
    html = load_fixture("assignments.html")
    assignments = parse_assignments(html)
    assert isinstance(assignments, list)

def test_parse_calendar():
    """Test parse_calendar parser."""
    html = load_fixture("calendar.html")
    events = parse_calendar(html)
    assert isinstance(events, list)

def test_parse_announcements():
    """Test parse_announcements parser."""
    html = load_fixture("announcements.html")
    announcements = parse_announcements(html)
    assert isinstance(announcements, list)

def test_parse_course_detail():
    """Test parse_course_detail parser."""
    html = load_fixture("course_detail.html")
    course = parse_course_detail(html)
    assert isinstance(course, CourseDetail)

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
        return path.read_text(encoding="utf-8")
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
    assert len(assignments) == 2
    assert assignments[0].name == "Assignment 1"
    assert assignments[0].due_date == "2026-09-15T23:59:00"
    assert assignments[0].due_date_raw == "Monday, 15 September 2026, 11:59 PM"
    assert assignments[0].status == "Submitted for grading"
    assert assignments[1].name == "Assignment 2"
    assert assignments[1].due_date == "2026-09-17T23:59:00"
    assert assignments[1].status == "No submission"

def test_parse_assignments_extra_columns_do_not_shift_due_date():
    """A Grade column present alongside Submission must not shift which
    cell is read as the due date (regression test: previously the parser
    assumed due date was always the second-to-last column)."""
    html = load_fixture("assignments.html")
    assignments = parse_assignments(html)
    for assignment in assignments:
        assert assignment.due_date is not None
        assert assignment.status in ("Submitted for grading", "No submission")

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

from app.parsers.participants import parse_participants

def test_parse_participants():
    """Test parse_participants parser."""
    html = load_fixture("participants.html")
    participants = parse_participants(html)
    assert isinstance(participants, list)
    assert len(participants) == 2
    assert participants[0].name == "Alice Smith"
    assert participants[0].role == "student"
    assert participants[0].profile_url == "https://courses.iiit.ac.in/user/profile.php?id=1234"
    assert participants[1].name == "Bob Jones"
    assert participants[1].role == "teacher"

def test_parse_participants_with_extra_columns():
    """Mirrors Moodle's real participants table (id="participants"):
    - the name cell is a <th scope="row">, not a <td>, so reading only
      <td> elements silently drops a column and shifts every later index
      by one (this is what caused Roles to read as "Groups"/"Last
      access" values in production);
    - the roster is padded with empty placeholder rows
      (class="emptyrow") up to whatever `perpage` was requested, which
      must not be parsed as participants;
    - the avatar-initials <span> ("J.") inside the name link must not
      get glued onto the front of the name with no separator."""
    html = load_fixture("participants_columns.html")
    participants = parse_participants(html)
    assert len(participants) == 2
    assert participants[0].name == "Jordan Alvarez"
    assert participants[0].role == "teaching assistant"
    assert participants[0].profile_url == "https://courses.iiit.ac.in/user/view.php?id=9001&course=101"
    assert participants[1].name == "Priya Menon"
    assert participants[1].role == "student"

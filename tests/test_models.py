from app.models import Course, Assignment, CalendarEvent, Announcement

def test_course_model():
    """Test Course model."""
    course = Course(id="5817", name="Algorithm Analysis & Design", url="https://courses.iiit.ac.in/course/view.php?id=5817")
    assert course.id == "5817"
    assert course.name == "Algorithm Analysis & Design"

def test_assignment_model():
    """Test Assignment model with optional due_date."""
    assign = Assignment(
        course="Algorithm Analysis & Design",
        name="Mini project 1",
        due_date="2026-09-13T23:59:00",
        due_date_raw="13 September 2026, 11:59 PM",
        status="not_submitted",
        url="https://courses.iiit.ac.in/mod/assign/view.php?id=70167"
    )
    assert assign.course == "Algorithm Analysis & Design"
    assert assign.due_date == "2026-09-13T23:59:00"

def test_calendar_event_model():
    """Test CalendarEvent model."""
    event = CalendarEvent(
        title="Mini project 1 (end submission) is due",
        date="2026-09-13",
        date_raw="13 September 2026",
        course="Operating Systems and Networks",
        event_type="assignment_due",
        url="https://courses.iiit.ac.in/mod/assign/view.php?id=70167"
    )
    assert event.event_type == "assignment_due"

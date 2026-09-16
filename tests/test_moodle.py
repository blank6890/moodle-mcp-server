import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.moodle import MoodleService
from app.config import Config
from app.models import Course, Assignment, CalendarEvent, CourseDetail, Announcement, Participant

@pytest.mark.asyncio
async def test_moodle_service_caching():
    """Test that MoodleService caches results."""
    config = Config()
    config.CACHE_TTL = 60

    mock_browser = AsyncMock()
    mock_http = AsyncMock()
    service = MoodleService(mock_browser, config, http_client=mock_http)

    mock_http.get = AsyncMock(return_value=("https://courses.iiit.ac.in/my/courses.php", "<a class='coursename'>Test</a>"))

    with patch("app.parsers.courses.parse_courses") as mock_parse:
        mock_parse.return_value = [Course(id="1", name="Test Course", url="https://test.com")]

        # First call: hits cache miss
        courses1 = await service.get_courses()
        assert len(courses1) == 1

        # Second call: hits cache hit (no new fetch)
        courses2 = await service.get_courses()
        assert len(courses2) == 1
        assert mock_http.get.call_count == 1

@pytest.mark.asyncio
async def test_moodle_service_uses_http_first():
    """Test that MoodleService prefers fast HTTP client over browser."""
    config = Config()
    config.ENABLE_HTTP_FIRST = True

    mock_browser = AsyncMock()
    mock_http = AsyncMock()

    courses_html = """
    <a class="coursename" href="https://courses.iiit.ac.in/course/view.php?id=101">
        <span class="multiline" title="Algorithms">Algorithms</span>
    </a>
    """
    mock_http.get.return_value = ("https://courses.iiit.ac.in/my/courses.php", courses_html)

    service = MoodleService(browser=mock_browser, config=config, http_client=mock_http)
    courses = await service.get_courses()

    assert len(courses) == 1
    assert courses[0].name == "Algorithms"
    mock_http.get.assert_called_once()
    mock_browser.navigate.assert_not_called()

@pytest.mark.asyncio
async def test_moodle_service_get_assignments():
    """Test get_assignments with HTTP transport and caching."""
    config = Config()
    mock_browser = AsyncMock()
    mock_http = AsyncMock()
    mock_http.get.return_value = ("https://courses.iiit.ac.in/my/", "<html>Assignments</html>")

    service = MoodleService(browser=mock_browser, config=config, http_client=mock_http)
    with patch("app.parsers.assignments.parse_assignments") as mock_parse:
        mock_parse.return_value = [Assignment(course="CS101", name="PA1", due_date=None, due_date_raw="20 Sep 2026", status="not_submitted", url="https://test.com")]
        res1 = await service.get_assignments()
        assert len(res1) == 1
        # cached call
        res2 = await service.get_assignments()
        assert len(res2) == 1
        assert mock_http.get.call_count == 1

@pytest.mark.asyncio
async def test_moodle_service_get_calendar():
    """Test get_calendar with HTTP transport and caching."""
    config = Config()
    mock_browser = AsyncMock()
    mock_http = AsyncMock()
    mock_http.get.return_value = ("https://courses.iiit.ac.in/calendar/view.php?view=upcoming", "<html>Calendar</html>")

    service = MoodleService(browser=mock_browser, config=config, http_client=mock_http)
    with patch("app.parsers.calendar.parse_calendar") as mock_parse:
        mock_parse.return_value = [CalendarEvent(title="Quiz", date="2026-09-20", date_raw="20 Sep", course="CS101", event_type="due", url="https://test.com")]
        res1 = await service.get_calendar(days_ahead=30)
        assert len(res1) == 1
        res2 = await service.get_calendar(days_ahead=30)
        assert len(res2) == 1
        assert mock_http.get.call_count == 1

@pytest.mark.asyncio
async def test_moodle_service_get_course_detail():
    """Test get_course_detail with HTTP transport."""
    config = Config()
    mock_browser = AsyncMock()
    mock_http = AsyncMock()
    mock_http.get.return_value = ("https://courses.iiit.ac.in/course/view.php?id=101", "<html>Course Detail</html>")

    service = MoodleService(browser=mock_browser, config=config, http_client=mock_http)
    with patch("app.parsers.course.parse_course_detail") as mock_parse:
        mock_parse.return_value = CourseDetail(id="101", name="Algorithms", url="https://test.com", sections=[])
        detail = await service.get_course_detail("101")
        assert detail.id == "101"
        assert mock_http.get.call_count == 1

@pytest.mark.asyncio
async def test_moodle_service_get_participants():
    """Test get_participants with HTTP transport."""
    config = Config()
    mock_browser = AsyncMock()
    mock_http = AsyncMock()
    mock_http.get.return_value = ("https://courses.iiit.ac.in/user/index.php?id=101", "<html>Users</html>")

    service = MoodleService(browser=mock_browser, config=config, http_client=mock_http)
    with patch("app.parsers.participants.parse_participants") as mock_parse:
        mock_parse.return_value = [Participant(name="Alice", role="Student", email=None, profile_url="https://test.com")]
        users = await service.get_participants("101")
        assert len(users) == 1
        assert users[0].name == "Alice"
        assert mock_http.get.call_count == 1

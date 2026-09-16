import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import app.main as main_module
from app.models import (
    SessionStatus, Course, Assignment, CalendarEvent, CourseDetail,
    Section, Resource, Announcement, Participant
)
from app.browser import SessionExpiredError
from mcp.types import ToolAnnotations

@pytest.fixture(autouse=True)
def reset_globals():
    """Reset module-level globals before each test."""
    main_module._config = None
    main_module._browser = None
    main_module._http_client = None
    main_module._moodle = None
    yield
    main_module._config = None
    main_module._browser = None
    main_module._http_client = None
    main_module._moodle = None

@pytest.mark.asyncio
async def test_init_globals_lazy_initialization():
    """Test that _init_globals initializes http_client and browser without starting Chromium."""
    with patch("app.main.BrowserManager") as mock_browser_cls, \
         patch("app.main.HttpClientManager") as mock_http_cls, \
         patch("app.main.MoodleService") as mock_moodle_cls:

        mock_browser_instance = MagicMock()
        mock_browser_cls.return_value = mock_browser_instance

        await main_module._init_globals()

        assert main_module._config is not None
        assert main_module._http_client is not None
        assert main_module._browser is not None
        assert main_module._moodle is not None

        # Ensure _init_browser is NOT called during lazy init
        mock_browser_instance._init_browser.assert_not_called()

def test_all_tools_have_read_only_annotations():
    """Test that all 9 tools declare explicit boolean annotations."""
    registered_tools = {}
    registered_annotations = {}

    class MockMCPServer:
        def __init__(self, name):
            self.name = name

        def tool(self, annotations=None, **kwargs):
            def decorator(fn):
                registered_tools[fn.__name__] = fn
                registered_annotations[fn.__name__] = annotations
                return fn
            return decorator

    with patch("app.main.MCPServer", MockMCPServer):
        server = main_module.create_mcp_server()
        assert server.name == "moodle-agent"

        expected_tools = [
            "check_health",
            "check_session",
            "get_courses",
            "get_assignments",
            "get_calendar",
            "get_course",
            "get_course_materials",
            "get_announcements",
            "get_participants",
        ]

        for tool_name in expected_tools:
            assert tool_name in registered_tools, f"Missing tool: {tool_name}"
            ann = registered_annotations[tool_name]
            assert isinstance(ann, ToolAnnotations), f"{tool_name} missing ToolAnnotations"
            assert ann.readOnlyHint is True, f"{tool_name} readOnlyHint must be True"
            assert ann.destructiveHint is False, f"{tool_name} destructiveHint must be False"
            assert ann.idempotentHint is True, f"{tool_name} idempotentHint must be True"
            assert ann.openWorldHint is True, f"{tool_name} openWorldHint must be True"

def _get_server_tools():
    registered_tools = {}

    class MockMCPServer:
        def __init__(self, name):
            self.name = name

        def tool(self, annotations=None, **kwargs):
            def decorator(fn):
                registered_tools[fn.__name__] = fn
                return fn
            return decorator

    with patch("app.main.MCPServer", MockMCPServer):
        main_module.create_mcp_server()
    return registered_tools

@pytest.mark.asyncio
async def test_check_health_tool():
    """Test check_health tool execution for healthy and expired states."""
    tools = _get_server_tools()
    check_health = tools["check_health"]

    # Healthy
    with patch("app.main._init_globals", new=AsyncMock()), \
         patch("app.main.check_auth_session", new=AsyncMock(return_value=SessionStatus(authenticated=True, detail="Active"))):
        res = await check_health()
        assert res["status"] == "healthy"
        assert res["authenticated"] is True
        assert res["detail"] == "Active"

    # Expired
    with patch("app.main._init_globals", new=AsyncMock()), \
         patch("app.main.check_auth_session", side_effect=SessionExpiredError("Expired")):
        res = await check_health()
        assert res["status"] == "healthy"
        assert res["authenticated"] is False
        assert res["detail"] == "Session expired"

    # Error
    with patch("app.main._init_globals", new=AsyncMock()), \
         patch("app.main.check_auth_session", side_effect=RuntimeError("Fatal error")):
        res = await check_health()
        assert res["status"] == "error"
        assert res["authenticated"] is False
        assert "Fatal error" in res["detail"]

@pytest.mark.asyncio
async def test_check_session_tool():
    """Test check_session tool execution for valid, expired, and error states."""
    tools = _get_server_tools()
    check_session = tools["check_session"]

    # Active session
    with patch("app.main._init_globals", new=AsyncMock()), \
         patch("app.main.check_auth_session", new=AsyncMock(return_value=SessionStatus(authenticated=True, detail="Session active"))):
        res = await check_session()
        assert res["authenticated"] is True
        assert res["detail"] == "Session active"

    # Expired session
    with patch("app.main._init_globals", new=AsyncMock()), \
         patch("app.main.check_auth_session", side_effect=SessionExpiredError("Expired")):
        res = await check_session()
        assert res["authenticated"] is False
        assert "Session expired" in res["detail"]

    # Exception
    with patch("app.main._init_globals", new=AsyncMock()), \
         patch("app.main.check_auth_session", side_effect=ConnectionError("Failed to connect")):
        res = await check_session()
        assert res["authenticated"] is False
        assert "Failed to connect" in res["detail"]

@pytest.mark.asyncio
async def test_get_courses_tool():
    """Test get_courses tool execution and session expiration handling."""
    tools = _get_server_tools()
    get_courses = tools["get_courses"]

    mock_moodle = AsyncMock()
    mock_moodle.get_courses.return_value = [
        Course(id="101", name="Algorithms", url="https://courses.iiit.ac.in/course/view.php?id=101")
    ]
    with patch("app.main._init_globals", new=AsyncMock()), \
         patch("app.main._moodle", mock_moodle):
        res = await get_courses()
        assert len(res) == 1
        assert res[0]["id"] == "101"
        assert res[0]["name"] == "Algorithms"

    mock_moodle.get_courses.side_effect = SessionExpiredError("Session dead")
    with patch("app.main._init_globals", new=AsyncMock()), \
         patch("app.main._moodle", mock_moodle):
        with pytest.raises(ValueError, match="Session expired"):
            await get_courses()

@pytest.mark.asyncio
async def test_get_assignments_tool():
    """Test get_assignments tool execution with and without filter."""
    tools = _get_server_tools()
    get_assignments = tools["get_assignments"]

    mock_moodle = AsyncMock()
    mock_moodle.get_assignments.return_value = [
        Assignment(course="Algorithms", name="PA1", due_date=None, due_date_raw="2026-09-20", status="submitted", url="https://courses.iiit.ac.in/mod/assign/view.php?id=1")
    ]
    with patch("app.main._init_globals", new=AsyncMock()), \
         patch("app.main._moodle", mock_moodle):
        res = await get_assignments(course_id="101")
        assert len(res) == 1
        assert res[0]["name"] == "PA1"
        mock_moodle.get_assignments.assert_called_with("101")

    mock_moodle.get_assignments.side_effect = SessionExpiredError("Session dead")
    with patch("app.main._init_globals", new=AsyncMock()), \
         patch("app.main._moodle", mock_moodle):
        with pytest.raises(ValueError, match="Session expired"):
            await get_assignments()

@pytest.mark.asyncio
async def test_get_calendar_tool():
    """Test get_calendar tool execution."""
    tools = _get_server_tools()
    get_calendar = tools["get_calendar"]

    mock_moodle = AsyncMock()
    mock_moodle.get_calendar.return_value = [
        CalendarEvent(title="Quiz 1", date="2026-09-20", date_raw="20 September 2026", course="Algorithms", event_type="due", url="https://test.com")
    ]
    with patch("app.main._init_globals", new=AsyncMock()), \
         patch("app.main._moodle", mock_moodle):
        res = await get_calendar(days_ahead=14)
        assert len(res) == 1
        assert res[0]["title"] == "Quiz 1"
        mock_moodle.get_calendar.assert_called_with(14)

    mock_moodle.get_calendar.side_effect = SessionExpiredError("Session dead")
    with patch("app.main._init_globals", new=AsyncMock()), \
         patch("app.main._moodle", mock_moodle):
        with pytest.raises(ValueError, match="Session expired"):
            await get_calendar()

@pytest.mark.asyncio
async def test_get_course_tool():
    """Test get_course tool execution."""
    tools = _get_server_tools()
    get_course = tools["get_course"]

    detail = CourseDetail(
        id="101",
        name="Algorithms",
        url="https://courses.iiit.ac.in/course/view.php?id=101",
        sections=[
            Section(
                title="Week 1",
                resources=[Resource(name="Lecture 1", resource_type="pdf", url="https://test.com/l1.pdf")]
            )
        ]
    )
    mock_moodle = AsyncMock()
    mock_moodle.get_course_detail.return_value = detail
    with patch("app.main._init_globals", new=AsyncMock()), \
         patch("app.main._moodle", mock_moodle):
        res = await get_course("101")
        assert res["id"] == "101"
        assert len(res["sections"]) == 1

    mock_moodle.get_course_detail.side_effect = SessionExpiredError("Session dead")
    with patch("app.main._init_globals", new=AsyncMock()), \
         patch("app.main._moodle", mock_moodle):
        with pytest.raises(ValueError, match="Session expired"):
            await get_course("101")

@pytest.mark.asyncio
async def test_get_course_materials_tool():
    """Test get_course_materials tool execution."""
    tools = _get_server_tools()
    get_course_materials = tools["get_course_materials"]

    detail = CourseDetail(
        id="101",
        name="Algorithms",
        url="https://courses.iiit.ac.in/course/view.php?id=101",
        sections=[
            Section(
                title="Week 1",
                resources=[Resource(name="Lecture 1", resource_type="pdf", url="https://test.com/l1.pdf")]
            )
        ]
    )
    mock_moodle = AsyncMock()
    mock_moodle.get_course_detail.return_value = detail
    with patch("app.main._init_globals", new=AsyncMock()), \
         patch("app.main._moodle", mock_moodle):
        res = await get_course_materials("101")
        assert len(res) == 1
        assert res[0]["title"] == "Week 1"
        assert res[0]["resources"][0]["name"] == "Lecture 1"

    mock_moodle.get_course_detail.side_effect = SessionExpiredError("Session dead")
    with patch("app.main._init_globals", new=AsyncMock()), \
         patch("app.main._moodle", mock_moodle):
        with pytest.raises(ValueError, match="Session expired"):
            await get_course_materials("101")

@pytest.mark.asyncio
async def test_get_announcements_tool():
    """Test get_announcements tool execution."""
    tools = _get_server_tools()
    get_announcements = tools["get_announcements"]

    mock_moodle = AsyncMock()
    mock_moodle.get_announcements.return_value = [
        Announcement(course="Algorithms", title="Welcome", date="2026-09-01", date_raw="1 Sep 2026", author="Prof", content_preview="Hello", url="https://test.com")
    ]
    with patch("app.main._init_globals", new=AsyncMock()), \
         patch("app.main._moodle", mock_moodle):
        res = await get_announcements(course_id="101", limit=10)
        assert len(res) == 1
        assert res[0]["title"] == "Welcome"

    mock_moodle.get_announcements.side_effect = SessionExpiredError("Session dead")
    with patch("app.main._init_globals", new=AsyncMock()), \
         patch("app.main._moodle", mock_moodle):
        with pytest.raises(ValueError, match="Session expired"):
            await get_announcements()

@pytest.mark.asyncio
async def test_get_participants_tool():
    """Test get_participants tool execution."""
    tools = _get_server_tools()
    get_participants = tools["get_participants"]

    mock_moodle = AsyncMock()
    mock_moodle.get_participants.return_value = [
        Participant(name="John Doe", role="student", profile_url="https://test.com")
    ]
    with patch("app.main._init_globals", new=AsyncMock()), \
         patch("app.main._moodle", mock_moodle):
        res = await get_participants("101")
        assert len(res) == 1
        assert res[0]["name"] == "John Doe"

    mock_moodle.get_participants.side_effect = SessionExpiredError("Session dead")
    with patch("app.main._init_globals", new=AsyncMock()), \
         patch("app.main._moodle", mock_moodle):
        with pytest.raises(ValueError, match="Session expired"):
            await get_participants("101")

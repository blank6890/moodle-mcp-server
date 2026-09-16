import pytest
from unittest.mock import AsyncMock
from app.auth import check_session
from app.browser import SessionExpiredError
from app.models import SessionStatus

@pytest.mark.asyncio
async def test_check_session_http_fast_path():
    """Test check_session uses fast HTTP client."""
    mock_http = AsyncMock()
    mock_http.get.return_value = ("https://courses.iiit.ac.in/my/", "<html><body>Dashboard Moodle</body></html>")

    status = await check_session(http_client=mock_http)
    assert status.authenticated is True
    assert "Authenticated" in status.detail
    mock_http.get.assert_called_once()

@pytest.mark.asyncio
async def test_check_session_browser_fallback():
    """Test check_session falls back to browser if browser is provided."""
    mock_browser = AsyncMock()
    mock_browser.navigate.return_value = ("https://courses.iiit.ac.in/my/", "<html>Dashboard</html>")

    status = await check_session(browser=mock_browser)
    assert status.authenticated is True
    assert "authenticated" in status.detail.lower()

@pytest.mark.asyncio
async def test_check_session_expired():
    """Test check_session raises SessionExpiredError on CAS redirect."""
    mock_http = AsyncMock()
    mock_http.get.side_effect = SessionExpiredError("Redirected to CAS")

    with pytest.raises(SessionExpiredError):
        await check_session(http_client=mock_http)

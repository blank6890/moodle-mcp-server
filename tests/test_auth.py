# tests/test_auth.py
import pytest
from unittest.mock import AsyncMock
from app.auth import check_session
from app.browser import SessionExpiredError
from app.models import SessionStatus

@pytest.mark.asyncio
async def test_check_session_authenticated():
    """Test check_session returns authenticated=True when on Moodle."""
    mock_browser = AsyncMock()
    mock_browser.navigate = AsyncMock(return_value=("https://courses.iiit.ac.in/my/", "<html>Dashboard</html>"))

    status = await check_session(mock_browser)
    assert status.authenticated is True
    assert "authenticated" in status.detail.lower()

@pytest.mark.asyncio
async def test_check_session_expired():
    """Test check_session raises SessionExpiredError on CAS redirect."""
    mock_browser = AsyncMock()
    mock_browser.navigate = AsyncMock(side_effect=SessionExpiredError("Redirected to CAS"))

    with pytest.raises(SessionExpiredError):
        await check_session(mock_browser)

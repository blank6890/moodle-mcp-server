# tests/test_browser.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.browser import BrowserManager
from app.config import Config

@pytest.mark.asyncio
async def test_browser_manager_initialization():
    """Test BrowserManager context manager."""
    config = Config()

    with patch("app.browser.async_playwright") as mock_playwright:
        # Mock the playwright chain
        mock_context = AsyncMock()
        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_playwright_instance = MagicMock()
        mock_playwright_instance.chromium = AsyncMock()
        mock_playwright_instance.chromium.launch_persistent_context = AsyncMock(return_value=mock_context)

        manager = BrowserManager(config)
        # Just verify the manager can be created
        assert manager.config == config

@pytest.mark.asyncio
async def test_navigate_returns_url_and_html():
    """Test that navigate returns final URL and HTML."""
    config = Config()
    manager = BrowserManager(config)

    # Mock internals
    manager._context = AsyncMock()
    manager._throttle_lock = AsyncMock()
    manager._initialized = True

    mock_page = AsyncMock()
    mock_page.url = "https://courses.iiit.ac.in/my/"
    mock_page.content = AsyncMock(return_value="<html>test</html>")
    mock_page.goto = AsyncMock()

    manager._context.new_page = AsyncMock(return_value=mock_page)

    url, html = await manager.navigate("https://courses.iiit.ac.in/my/")
    assert url == "https://courses.iiit.ac.in/my/"
    assert html == "<html>test</html>"

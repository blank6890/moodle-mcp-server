import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.config import Config
from app.browser import BrowserManager

@pytest.mark.asyncio
async def test_browser_manager_initialization():
    """Test BrowserManager creation."""
    config = Config()
    manager = BrowserManager(config)
    assert manager.config == config
    assert manager.BLOCKED_RESOURCE_TYPES == {"image", "media", "font", "stylesheet"}

@pytest.mark.asyncio
async def test_browser_page_reuse_and_route_blocking():
    """Test that navigate reuses persistent page tab and returns url and content."""
    config = Config()
    config.CHROMIUM_PATH = None
    manager = BrowserManager(config)

    mock_page = AsyncMock()
    mock_page.url = "https://courses.iiit.ac.in/my/"
    mock_page.content.return_value = "<html><body>Dashboard</body></html>"
    mock_page.goto = AsyncMock()
    mock_page.is_closed = MagicMock(return_value=False)

    mock_context = AsyncMock()
    mock_context.new_page.return_value = mock_page
    mock_context.route = AsyncMock()

    manager._context = mock_context
    manager._page = mock_page
    manager._initialized = True

    url, html = await manager.navigate("https://courses.iiit.ac.in/my/")
    assert url == "https://courses.iiit.ac.in/my/"
    assert "Dashboard" in html
    mock_page.goto.assert_called_once_with("https://courses.iiit.ac.in/my/", wait_until="domcontentloaded", timeout=15000)

@pytest.mark.asyncio
async def test_handle_route_blocks_assets():
    """Test route handler blocks images/fonts/media/stylesheets."""
    config = Config()
    manager = BrowserManager(config)

    # Test blocked resource
    mock_route = AsyncMock()
    mock_route.request.resource_type = "image"
    await manager._handle_route(mock_route)
    mock_route.abort.assert_called_once()
    mock_route.continue_.assert_not_called()

    # Test allowed resource
    mock_route_doc = AsyncMock()
    mock_route_doc.request.resource_type = "document"
    await manager._handle_route(mock_route_doc)
    mock_route_doc.continue_.assert_called_once()

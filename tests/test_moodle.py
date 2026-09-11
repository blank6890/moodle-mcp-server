import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.moodle import MoodleService
from app.config import Config
from app.models import Course

@pytest.mark.asyncio
async def test_moodle_service_caching():
    """Test that MoodleService caches results."""
    config = Config()
    config.CACHE_TTL = 60
    
    mock_browser = AsyncMock()
    service = MoodleService(mock_browser, config)
    
    mock_browser.navigate = AsyncMock(return_value=("https://courses.iiit.ac.in/my/courses.php", "<html></html>"))
    
    with patch("app.parsers.courses.parse_courses") as mock_parse:
        mock_parse.return_value = [Course(id="1", name="Test Course", url="https://test.com")]
        
        # First call: hits cache miss
        courses1 = await service.get_courses()
        assert len(courses1) == 1
        
        # Second call: hits cache hit (no new navigate call)
        courses2 = await service.get_courses()
        assert len(courses2) == 1
        assert mock_browser.navigate.call_count == 1  # Only called once

import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from app.config import Config
from app.browser import SessionExpiredError
from app.http_client import HttpClientManager

@pytest.fixture
def mock_session_dir(tmp_path):
    state_file = tmp_path / "state.json"
    state_data = {
        "cookies": [
            {
                "name": "MoodleSession",
                "value": "mock_session_token_123",
                "domain": "courses.iiit.ac.in",
                "path": "/"
            },
            {
                "name": "MOODLEID1_",
                "value": "mock_moodle_id_456",
                "domain": "courses.iiit.ac.in",
                "path": "/"
            }
        ]
    }
    state_file.write_text(json.dumps(state_data))
    return tmp_path

@pytest.mark.asyncio
async def test_extract_cookies_from_state(mock_session_dir):
    config = Config()
    config.SESSION_DIR = mock_session_dir
    client = HttpClientManager(config)
    cookies = client._load_cookies()
    assert cookies["MoodleSession"] == "mock_session_token_123"
    assert cookies["MOODLEID1_"] == "mock_moodle_id_456"

@pytest.mark.asyncio
async def test_get_detects_session_expiry(mock_session_dir):
    config = Config()
    config.SESSION_DIR = mock_session_dir
    client = HttpClientManager(config)

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock()
        mock_response.url = "https://login.iiit.ac.in/cas/login?service=https://courses.iiit.ac.in"
        mock_response.status_code = 200
        mock_response.text = "CAS Login Page"
        mock_get.return_value = mock_response

        with pytest.raises(SessionExpiredError):
            await client.get("https://courses.iiit.ac.in/my/")

@pytest.mark.asyncio
async def test_get_successful_html(mock_session_dir):
    config = Config()
    config.SESSION_DIR = mock_session_dir
    client = HttpClientManager(config)

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock()
        mock_response.url = "https://courses.iiit.ac.in/my/courses.php"
        mock_response.status_code = 200
        mock_response.text = "<html><body><a class='coursename'>Test Course</a></body></html>"
        mock_get.return_value = mock_response

        final_url, html = await client.get("https://courses.iiit.ac.in/my/courses.php")
        assert "Test Course" in html
        assert final_url == "https://courses.iiit.ac.in/my/courses.php"

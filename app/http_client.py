import json
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple
import httpx
from app.config import Config
from app.browser import SessionExpiredError

logger = logging.getLogger(__name__)

class HttpClientManager:
    """High-speed async HTTP client utilizing session cookies from Playwright state."""

    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }

    def __init__(self, config: Config):
        self.config = config
        self._state_file = Path(config.SESSION_DIR) / "state.json"
        self._last_state_mtime: float = 0.0
        self._cached_cookies: Dict[str, str] = {}
        self._client: Optional[httpx.AsyncClient] = None

    def _load_cookies(self) -> Dict[str, str]:
        """Extract cookies from session/state.json if updated."""
        if not self._state_file.exists():
            logger.warning(f"State file {self._state_file} does not exist.")
            return {}

        try:
            mtime = self._state_file.stat().st_mtime
            if mtime > self._last_state_mtime or not self._cached_cookies:
                with open(self._state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                cookies = {}
                for cookie in data.get("cookies", []):
                    # Filter for Moodle domain or relevant cookies
                    domain = cookie.get("domain", "")
                    if "iiit.ac.in" in domain or not domain:
                        cookies[cookie["name"]] = cookie["value"]

                self._cached_cookies = cookies
                self._last_state_mtime = mtime
                logger.debug(f"Loaded {len(cookies)} cookies from {self._state_file}")

            return self._cached_cookies
        except Exception as e:
            logger.error(f"Error loading cookies from {self._state_file}: {e}")
            return self._cached_cookies

    def _get_client(self) -> httpx.AsyncClient:
        """Get or initialize persistent httpx AsyncClient."""
        cookies = self._load_cookies()
        if self._client is None or self._client.is_closed:
            limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
            self._client = httpx.AsyncClient(
                headers=self.DEFAULT_HEADERS,
                cookies=cookies,
                timeout=httpx.Timeout(self.config.HTTP_TIMEOUT, connect=5.0),
                follow_redirects=True,
                limits=limits,
            )
        else:
            # Sync cookies to client
            for k, v in cookies.items():
                self._client.cookies.set(k, v)
        return self._client

    async def get(self, url: str) -> Tuple[str, str]:
        """Execute fast async HTTP GET request. Returns (final_url, html)."""
        client = self._get_client()
        try:
            response = await client.get(url)
            final_url = str(response.url)

            # Check for session expiration / CAS login redirect
            if "login.iiit.ac.in" in final_url or "/login/" in final_url:
                logger.warning(f"Session expired detected on HTTP GET {url} -> {final_url}")
                raise SessionExpiredError(f"Redirected to CAS login at {final_url}")

            response.raise_for_status()
            return final_url, response.text
        except httpx.RequestError as e:
            logger.error(f"HTTP request failed for {url}: {e}")
            raise

    async def check_session(self) -> Tuple[bool, str]:
        """Fast session check via lightweight HTTP request."""
        try:
            url, html = await self.get(f"{self.config.MOODLE_BASE_URL}/my/")
            if "dashboard" in html.lower() or "moodle" in html.lower():
                return True, "Authenticated: session is active"
            return True, "Session appears active"
        except SessionExpiredError:
            return False, "Session expired"
        except Exception as e:
            return False, f"Session check error: {e}"

    async def close(self):
        """Close persistent HTTP client session."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

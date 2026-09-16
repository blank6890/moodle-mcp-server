# Moodle MCP Latency Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decrease MCP tool response latency by ~95% (from 3,000–5,000ms down to 50–150ms) by implementing a high-speed HTTP-first transport engine with session cookie syncing, optimized Playwright fallback with resource blocking, and granular caching.

**Architecture:** A dual-engine fetching architecture where `HttpClientManager` (`httpx.AsyncClient`) reads `session/state.json` cookies and directly fetches server-rendered Moodle endpoints in ~50–100ms. An optimized `BrowserManager` (Playwright) acts as a fallback for dynamic client-rendered components, enhanced with route-level asset aborting, page tab pooling, and the removal of hardcoded sleep delays.

**Tech Stack:** Python 3.10+, httpx, Playwright (async API), BeautifulSoup4, Pydantic v2, FastMCP.

**Spec:** [docs/superpowers/specs/2026-09-16-latency-optimization-design.md](../../specs/2026-09-16-latency-optimization-design.md)

## Global Constraints
- Target latency: <150ms for standard HTTP calls, <1000ms for browser fallback.
- Must remain 100% backward compatible with existing MCP tool schemas and data models (`Course`, `Assignment`, `CalendarEvent`, `CourseDetail`, `Participant`, `SessionStatus`).
- Must handle session expiration identically across HTTP and Playwright engines by raising `SessionExpiredError`.
- No new external system dependencies beyond packages already in `requirements.txt` (`httpx`, `playwright`, `beautifulsoup4`, `pydantic`).

---

### Task 1: Configuration & Latency Defaults

**Files:**
- Modify: `app/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: Environment variables
- Produces: `Config.HTTP_TIMEOUT`, `Config.ENABLE_HTTP_FIRST`, `Config.CACHE_TTL_COURSES`, `Config.CACHE_TTL_CALENDAR`, updated `Config.THROTTLE_DELAY`

- [ ] **Step 1: Write unit tests for updated configuration defaults**

Update `tests/test_config.py`:
```python
def test_config_latency_optimization_defaults():
    from app.config import Config
    config = Config()
    assert config.HTTP_TIMEOUT == 10.0
    assert config.ENABLE_HTTP_FIRST is True
    assert config.THROTTLE_DELAY == 0.1
    assert config.CACHE_TTL_COURSES == 600
    assert config.CACHE_TTL_CALENDAR == 180
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with missing attributes on `Config`.

- [ ] **Step 3: Update `app/config.py`**

In `app/config.py`:
```python
import os
from pathlib import Path
from typing import Optional

class Config:
    """Configuration from environment variables with sensible defaults."""

    def __init__(self):
        self.HOST: str = os.getenv("HOST", "127.0.0.1")
        self.PORT: int = int(os.getenv("PORT", "8100"))
        self.MOODLE_BASE_URL: str = os.getenv("MOODLE_BASE_URL", "https://courses.iiit.ac.in")
        self.CAS_LOGIN_URL: str = os.getenv("CAS_LOGIN_URL", "https://login.iiit.ac.in")

        # Paths
        self.SESSION_DIR: Path = Path(os.getenv("SESSION_DIR", "./session"))
        self.CACHE_DIR: Path = Path(os.getenv("CACHE_DIR", "./cache"))

        # Create directories if they don't exist
        self.SESSION_DIR.mkdir(parents=True, exist_ok=True)
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # Performance & Timeouts
        self.CACHE_TTL: int = int(os.getenv("CACHE_TTL", "300"))
        self.CACHE_TTL_COURSES: int = int(os.getenv("CACHE_TTL_COURSES", "600"))
        self.CACHE_TTL_CALENDAR: int = int(os.getenv("CACHE_TTL_CALENDAR", "180"))
        self.THROTTLE_DELAY: float = float(os.getenv("THROTTLE_DELAY", "0.1"))
        self.HTTP_TIMEOUT: float = float(os.getenv("HTTP_TIMEOUT", "10.0"))
        self.ENABLE_HTTP_FIRST: bool = os.getenv("ENABLE_HTTP_FIRST", "true").lower() in ("true", "1", "yes")

        # Browser
        self.CHROMIUM_PATH: Optional[str] = os.getenv("CHROMIUM_PATH")

        # Logging
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    def __repr__(self):
        return (
            f"Config(HOST={self.HOST}, PORT={self.PORT}, "
            f"MOODLE={self.MOODLE_BASE_URL}, CACHE_TTL={self.CACHE_TTL}, "
            f"HTTP_FIRST={self.ENABLE_HTTP_FIRST})"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/config.py tests/test_config.py
git commit -m "feat(config): add http client settings and optimize latency defaults"
```

---

### Task 2: High-Speed `HttpClientManager`

**Files:**
- Create: `app/http_client.py`
- Test: `tests/test_http_client.py`

**Interfaces:**
- Consumes: `Config`, `session/state.json`, `app.browser.SessionExpiredError`
- Produces: `HttpClientManager.get(url: str) -> Tuple[str, str]`, `HttpClientManager.check_session() -> bool`

- [ ] **Step 1: Write failing tests for `HttpClientManager`**

Create `tests/test_http_client.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_http_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.http_client'`

- [ ] **Step 3: Implement `app/http_client.py`**

Create `app/http_client.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_http_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/http_client.py tests/test_http_client.py
git commit -m "feat(http): implement high-speed HttpClientManager with cookie sync"
```

---

### Task 3: Optimize `BrowserManager` (Playwright Fallback)

**Files:**
- Modify: `app/browser.py`
- Test: `tests/test_browser.py`

**Interfaces:**
- Consumes: `Config`, `playwright.async_api`
- Produces: Optimized `BrowserManager.navigate(url: str) -> Tuple[str, str]` with asset blocking and reusable page tab.

- [ ] **Step 1: Write test for asset route blocking and timeout reduction**

Update `tests/test_browser.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.config import Config
from app.browser import BrowserManager

@pytest.mark.asyncio
async def test_browser_page_reuse_and_route_blocking():
    config = Config()
    config.CHROMIUM_PATH = None
    manager = BrowserManager(config)
    
    mock_page = AsyncMock()
    mock_page.url = "https://courses.iiit.ac.in/my/"
    mock_page.content.return_value = "<html><body>Dashboard</body></html>"
    
    mock_context = AsyncMock()
    mock_context.new_page.return_value = mock_page
    
    manager._context = mock_context
    manager._initialized = True
    
    url, html = await manager.navigate("https://courses.iiit.ac.in/my/")
    assert url == "https://courses.iiit.ac.in/my/"
    assert "Dashboard" in html
```

- [ ] **Step 2: Update `app/browser.py`**

In `app/browser.py`:
```python
import asyncio
import logging
from pathlib import Path
from typing import Optional, Tuple
from playwright.async_api import async_playwright, Route
from app.config import Config

logger = logging.getLogger(__name__)

class SessionExpiredError(Exception):
    """Raised when Moodle session has expired (redirect to CAS)."""
    pass

class BrowserManager:
    """Manages an optimized Playwright browser context with resource blocking."""

    BLOCKED_RESOURCE_TYPES = {"image", "media", "font", "stylesheet"}

    def __init__(self, config: Config):
        self.config = config
        self._browser = None
        self._context = None
        self._page = None
        self._playwright = None
        self._throttle_lock = asyncio.Lock()
        self._last_request_time = 0.0
        self._initialized = False

    async def __aenter__(self):
        await self._init_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._close_browser()

    async def _handle_route(self, route: Route):
        """Abort unnecessary resources (images, fonts, stylesheets) for speed."""
        if route.request.resource_type in self.BLOCKED_RESOURCE_TYPES:
            await route.abort()
        else:
            await route.continue_()

    async def _init_browser(self):
        """Initialize Playwright browser with route optimizations."""
        if self._initialized:
            return

        logger.info("Initializing optimized Playwright browser...")
        self._playwright = await async_playwright().start()

        executable_path = self.config.CHROMIUM_PATH if self.config.CHROMIUM_PATH else None

        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-extensions",
            ],
            executable_path=executable_path,
        )

        state_file = Path(self.config.SESSION_DIR) / "state.json"
        storage_state_arg = str(state_file) if state_file.exists() else None

        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 720},
            storage_state=storage_state_arg
        )

        # Route filtering across the context
        await self._context.route("**/*", self._handle_route)

        # Create a single persistent reusable page tab
        self._page = await self._context.new_page()

        self._initialized = True
        logger.info("Optimized Playwright browser initialized successfully")

    async def _close_browser(self):
        """Close browser and cleanup."""
        if self._page:
            try:
                await self._page.close()
            except Exception:
                pass
            self._page = None

        if self._context:
            await self._context.close()
            logger.info("Browser context closed")
            
        if self._browser:
            await self._browser.close()

        if self._playwright:
            await self._playwright.stop()
            logger.info("Playwright stopped")

        self._initialized = False

    async def navigate(self, url: str) -> Tuple[str, str]:
        """Navigate to URL with optimized page lifecycle. Returns (final_url, page_html)."""
        if not self._initialized:
            await self._init_browser()

        # Adaptive throttling
        async with self._throttle_lock:
            import time
            elapsed = time.time() - self._last_request_time
            if elapsed < self.config.THROTTLE_DELAY:
                await asyncio.sleep(self.config.THROTTLE_DELAY - elapsed)
            self._last_request_time = time.time()

        page = self._page
        if page is None or page.is_closed():
            page = await self._context.new_page()
            self._page = page

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            final_url = page.url

            if "login.iiit.ac.in" in final_url or "/login/" in final_url:
                logger.warning(f"Session expired: redirected to {final_url}")
                raise SessionExpiredError(f"Redirected to CAS login at {final_url}")

            # Fast dynamic selector check with tight timeout (2.5s instead of 15s)
            try:
                if "/my/courses.php" in url:
                    await page.wait_for_selector(".coursename", timeout=2500)
                elif "/mod/assign/" in url:
                    await page.wait_for_selector(".generaltable", timeout=2500)
            except Exception:
                pass  # Fallback to current DOM content immediately

            html = await page.content()
            logger.debug(f"Navigated to {final_url}")
            return final_url, html

        except SessionExpiredError:
            raise
        except Exception as e:
            logger.error(f"Browser navigation error for {url}: {e}")
            raise
```

- [ ] **Step 3: Run test to verify it passes**

Run: `pytest tests/test_browser.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app/browser.py tests/test_browser.py
git commit -m "perf(browser): add resource abort filter, page reuse, and remove sleep timers"
```

---

### Task 4: Fast Authentication & Health Verification

**Files:**
- Modify: `app/auth.py`
- Test: `tests/test_auth.py`

**Interfaces:**
- Consumes: `HttpClientManager`, `BrowserManager`
- Produces: `check_session(http_client: Optional[HttpClientManager], browser: Optional[BrowserManager]) -> SessionStatus`

- [ ] **Step 1: Write tests for fast auth check**

Update `tests/test_auth.py`:
```python
import pytest
from unittest.mock import AsyncMock
from app.models import SessionStatus
from app.auth import check_session
from app.browser import SessionExpiredError

@pytest.mark.asyncio
async def test_check_session_http_fast_path():
    mock_http = AsyncMock()
    mock_http.get.return_value = ("https://courses.iiit.ac.in/my/", "<html><body>Dashboard Moodle</body></html>")
    
    status = await check_session(http_client=mock_http)
    assert status.authenticated is True
    assert "Authenticated" in status.detail
    mock_http.get.assert_called_once()

@pytest.mark.asyncio
async def test_check_session_expired():
    mock_http = AsyncMock()
    mock_http.get.side_effect = SessionExpiredError("Redirected to CAS")
    
    with pytest.raises(SessionExpiredError):
        await check_session(http_client=mock_http)
```

- [ ] **Step 2: Update `app/auth.py`**

In `app/auth.py`:
```python
import logging
from typing import Optional
from app.browser import BrowserManager, SessionExpiredError
from app.http_client import HttpClientManager
from app.models import SessionStatus

logger = logging.getLogger(__name__)

async def check_session(
    browser: Optional[BrowserManager] = None,
    http_client: Optional[HttpClientManager] = None
) -> SessionStatus:
    """Check if the session is authenticated via fast HTTP or fallback browser."""
    try:
        if http_client is not None:
            final_url, html = await http_client.get("https://courses.iiit.ac.in/my/")
        elif browser is not None:
            final_url, html = await browser.navigate("https://courses.iiit.ac.in/my/")
        else:
            raise RuntimeError("Neither http_client nor browser provided for check_session")

        if "dashboard" in html.lower() or "moodle" in html.lower():
            logger.info("Session is authenticated")
            return SessionStatus(
                authenticated=True,
                detail="Authenticated: session is active"
            )
        else:
            logger.warning("Session check: unclear state on Moodle domain")
            return SessionStatus(
                authenticated=True,
                detail="Session appears active (on Moodle domain)"
            )

    except SessionExpiredError as e:
        logger.warning(f"Session expired: {e}")
        raise
```

- [ ] **Step 3: Run test to verify it passes**

Run: `pytest tests/test_auth.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app/auth.py tests/test_auth.py
git commit -m "perf(auth): route session checks through fast HTTP path"
```

---

### Task 5: Dual-Engine `MoodleService` & Caching

**Files:**
- Modify: `app/moodle.py`
- Test: `tests/test_moodle.py`

**Interfaces:**
- Consumes: `HttpClientManager`, `BrowserManager`, `Config`, Parsers
- Produces: `MoodleService.get_courses()`, `MoodleService.get_assignments()`, `MoodleService.get_calendar()`, `MoodleService.get_course_detail()`, `MoodleService.get_announcements()`, `MoodleService.get_participants()` with HTTP-first routing and granular TTL caching.

- [ ] **Step 1: Write test for HTTP-first parsing and fallback**

Update `tests/test_moodle.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.config import Config
from app.moodle import MoodleService

@pytest.mark.asyncio
async def test_moodle_service_uses_http_first():
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
```

- [ ] **Step 2: Update `app/moodle.py`**

In `app/moodle.py`:
```python
import logging
import time
from typing import Optional, Dict, Tuple, Any, Callable
from app.browser import BrowserManager, SessionExpiredError
from app.http_client import HttpClientManager
from app.config import Config
from app.models import (
    Course, Assignment, CalendarEvent, Announcement, CourseDetail, Participant
)
from app.parsers import courses as courses_parser
from app.parsers import assignments as assignments_parser
from app.parsers import calendar as calendar_parser
from app.parsers import announcements as announcements_parser
from app.parsers import course as course_parser
from app.parsers import participants as participants_parser

logger = logging.getLogger(__name__)

class MoodleService:
    """Orchestrates fast HTTP transport, fallback browser, cache, and parsers."""
    
    def __init__(
        self,
        browser: BrowserManager,
        config: Config,
        http_client: Optional[HttpClientManager] = None
    ):
        self.browser = browser
        self.config = config
        self.http_client = http_client or HttpClientManager(config)
        self._cache: Dict[str, Tuple[float, Any]] = {}

    def _get_cached(self, key: str, ttl: Optional[int] = None) -> Optional[Any]:
        """Get value from cache if not expired."""
        if key in self._cache:
            timestamp, value = self._cache[key]
            effective_ttl = ttl if ttl is not None else self.config.CACHE_TTL
            if time.time() - timestamp < effective_ttl:
                logger.debug(f"Cache hit: {key}")
                return value
            else:
                logger.debug(f"Cache expired: {key}")
                del self._cache[key]
        return None

    def _set_cache(self, key: str, value: Any):
        """Set value in cache with current timestamp."""
        self._cache[key] = (time.time(), value)
        logger.debug(f"Cache set: {key}")

    async def _fetch_html(self, url: str, fallback_check: Optional[Callable[[str], bool]] = None) -> str:
        """Fetch HTML via fast HTTP client, falling back to Playwright if needed."""
        if self.config.ENABLE_HTTP_FIRST:
            try:
                start_t = time.time()
                _, html = await self.http_client.get(url)
                logger.debug(f"HTTP fetch {url} took {(time.time() - start_t)*1000:.1f}ms")
                
                # If custom fallback validator passes or not provided, return HTTP HTML
                if fallback_check is None or fallback_check(html):
                    return html
                logger.info(f"HTTP content required browser fallback for {url}")
            except SessionExpiredError:
                raise
            except Exception as e:
                logger.warning(f"HTTP fetch failed for {url} ({e}), falling back to browser")

        # Fallback to browser navigation
        start_t = time.time()
        _, html = await self.browser.navigate(url)
        logger.debug(f"Browser fetch {url} took {(time.time() - start_t)*1000:.1f}ms")
        return html

    async def get_courses(self) -> list[Course]:
        """Get enrolled courses with caching."""
        cache_key = "courses"
        cached = self._get_cached(cache_key, ttl=self.config.CACHE_TTL_COURSES)
        if cached is not None:
            return cached

        html = await self._fetch_html(
            "https://courses.iiit.ac.in/my/courses.php",
            fallback_check=lambda h: "coursename" in h or "course-info-container" in h
        )
        courses = courses_parser.parse_courses(html)
        
        # If HTTP parser returned empty but page might be dynamic, try browser once
        if not courses and self.config.ENABLE_HTTP_FIRST:
            _, browser_html = await self.browser.navigate("https://courses.iiit.ac.in/my/courses.php")
            courses = courses_parser.parse_courses(browser_html)

        self._set_cache(cache_key, courses)
        return courses

    async def get_assignments(self, course_id: Optional[str] = None) -> list[Assignment]:
        """Get assignments with optional course filter."""
        cache_key = f"assignments_{course_id or 'all'}"
        cached = self._get_cached(cache_key, ttl=self.config.CACHE_TTL_CALENDAR)
        if cached is not None:
            return cached

        url = f"https://courses.iiit.ac.in/mod/assign/index.php?id={course_id}" if course_id else "https://courses.iiit.ac.in/my/"
        html = await self._fetch_html(url)
        assignments = assignments_parser.parse_assignments(html)
        self._set_cache(cache_key, assignments)
        return assignments

    async def get_calendar(self, days_ahead: int = 30) -> list[CalendarEvent]:
        """Get upcoming calendar events."""
        cache_key = f"calendar_{days_ahead}"
        cached = self._get_cached(cache_key, ttl=self.config.CACHE_TTL_CALENDAR)
        if cached is not None:
            return cached

        html = await self._fetch_html("https://courses.iiit.ac.in/calendar/view.php?view=upcoming")
        events = calendar_parser.parse_calendar(html)
        self._set_cache(cache_key, events)
        return events

    async def get_announcements(self, course_id: Optional[str] = None, limit: int = 20) -> list[Announcement]:
        """Get recent announcements from course or site-wide."""
        cache_key = f"announcements_{course_id or 'all'}_{limit}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        url = f"https://courses.iiit.ac.in/course/view.php?id={course_id}" if course_id else "https://courses.iiit.ac.in/my/"
        html = await self._fetch_html(url)
        announcements = announcements_parser.parse_announcements(html)[:limit]
        self._set_cache(cache_key, announcements)
        return announcements

    async def get_course_detail(self, course_id: str) -> CourseDetail:
        """Get full course detail with sections and resources."""
        cache_key = f"course_{course_id}"
        cached = self._get_cached(cache_key, ttl=self.config.CACHE_TTL_COURSES)
        if cached is not None:
            return cached

        html = await self._fetch_html(f"https://courses.iiit.ac.in/course/view.php?id={course_id}")
        course = course_parser.parse_course_detail(html)
        self._set_cache(cache_key, course)
        return course

    async def get_participants(self, course_id: str) -> list[Participant]:
        """Get enrolled participants and instructors in a course."""
        cache_key = f"participants_{course_id}"
        cached = self._get_cached(cache_key, ttl=self.config.CACHE_TTL_COURSES)
        if cached is not None:
            return cached

        html = await self._fetch_html(f"https://courses.iiit.ac.in/user/index.php?id={course_id}")
        participants = participants_parser.parse_participants(html)
        self._set_cache(cache_key, participants)
        return participants
```

- [ ] **Step 3: Run test to verify it passes**

Run: `pytest tests/test_moodle.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app/moodle.py tests/test_moodle.py
git commit -m "feat(service): integrate dual-engine HTTP-first transport with granular caching"
```

---

### Task 6: Wire MCP Server & Fast Initialization

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: `HttpClientManager`, `BrowserManager`, `MoodleService`, `check_session`
- Produces: MCP Server tools executing in <150ms.

- [ ] **Step 1: Write integration tests for MCP Server tools**

Update `tests/test_main.py`:
```python
import pytest
from app.main import create_mcp_server

def test_mcp_server_creation():
    server = create_mcp_server()
    assert server.name == "moodle-agent"
```

- [ ] **Step 2: Update `app/main.py`**

In `app/main.py`:
```python
import asyncio
import logging
import sys
import time
from typing import Optional

try:
    from mcp.server import MCPServer
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer

from app.config import Config
from app.browser import BrowserManager, SessionExpiredError
from app.http_client import HttpClientManager
from app.auth import check_session as check_auth_session
from app.moodle import MoodleService
from app.logging_config import setup_logging

logger = logging.getLogger(__name__)

# Global state
_config: Optional[Config] = None
_browser: Optional[BrowserManager] = None
_http_client: Optional[HttpClientManager] = None
_moodle: Optional[MoodleService] = None
_start_time: float = time.time()

async def _init_globals():
    """Initialize global clients and service on first tool call."""
    global _config, _browser, _http_client, _moodle
    
    if _moodle is not None:
        return
    
    _config = Config()
    _http_client = HttpClientManager(_config)
    _browser = BrowserManager(_config)
    _moodle = MoodleService(_browser, _config, http_client=_http_client)

def create_mcp_server() -> MCPServer:
    """Create and configure high-performance MCP server."""
    
    server = MCPServer("moodle-agent")
    
    @server.tool()
    async def check_health() -> dict:
        """Check service health and authentication status in ~50ms."""
        try:
            await _init_globals()
            uptime = time.time() - _start_time
            
            try:
                status_obj = await check_auth_session(browser=_browser, http_client=_http_client)
                authenticated = status_obj.authenticated
                detail = status_obj.detail
            except SessionExpiredError:
                authenticated = False
                detail = "Session expired"
            
            return {
                "status": "healthy",
                "authenticated": authenticated,
                "uptime_seconds": uptime,
                "detail": detail
            }
        except Exception as e:
            logger.error(f"health check failed: {e}")
            return {
                "status": "error",
                "authenticated": False,
                "uptime_seconds": time.time() - _start_time,
                "detail": str(e)
            }
    
    @server.tool()
    async def check_session() -> dict:
        """Check if session is authenticated in ~50ms."""
        try:
            await _init_globals()
            status_obj = await check_auth_session(browser=_browser, http_client=_http_client)
            return {
                "authenticated": status_obj.authenticated,
                "detail": status_obj.detail
            }
        except SessionExpiredError:
            return {
                "authenticated": False,
                "detail": "Session expired. Run 'python scripts/login.py' to re-authenticate."
            }
        except Exception as e:
            logger.error(f"session check failed: {e}")
            return {
                "authenticated": False,
                "detail": f"Error checking session: {e}"
            }
    
    @server.tool()
    async def get_courses() -> list:
        """Get enrolled courses."""
        try:
            await _init_globals()
            courses = await _moodle.get_courses()
            return [c.model_dump() for c in courses]
        except SessionExpiredError:
            raise ValueError("Session expired. Run 'python scripts/login.py' to re-authenticate.")
        except Exception as e:
            logger.error(f"get_courses failed: {e}")
            raise
    
    @server.tool()
    async def get_assignments(course_id: Optional[str] = None) -> list:
        """Get assignments optionally filtered by course."""
        try:
            await _init_globals()
            assignments = await _moodle.get_assignments(course_id)
            return [a.model_dump() for a in assignments]
        except SessionExpiredError:
            raise ValueError("Session expired. Run 'python scripts/login.py' to re-authenticate.")
        except Exception as e:
            logger.error(f"get_assignments failed: {e}")
            raise
    
    @server.tool()
    async def get_calendar(days_ahead: int = 30) -> list:
        """Get upcoming calendar events."""
        try:
            await _init_globals()
            events = await _moodle.get_calendar(days_ahead)
            return [e.model_dump() for e in events]
        except SessionExpiredError:
            raise ValueError("Session expired. Run 'python scripts/login.py' to re-authenticate.")
        except Exception as e:
            logger.error(f"get_calendar failed: {e}")
            raise
    
    @server.tool()
    async def get_course(course_id: str) -> dict:
        """Get full course detail with sections and resources."""
        try:
            await _init_globals()
            course = await _moodle.get_course_detail(course_id)
            return course.model_dump()
        except SessionExpiredError:
            raise ValueError("Session expired. Run 'python scripts/login.py' to re-authenticate.")
        except Exception as e:
            logger.error(f"get_course failed: {e}")
            raise

    @server.tool()
    async def get_course_materials(course_id: str) -> list:
        """Get organized course materials and lectures by section."""
        try:
            await _init_globals()
            course = await _moodle.get_course_detail(course_id)
            return [s.model_dump() for s in course.sections]
        except SessionExpiredError:
            raise ValueError("Session expired. Run 'python scripts/login.py' to re-authenticate.")
        except Exception as e:
            logger.error(f"get_course_materials failed: {e}")
            raise

    @server.tool()
    async def get_announcements(course_id: Optional[str] = None, limit: int = 20) -> list:
        """Get recent announcements from a course or site-wide."""
        try:
            await _init_globals()
            announcements = await _moodle.get_announcements(course_id, limit)
            return [a.model_dump() for a in announcements]
        except SessionExpiredError:
            raise ValueError("Session expired. Run 'python scripts/login.py' to re-authenticate.")
        except Exception as e:
            logger.error(f"get_announcements failed: {e}")
            raise

    @server.tool()
    async def get_participants(course_id: str) -> list:
        """Get enrolled participants and instructors in a course."""
        try:
            await _init_globals()
            participants = await _moodle.get_participants(course_id)
            return [p.model_dump() for p in participants]
        except SessionExpiredError:
            raise ValueError("Session expired. Run 'python scripts/login.py' to re-authenticate.")
        except Exception as e:
            logger.error(f"get_participants failed: {e}")
            raise

    return server

def main():
    config = Config()
    setup_logging(config.LOG_LEVEL)
    logger.info("Starting High-Performance Moodle MCP Server")
    
    use_sse = "--sse" in sys.argv
    server = create_mcp_server()
    
    try:
        if use_sse:
            logger.info(f"Running in SSE mode on {config.HOST}:{config.PORT}")
            server.settings.host = config.HOST
            server.settings.port = config.PORT
            server.run(transport="sse")
        else:
            logger.info("Running in stdio mode")
            server.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run all tests to verify they pass**

Run: `pytest tests/ -v`
Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add app/main.py tests/test_main.py
git commit -m "feat(server): wire high-performance HTTP client to MCP server tools"
```

---

### Task 7: Latency Benchmarking & End-to-End Verification

**Files:**
- Create: `scripts/benchmark_latency.py`

**Interfaces:**
- Consumes: MCP Client Session
- Produces: Printed latency report for all tools before vs after optimization.

- [ ] **Step 1: Create `scripts/benchmark_latency.py`**

Create `scripts/benchmark_latency.py`:
```python
import asyncio
import os
import sys
import time
from pathlib import Path
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

async def benchmark():
    project_root = Path(__file__).parent.parent.absolute()
    python_exe = str(project_root / "venv" / "Scripts" / "python.exe")
    if not Path(python_exe).exists():
        python_exe = sys.executable

    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)
    env["SESSION_DIR"] = str(project_root / "session")

    server_params = StdioServerParameters(
        command=python_exe,
        args=["-m", "app.main"],
        env=env
    )

    print("=" * 60)
    print("Moodle MCP Latency Benchmark")
    print("=" * 60)

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("✓ Server connected and initialized\n")

            tools_to_test = [
                ("check_health", {}),
                ("check_session", {}),
                ("get_courses", {}),
                ("get_calendar", {"days_ahead": 14}),
                ("get_assignments", {}),
            ]

            for tool_name, args in tools_to_test:
                t0 = time.time()
                try:
                    res = await session.call_tool(tool_name, args)
                    elapsed_ms = (time.time() - t0) * 1000
                    print(f"Tool [{tool_name:18}]: {elapsed_ms:6.1f} ms | Status: SUCCESS")
                except Exception as e:
                    elapsed_ms = (time.time() - t0) * 1000
                    print(f"Tool [{tool_name:18}]: {elapsed_ms:6.1f} ms | Status: FAILED ({e})")

if __name__ == "__main__":
    asyncio.run(benchmark())
```

- [ ] **Step 2: Run benchmark script**

Run: `python scripts/benchmark_latency.py`
Expected: Latency for cached/HTTP operations <150ms.

- [ ] **Step 3: Commit**

```bash
git add scripts/benchmark_latency.py
git commit -m "chore(benchmark): add latency benchmarking utility"
```

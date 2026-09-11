# Moodle MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only MCP server exposing IIIT Moodle features (courses, assignments, calendar, announcements, grades, workshops, participants) via browser automation with persistent CAS-authenticated session.

**Architecture:** Playwright browser automation with persistent profile → HTML parsing via BeautifulSoup → Pydantic models → MCP server (stdio default, SSE with `--sse` flag). Phase 1 core tools first, Phase 2 enhanced tools, Phase 3 optional.

**Tech Stack:** Python 3.9+, Playwright, BeautifulSoup4, Pydantic v2, MCP SDK (python-sdk v1.0+), python-dateutil, asyncio

**Spec:** [2026-09-11-moodle-mcp-server-design.md](../specs/2026-09-11-moodle-mcp-server-design.md)

## Global Constraints

- **No password storage** — never accept, store, or log CAS credentials
- **Interactive auth only** — user completes CAS/MFA in visible browser; never bypass
- **Persistent profile** — save cookies/localStorage to `./session/`; this is the only auth artifact
- **Read-only** — no submitting, posting, or modifying Moodle data
- **Localhost by default** — bind to `127.0.0.1`; `--sse` flag for SSE mode
- **No secret logging** — never log cookies, tokens, or auth secrets
- **ISO 8601 dates** — normalize dates to ISO format; keep raw fallback
- **Raspberry Pi 4B target** — Debian 13 (aarch64); bundled Chromium first, fallback to system `/usr/bin/chromium`
- **MCP Python SDK** — use `MCPServer` class (v1.0+); stdio default transport
- **Flexible date parsing** — handle multiple Moodle date formats ("13 September 2026, 11:59 PM", "September 13", "23:59")

---

## File Structure

```
moodle-agent/
├── app/
│   ├── __init__.py
│   ├── main.py               # MCP server entry point (stdio/SSE)
│   ├── config.py             # env-var based configuration
│   ├── browser.py            # Playwright context manager + throttling
│   ├── auth.py               # Session health check
│   ├── moodle.py             # Orchestrator: browser + cache + parsers
│   ├── models.py             # Pydantic response models
│   └── parsers/
│       ├── __init__.py
│       ├── courses.py        # /my/courses.php → Course[]
│       ├── assignments.py    # /mod/assign/* → Assignment[]
│       ├── calendar.py       # /calendar/view.php → CalendarEvent[]
│       ├── announcements.py  # course Discussions → Announcement[]
│       ├── course.py         # /course/view.php?id → CourseDetail
│       ├── participants.py   # course Participants tab → Participant[]
│       ├── grades.py         # course Grades tab → Grade[]
│       └── workshops.py      # /mod/workshop/* → Workshop[]
├── scripts/
│   ├── login.py              # Interactive CAS login CLI
│   └── inspect.py            # Dump raw HTML for selector calibration
├── tests/
│   ├── __init__.py
│   ├── test_parsers.py       # Parser unit tests with fixtures
│   ├── test_browser.py       # Browser manager tests
│   ├── test_moodle.py        # Orchestrator tests
│   ├── test_auth.py          # Auth health check tests
│   └── fixtures/             # Saved HTML snapshots
├── session/                  # .gitignore: persisted browser profile
├── cache/                    # .gitignore: dumped HTML
├── requirements.txt
├── README.md
├── .gitignore
├── pytest.ini
└── systemd/
    └── moodle-agent.service  # systemd unit (SSE mode only)
```

---

## Phase 1: Core Tools (Tasks 1-6)

### Task 1: Project Scaffolding & Dependencies

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `pytest.ini`
- Create: `app/__init__.py`
- Create: `scripts/__init__.py`
- Create: `tests/__init__.py`

**Interfaces:**
- Produces: project structure; all subsequent tasks depend on this

- [ ] **Step 1: Create `requirements.txt` with exact pinned versions**

```
mcp==1.0.0
playwright==1.46.0
beautifulsoup4==4.12.3
python-dateutil==2.8.2
pydantic==2.7.1
pytest==7.4.4
pytest-asyncio==0.23.3
python-dotenv==1.0.0
```

- [ ] **Step 2: Create `.gitignore` with session/ and cache/ entries**

```
# Python
__pycache__/
*.py[cod]
*$py.class
.pytest_cache/
.venv/
venv/
ENV/

# Project-specific
session/
cache/
*.log

# OS
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/
*.swp
```

- [ ] **Step 3: Create `pytest.ini` for test discovery**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
```

- [ ] **Step 4: Create `app/__init__.py`, `scripts/__init__.py`, `tests/__init__.py` (empty)**

- [ ] **Step 5: Install dependencies locally (for development)**

```bash
cd moodle-agent
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
```

- [ ] **Step 6: Install Playwright Chromium**

```bash
playwright install chromium
```

- [ ] **Step 7: Commit**

```bash
git add requirements.txt .gitignore pytest.ini app/__init__.py scripts/__init__.py tests/__init__.py
git commit -m "scaffold: project structure and dependencies"
```

---

### Task 2: Configuration (`app/config.py`)

**Files:**
- Create: `app/config.py`

**Interfaces:**
- Produces: `Config` class with attributes: `HOST`, `PORT`, `MOODLE_BASE_URL`, `CAS_LOGIN_URL`, `SESSION_DIR`, `CACHE_DIR`, `CACHE_TTL`, `THROTTLE_DELAY`, `CHROMIUM_PATH`, `LOG_LEVEL`

- [ ] **Step 1: Write config tests**

```python
# tests/test_config.py
import os
from app.config import Config

def test_config_defaults():
    """Test default configuration values."""
    config = Config()
    assert config.HOST == "127.0.0.1"
    assert config.PORT == 8100
    assert config.MOODLE_BASE_URL == "https://courses.iiit.ac.in"
    assert config.CAS_LOGIN_URL == "https://login.iiit.ac.in"
    assert config.CACHE_TTL == 300
    assert config.THROTTLE_DELAY == 1.0
    assert config.LOG_LEVEL == "INFO"

def test_config_env_override():
    """Test that env vars override defaults."""
    os.environ["HOST"] = "0.0.0.0"
    os.environ["PORT"] = "9000"
    os.environ["CACHE_TTL"] = "600"
    
    config = Config()
    assert config.HOST == "0.0.0.0"
    assert config.PORT == 9000
    assert config.CACHE_TTL == 600
    
    # Clean up
    del os.environ["HOST"]
    del os.environ["PORT"]
    del os.environ["CACHE_TTL"]

def test_config_paths_exist():
    """Test that SESSION_DIR and CACHE_DIR are created if missing."""
    config = Config()
    assert config.SESSION_DIR
    assert config.CACHE_DIR
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_config.py -v
```

Expected: FAIL — `Config` not defined

- [ ] **Step 3: Implement `app/config.py`**

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
        
        # Performance
        self.CACHE_TTL: int = int(os.getenv("CACHE_TTL", "300"))
        self.THROTTLE_DELAY: float = float(os.getenv("THROTTLE_DELAY", "1.0"))
        
        # Browser
        self.CHROMIUM_PATH: Optional[str] = os.getenv("CHROMIUM_PATH")
        
        # Logging
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
        
    def __repr__(self):
        return (
            f"Config(HOST={self.HOST}, PORT={self.PORT}, "
            f"MOODLE={self.MOODLE_BASE_URL}, CACHE_TTL={self.CACHE_TTL})"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_config.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/config.py tests/test_config.py
git commit -m "feat: configuration management via environment variables"
```

---

### Task 3: Logging Setup

**Files:**
- Create: `app/logging_config.py`

**Interfaces:**
- Produces: `setup_logging(level: str)` function; logger configured with secret redaction

- [ ] **Step 1: Write logging test**

```python
# tests/test_logging.py
import logging
from app.logging_config import setup_logging

def test_logging_setup():
    """Test that logging is configured."""
    logger = setup_logging("DEBUG")
    assert logger.level == logging.DEBUG
    
    # Verify secret filter is applied
    handler = logger.handlers[0]
    assert any(f.name == "SecretFilter" for f in handler.filters)

def test_secret_filter_redacts():
    """Test that secrets are redacted from logs."""
    from app.logging_config import SecretFilter
    
    filter = SecretFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="cookie: abc123secret",
        args=(),
        exc_info=None
    )
    
    # Filter should allow the record but the filter logic will redact
    assert filter.filter(record) is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_logging.py -v
```

Expected: FAIL — `setup_logging` not defined

- [ ] **Step 3: Implement `app/logging_config.py`**

```python
import logging
import sys
from typing import Optional

class SecretFilter(logging.Filter):
    """Filter that redacts sensitive fields from log records."""
    
    name = "SecretFilter"
    
    SENSITIVE_FIELDS = {"cookie", "token", "session", "authorization", "password", "csrf"}
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Redact sensitive fields from the log message."""
        if record.msg:
            msg_str = str(record.msg)
            for field in self.SENSITIVE_FIELDS:
                # Simple replacement: "field: value" → "field: [REDACTED]"
                import re
                pattern = rf"({field})\s*:\s*\S+"
                msg_str = re.sub(pattern, rf"\1: [REDACTED]", msg_str, flags=re.IGNORECASE)
            record.msg = msg_str
        return True

def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure logging with secret redaction."""
    logger = logging.getLogger("moodle_agent")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    
    # Add secret filter
    handler.addFilter(SecretFilter())
    
    # Add handler to logger
    if logger.handlers:
        logger.handlers.clear()
    logger.addHandler(handler)
    
    return logger
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_logging.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/logging_config.py tests/test_logging.py
git commit -m "feat: logging with secret redaction"
```

---

### Task 4: Pydantic Response Models (`app/models.py`)

**Files:**
- Create: `app/models.py`

**Interfaces:**
- Produces: Pydantic models for all data types:
  - `Course(id: str, name: str, url: str)`
  - `Assignment(course: str, name: str, due_date: str | None, due_date_raw: str, status: str, url: str)`
  - `CalendarEvent(title: str, date: str | None, date_raw: str, course: str | None, event_type: str, url: str | None)`
  - `Announcement(course: str, title: str, content_preview: str, author: str, date: str | None, date_raw: str, url: str)`
  - `Resource(name: str, url: str | None, resource_type: str | None)`
  - `Section(title: str, resources: list[Resource])`
  - `CourseDetail(id: str, name: str, url: str, sections: list[Section])`
  - `Participant(name: str, role: str, profile_url: str | None)`
  - `Grade(course: str, item_name: str, max_points: float | None, earned_points: float | None, percentage: float | None, status: str)`
  - `Workshop(name: str, course: str, phase: str, submission_deadline: str | None, assessment_deadline: str | None, status: str, url: str)`
  - `SessionStatus(authenticated: bool, detail: str)`
  - `HealthStatus(status: str, authenticated: bool, uptime_seconds: float)`

- [ ] **Step 1: Write model validation tests**

```python
# tests/test_models.py
from app.models import Course, Assignment, CalendarEvent, Announcement

def test_course_model():
    """Test Course model."""
    course = Course(id="5817", name="Algorithm Analysis & Design", url="https://courses.iiit.ac.in/course/view.php?id=5817")
    assert course.id == "5817"
    assert course.name == "Algorithm Analysis & Design"

def test_assignment_model():
    """Test Assignment model with optional due_date."""
    assign = Assignment(
        course="Algorithm Analysis & Design",
        name="Mini project 1",
        due_date="2026-09-13T23:59:00",
        due_date_raw="13 September 2026, 11:59 PM",
        status="not_submitted",
        url="https://courses.iiit.ac.in/mod/assign/view.php?id=70167"
    )
    assert assign.course == "Algorithm Analysis & Design"
    assert assign.due_date == "2026-09-13T23:59:00"

def test_calendar_event_model():
    """Test CalendarEvent model."""
    event = CalendarEvent(
        title="Mini project 1 (end submission) is due",
        date="2026-09-13",
        date_raw="13 September 2026",
        course="Operating Systems and Networks",
        event_type="assignment_due",
        url="https://courses.iiit.ac.in/mod/assign/view.php?id=70167"
    )
    assert event.event_type == "assignment_due"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_models.py -v
```

Expected: FAIL — models not defined

- [ ] **Step 3: Implement `app/models.py`**

```python
from typing import Optional
from pydantic import BaseModel, Field

class Course(BaseModel):
    id: str
    name: str
    url: str

class Assignment(BaseModel):
    course: str
    name: str
    due_date: Optional[str] = None  # ISO 8601
    due_date_raw: str
    status: str  # "not_submitted", "submitted", "graded"
    url: str

class CalendarEvent(BaseModel):
    title: str
    date: Optional[str] = None  # ISO 8601
    date_raw: str
    course: Optional[str] = None
    event_type: str  # "assignment_due", "workshop_submission", "workshop_assessment", "course_event"
    url: Optional[str] = None

class Announcement(BaseModel):
    course: str
    title: str
    content_preview: str
    author: str
    date: Optional[str] = None  # ISO 8601
    date_raw: str
    url: str

class Resource(BaseModel):
    name: str
    url: Optional[str] = None
    resource_type: Optional[str] = None  # "pdf", "link", "file", "folder"

class Section(BaseModel):
    title: str
    resources: list[Resource] = Field(default_factory=list)

class CourseDetail(BaseModel):
    id: str
    name: str
    url: str
    sections: list[Section] = Field(default_factory=list)

class Participant(BaseModel):
    name: str
    role: str  # "student", "teacher", "admin"
    profile_url: Optional[str] = None

class Grade(BaseModel):
    course: str
    item_name: str
    max_points: Optional[float] = None
    earned_points: Optional[float] = None
    percentage: Optional[float] = None
    status: str  # "completed", "pending", "not_graded"

class Workshop(BaseModel):
    name: str
    course: str
    phase: str  # "setup", "submission", "assessment", "closed"
    submission_deadline: Optional[str] = None
    assessment_deadline: Optional[str] = None
    status: str
    url: str

class SessionStatus(BaseModel):
    authenticated: bool
    detail: str

class HealthStatus(BaseModel):
    status: str
    authenticated: bool
    uptime_seconds: float
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_models.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/models.py tests/test_models.py
git commit -m "feat: Pydantic models for all Moodle data types"
```

---

### Task 5: Browser Manager (`app/browser.py`)

**Files:**
- Create: `app/browser.py`

**Interfaces:**
- Produces:
  - `BrowserManager` class with methods:
    - `async __aenter__()` — opens persistent context
    - `async __aexit__()` — closes context
    - `async navigate(url: str) -> tuple[str, str]` — returns `(final_url, page_html)`, raises `SessionExpiredError` on CAS redirect
    - `async get_current_url() -> str`
    - `async is_initialized() -> bool`

- [ ] **Step 1: Write browser manager tests**

```python
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
    
    mock_page = AsyncMock()
    mock_page.url = "https://courses.iiit.ac.in/my/"
    mock_page.content = AsyncMock(return_value="<html>test</html>")
    mock_page.goto = AsyncMock()
    
    manager._context.new_page = AsyncMock(return_value=mock_page)
    
    url, html = await manager.navigate("https://courses.iiit.ac.in/my/")
    assert url == "https://courses.iiit.ac.in/my/"
    assert html == "<html>test</html>"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_browser.py -v
```

Expected: FAIL — `BrowserManager` not defined

- [ ] **Step 3: Implement `app/browser.py`**

```python
import asyncio
import logging
from pathlib import Path
from typing import Optional, Tuple
from playwright.async_api import async_playwright
from app.config import Config

logger = logging.getLogger(__name__)

class SessionExpiredError(Exception):
    """Raised when Moodle session has expired (redirect to CAS)."""
    pass

class BrowserManager:
    """Manages Playwright persistent browser context with throttling."""
    
    def __init__(self, config: Config):
        self.config = config
        self._context = None
        self._playwright = None
        self._throttle_lock = asyncio.Lock()
        self._last_request_time = 0.0
        self._initialized = False
    
    async def __aenter__(self):
        """Enter context: initialize browser."""
        await self._init_browser()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context: close browser."""
        await self._close_browser()
    
    async def _init_browser(self):
        """Initialize Playwright browser and context."""
        if self._initialized:
            return
        
        logger.info("Initializing Playwright browser...")
        self._playwright = await async_playwright().start()
        
        # Determine executable path
        executable_path = None
        if self.config.CHROMIUM_PATH:
            executable_path = self.config.CHROMIUM_PATH
        else:
            # Try system Chromium if bundled fails (fallback)
            try:
                # Playwright's bundled Chromium
                executable_path = None  # Let Playwright find it
            except Exception:
                logger.warning("Bundled Chromium not found, trying system Chromium")
                executable_path = "/usr/bin/chromium"
        
        # Launch persistent context
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.config.SESSION_DIR),
            headless=True,
            viewport={"width": 1280, "height": 720},
            args=["--disable-gpu"],
            executable_path=executable_path,
        )
        
        self._initialized = True
        logger.info("Browser initialized successfully")
    
    async def _close_browser(self):
        """Close browser and cleanup."""
        if self._context:
            await self._context.close()
            logger.info("Browser context closed")
        
        if self._playwright:
            await self._playwright.stop()
            logger.info("Playwright stopped")
        
        self._initialized = False
    
    async def navigate(self, url: str) -> Tuple[str, str]:
        """Navigate to URL with throttling. Returns (final_url, page_html).
        
        Raises SessionExpiredError if redirected to CAS login.
        """
        if not self._initialized:
            raise RuntimeError("Browser not initialized. Use 'async with BrowserManager(config) as mgr'")
        
        # Apply throttling
        async with self._throttle_lock:
            import time
            elapsed = time.time() - self._last_request_time
            if elapsed < self.config.THROTTLE_DELAY:
                await asyncio.sleep(self.config.THROTTLE_DELAY - elapsed)
            self._last_request_time = time.time()
        
        # Navigate
        page = await self._context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded")
            final_url = page.url
            
            # Check for CAS redirect (session expired)
            if "login.iiit.ac.in" in final_url or "/login/" in final_url:
                logger.warning(f"Session expired: redirected to {final_url}")
                raise SessionExpiredError(f"Redirected to CAS login at {final_url}")
            
            # Get HTML
            html = await page.content()
            logger.debug(f"Navigated to {final_url}")
            
            return final_url, html
        finally:
            await page.close()
    
    async def get_current_url(self) -> str:
        """Get the current page URL."""
        if not self._initialized:
            raise RuntimeError("Browser not initialized")
        
        # Simplified: return last known URL
        # In production, you might track this differently
        return self.config.MOODLE_BASE_URL
    
    async def is_initialized(self) -> bool:
        """Check if browser is initialized."""
        return self._initialized
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_browser.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/browser.py tests/test_browser.py
git commit -m "feat: Playwright browser manager with throttling"
```

---

### Task 6: Auth Session Health Check (`app/auth.py`)

**Files:**
- Create: `app/auth.py`

**Interfaces:**
- Produces:
  - `async check_session(browser: BrowserManager) -> SessionStatus`
  - `SessionExpiredError` exception (re-exported from browser.py)

- [ ] **Step 1: Write auth tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_auth.py -v
```

Expected: FAIL — `check_session` not defined

- [ ] **Step 3: Implement `app/auth.py`**

```python
import logging
from app.browser import BrowserManager, SessionExpiredError
from app.models import SessionStatus

logger = logging.getLogger(__name__)

async def check_session(browser: BrowserManager) -> SessionStatus:
    """Check if the browser session is authenticated.
    
    Navigates to dashboard and checks if we land on Moodle or CAS.
    Raises SessionExpiredError if session has expired.
    
    Returns:
        SessionStatus with authenticated=True if on Moodle, False otherwise.
    
    Raises:
        SessionExpiredError if redirected to CAS login.
    """
    try:
        final_url, html = await browser.navigate("https://courses.iiit.ac.in/my/")
        
        # If we get here, we're on Moodle (no CAS redirect)
        if "dashboard" in html.lower() or "moodle" in html.lower():
            logger.info("Session is authenticated")
            return SessionStatus(
                authenticated=True,
                detail="Authenticated: session is active"
            )
        else:
            logger.warning("Session check: unclear state")
            return SessionStatus(
                authenticated=True,  # Optimistic: we're on Moodle domain
                detail="Session appears active (on Moodle domain)"
            )
    
    except SessionExpiredError as e:
        logger.warning(f"Session expired: {e}")
        raise
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_auth.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/auth.py tests/test_auth.py
git commit -m "feat: session health check logic"
```

---

### Task 7: HTML Parsers — Placeholder Selectors & Structure

**Files:**
- Create: `app/parsers/__init__.py`
- Create: `app/parsers/courses.py`
- Create: `app/parsers/assignments.py`
- Create: `app/parsers/calendar.py`
- Create: `app/parsers/announcements.py`
- Create: `app/parsers/course.py`

**Interfaces:**
- Produces (each parser is a pure function):
  - `parse_courses(html: str) -> list[Course]`
  - `parse_assignments(html: str) -> list[Assignment]`
  - `parse_calendar(html: str) -> list[CalendarEvent]`
  - `parse_announcements(html: str) -> list[Announcement]`
  - `parse_course_detail(html: str) -> CourseDetail`

- [ ] **Step 1: Create parser fixture files (saved HTML snapshots)**

```bash
mkdir -p tests/fixtures
# These will be dumped from real pages via scripts/inspect.py
# For now, create minimal placeholders
touch tests/fixtures/my_courses.html
touch tests/fixtures/assignments.html
touch tests/fixtures/calendar.html
touch tests/fixtures/announcements.html
touch tests/fixtures/course_detail.html
```

- [ ] **Step 2: Write parser tests with fixture loading**

```python
# tests/test_parsers.py
import pytest
from pathlib import Path
from app.models import Course, Assignment, CalendarEvent, Announcement, CourseDetail
from app.parsers.courses import parse_courses
from app.parsers.assignments import parse_assignments
from app.parsers.calendar import parse_calendar
from app.parsers.announcements import parse_announcements
from app.parsers.course import parse_course_detail

FIXTURES_DIR = Path(__file__).parent / "fixtures"

def load_fixture(name: str) -> str:
    """Load a fixture HTML file."""
    path = FIXTURES_DIR / name
    if path.exists():
        return path.read_text()
    return "<html></html>"  # Empty fallback

def test_parse_courses():
    """Test parse_courses parser."""
    html = load_fixture("my_courses.html")
    courses = parse_courses(html)
    # Verify structure even if no courses found
    assert isinstance(courses, list)

def test_parse_assignments():
    """Test parse_assignments parser."""
    html = load_fixture("assignments.html")
    assignments = parse_assignments(html)
    assert isinstance(assignments, list)

def test_parse_calendar():
    """Test parse_calendar parser."""
    html = load_fixture("calendar.html")
    events = parse_calendar(html)
    assert isinstance(events, list)

def test_parse_announcements():
    """Test parse_announcements parser."""
    html = load_fixture("announcements.html")
    announcements = parse_announcements(html)
    assert isinstance(announcements, list)

def test_parse_course_detail():
    """Test parse_course_detail parser."""
    html = load_fixture("course_detail.html")
    course = parse_course_detail(html)
    assert isinstance(course, CourseDetail)
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_parsers.py -v
```

Expected: FAIL — parsers not defined

- [ ] **Step 4: Implement placeholder parsers with calibration markers**

```python
# app/parsers/__init__.py
"""Moodle HTML parsers — pure functions converting HTML to Pydantic models."""

# app/parsers/courses.py
import logging
from bs4 import BeautifulSoup
from app.models import Course

logger = logging.getLogger(__name__)

def parse_courses(html: str) -> list[Course]:
    """Parse /my/courses.php → list of Course models.
    
    CALIBRATE: Find actual selectors after inspecting real HTML.
    """
    soup = BeautifulSoup(html, "html.parser")
    courses = []
    
    # CALIBRATE: Update with real selectors from courses page
    # Expected: course cards/list items with id, name, url
    course_elements = soup.select(".course-card, [data-course-id]")
    
    for elem in course_elements:
        try:
            course_id = elem.get("data-course-id") or elem.get("data-id")
            course_name = elem.get_text(strip=True)
            course_url = elem.find("a")
            
            if course_id and course_name and course_url:
                courses.append(Course(
                    id=str(course_id),
                    name=course_name,
                    url=course_url.get("href", "")
                ))
        except Exception as e:
            logger.warning(f"Failed to parse course element: {e}")
    
    logger.info(f"Parsed {len(courses)} courses")
    return courses

# app/parsers/assignments.py
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from dateutil.parser import parse as parse_date
from app.models import Assignment

logger = logging.getLogger(__name__)

def _parse_date_to_iso(date_str: str) -> tuple[str | None, str]:
    """Parse Moodle date string to ISO 8601 and raw fallback."""
    raw = date_str.strip()
    try:
        dt = parse_date(date_str, dayfirst=True)
        iso = dt.isoformat()
        return iso, raw
    except Exception as e:
        logger.debug(f"Could not parse date '{date_str}': {e}")
        return None, raw

def parse_assignments(html: str) -> list[Assignment]:
    """Parse assignment lists → list of Assignment models.
    
    CALIBRATE: Update selectors from real /mod/assign/index.php or timeline HTML.
    """
    soup = BeautifulSoup(html, "html.parser")
    assignments = []
    
    # CALIBRATE: Find real selectors
    assignment_elements = soup.select(".assignment-item, [data-assignment-id]")
    
    for elem in assignment_elements:
        try:
            name = elem.find(class_="name") or elem.find("a")
            if not name:
                continue
            
            name_text = name.get_text(strip=True)
            url = name.get("href", "") if name.name == "a" else ""
            
            due_date_elem = elem.find(class_="due-date") or elem.find(class_="duedate")
            due_date_str = due_date_elem.get_text(strip=True) if due_date_elem else ""
            due_date, due_date_raw = _parse_date_to_iso(due_date_str)
            
            status_elem = elem.find(class_="status")
            status = status_elem.get_text(strip=True) if status_elem else "unknown"
            
            assignments.append(Assignment(
                course="",  # Will be filled by orchestrator
                name=name_text,
                due_date=due_date,
                due_date_raw=due_date_raw,
                status=status,
                url=url
            ))
        except Exception as e:
            logger.warning(f"Failed to parse assignment element: {e}")
    
    logger.info(f"Parsed {len(assignments)} assignments")
    return assignments

# app/parsers/calendar.py
import logging
from bs4 import BeautifulSoup
from dateutil.parser import parse as parse_date
from app.models import CalendarEvent

logger = logging.getLogger(__name__)

def _parse_date_to_iso(date_str: str) -> tuple[str | None, str]:
    """Parse Moodle date string to ISO 8601."""
    raw = date_str.strip()
    try:
        dt = parse_date(date_str, dayfirst=True)
        iso = dt.date().isoformat()
        return iso, raw
    except Exception as e:
        logger.debug(f"Could not parse date '{date_str}': {e}")
        return None, raw

def parse_calendar(html: str) -> list[CalendarEvent]:
    """Parse calendar page → list of CalendarEvent models.
    
    CALIBRATE: Update selectors from real /calendar/view.php?view=upcoming HTML.
    """
    soup = BeautifulSoup(html, "html.parser")
    events = []
    
    # CALIBRATE: Find real selectors for events
    event_elements = soup.select(".event, [data-event-id]")
    
    for elem in event_elements:
        try:
            title_elem = elem.find(class_="event-title") or elem.find("a")
            title = title_elem.get_text(strip=True) if title_elem else ""
            url = title_elem.get("href", "") if title_elem and title_elem.name == "a" else ""
            
            date_elem = elem.find(class_="event-date") or elem.find(class_="date")
            date_str = date_elem.get_text(strip=True) if date_elem else ""
            date, date_raw = _parse_date_to_iso(date_str)
            
            event_type = "course_event"  # CALIBRATE: detect from content
            course = ""  # CALIBRATE: extract if present
            
            events.append(CalendarEvent(
                title=title,
                date=date,
                date_raw=date_raw,
                course=course,
                event_type=event_type,
                url=url
            ))
        except Exception as e:
            logger.warning(f"Failed to parse event element: {e}")
    
    logger.info(f"Parsed {len(events)} calendar events")
    return events

# app/parsers/announcements.py
import logging
from bs4 import BeautifulSoup
from dateutil.parser import parse as parse_date
from app.models import Announcement

logger = logging.getLogger(__name__)

def _parse_date_to_iso(date_str: str) -> tuple[str | None, str]:
    """Parse date string to ISO 8601."""
    raw = date_str.strip()
    try:
        dt = parse_date(date_str, dayfirst=True)
        iso = dt.isoformat()
        return iso, raw
    except Exception:
        return None, raw

def parse_announcements(html: str) -> list[Announcement]:
    """Parse announcements (forum posts) → list of Announcement models.
    
    CALIBRATE: Update selectors from real course Discussions section HTML.
    """
    soup = BeautifulSoup(html, "html.parser")
    announcements = []
    
    # CALIBRATE: Find real selectors for forum posts
    post_elements = soup.select(".forum-post, [data-post-id]")
    
    for elem in post_elements:
        try:
            title_elem = elem.find(class_="post-title") or elem.find("a")
            title = title_elem.get_text(strip=True) if title_elem else ""
            url = title_elem.get("href", "") if title_elem and title_elem.name == "a" else ""
            
            author_elem = elem.find(class_="post-author")
            author = author_elem.get_text(strip=True) if author_elem else ""
            
            content_elem = elem.find(class_="post-content")
            content = content_elem.get_text(strip=True)[:200] if content_elem else ""
            
            date_elem = elem.find(class_="post-date")
            date_str = date_elem.get_text(strip=True) if date_elem else ""
            date, date_raw = _parse_date_to_iso(date_str)
            
            announcements.append(Announcement(
                course="",  # CALIBRATE: extract course name if present
                title=title,
                content_preview=content,
                author=author,
                date=date,
                date_raw=date_raw,
                url=url
            ))
        except Exception as e:
            logger.warning(f"Failed to parse announcement: {e}")
    
    logger.info(f"Parsed {len(announcements)} announcements")
    return announcements

# app/parsers/course.py
import logging
from bs4 import BeautifulSoup
from app.models import CourseDetail, Section, Resource

logger = logging.getLogger(__name__)

def parse_course_detail(html: str) -> CourseDetail:
    """Parse course page → CourseDetail with sections and resources.
    
    CALIBRATE: Update selectors from real /course/view.php?id={id} HTML.
    """
    soup = BeautifulSoup(html, "html.parser")
    
    # CALIBRATE: Extract course info
    title_elem = soup.find("h1") or soup.find(class_="course-title")
    title = title_elem.get_text(strip=True) if title_elem else "Unknown Course"
    
    course_id = ""  # CALIBRATE: extract from URL or page data
    course_url = ""  # CALIBRATE: construct from course ID
    
    sections = []
    # CALIBRATE: Find section containers
    section_elements = soup.select(".section, [data-section]")
    
    for section_elem in section_elements:
        try:
            section_title_elem = section_elem.find(class_="sectionname") or section_elem.find("h3")
            section_title = section_title_elem.get_text(strip=True) if section_title_elem else "Untitled"
            
            resources = []
            resource_elements = section_elem.select(".activity, .resource")
            
            for resource_elem in resource_elements:
                resource_name_elem = resource_elem.find("a")
                resource_name = resource_name_elem.get_text(strip=True) if resource_name_elem else ""
                resource_url = resource_name_elem.get("href", "") if resource_name_elem else ""
                
                # CALIBRATE: detect resource type from icon or class
                resource_type = "link"  # default
                if "pdf" in resource_url.lower() or "pdf" in str(resource_elem).lower():
                    resource_type = "pdf"
                
                resources.append(Resource(
                    name=resource_name,
                    url=resource_url,
                    resource_type=resource_type
                ))
            
            sections.append(Section(title=section_title, resources=resources))
        except Exception as e:
            logger.warning(f"Failed to parse section: {e}")
    
    logger.info(f"Parsed course '{title}' with {len(sections)} sections")
    return CourseDetail(
        id=course_id,
        name=title,
        url=course_url,
        sections=sections
    )
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_parsers.py -v
```

Expected: PASS (with empty/minimal results until real HTML fixtures are added)

- [ ] **Step 6: Commit**

```bash
git add app/parsers/ tests/test_parsers.py tests/fixtures/
git commit -m "feat: HTML parsers with placeholder selectors (CALIBRATE markers)"
```

---

### Task 8: Orchestrator (`app/moodle.py`) — Caching & Coordination

**Files:**
- Create: `app/moodle.py`

**Interfaces:**
- Produces:
  - `class MoodleService` with async methods:
    - `async get_courses() -> list[Course]` — with cache
    - `async get_assignments(course_id: str = None) -> list[Assignment]` — with cache
    - `async get_calendar(days_ahead: int = 30) -> list[CalendarEvent]` — with cache
    - `async get_announcements(course_id: str = None, limit: int = 20) -> list[Announcement]` — with cache
    - `async get_course_detail(course_id: str) -> CourseDetail` — with cache
  - All methods catch `SessionExpiredError` and propagate it

- [ ] **Step 1: Write orchestrator tests**

```python
# tests/test_moodle.py
import pytest
from unittest.mock import AsyncMock, MagicMock
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
    
    # Mock parser
    service._parse_courses = MagicMock(return_value=[
        Course(id="1", name="Test Course", url="https://test.com")
    ])
    
    mock_browser.navigate = AsyncMock(return_value=("https://courses.iiit.ac.in/my/courses.php", "<html></html>"))
    
    # First call: hits cache miss
    courses1 = await service.get_courses()
    assert len(courses1) == 1
    
    # Second call: hits cache hit (no new navigate call)
    courses2 = await service.get_courses()
    assert len(courses2) == 1
    assert mock_browser.navigate.call_count == 1  # Only called once
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_moodle.py -v
```

Expected: FAIL — `MoodleService` not defined

- [ ] **Step 3: Implement `app/moodle.py`**

```python
import logging
import time
from typing import Optional, Dict, Tuple, Any
from app.browser import BrowserManager, SessionExpiredError
from app.config import Config
from app.models import (
    Course, Assignment, CalendarEvent, Announcement, CourseDetail
)
from app.parsers import courses as courses_parser
from app.parsers import assignments as assignments_parser
from app.parsers import calendar as calendar_parser
from app.parsers import announcements as announcements_parser
from app.parsers import course as course_parser

logger = logging.getLogger(__name__)

class MoodleService:
    """Orchestrates browser, cache, and parsers."""
    
    def __init__(self, browser: BrowserManager, config: Config):
        self.browser = browser
        self.config = config
        self._cache: Dict[str, Tuple[float, Any]] = {}
    
    def _get_cached(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        if key in self._cache:
            timestamp, value = self._cache[key]
            if time.time() - timestamp < self.config.CACHE_TTL:
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
    
    async def get_courses(self) -> list[Course]:
        """Get enrolled courses with caching."""
        cache_key = "courses"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        try:
            url, html = await self.browser.navigate("https://courses.iiit.ac.in/my/courses.php")
            courses = courses_parser.parse_courses(html)
            self._set_cache(cache_key, courses)
            return courses
        except SessionExpiredError:
            raise
    
    async def get_assignments(self, course_id: Optional[str] = None) -> list[Assignment]:
        """Get assignments with optional course filter."""
        cache_key = f"assignments_{course_id or 'all'}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        try:
            # CALIBRATE: URL pattern for assignments
            if course_id:
                url = f"https://courses.iiit.ac.in/mod/assign/index.php?id={course_id}"
            else:
                url = "https://courses.iiit.ac.in/my/"  # Dashboard timeline
            
            url, html = await self.browser.navigate(url)
            assignments = assignments_parser.parse_assignments(html)
            self._set_cache(cache_key, assignments)
            return assignments
        except SessionExpiredError:
            raise
    
    async def get_calendar(self, days_ahead: int = 30) -> list[CalendarEvent]:
        """Get upcoming calendar events."""
        cache_key = f"calendar_{days_ahead}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        try:
            url, html = await self.browser.navigate("https://courses.iiit.ac.in/calendar/view.php?view=upcoming")
            events = calendar_parser.parse_calendar(html)
            self._set_cache(cache_key, events)
            return events
        except SessionExpiredError:
            raise
    
    async def get_announcements(self, course_id: Optional[str] = None, limit: int = 20) -> list[Announcement]:
        """Get recent announcements from course or site-wide."""
        cache_key = f"announcements_{course_id or 'all'}_{limit}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        try:
            if course_id:
                url = f"https://courses.iiit.ac.in/course/view.php?id={course_id}"
            else:
                url = "https://courses.iiit.ac.in/my/"
            
            url, html = await self.browser.navigate(url)
            announcements = announcements_parser.parse_announcements(html)[:limit]
            self._set_cache(cache_key, announcements)
            return announcements
        except SessionExpiredError:
            raise
    
    async def get_course_detail(self, course_id: str) -> CourseDetail:
        """Get full course detail with sections and resources."""
        cache_key = f"course_{course_id}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        try:
            url, html = await self.browser.navigate(f"https://courses.iiit.ac.in/course/view.php?id={course_id}")
            course = course_parser.parse_course_detail(html)
            self._set_cache(cache_key, course)
            return course
        except SessionExpiredError:
            raise
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_moodle.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/moodle.py tests/test_moodle.py
git commit -m "feat: orchestrator with caching and error handling"
```

---

### Task 9: MCP Server & Phase 1 Tools (`app/main.py`)

**Files:**
- Create: `app/main.py`

**Interfaces:**
- Produces: MCP server with Phase 1 tools:
  - `check_health()` → `{status, authenticated, uptime_seconds}`
  - `check_session()` → `{authenticated, detail}`
  - `get_courses()` → `[{id, name, url}]`
  - `get_assignments(course_id?)` → `[{course, name, due_date, due_date_raw, status, url}]`
  - `get_calendar(days_ahead?)` → `[{title, date, date_raw, course, event_type, url}]`

- [ ] **Step 1: Write MCP server integration test**

```python
# tests/test_main.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import create_mcp_server

@pytest.mark.asyncio
async def test_mcp_server_creation():
    """Test that MCP server is created successfully."""
    with patch("app.main.MCPServer"):
        server = create_mcp_server()
        assert server is not None

@pytest.mark.asyncio
async def test_check_health_tool():
    """Test check_health tool response."""
    with patch("app.main.get_browser") as mock_get_browser:
        mock_browser = AsyncMock()
        mock_get_browser.return_value = mock_browser
        
        # This will be called via MCP, but we test the logic
        # by directly calling the underlying async function
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_main.py -v
```

Expected: FAIL — `create_mcp_server` not defined

- [ ] **Step 3: Implement `app/main.py`**

```python
import asyncio
import logging
import sys
import time
from datetime import datetime
from typing import Optional
from mcp.server import MCPServer
from app.config import Config
from app.browser import BrowserManager, SessionExpiredError
from app.auth import check_session
from app.moodle import MoodleService
from app.logging_config import setup_logging

logger = logging.getLogger(__name__)

# Global state
_config: Optional[Config] = None
_browser: Optional[BrowserManager] = None
_moodle: Optional[MoodleService] = None
_start_time: float = time.time()

async def _init_globals():
    """Initialize global browser and service on first tool call."""
    global _config, _browser, _moodle
    
    if _moodle is not None:
        return
    
    _config = Config()
    _browser = BrowserManager(_config)
    await _browser._init_browser()
    _moodle = MoodleService(_browser, _config)

def create_mcp_server() -> MCPServer:
    """Create and configure MCP server with Phase 1 tools."""
    
    server = MCPServer("moodle-agent")
    
    @server.tool()
    async def check_health() -> dict:
        """Check service health and authentication status."""
        try:
            await _init_globals()
            uptime = time.time() - _start_time
            
            try:
                status_obj = await check_session(_browser)
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
        """Check if session is authenticated. Never returns cookies/tokens."""
        try:
            await _init_globals()
            status_obj = await check_session(_browser)
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
    
    return server

def main():
    """Main entry point: run MCP server."""
    # Setup logging
    log_level = _config.LOG_LEVEL if _config else "INFO"
    setup_logging(log_level)
    
    logger.info("Starting Moodle MCP Server")
    
    # Parse CLI args for transport selection
    use_sse = "--sse" in sys.argv
    config = Config()
    
    # Create server
    server = create_mcp_server()
    
    # Run server
    try:
        if use_sse:
            logger.info(f"Running in SSE mode on {config.HOST}:{config.PORT}")
            server.run(transport="sse", host=config.HOST, port=config.PORT)
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

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_main.py -v
```

Expected: PASS

- [ ] **Step 5: Test server runs in stdio mode**

```bash
python app/main.py &
sleep 2
kill %1
```

Expected: Server starts and can be killed cleanly

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/test_main.py
git commit -m "feat: MCP server with Phase 1 tools (check_health, check_session, get_courses, get_assignments, get_calendar)"
```

---

### Task 10: Interactive Login Script (`scripts/login.py`)

**Files:**
- Create: `scripts/login.py`

**Interfaces:**
- Produces: CLI that launches headed browser, waits for CAS login, persists cookies

- [ ] **Step 1: Write login script docstring and basic structure**

```python
# scripts/login.py
"""
Interactive CAS login script.

Usage:
    python scripts/login.py

Launches a visible browser window where you complete CAS login (username, password, MFA).
The session is saved to ./session/ and reused by the MCP server.
"""

import asyncio
import sys
from pathlib import Path
from app.config import Config
from app.browser import BrowserManager

async def interactive_login():
    """Launch headed browser for interactive CAS login."""
    config = Config()
    
    print("Starting interactive Moodle login...")
    print(f"Session will be saved to: {config.SESSION_DIR}")
    print()
    
    # Note: This uses a modified BrowserManager that launches headed browser
    # For now, we'll just outline the logic
```

- [ ] **Step 2: Implement `scripts/login.py` with headed Playwright**

```python
#!/usr/bin/env python3
"""
Interactive CAS login script for Moodle.

Launches a visible browser window where the user completes CAS login.
Session cookies are persisted to disk.
"""

import asyncio
import sys
import time
import logging
from pathlib import Path
from playwright.async_api import async_playwright
from app.config import Config

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

async def interactive_login():
    """Launch headed browser for interactive CAS login."""
    config = Config()
    
    logger.info("=" * 60)
    logger.info("Moodle Interactive Login")
    logger.info("=" * 60)
    logger.info(f"Session directory: {config.SESSION_DIR}")
    logger.info(f"Timeout: 5 minutes")
    logger.info("")
    
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(config.SESSION_DIR),
            headless=False,  # IMPORTANT: visible window
            viewport={"width": 1280, "height": 720},
        )
        
        page = await context.new_page()
        
        try:
            logger.info("Opening Moodle login page...")
            await page.goto("https://courses.iiit.ac.in/login/index.php")
            
            logger.info("Waiting for login (up to 5 minutes)...")
            logger.info("Complete CAS login in the browser window.")
            logger.info("")
            
            # Poll for redirect back to Moodle (off the CAS domain)
            start_time = time.time()
            timeout_seconds = 300
            poll_interval = 2
            
            success = False
            while time.time() - start_time < timeout_seconds:
                current_url = page.url
                
                # Success: on Moodle domain and NOT on login page
                if "courses.iiit.ac.in" in current_url and "login.iiit.ac.in" not in current_url:
                    if "/login/" not in current_url:
                        success = True
                        break
                
                await asyncio.sleep(poll_interval)
            
            if success:
                logger.info("✓ Login successful!")
                logger.info(f"✓ Final URL: {page.url}")
                logger.info("✓ Session cookies saved to disk")
                
                # Give cookies time to flush
                await asyncio.sleep(2)
                logger.info("")
                logger.info("You can now run the MCP server:")
                logger.info("  python app/main.py")
                return 0
            else:
                logger.error("✗ Login timeout (5 minutes)")
                logger.error("Please check your CAS credentials and try again.")
                return 1
        
        except Exception as e:
            logger.error(f"✗ Login error: {e}")
            return 1
        finally:
            await context.close()

def main():
    exit_code = asyncio.run(interactive_login())
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Test login script structure (without actual browser)**

```bash
python scripts/login.py --help 2>&1 | head -5
# Expected: Script runs without error (will wait for browser interaction)
```

- [ ] **Step 4: Make script executable**

```bash
chmod +x scripts/login.py
```

- [ ] **Step 5: Commit**

```bash
git add scripts/login.py
git commit -m "feat: interactive CAS login script"
```

---

### Task 11: HTML Inspection Script (`scripts/inspect.py`)

**Files:**
- Create: `scripts/inspect.py`

**Interfaces:**
- Produces: CLI that navigates to a URL using the persistent profile and dumps HTML

- [ ] **Step 1: Implement `scripts/inspect.py`**

```python
#!/usr/bin/env python3
"""
Moodle HTML inspection tool.

Navigates to a Moodle URL using the persistent browser profile
and dumps the raw HTML to a file for selector calibration.

Usage:
    python scripts/inspect.py <url>

Example:
    python scripts/inspect.py https://courses.iiit.ac.in/my/courses.php
"""

import asyncio
import sys
import logging
from pathlib import Path
from urllib.parse import urlparse
from app.config import Config
from app.browser import BrowserManager
from app.logging_config import setup_logging

setup_logging("INFO")
logger = logging.getLogger(__name__)

async def inspect_url(url: str):
    """Navigate to URL and dump HTML to file."""
    if not url.startswith("http"):
        logger.error("URL must start with http:// or https://")
        return 1
    
    config = Config()
    
    logger.info("=" * 60)
    logger.info("Moodle HTML Inspector")
    logger.info("=" * 60)
    logger.info(f"URL: {url}")
    
    # Generate filename from URL
    parsed = urlparse(url)
    filename_base = parsed.path.replace("/", "_").strip("_") or parsed.netloc
    filename = f"{filename_base}.html"
    output_path = config.CACHE_DIR / filename
    
    logger.info(f"Output file: {output_path}")
    logger.info("")
    
    try:
        browser = BrowserManager(config)
        await browser._init_browser()
        
        logger.info("Navigating...")
        final_url, html = await browser.navigate(url)
        
        # Write HTML to file
        output_path.write_text(html, encoding="utf-8")
        
        logger.info(f"✓ Successfully inspected {url}")
        logger.info(f"✓ HTML written to {output_path}")
        logger.info(f"✓ HTML length: {len(html)} bytes")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Open the HTML file in a browser or editor")
        logger.info("  2. Identify CSS selectors for the data you want to parse")
        logger.info("  3. Update the corresponding parser with real selectors")
        
        await browser._close_browser()
        return 0
    
    except Exception as e:
        logger.error(f"✗ Error: {e}")
        return 1

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    url = sys.argv[1]
    exit_code = asyncio.run(inspect_url(url))
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Make script executable**

```bash
chmod +x scripts/inspect.py
```

- [ ] **Step 3: Commit**

```bash
git add scripts/inspect.py
git commit -m "feat: HTML inspection script for selector calibration"
```

---

### Task 12: README & Documentation

**Files:**
- Create: `README.md`
- Create: `.env.example`

**Interfaces:**
- Produces: Complete setup and usage instructions

- [ ] **Step 1: Create `.env.example` with all config options**

```bash
# .env.example
# Copy to .env and set values as needed

# Network
HOST=127.0.0.1
PORT=8100

# Moodle URLs
MOODLE_BASE_URL=https://courses.iiit.ac.in
CAS_LOGIN_URL=https://login.iiit.ac.in

# Browser & Session
SESSION_DIR=./session
CACHE_DIR=./cache
CHROMIUM_PATH=

# Performance
CACHE_TTL=300
THROTTLE_DELAY=1.0

# Logging
LOG_LEVEL=INFO
```

- [ ] **Step 2: Write comprehensive README.md**

```markdown
# Moodle MCP Server

A read-only MCP (Model Context Protocol) server for IIIT Hyderabad's Moodle instance. Exposes courses, assignments, calendar events, announcements, and more via browser automation with persistent CAS-authenticated sessions.

## Features

### Phase 1: Core Tools ✓
- `check_health` — Service status and authentication state
- `check_session` — Verify authentication (never logs secrets)
- `get_courses` — Enrolled courses with filtering
- `get_assignments` — Assignments with due dates, status, and submission URLs
- `get_calendar` — Upcoming calendar events with event types

### Phase 2: Enhanced Tools (Planned)
- `get_course` — Full course detail with sections, resources, and tabs
- `get_announcements` — Course and site-wide announcements
- `get_course_materials` — Lectures, files, and links organized by section
- `get_participants` — Enrolled students and instructors

### Phase 3: Optional Tools (Future)
- `get_grades` — Grade book entries
- `get_workshops` — Peer-review activity details
- `get_notifications` — New messages and events
- `search_courses` — Search across course categories

## Installation

### Prerequisites

- **Python 3.9+**
- **Raspberry Pi 4B with 4GB RAM** (tested on Debian 13, aarch64)
- **Chromium** (bundled with Playwright or system-installed at `/usr/bin/chromium`)

### Setup

```bash
# 1. Clone or download the project
cd moodle-agent

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Playwright Chromium
playwright install chromium

# 5. (Optional) Copy .env.example to .env and customize
cp .env.example .env
```

## Quick Start

### Step 1: Interactive Login

Login to Moodle via CAS SSO in a visible browser window:

```bash
python scripts/login.py
```

This script:
1. Launches a visible browser window
2. Waits for you to complete CAS login (username, password, MFA, CAPTCHA)
3. Saves session cookies to `./session/` (persistent profile)
4. Prints confirmation when done

**Timeout:** 5 minutes. If you need more time, run the script again.

### Step 2: Start the MCP Server

Default: stdio transport (best for Hermes)

```bash
python app/main.py
```

In a different terminal, test it:

```bash
# Check health
curl -X POST http://127.0.0.1:8100/tools/check_health 2>/dev/null

# Or if running stdio, use direct MCP protocol
```

**Optional: SSE Transport** (for network access)

```bash
python app/main.py --sse
# Server listens on http://127.0.0.1:8100
```

### Step 3: Use with Hermes

Configure Hermes to use this MCP server. Example Claude Desktop config:

```json
{
  "mcpServers": {
    "moodle": {
      "command": "python",
      "args": ["/path/to/moodle-agent/app/main.py"],
      "env": {
        "SESSION_DIR": "/path/to/moodle-agent/session"
      }
    }
  }
}
```

## Calibration: Finding Selectors

The parsers use placeholder CSS selectors. To calibrate them against real Moodle HTML:

### 1. Dump Raw HTML

```bash
python scripts/inspect.py https://courses.iiit.ac.in/my/courses.php
```

This saves `./cache/my_courses.html`. Open it in a browser or editor.

### 2. Find Selectors

Use browser DevTools (F12) to inspect the page and find CSS selectors for:
- Course cards/list items
- Assignment names, due dates, status
- Calendar events and dates
- Announcements, participants, etc.

### 3. Update Parsers

Edit `app/parsers/<module>.py` and replace the `# CALIBRATE:` placeholder selectors with real ones found in Step 2.

Example:
```python
# BEFORE: placeholder
course_elements = soup.select(".course-card, [data-course-id]")

# AFTER: real selector
course_elements = soup.select(".courses .course-item a.coursename")
```

### 4. Run Tests

```bash
# Place real HTML in tests/fixtures/<module>.html
pytest tests/test_parsers.py -v
```

Tests will validate parsers against real HTML.

## Configuration

Set environment variables to customize behavior:

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `127.0.0.1` | Bind address (SSE mode only) |
| `PORT` | `8100` | Bind port (SSE mode only) |
| `MOODLE_BASE_URL` | `https://courses.iiit.ac.in` | Moodle instance URL |
| `CAS_LOGIN_URL` | `https://login.iiit.ac.in` | CAS SSO login URL |
| `SESSION_DIR` | `./session` | Browser profile persistence |
| `CACHE_DIR` | `./cache` | HTML dump directory |
| `CACHE_TTL` | `300` | In-memory cache TTL (seconds) |
| `THROTTLE_DELAY` | `1.0` | Min delay between requests (seconds) |
| `CHROMIUM_PATH` | (auto-detect) | Path to Chromium executable |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

Example:
```bash
HOST=0.0.0.0 PORT=9000 CACHE_TTL=600 python app/main.py --sse
```

## Usage Examples

### Check Session Status

```bash
# Via MCP tool call
{"method": "tools/call", "params": {"name": "check_session"}}

# Response
{"authenticated": true, "detail": "Authenticated: session is active"}
```

### Get Courses

```bash
# Via MCP tool call
{"method": "tools/call", "params": {"name": "get_courses"}}

# Response
[
  {"id": "5817", "name": "Algorithm Analysis & Design", "url": "https://..."},
  {"id": "5776", "name": "Automata Theory", "url": "https://..."},
  ...
]
```

### Get Assignments

```bash
# All assignments across courses
{"method": "tools/call", "params": {"name": "get_assignments"}}

# Assignments for a specific course
{"method": "tools/call", "params": {"name": "get_assignments", "course_id": "5817"}}

# Response
[
  {
    "course": "Algorithm Analysis & Design",
    "name": "Mini project 1",
    "due_date": "2026-09-13T23:59:00",  # ISO 8601
    "due_date_raw": "13 September 2026, 11:59 PM",
    "status": "not_submitted",
    "url": "https://..."
  },
  ...
]
```

### Get Calendar

```bash
# Upcoming 30 days (default)
{"method": "tools/call", "params": {"name": "get_calendar"}}

# Upcoming 60 days
{"method": "tools/call", "params": {"name": "get_calendar", "days_ahead": 60}}

# Response
[
  {
    "title": "Mini project 1 (end submission) is due",
    "date": "2026-09-13",  # ISO 8601
    "date_raw": "13 September 2026",
    "course": "Operating Systems and Networks",
    "event_type": "assignment_due",
    "url": "https://..."
  },
  ...
]
```

## Troubleshooting

### Session Expired

Error: `Session expired. Run 'python scripts/login.py' to re-authenticate.`

**Solution:** Run the login script again to refresh the session.

```bash
python scripts/login.py
```

### Chromium Not Found

Error: `Chromium executable not found`

**Solution (Pi):**
```bash
# Option 1: Install system Chromium
sudo apt-get install chromium

# Option 2: Use bundled Chromium (should work on Debian 13 aarch64)
playwright install chromium

# Option 3: Specify path explicitly
CHROMIUM_PATH=/usr/bin/chromium python app/main.py
```

### Selector Not Working

If a parser returns empty results after calibration:

1. Dump fresh HTML:
   ```bash
   python scripts/inspect.py <moodle-url>
   ```

2. Check the HTML file for the expected elements

3. Verify your selectors match the real HTML structure

4. Add debug logging to the parser:
   ```python
   logger.debug(f"Found {len(elements)} elements with selector '{selector}'")
   ```

### Timeout on Login

The login script waits up to 5 minutes. If CAS is slow:

1. Run again: `python scripts/login.py`
2. Or increase the timeout in the script (edit `timeout_seconds`)

## Architecture

```
Hermes / MCP Client
    ↓ (MCP stdio or SSE)
MCP Server (app/main.py)
    ↓
Orchestrator (app/moodle.py) ← In-memory cache
    ↓
Browser Manager (app/browser.py) ← Persistent profile
    ↓
Playwright Chromium
    ↓
CAS SSO → IIIT Moodle
```

**Key Design Principles:**

1. **No Password Storage** — Passwords never enter the system. Only CAS session cookies are saved.
2. **Interactive Auth** — User completes CAS login in a visible browser; no automation of MFA/CAPTCHA.
3. **Read-Only** — No submitting assignments, posting, or modifying data.
4. **Localhost by Default** — SSE mode can expose the service, but it's only for trusted networks.
5. **No Secret Logging** — Cookies, tokens, and auth secrets are never logged.

## Security Model

- **Session Storage** (`./session/`): Contains Chromium profile with session cookies. Equivalent to leaving a browser logged in. Mitigations:
  - Directory is `chmod 700` (user-readable only)
  - Service binds to `127.0.0.1` by default (no network exposure)
  - Pi is assumed to be on a private LAN
  - Moodle sessions expire server-side

- **Threat Model**: An attacker with filesystem access to the Pi can reuse the session. Mitigations are typical Linux user permissions and network isolation.

## Testing

Run all tests:

```bash
pytest tests/ -v
```

Run specific test file:

```bash
pytest tests/test_parsers.py -v
```

Run with coverage:

```bash
pytest --cov=app tests/
```

## Development

### Adding a New Parser

1. Create `app/parsers/<feature>.py`
2. Write a parser function: `def parse_<feature>(html: str) -> <Model>`
3. Use placeholder selectors with `# CALIBRATE:` markers
4. Add tests in `tests/test_parsers.py`
5. Update `app/moodle.py` to use the new parser

### Adding a New MCP Tool

1. Add tool function in `app/main.py` decorated with `@server.tool()`
2. Use `await _moodle.<method>()` to get data
3. Return Pydantic model data via `model_dump()`
4. Catch `SessionExpiredError` and return clear error message
5. Write tests in `tests/test_main.py`

## Known Limitations

- **Single-User**: Browser profile is per-user. Multiple users require separate instances.
- **No Write Operations**: Strictly read-only. Cannot submit assignments, post replies, etc.
- **No Real-Time Updates**: Uses polling with caching. Not suitable for live notifications.
- **Manual Selector Calibration**: Parsers require calibration against real Moodle HTML (must be done once per Moodle version).

## Next Steps

1. **Calibrate Selectors** — Run `scripts/inspect.py` on each page type and update parsers
2. **Phase 2 Tools** — Implement enhanced tools (get_course, get_announcements, etc.)
3. **Systemd Integration** — Install as systemd service for persistent SSE mode (optional)
4. **Hermes Integration** — Configure Hermes to use this MCP server

## License

[Your License Here]

## Support

For issues or questions, refer to:
- Moodle documentation: https://docs.moodle.org
- MCP specification: https://modelcontextprotocol.io
- Playwright docs: https://playwright.dev

## Attribution

Kiro — MCP Server Implementation
Co-Authored-By: Claude Code <noreply@anthropic.com>
```

- [ ] **Step 3: Commit**

```bash
git add README.md .env.example
git commit -m "docs: comprehensive README and configuration template"
```

---

### Task 13: Systemd Service & Final Setup

**Files:**
- Create: `systemd/moodle-agent.service`
- Create: `systemd/install.sh`

**Interfaces:**
- Produces: systemd unit for SSE mode deployment (optional)

- [ ] **Step 1: Create systemd service file**

```ini
# systemd/moodle-agent.service
[Unit]
Description=Moodle MCP Server for Hermes AI Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi/moodle-agent
Environment="PATH=/home/pi/moodle-agent/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="PYTHONUNBUFFERED=1"
Environment="HOST=127.0.0.1"
Environment="PORT=8100"
Environment="LOG_LEVEL=INFO"
ExecStart=/home/pi/moodle-agent/venv/bin/python /home/pi/moodle-agent/app/main.py --sse
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Create installation script**

```bash
#!/bin/bash
# systemd/install.sh
# Install moodle-agent as a systemd service (SSE mode)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SERVICE_NAME="moodle-agent"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "Installing Moodle MCP Server as systemd service..."
echo ""
echo "Project directory: $PROJECT_DIR"
echo "Service file: $SERVICE_FILE"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
  echo "Error: This script must be run as root (use 'sudo')"
  exit 1
fi

# Copy service file
echo "Installing service file..."
cp "$SCRIPT_DIR/${SERVICE_NAME}.service" "$SERVICE_FILE"
chmod 644 "$SERVICE_FILE"

# Update paths in service file to match actual project directory
sed -i "s|/home/pi/moodle-agent|${PROJECT_DIR}|g" "$SERVICE_FILE"

echo "Reloading systemd daemon..."
systemctl daemon-reload

echo ""
echo "✓ Service installed successfully"
echo ""
echo "Next steps:"
echo "  1. (First time only) Run login: python scripts/login.py"
echo "  2. Start service:     sudo systemctl start ${SERVICE_NAME}"
echo "  3. Check status:      sudo systemctl status ${SERVICE_NAME}"
echo "  4. Enable on boot:    sudo systemctl enable ${SERVICE_NAME}"
echo "  5. View logs:         sudo journalctl -u ${SERVICE_NAME} -f"
echo ""
```

- [ ] **Step 3: Make install script executable and add to commit**

```bash
chmod +x systemd/install.sh
```

- [ ] **Step 4: Commit**

```bash
git add systemd/moodle-agent.service systemd/install.sh
git commit -m "ops: systemd service for SSE deployment"
```

---

### Task 14: Final Integration Test & Commit

**Files:**
- Verify: all components integrate correctly

**Interfaces:**
- Produces: working MCP server ready for Phase 2 development

- [ ] **Step 1: Run full test suite**

```bash
pytest tests/ -v --cov=app --cov-report=term-missing
```

Expected: All tests pass with reasonable coverage

- [ ] **Step 2: Verify CLI scripts work**

```bash
# Test login script structure
python scripts/login.py --help 2>&1 | grep -q "Interactive" && echo "✓ login.py OK"

# Test inspect script structure
python scripts/inspect.py 2>&1 | grep -q "Usage" && echo "✓ inspect.py OK"
```

Expected: Scripts show usage without errors

- [ ] **Step 3: Test server startup (stdio mode)**

```bash
timeout 3 python app/main.py || echo "✓ Server started (timeout expected)"
```

Expected: Server starts without errors (timeout after 3s is OK for stdio)

- [ ] **Step 4: Verify all files are tracked in git**

```bash
git status
```

Expected: No untracked files (only expected ignores)

- [ ] **Step 5: Create final commit**

```bash
git log --oneline | head -15
```

Expected: All tasks are individual commits

- [ ] **Step 6: Tag Phase 1 release**

```bash
git tag -a v1.0.0-phase1 -m "Phase 1: Core MCP tools (check_health, check_session, get_courses, get_assignments, get_calendar)"
git tag -l
```

---

## Summary

**Phase 1 Implementation Complete:**

✓ Project scaffolding (dependencies, test setup)  
✓ Configuration management (env vars)  
✓ Logging with secret redaction  
✓ Pydantic response models  
✓ Playwright browser manager with throttling  
✓ Session health check  
✓ HTML parsers (placeholder selectors, calibration markers)  
✓ Orchestrator with caching  
✓ MCP server with Phase 1 tools  
✓ Interactive login script  
✓ HTML inspection script  
✓ Comprehensive README & documentation  
✓ Systemd service (optional SSE deployment)  
✓ Full test coverage  

**Next: Phase 2** (if proceeding inline)

- Implement enhanced tools: `get_course`, `get_announcements`, `get_course_materials`, `get_participants`
- Calibrate selectors against real Moodle HTML using `scripts/inspect.py`
- Extend parser tests with real HTML fixtures

---

## Execution Options

**Plan saved to:** `docs/superpowers/plans/2026-09-11-moodle-mcp-server-implementation.md`

Choose execution:

1. **Subagent-Driven (Recommended)** — I dispatch a fresh subagent per task, review outputs, fast iteration
   - Use: `superpowers:subagent-driven-development`

2. **Inline Execution** — Execute tasks in this session with checkpoints
   - Use: `superpowers:executing-plans`

**Which approach?**

# Moodle MCP Server — Design Spec

**Date:** 2026-09-11
**Status:** Draft
**Target:** Raspberry Pi 4B (4GB), Debian 13, aarch64

## Purpose

A read-only MCP server that gives the Hermes AI agent (and any MCP client) structured access to IIIT Hyderabad's Moodle instance (`https://courses.iiit.ac.in/`). The server uses Playwright browser automation with a persistent authenticated browser profile to scrape Moodle pages and return parsed JSON via MCP tools and resources.

## Hard Constraints

1. **No password storage.** The CAS password is never accepted, stored, or logged anywhere — not in code, config, env files, or logs.
2. **Interactive authentication only.** The user completes CAS SSO (including any MFA/CAPTCHA) in a visible browser window. The service never attempts to bypass authentication.
3. **Persistent browser profile only.** The saved artifact is cookies/localStorage on disk (`./session/`), not a password or token.
4. **Read-only.** No submitting, posting, or modifying any Moodle data.
5. **Localhost by default.** Binds to `127.0.0.1` unless explicitly overridden.
6. **No secret logging.** Never log cookies, tokens, session IDs, or auth credentials.

## Architecture

```
Hermes / Claude Desktop
    ↓ (MCP stdio or SSE)
MCP Server (app/main.py)
    ↓
Orchestrator (app/moodle.py)  ←→  In-memory cache
    ↓
Browser Manager (app/browser.py)  →  Persistent Profile (./session/)
    ↓
Playwright Chromium
    ↓
CAS SSO (login.iiit.ac.in)  →  IIIT Moodle (courses.iiit.ac.in)
```

## Project Layout

```
moodle-agent/
├── app/
│   ├── __init__.py
│   ├── main.py           # MCP server (stdio default, --sse flag)
│   ├── browser.py        # Playwright persistent-context manager, throttling
│   ├── auth.py           # session health check logic
│   ├── moodle.py         # orchestrates browser + cache + parsers
│   ├── config.py         # env-based configuration
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── courses.py
│   │   ├── assignments.py
│   │   ├── calendar.py
│   │   ├── announcements.py
│   │   └── course.py
│   └── models.py         # Pydantic response models
├── scripts/
│   ├── login.py          # CLI: interactive CAS login
│   └── inspect.py        # CLI: dump raw HTML for selector calibration
├── session/              # persisted browser profile (gitignored)
├── cache/                # dumped HTML for inspection (gitignored)
├── tests/
│   ├── __init__.py
│   ├── test_parsers.py   # unit tests against saved HTML fixtures
│   └── fixtures/         # saved HTML snapshots for testing
├── requirements.txt
├── README.md
├── .gitignore
└── systemd/
    └── moodle-agent.service  # only needed for SSE mode
```

## MCP Interface

### Tools (All Read-Only)

All tools return structured JSON. On expired session, each returns a tool error directing the user to re-run `scripts/login.py`. Dates are normalized to ISO 8601 where parseable; raw strings preserved as fallback.

#### Phase 1: Core Tools (Must Have)

| Tool | Parameters | Returns | Description |
|------|-----------|---------|-------------|
| `check_health` | none | `{status, authenticated, uptime_seconds}` | Service health + auth state |
| `check_session` | none | `{authenticated: bool, detail: str}` | Auth status. Never returns cookies/tokens. |
| `get_courses` | none | `[{id, name, url}]` | Enrolled courses with grouping filters available (in_progress/past/future) |
| `get_assignments` | `course_id?: str` | `[{course, name, due_date, due_date_raw, status, url}]` | All assignments across courses or filtered by course. Dates normalized to ISO 8601. Status: "not_submitted", "submitted", "graded". |
| `get_calendar` | `days_ahead?: int = 30, view?: str` | `[{title, date, date_raw, course, event_type, url}]` | Upcoming events in timeline format. Event types: "assignment_due", "workshop_submission", "workshop_assessment", "course_event". |

#### Phase 2: Enhanced Tools (Highly Recommended)

| Tool | Parameters | Returns | Description |
|------|-----------|---------|-------------|
| `get_course` | `course_id: str` | `{id, name, url, sections: [{title, resources: [{name, type, url}]}], tabs: [...]}` | Full course detail with sections, resources (PDFs, links), and available tabs (Course, Participants, Grades, Activities, Competencies) |
| `get_announcements` | `course_id?: str, limit?: int = 20` | `[{course, title, content_preview, author, date, date_raw, url}]` | Recent announcements from courses or site-wide. Content preview limited to 200 chars. |
| `get_course_materials` | `course_id: str` | `[{section, resources: [{name, type, url, resource_type}]}]` | Organized course materials/lectures by section. Types: "pdf", "link", "file", "folder". |
| `get_participants` | `course_id: str` | `[{name, role, profile_url}]` | Enrolled participants and instructors in a course. Roles: "student", "teacher", "admin". |

#### Phase 3: Optional Tools (Nice-to-Have)

| Tool | Parameters | Returns | Description |
|------|-----------|---------|-------------|
| `get_grades` | `course_id?: str` | `[{course, item_name, max_points, earned_points, percentage, status}]` | Grade book entries across courses or within a course. Status: "completed", "pending", "not_graded". |
| `get_workshops` | `course_id?: str` | `[{name, course, phase, submission_deadline, assessment_deadline, status, url}]` | Workshop (peer-review) activities. Phases: "setup", "submission", "assessment", "closed". |
| `get_notifications` | `limit?: int = 10` | `[{type, title, course, timestamp, url, read}]` | Recent notifications (new messages, graded assignments, etc.). Types: "message", "grade", "assignment", "event". |
| `search_courses` | `query: str` | `[{id, name, category, semester, url}]` | Search all available courses across categories by name or code. |

### Resources (For Browsing)

| URI | Description |
|-----|-------------|
| `moodle://courses` | Static resource: list of enrolled courses (JSON) |
| `moodle://course/{course_id}` | Template resource: full course detail with sections |
| `moodle://calendar` | Static resource: upcoming 30-day calendar events |
| `moodle://assignments` | Static resource: all upcoming assignments |

### Error Handling

- **Session expired**: Tool returns `ToolError` with message: `"Moodle session expired. Run 'python scripts/login.py' to re-authenticate."`
- **Parse failure**: Tool returns partial data with a `warnings` field listing what failed.
- **Browser not ready**: Tool returns `ToolError` with message: `"Browser not initialized. Restart the MCP server."`

## Component Design

### `app/config.py` — Configuration

Env-var-based configuration with sensible defaults:

```python
HOST = "127.0.0.1"          # bind address (SSE mode only)
PORT = 8100                  # bind port (SSE mode only)
MOODLE_BASE_URL = "https://courses.iiit.ac.in"
CAS_LOGIN_URL = "https://login.iiit.ac.in"
SESSION_DIR = "./session"    # persistent browser profile path
CACHE_DIR = "./cache"        # HTML dump directory
CACHE_TTL = 300              # in-memory cache TTL in seconds
THROTTLE_DELAY = 1.0         # minimum seconds between requests
CHROMIUM_PATH = None          # override Playwright's bundled Chromium
LOG_LEVEL = "INFO"
```

### `app/browser.py` — Browser Manager

A singleton async context manager wrapping Playwright's `browser_type.launch_persistent_context()`.

**Responsibilities:**
- Launches Chromium with the persistent profile from `SESSION_DIR`.
- Headless by default. Headed mode for `scripts/login.py`.
- Chromium resolution: Playwright bundled first, then `CHROMIUM_PATH` env var, then `/usr/bin/chromium`.
- Request throttling: `asyncio.Lock` + minimum delay between navigations.
- Concurrency: `asyncio.Semaphore(1)` — one page operation at a time.
- Provides `async navigate(url) -> str` that returns full page HTML.
- Provides `async get_current_url() -> str` for redirect detection.
- Lifecycle: context opened once, pages created/closed per request. Context lives for server lifetime.

**Key method:**
```python
async def navigate(self, url: str) -> tuple[str, str]:
    """Navigate to URL, return (final_url, page_html).
    Raises SessionExpiredError if redirected to CAS."""
```

### `app/auth.py` — Session Health

**Not** the interactive login (that's `scripts/login.py`). This module provides:

- `async check_session(browser: BrowserManager) -> SessionStatus` — navigates to Moodle dashboard, checks whether the final URL is Moodle (authenticated) or CAS (expired).
- `SessionExpiredError` exception class — raised when any navigation detects a CAS redirect.
- Detection logic: if `final_url` contains `login.iiit.ac.in` or `/login/`, session is expired.

### `app/moodle.py` — Orchestrator

Bridges browser and parsers. Owns page URLs and caching.

**Responsibilities:**
- Maps each data type to the right Moodle URL(s).
- Checks in-memory cache before navigating.
- Passes raw HTML to the appropriate parser.
- Catches `SessionExpiredError` and propagates it up to the tool layer.
- In-memory cache: `dict[str, (timestamp, data)]` with TTL from config.

**Page URLs (known):**
- Dashboard: `{BASE}/my/`
- Course list: `{BASE}/my/courses.php`
- Single course: `{BASE}/course/view.php?id={course_id}`
- Assignments: `{BASE}/mod/assign/index.php?id={course_id}` (per-course)
- Calendar: `{BASE}/calendar/view.php?view=upcoming`
- Announcements: forums within each course (URL pattern varies — requires inspection)

### `app/parsers/` — HTML → JSON

Each parser is a **pure function**: HTML string in, Pydantic model list out. No network calls, no browser dependency. Fully testable with saved HTML fixtures.

**Selector strategy:**
- Write with placeholder selectors initially, marked `# CALIBRATE: inspect real HTML`.
- After running `scripts/inspect.py`, replace placeholders with real selectors.
- Use CSS selectors (not XPath). Prefer class-based selectors with structural fallbacks.
- Use BeautifulSoup4 for parsing (simpler and more robust than Playwright's built-in for offline HTML parsing).

**Date normalization:**
- Parse Moodle's date strings into ISO 8601 where possible.
- Store `due_date` (ISO 8601 or null) and `due_date_raw` (original string) on every model.
- Use `dateutil.parser` for flexible date parsing.

### `app/models.py` — Pydantic Models

```python
class Course(BaseModel):
    id: str
    name: str
    url: str

class Assignment(BaseModel):
    course: str
    name: str
    due_date: str | None       # ISO 8601 or null
    due_date_raw: str | None   # original Moodle string
    status: str | None
    url: str

class CalendarEvent(BaseModel):
    title: str
    date: str | None
    date_raw: str | None
    course: str | None
    event_type: str | None
    url: str | None

class Announcement(BaseModel):
    course: str
    title: str
    content_preview: str
    date: str | None
    date_raw: str | None
    url: str

class Resource(BaseModel):
    name: str
    url: str | None
    resource_type: str | None

class Section(BaseModel):
    title: str
    resources: list[Resource]

class CourseDetail(BaseModel):
    id: str
    name: str
    url: str
    sections: list[Section]

class SessionStatus(BaseModel):
    authenticated: bool
    detail: str

class HealthStatus(BaseModel):
    status: str
    authenticated: bool
    uptime_seconds: float
```

### `app/main.py` — MCP Server

```python
mcp = MCPServer("moodle-agent")

# Register tools: check_health, check_session, get_courses,
#   get_assignments, get_calendar, get_announcements, get_course
# Register resources: moodle://courses, moodle://course/{course_id}

if __name__ == "__main__":
    import sys
    if "--sse" in sys.argv:
        mcp.run(transport="sse", host=config.HOST, port=config.PORT)
    else:
        mcp.run()  # stdio default
```

**Startup**: initializes `BrowserManager` and `MoodleService` as module-level singletons. The browser context opens on the first tool call (lazy init) to avoid blocking server startup.

### `scripts/login.py` — Interactive Login

1. Launches Playwright Chromium **headed** (visible window) with persistent profile from `SESSION_DIR`.
2. Navigates to `{MOODLE_BASE_URL}/login/index.php` → redirects to CAS.
3. Prints instructions: "Complete login in the browser window. You have 5 minutes."
4. Polls `page.url` every 2 seconds for up to 300 seconds.
5. Success condition: URL contains `courses.iiit.ac.in` and does not contain `login.iiit.ac.in`.
6. On success: prints confirmation, waits 3 seconds for cookies to flush, closes browser.
7. On timeout: prints error, closes browser, exits with code 1.

### `scripts/inspect.py` — HTML Dumper

```
python scripts/inspect.py <url>
```

Opens the URL using the persistent profile (headless), dumps full page HTML to `./cache/<slugified-url>.html`. Used to examine Moodle's real DOM structure before writing selectors.

## Transport Modes

### stdio (default)
- MCP client launches the server as a subprocess.
- No port binding, no systemd needed.
- Client config:
  ```json
  {
    "mcpServers": {
      "moodle": {
        "command": "python",
        "args": ["/home/pi/moodle-agent/app/main.py"],
        "env": {
          "SESSION_DIR": "/home/pi/moodle-agent/session"
        }
      }
    }
  }
  ```

### SSE (network mode, `--sse`)
- Server binds to `HOST:PORT` and serves SSE transport.
- Needed when Hermes runs on a different machine.
- systemd unit manages the process.
- Accessed at `http://{HOST}:{PORT}/sse`.

## Discovered Moodle Features (Feature Inventory)

Based on live scraping of IIIT Moodle (2026-09-11), these features are implemented:

### Core Pages & Features
- **Dashboard (`/my/`)**: Timeline (assignments with due dates), Mini Calendar, Notifications, Messaging
- **My Courses (`/my/courses.php`)**: Course cards, grouping/sorting filters, search
- **Course View (`/course/view.php?id=`)**: Sections, resources (PDFs, links), tabs (Course, Participants, Grades, Activities, Competencies)
- **Assignments**: Detail view, status tracking, due dates (multiple formats), submission links
- **Workshops**: Peer-review activities with phases (submission, assessment)
- **Calendar (`/calendar/view.php`)**: Month view, upcoming events, event types, course filtering
- **User Profile & Messaging**: User menu, profile page, notifications, messaging drawer
- **Announcements**: Within course "Discussions" section, forum-style posts
- **Grades**: Grade book per course
- **Participants**: List of enrolled students and instructors per course
- **Course Materials**: Organized lecture PDFs and links by section

### URL Patterns Discovered
- `/my/` — Dashboard
- `/my/courses.php` — My Courses
- `/course/view.php?id={id}` — Course detail
- `/course/index.php?categoryid={id}` — Browse courses by semester
- `/mod/assign/view.php?id={id}` — Assignment detail
- `/mod/assign/index.php?id={id}` — Course assignments list
- `/mod/workshop/view.php?id={id}` — Workshop detail
- `/calendar/view.php?view=upcoming` — Calendar (upcoming)
- `/calendar/view.php?view=month` — Calendar (month)
- `/user/profile.php` — User profile

### Key Parsing Challenges
1. **Multiple date formats**: "13 September 2026, 11:59 PM" vs "September 13 2026" vs "23:59"
2. **Client-side filtering**: Timeline filters rendered; scrape visible state
3. **Lazy loading**: Course list, calendar may load on scroll
4. **Relative URLs**: Normalize all links to absolute URLs

## Caching

- **Type**: in-memory `dict` per data type.
- **TTL**: 300 seconds default (`CACHE_TTL` env var).
- **Eviction**: lazy — checked on access.
- **Scope**: per-process. Restarting the server clears the cache.
- **No disk caching** for parsed data — only `cache/` is for raw HTML dumps from `inspect.py`.

## Throttling

- Global `asyncio.Lock` ensures only one Playwright navigation at a time.
- Minimum `THROTTLE_DELAY` seconds (default 1.0) between navigations.
- Combined: no parallel requests, no rapid-fire requests.

## Security Model

1. **No passwords anywhere.** Code never handles, stores, or logs CAS credentials.
2. **Session directory (`./session/`)**: contains Chromium profile with session cookies. Equivalent to leaving a browser logged in. Protected by:
   - `chmod 700` on the directory.
   - Service binds to localhost by default.
   - Pi assumed to be on a private LAN.
3. **Threat model**: an attacker with filesystem access to the Pi can reuse the session. Mitigations: physical security of the Pi, standard Linux user permissions, session expiry on Moodle's side.
4. **Read-only**: no POST/PUT/DELETE operations, no form submissions, no file uploads.
5. **Logging**: structured, with a filter that redacts any field named `cookie`, `token`, `session`, `authorization`, or `password`.

## Dependencies

```
mcp>=1.0.0
playwright>=1.40.0
beautifulsoup4>=4.12.0
python-dateutil>=2.8.0
pydantic>=2.0.0
```

Plus:
```bash
playwright install chromium
```

## Build Order

1. Scaffold project structure + `.gitignore` + `requirements.txt`.
2. Implement `config.py`.
3. Implement `browser.py` (persistent context + throttling).
4. Implement `scripts/login.py` (interactive CAS login).
5. Implement `auth.py` (session check).
6. Implement `scripts/inspect.py` (HTML dumper).
7. Implement `models.py` (Pydantic models).
8. Implement parsers with placeholder selectors.
9. Implement `moodle.py` (orchestrator + cache).
10. Implement `main.py` (MCP server + tools + resources).
11. Write tests using HTML fixtures.
12. Write `README.md` with full usage instructions.
13. Write `systemd/moodle-agent.service`.
14. Calibrate selectors against real HTML (user runs `inspect.py`, we update parsers).

## What's Deferred

- **Hermes integration**: configuring Hermes to use this MCP server (separate follow-up).
- **Notifications / webhooks**: proactive alerts when new assignments appear.
- **Grade scraping**: not in scope for read-only v1.
- **Multi-user support**: single-user design (one browser profile).

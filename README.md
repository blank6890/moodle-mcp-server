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

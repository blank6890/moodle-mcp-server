# 🎓 Moodle MCP Server

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Model Context Protocol](https://img.shields.io/badge/MCP-Protocol-6366F1?style=for-the-badge&logo=anthropic&logoColor=white)](https://modelcontextprotocol.io/)
[![Playwright](https://img.shields.io/badge/Playwright-Automated-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)](https://playwright.dev/)
[![Tests](https://img.shields.io/badge/Tests-41%20Passed-brightgreen?style=for-the-badge&logo=pytest&logoColor=white)](#testing--verification)
[![M8ven Score](https://m8ven.ai/badge/mcp/blank6890/moodle-mcp-server)](https://m8ven.ai/mcp/blank6890/moodle-mcp-server)
[![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](LICENSE)

<p align="center">
  <strong>A high-performance, read-only Model Context Protocol (MCP) server connecting LLMs to Moodle with CAS SSO authentication.</strong>
</p>

<p align="center">
  <a href="#key-features">Key Features</a> •
  <a href="#system-architecture">Architecture</a> •
  <a href="#installation--setup">Installation</a> •
  <a href="#mcp-tools-reference">Tools Reference</a> •
  <a href="#claude-integration">Claude Integration</a> •
  <a href="#configuration">Configuration</a> •
  <a href="#security-model">Security</a>
</p>

</div>

---

## 🌟 Overview

**Moodle MCP Server** empowers AI assistants (like Claude Code, Claude Desktop, Cursor, and custom MCP clients) to seamlessly query course syllabi, assignment deadlines, calendar events, lecture materials, announcements, and participants from **IIIT Hyderabad's Moodle LMS**.

Built with a **hybrid HTTP-first engine**, it delivers sub-50ms query latency via persisted session cookies while maintaining a resilient Playwright fallback for dynamic JavaScript rendering.

```
┌─────────────────┐       MCP (stdio / SSE)       ┌────────────────────────┐
│   Claude Code   │ ◄───────────────────────────► │   Moodle MCP Server    │
│  Claude Desktop │                               │   (FastMCP Engine)     │
└─────────────────┘                               └───────────┬────────────┘
                                                              │
                                     ┌────────────────────────┴────────────────────────┐
                                     ▼                                                 ▼
                          ⚡ Fast HTTP (httpx)                            🎭 Playwright Browser
                          • Cached Cookie Transport                       • Dynamic JS Fallback
                          • Latency < 50ms                                • Interactive CAS SSO
                                     │                                                 │
                                     └────────────────────────┬────────────────────────┘
                                                              ▼
                                                 🏛️ IIIT Moodle Instance
                                                   (courses.iiit.ac.in)
```

---

## ✨ Key Features

- ⚡ **Sub-50ms Latency (Hybrid Engine)** — Requests hit a fast async HTTP transport using authenticated cookie state, falling back to headless Chromium only for dynamic DOM rendering.
- 🔒 **Zero-Password Security** — Passwords and MFA tokens are never requested, stored, or logged. Authentication occurs via interactive CAS SSO in a visible browser window.
- 🛡️ **MCP Safety Annotations** — Complies with the latest MCP specification, flagging all endpoints with `readOnlyHint=True` and `destructiveHint=False`.
- 🧠 **Native Claude Skill Included** — Comes with `.claude/skills/moodle.md` for zero-configuration, natural conversational workflows in Claude Code.
- 📅 **Smart Date & Deadline Normalization** — Automatically normalizes Moodle deadlines into ISO-8601 strings while preserving human-readable relative dates (`Tomorrow, 11:59 PM`).
- 🍓 **Lightweight & Cross-Platform** — Runs effortlessly on Windows, macOS, Linux, and resource-constrained environments like **Raspberry Pi 4B (ARM64)**.
- 🔄 **Multi-Transport Support** — Native support for both `stdio` (CLI / Claude Desktop) and `SSE` (Network / Remote MCP clients).

---

## 🛠️ MCP Tools Reference

The server exposes **9 specialized read-only tools** designed for structured LLM querying:

| Tool | Parameters | Returns | Description |
|:---|:---|:---|:---|
| `check_health` | _None_ | `HealthStatus` | Returns uptime, system health, and current authentication status. |
| `check_session` | _None_ | `SessionStatus` | Verifies CAS authentication state without revealing sensitive tokens. |
| `get_courses` | _None_ | `List[Course]` | Fetches all active and enrolled courses with their names, IDs, and URLs. |
| `get_assignments` | `course_id` _(optional)_ | `List[Assignment]` | Retrieves pending & submitted assignments with deadlines and submission links. |
| `get_calendar` | `days_ahead` _(default: 30)_ | `List[CalendarEvent]` | Fetches upcoming events, submissions, and course milestones from the calendar. |
| `get_course` | `course_id` _(required)_ | `CourseDetail` | Retrieves full course structure, sections, syllabus, and resource lists. |
| `get_course_materials` | `course_id` _(required)_ | `List[Section]` | Extracts organized lectures, PDFs, folders, and external links by topic section. |
| `get_announcements` | `course_id` _(opt)_, `limit` _(opt)_ | `List[Announcement]` | Fetches recent announcements and discussion posts with previews & authors. |
| `get_participants` | `course_id` _(required)_ | `List[Participant]` | Lists enrolled students, teaching assistants, and professors for a course. |

<details>
<summary><strong>🔍 Click to view Data Models Schema</strong></summary>

```python
class Course(BaseModel):
    id: str
    name: str
    url: str

class Assignment(BaseModel):
    course: str
    name: str
    due_date: Optional[str]      # ISO 8601 (e.g. "2026-09-20T23:59:00")
    due_date_raw: str            # Display string (e.g. "Sunday, 20 September, 11:59 PM")
    status: str                  # "submitted" | "not_submitted" | "graded"
    url: str

class CalendarEvent(BaseModel):
    title: str
    date: Optional[str]          # ISO 8601
    date_raw: str
    course: Optional[str]
    event_type: str              # "assignment_due" | "workshop_submission" | "course_event"
    url: Optional[str]
```
</details>

---

## 🚀 Installation & Setup

### 1. Prerequisites

- **Python 3.9+** (Tested up to Python 3.14)
- **Chromium** (Managed automatically via Playwright)
- Compatible with Windows, macOS, Linux, and Raspberry Pi (aarch64)

### 2. Clone & Setup Environment

```bash
# Clone the repository
git clone https://github.com/blank6890/moodle-mcp-server.git
cd moodle-mcp-server

# Create and activate virtual environment
python -m venv venv

# On Linux / macOS:
source venv/bin/activate

# On Windows (PowerShell):
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser binary
playwright install chromium
```

---

## 🔐 Authentication (Interactive CAS Login)

Moodle requires CAS SSO credentials. To protect your security, the server **never handles passwords directly**.

Run the interactive login script:

```bash
python scripts/login.py
```

```
============================================================
Moodle Interactive Login
============================================================
Opening Moodle login page...
Waiting for login (up to 5 minutes)...
Complete CAS login in the browser window.
✓ Login successful!
✓ Session cookies saved to ./session/state.json
```

1. A visible Chromium window will launch displaying the IIIT CAS Login page.
2. Complete your login (enter your username, password, and 2FA/CAPTCHA if prompted).
3. Once authenticated, cookies are securely saved to `./session/state.json`.
4. The browser closes automatically. Your session is now ready!

> 💡 **Session Expired?** If your session expires after several days, simply run `python scripts/login.py` again to refresh `./session/state.json`.

---

## 🤖 Claude Integration

### Option A: Connect to Claude Code (CLI)

Add the MCP server to Claude Code with persistent session configuration:

```bash
claude mcp add moodle python -s local -e SESSION_DIR=./session -e PYTHONPATH=. -- -m app.main
```

### Option B: Connect to Claude Desktop

Add this configuration to your Claude Desktop configuration file:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "moodle": {
      "command": "python",
      "args": ["-m", "app.main"],
      "cwd": "/path/to/moodle-mcp-server",
      "env": {
        "PYTHONPATH": ".",
        "SESSION_DIR": "./session"
      }
    }
  }
}
```

*(Replace `/path/to/moodle-mcp-server` and `python` with the absolute paths to your project directory and virtual environment Python interpreter).*

### Option C: Standalone Server

You can also run the server directly:

```bash
# Standard I/O mode (for MCP clients)
python app/main.py

# Server-Sent Events (SSE) mode (for remote connections)
python app/main.py --sse
```

---

## 💬 Conversational Examples

Once connected, you can interact with Moodle using natural language:

<table>
<tr>
<td><strong>User Prompt</strong></td>
<td><strong>Claude MCP Action</strong></td>
</tr>
<tr>
<td><em>"What assignments are due this week?"</em></td>
<td>Calls <code>get_calendar(days_ahead=7)</code> & <code>get_assignments()</code> to summarize pending tasks grouped by course with clickable links.</td>
</tr>
<tr>
<td><em>"Show my syllabus and lecture slides for Distributed Systems"</em></td>
<td>Resolves course ID via <code>get_courses()</code>, then invokes <code>get_course_materials(course_id="...")</code> to list section resources and PDFs.</td>
</tr>
<tr>
<td><em>"Are there any new announcements in Automata Theory?"</em></td>
<td>Calls <code>get_announcements(course_id="5776")</code> and outputs latest posts with author notes and dates.</td>
</tr>
<tr>
<td><em>"Who is teaching Computer Networks?"</em></td>
<td>Calls <code>get_participants(course_id="...")</code> filtered by instructor roles.</td>
</tr>
</table>

---

## ⚙️ Configuration

Customize runtime behavior via environment variables or a `.env` file:

| Variable | Type | Default | Description |
|:---|:---:|:---|:---|
| `MOODLE_BASE_URL` | `string` | `https://courses.iiit.ac.in` | Target Moodle instance URL |
| `CAS_LOGIN_URL` | `string` | `https://login.iiit.ac.in` | CAS SSO Authentication URL |
| `SESSION_DIR` | `path` | `./session` | Directory storing authenticated browser session state |
| `CACHE_DIR` | `path` | `./cache` | Directory for cached HTML snapshots |
| `ENABLE_HTTP_FIRST`| `bool` | `true` | Use fast HTTP transport before falling back to browser |
| `CACHE_TTL` | `int` | `300` | Global in-memory cache TTL (seconds) |
| `CACHE_TTL_COURSES`| `int` | `600` | Course listing cache TTL (seconds) |
| `CACHE_TTL_CALENDAR`| `int` | `180` | Calendar & assignment cache TTL (seconds) |
| `HTTP_TIMEOUT` | `float` | `10.0` | HTTP request timeout in seconds |
| `THROTTLE_DELAY` | `float` | `0.1` | Minimum delay between requests |
| `HOST` | `string` | `127.0.0.1` | Bind host for SSE transport mode |
| `PORT` | `int` | `8100` | Bind port for SSE transport mode |
| `LOG_LEVEL` | `string` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

---

## ⚡ Performance & Benchmarks

The built-in hybrid architecture avoids spawning a heavy browser process for every query:

| Tool Endpoint | HTTP-First (Cached) | Full Browser Fallback | Speedup |
|:---|:---:|:---:|:---:|
| `check_health` | **~12 ms** | ~450 ms | **37x** |
| `check_session` | **~35 ms** | ~800 ms | **22x** |
| `get_courses` | **~48 ms** | ~1,200 ms | **25x** |
| `get_assignments` | **~52 ms** | ~1,450 ms | **27x** |
| `get_calendar` | **~44 ms** | ~1,100 ms | **25x** |

Run the benchmark suite locally:
```bash
python scripts/benchmark_latency.py
```

---

## 🔒 Security & Privacy

1. **Zero Credential Exposure**: Your Moodle password and 2FA credentials are never passed as command-line arguments, environment variables, or tool inputs.
2. **Local Session Vault**: Cookies are saved locally in `./session/state.json` (ignored in `.gitignore`).
3. **Strictly Read-Only**: The server implements query tools only. It cannot submit assignments, post forum messages, modify profile details, or delete files.
4. **Sanitized Tool Outputs**: Tool outputs sanitize raw session tokens, ensuring sensitive headers or auth keys are never sent in LLM context windows.

---

## 🧪 Testing & Verification

The project includes an extensive automated test suite covering HTTP clients, browser managers, data models, and HTML parsers:

```bash
# Run full test suite
pytest

# Run tests with verbose output
pytest -v

# Run with test coverage
pytest --cov=app tests/
```

---

## ❓ Troubleshooting

<details>
<summary><strong>Q: I get "Session expired. Run 'python scripts/login.py'"</strong></summary>

CAS sessions expire periodically based on university security policies. Simply run:
```bash
python scripts/login.py
```
Log in once, and the server will immediately resume operating without needing a restart.
</details>

<details>
<summary><strong>Q: Playwright error: "Executable doesn't exist at ..."</strong></summary>

Ensure Chromium is installed for Playwright:
```bash
playwright install chromium
```
If using a custom Chromium binary (e.g. on Raspberry Pi), set the environment variable:
```bash
export CHROMIUM_PATH="/usr/bin/chromium"
```
</details>

<details>
<summary><strong>Q: How do I change the logging verbosity?</strong></summary>

Set `LOG_LEVEL=DEBUG` in your environment:
```bash
export LOG_LEVEL=DEBUG
python app/main.py
```
</details>

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for more information.

<div align="center">
  <sub>Built with ❤️ for the IIIT Hyderabad community & the MCP ecosystem.</sub>
</div>

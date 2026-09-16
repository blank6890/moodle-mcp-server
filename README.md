# Moodle MCP Server

[![M8ven Score](https://m8ven.ai/badge/mcp/blank6890/moodle-mcp-server)](https://m8ven.ai/mcp/blank6890/moodle-mcp-server)

A read-only MCP (Model Context Protocol) server for IIIT Hyderabad's Moodle instance. Exposes courses, assignments, calendar events, announcements, and more via browser automation with persistent CAS-authenticated sessions.

## Features

### Phase 1: Core Tools ✓
- `check_health` — Service status and authentication state
- `check_session` — Verify authentication (never logs secrets)
- `get_courses` — Enrolled courses with filtering
- `get_assignments` — Assignments with due dates, status, and submission URLs
- `get_calendar` — Upcoming calendar events with event types

### Phase 2: Enhanced Tools ✓
- `get_course` — Full course detail with sections, resources, and tabs
- `get_announcements` — Course and site-wide announcements
- `get_course_materials` — Lectures, files, and links organized by section
- `get_participants` — Enrolled students and instructors

## Installation

### Prerequisites

- **Python 3.9+**
- **Raspberry Pi 4B with 4GB RAM** (tested on Debian 13, aarch64) or Windows/Mac/Linux
- **Chromium** (bundled with Playwright)

### Setup

```bash
# 1. Clone or download the project
git clone https://github.com/blank6890/moodle-mcp-server.git
cd moodle-mcp-server

# 2. Create a virtual environment
python -m venv venv
# Linux/Mac
source venv/bin/activate
# Windows
.\venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Playwright Chromium
playwright install chromium
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
3. Saves session cookies to `./session/state.json` (persistent profile)
4. Prints confirmation when done

**Timeout:** 5 minutes. If you need more time, run the script again.

### Step 2: Use in Claude Code

Run this command inside the project directory to add the MCP server to Claude Code:

```bash
claude mcp add moodle python -s local -e SESSION_DIR=./session -e PYTHONPATH=. -- -m app.main
```

### Step 3: Start the MCP Server (Alternative manual start)

```bash
# stdio transport
python app/main.py

# SSE transport
python app/main.py --sse
```

## Claude Skill

This repository includes a skill file (`.claude/skills/moodle.md`) that teaches Claude how to use the MCP tools seamlessly. By invoking the skill or asking about courses/deadlines, Claude automatically aggregates data via the MCP endpoints and formats them beautifully!

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

## Security Model

- **No Password Storage** — Passwords never enter the system. Only CAS session cookies are saved natively by Playwright.
- **Interactive Auth** — User completes CAS login in a visible browser; no automation of MFA/CAPTCHA.
- **Read-Only** — The integration strictly fetches DOM structures without engaging in POST forms or destructive actions.

## Troubleshooting

### Session Expired

Error: `Redirected to CAS login at https://login.iiit.ac.in...`
**Solution:** The session has naturally expired. Rerun the login script to re-authenticate:
```bash
python scripts/login.py
```

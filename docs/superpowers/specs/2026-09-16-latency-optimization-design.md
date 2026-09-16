# Design Specification: Moodle MCP Latency Optimization

## 1. Overview & Problem Statement
The Moodle MCP server currently relies solely on Playwright (headless Chromium) for all network interactions and page rendering. This causes significant response latency:
- **Playwright overhead**: ~2,000–5,000ms per request due to browser context and page lifecycle (`new_page()` / `close()`), DOM execution, asset loading (images, fonts, stylesheets), and unconditional sleeps (`page.wait_for_timeout(1000)`).
- **Throttling & long timeouts**: Hardcoded delays (`THROTTLE_DELAY = 1.0s`, `wait_for_selector(timeout=15000)`) further degrade responsiveness.

This design introduces a **Hybrid HTTP-First Architecture** that leverages cached session cookies in `session/state.json` to execute direct async HTTP requests (`httpx.AsyncClient`) for static/SSR endpoints in **50–150ms**, while retaining an optimized Playwright browser as a fallback for dynamic client-side rendered pages.

---

## 2. Architecture & Components

```
                    ┌─────────────────────────┐
                    │     MCP Client / LLM    │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │      FastMCP Server     │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │      MoodleService      │
                    │   (In-Memory Cache)     │
                    └─────┬─────────────┬─────┘
                          │             │
              (Fast Path) │             │ (Fallback for dynamic JS)
                          ▼             ▼
       ┌────────────────────────┐  ┌────────────────────────┐
       │   HttpClientManager    │  │     BrowserManager     │
       │  (httpx.AsyncClient)   │  │  (Playwright Headless) │
       │  - Cookie extraction   │  │  - Resource blocking   │
       │  - Keep-alive pooling  │  │  - Page reuse          │
       │  - Auto state reload   │  │  - Tight timeouts      │
       └───────────┬────────────┘  └───────────┬────────────┘
                   │                           │
                   └─────────────┬─────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │  HTML Parsers (BS4)     │
                    │  - courses, assignments │
                    │  - calendar, materials  │
                    └─────────────────────────┘
```

### 2.1. `HttpClientManager` (`app/http_client.py`)
- **Async HTTP Engine**: Powered by `httpx.AsyncClient` with connection pooling, HTTP/1.1 & HTTP/2 keep-alive.
- **Cookie Synchronization**: Reads cookies (`MoodleSession`, `MOODLEID1_`, etc.) directly from `session/state.json`. Monitors file modification timestamps and automatically re-syncs if `scripts/login.py` updates the session.
- **Redirect & Session Expiry Detection**: Identifies 302 redirects to `login.iiit.ac.in` or `/login/` and raises `SessionExpiredError`.
- **Latency**: ~50–150ms.

### 2.2. Optimized `BrowserManager` (`app/browser.py`)
- **Resource Abort Filtering**: Intercepts routes (`page.route("**/*")`) to block `image`, `stylesheet`, `font`, and `media` downloads.
- **Page Tab Pooling**: Maintains a persistent browser page instead of recreating page tabs per navigation.
- **Timer Optimization**:
  - Removes unconditional `wait_for_timeout(1000)`.
  - Replaces 15s selector timeouts with tight 2.5s timeouts.
  - Lowers default `THROTTLE_DELAY` from 1.0s to 0.1s.

### 2.3. Service Orchestration (`app/moodle.py`)
- **Dual-Engine Orchestration**:
  1. Check in-memory cache.
  2. Attempt `HttpClientManager.get(url)`.
  3. Parse HTML using existing BeautifulSoup parsers.
  4. If parser returns valid data, cache and return.
  5. If parser returns empty results for a known dynamic page (e.g. dynamic course cards), fall back to `BrowserManager.navigate(url)`.
  6. If session has expired, raise `SessionExpiredError` immediately.

### 2.4. Fast Health & Session Checks (`app/auth.py`, `app/main.py`)
- Replaces heavy browser navigation in `check_session` / `check_health` with lightweight HTTP HEAD/GET to `/my/` (~30–50ms).

---

## 3. Configuration Updates (`app/config.py`)
- `HTTP_TIMEOUT`: Request timeout for HTTP client (default: `10.0`s).
- `ENABLE_HTTP_FIRST`: Feature flag to enable/disable fast HTTP path (default: `True`).
- `THROTTLE_DELAY`: Default updated to `0.1`s for read requests.
- `CACHE_TTL_COURSES`: Granular TTL for course listings (`600`s).
- `CACHE_TTL_CALENDAR`: Granular TTL for calendar/assignments (`180`s).

---

## 4. Error Handling & Edge Cases
1. **Expired Session**: Raises `SessionExpiredError` across both HTTP and Playwright layers, prompting user to run `python scripts/login.py`.
2. **Missing `state.json`**: If no session file is present, immediately prompts for login without launching browser instances.
3. **Network Drops & Timeouts**: Retries HTTP request once before triggering Playwright fallback.
4. **Parser Compatibility**: Output data models (`Course`, `Assignment`, `CalendarEvent`, `CourseDetail`, `Participant`) remain 100% identical.

---

## 5. Verification & Testing Plan
1. **Unit Tests**:
   - `test_http_client.py`: Test cookie parsing, state file reloading, redirect detection.
   - `test_moodle_service.py`: Verify HTTP-first execution and Playwright fallback triggers.
   - `test_browser.py`: Verify route aborts and removal of sleep delays.
2. **End-to-End Latency Benchmarking**:
   - Benchmark `check_health`, `get_courses`, `get_assignments`, `get_calendar`, `get_course` response times.
   - Target: <150ms for cached/HTTP calls, >90% latency reduction.

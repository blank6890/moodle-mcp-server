# Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 2 tools: `get_course`, `get_announcements`, `get_course_materials`, and `get_participants`.

**Architecture:** We will reuse the `CourseDetail` parsing for `get_course` and `get_course_materials`. We will reuse the `announcements` parser for `get_announcements`. We will implement a new parser for `participants` returning a list of `Participant` models, hook it into `MoodleService`, and expose all four via new tools in `app/main.py`.

**Tech Stack:** Python, BeautifulSoup4, Playwright, MCP.

**Spec:** `docs/superpowers/specs/2026-09-11-moodle-mcp-server-design.md`

## Global Constraints

- No password storage.
- Interactive authentication only.
- Persistent browser profile only.
- Read-only.
- Localhost by default.
- No secret logging.

---

### Task 1: Complete `get_course` and `get_course_materials` tools

**Files:**
- Modify: `app/main.py`

**Interfaces:**
- Consumes: `app.moodle.MoodleService.get_course_detail`
- Produces: `@server.tool() async def get_course(course_id: str) -> dict`, `@server.tool() async def get_course_materials(course_id: str) -> list`

- [ ] **Step 1: Write the tool endpoints in `app/main.py`**

Open `app/main.py` and add:

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add app/main.py
git commit -m "feat: implement get_course and get_course_materials tools"
```

---

### Task 2: Complete `get_announcements` tool

**Files:**
- Modify: `app/main.py`

**Interfaces:**
- Consumes: `app.moodle.MoodleService.get_announcements`
- Produces: `@server.tool() async def get_announcements(course_id: Optional[str] = None, limit: int = 20) -> list`

- [ ] **Step 1: Write the tool endpoints in `app/main.py`**

Open `app/main.py` and add:

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add app/main.py
git commit -m "feat: implement get_announcements tool"
```

---

### Task 3: Implement Participants parser and fetcher

**Files:**
- Create: `app/parsers/participants.py`
- Modify: `app/parsers/__init__.py`
- Modify: `app/moodle.py`
- Modify: `tests/test_parsers.py`

**Interfaces:**
- Consumes: Raw HTML from Moodle participants page
- Produces: `parse_participants(html: str) -> list[Participant]`, `MoodleService.get_participants(course_id: str) -> list[Participant]`

- [ ] **Step 1: Write `app/parsers/participants.py`**

```python
import logging
from bs4 import BeautifulSoup
from app.models import Participant

logger = logging.getLogger(__name__)

def parse_participants(html: str) -> list[Participant]:
    """Parse participants page → list of Participant models.

    CALIBRATE: Update selectors from real course participants HTML.
    """
    soup = BeautifulSoup(html, "html.parser")
    participants = []

    # CALIBRATE: Find real selectors for participant rows
    row_elements = soup.select(".userlist table tbody tr, [data-user-id]")

    for row in row_elements:
        try:
            name_elem = row.find(class_="username") or row.find("a")
            name = name_elem.get_text(strip=True) if name_elem else ""
            profile_url = name_elem.get("href", "") if name_elem and name_elem.name == "a" else ""

            role_elem = row.find(class_="role") or row.select_one("td:nth-of-type(4)")
            role = role_elem.get_text(strip=True).lower() if role_elem else "student"

            if name:
                participants.append(Participant(
                    name=name,
                    role=role,
                    profile_url=profile_url
                ))
        except Exception as e:
            logger.warning(f"Failed to parse participant: {e}")

    logger.info(f"Parsed {len(participants)} participants")
    return participants
```

- [ ] **Step 2: Export in `app/parsers/__init__.py`**

Verify `app/parsers/__init__.py` doesn't strictly need exports since `app/moodle.py` imports directly, but it's good practice. (Optional). We can just rely on direct import.

- [ ] **Step 3: Update `app/moodle.py` to add `get_participants`**

In `app/moodle.py`, add the import:
```python
from app.parsers import participants as participants_parser
```

And add the method:
```python
    async def get_participants(self, course_id: str) -> list[Participant]:
        """Get enrolled participants and instructors in a course."""
        cache_key = f"participants_{course_id}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        try:
            url, html = await self.browser.navigate(f"https://courses.iiit.ac.in/user/index.php?id={course_id}")
            participants = participants_parser.parse_participants(html)
            self._set_cache(cache_key, participants)
            return participants
        except SessionExpiredError:
            raise
```

- [ ] **Step 4: Add test in `tests/test_parsers.py`**

In `tests/test_parsers.py`, add imports and test:
```python
from app.parsers.participants import parse_participants

def test_parse_participants():
    """Test parse_participants parser."""
    html = load_fixture("participants.html")
    participants = parse_participants(html)
    assert isinstance(participants, list)
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_parsers.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/parsers/participants.py app/moodle.py tests/test_parsers.py
git commit -m "feat: implement participants parsing and retrieval"
```

---

### Task 4: Complete `get_participants` tool

**Files:**
- Modify: `app/main.py`

**Interfaces:**
- Consumes: `app.moodle.MoodleService.get_participants`
- Produces: `@server.tool() async def get_participants(course_id: str) -> list`

- [ ] **Step 1: Add the tool endpoint in `app/main.py`**

Open `app/main.py` and add:

```python
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
```

- [ ] **Step 2: Run all tests to make sure syntax is good**

Run: `pytest tests/ -v`
Expected: All passing.

- [ ] **Step 3: Commit**

```bash
git add app/main.py
git commit -m "feat: implement get_participants tool"
```

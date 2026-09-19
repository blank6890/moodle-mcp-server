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

        # perpage=5000 avoids Moodle's default 20-per-page pagination,
        # which was silently truncating rosters on larger courses and
        # could miss instructor/TA rows entirely depending on sort order.
        html = await self._fetch_html(
            f"https://courses.iiit.ac.in/user/index.php?id={course_id}&perpage=5000"
        )
        participants = participants_parser.parse_participants(html)
        self._set_cache(cache_key, participants)
        return participants

import logging
import time
from typing import Optional, Dict, Tuple, Any
from app.browser import BrowserManager, SessionExpiredError
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

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

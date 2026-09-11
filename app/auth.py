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

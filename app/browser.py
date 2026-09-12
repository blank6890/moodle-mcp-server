import asyncio
import logging
from pathlib import Path
from typing import Optional, Tuple
from playwright.async_api import async_playwright
from app.config import Config

logger = logging.getLogger(__name__)

class SessionExpiredError(Exception):
    """Raised when Moodle session has expired (redirect to CAS)."""
    pass

class BrowserManager:
    """Manages Playwright browser context with throttling."""

    def __init__(self, config: Config):
        self.config = config
        self._browser = None
        self._context = None
        self._playwright = None
        self._throttle_lock = asyncio.Lock()
        self._last_request_time = 0.0
        self._initialized = False

    async def __aenter__(self):
        """Enter context: initialize browser."""
        await self._init_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context: close browser."""
        await self._close_browser()

    async def _init_browser(self):
        """Initialize Playwright browser and context."""
        if self._initialized:
            return

        logger.info("Initializing Playwright browser...")
        self._playwright = await async_playwright().start()

        executable_path = None
        if self.config.CHROMIUM_PATH:
            executable_path = self.config.CHROMIUM_PATH

        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=["--disable-gpu"],
            executable_path=executable_path,
        )

        state_file = Path(self.config.SESSION_DIR) / "state.json"
        storage_state_arg = str(state_file) if state_file.exists() else None

        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 720},
            storage_state=storage_state_arg
        )

        self._initialized = True
        logger.info("Browser initialized successfully")

    async def _close_browser(self):
        """Close browser and cleanup."""
        if self._context:
            await self._context.close()
            logger.info("Browser context closed")
            
        if self._browser:
            await self._browser.close()

        if self._playwright:
            await self._playwright.stop()
            logger.info("Playwright stopped")

        self._initialized = False

    async def navigate(self, url: str) -> Tuple[str, str]:
        """Navigate to URL with throttling. Returns (final_url, page_html)."""
        if not self._initialized:
            raise RuntimeError("Browser not initialized")

        # Apply throttling
        async with self._throttle_lock:
            import time
            elapsed = time.time() - self._last_request_time
            if elapsed < self.config.THROTTLE_DELAY:
                await asyncio.sleep(self.config.THROTTLE_DELAY - elapsed)
            self._last_request_time = time.time()

        page = await self._context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded")
            final_url = page.url

            if "login.iiit.ac.in" in final_url or "/login/" in final_url:
                logger.warning(f"Session expired: redirected to {final_url}")
                raise SessionExpiredError(f"Redirected to CAS login at {final_url}")

            # Wait briefly for common JS to render key elements if they exist
            try:
                if "/my/courses.php" in url:
                    await page.wait_for_selector(".coursename", timeout=15000)
                elif "/mod/assign/" in url:
                    await page.wait_for_selector(".generaltable", timeout=15000)
                else:
                    await page.wait_for_timeout(1000)  # general short wait for JS execution
            except Exception as e:
                logger.warning(f"Timeout waiting for dynamic selector in {url}: {e}")

            html = await page.content()
            logger.debug(f"Navigated to {final_url}")

            return final_url, html
        finally:
            await page.close()

    async def get_current_url(self) -> str:
        """Get the current page URL."""
        if not self._initialized:
            raise RuntimeError("Browser not initialized")
        return self.config.MOODLE_BASE_URL

    async def is_initialized(self) -> bool:
        """Check if browser is initialized."""
        return self._initialized

import asyncio
import logging
from pathlib import Path
from typing import Optional, Tuple
from playwright.async_api import async_playwright, Route
from app.config import Config

logger = logging.getLogger(__name__)

class SessionExpiredError(Exception):
    """Raised when Moodle session has expired (redirect to CAS)."""
    pass

class BrowserManager:
    """Manages an optimized Playwright browser context with resource blocking."""

    BLOCKED_RESOURCE_TYPES = {"image", "media", "font", "stylesheet"}

    def __init__(self, config: Config):
        self.config = config
        self._browser = None
        self._context = None
        self._page = None
        self._playwright = None
        self._throttle_lock = asyncio.Lock()
        self._last_request_time = 0.0
        self._initialized = False

    async def __aenter__(self):
        await self._init_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._close_browser()

    async def _handle_route(self, route: Route):
        """Abort unnecessary resources (images, fonts, stylesheets) for speed."""
        if route.request.resource_type in self.BLOCKED_RESOURCE_TYPES:
            await route.abort()
        else:
            await route.continue_()

    async def _init_browser(self):
        """Initialize Playwright browser with route optimizations."""
        if self._initialized:
            return

        logger.info("Initializing optimized Playwright browser...")
        self._playwright = await async_playwright().start()

        executable_path = self.config.CHROMIUM_PATH if self.config.CHROMIUM_PATH else None

        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-extensions",
            ],
            executable_path=executable_path,
        )

        state_file = Path(self.config.SESSION_DIR) / "state.json"
        storage_state_arg = str(state_file) if state_file.exists() else None

        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 720},
            storage_state=storage_state_arg
        )

        # Route filtering across the context
        await self._context.route("**/*", self._handle_route)

        # Create a single persistent reusable page tab
        self._page = await self._context.new_page()

        self._initialized = True
        logger.info("Optimized Playwright browser initialized successfully")

    async def _close_browser(self):
        """Close browser and cleanup."""
        if self._page:
            try:
                await self._page.close()
            except Exception:
                pass
            self._page = None

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
        """Navigate to URL with optimized page lifecycle. Returns (final_url, page_html)."""
        if not self._initialized:
            await self._init_browser()

        # Adaptive throttling
        async with self._throttle_lock:
            import time
            elapsed = time.time() - self._last_request_time
            if elapsed < self.config.THROTTLE_DELAY:
                await asyncio.sleep(self.config.THROTTLE_DELAY - elapsed)
            self._last_request_time = time.time()

        page = self._page
        if page is None or (hasattr(page, "is_closed") and page.is_closed()):
            page = await self._context.new_page()
            self._page = page

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            final_url = page.url

            if "login.iiit.ac.in" in final_url or "/login/" in final_url:
                logger.warning(f"Session expired: redirected to {final_url}")
                raise SessionExpiredError(f"Redirected to CAS login at {final_url}")

            # Fast dynamic selector check with tight timeout (2.5s instead of 15s)
            try:
                if "/my/courses.php" in url:
                    await page.wait_for_selector(".coursename", timeout=2500)
                elif "/mod/assign/" in url:
                    await page.wait_for_selector(".generaltable", timeout=2500)
            except Exception:
                pass  # Fallback to current DOM content immediately

            html = await page.content()
            logger.debug(f"Navigated to {final_url}")
            return final_url, html

        except SessionExpiredError:
            raise
        except Exception as e:
            logger.error(f"Browser navigation error for {url}: {e}")
            raise

    async def get_current_url(self) -> str:
        """Get the current page URL."""
        if self._page and hasattr(self._page, "url") and self._page.url:
            return self._page.url
        return self.config.MOODLE_BASE_URL

    async def is_initialized(self) -> bool:
        """Check if browser is initialized."""
        return self._initialized

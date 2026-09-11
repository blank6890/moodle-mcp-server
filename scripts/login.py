#!/usr/bin/env python3
"""
Interactive CAS login script for Moodle.

Launches a visible browser window where the user completes CAS login.
Session cookies are persisted to disk.
"""

import asyncio
import sys
import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))
import logging
from pathlib import Path
from playwright.async_api import async_playwright
from app.config import Config

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

async def interactive_login():
    """Launch headed browser for interactive CAS login."""
    config = Config()
    
    logger.info("=" * 60)
    logger.info("Moodle Interactive Login")
    logger.info("=" * 60)
    logger.info(f"Session directory: {config.SESSION_DIR}")
    logger.info(f"Timeout: 5 minutes")
    logger.info("")
    
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(config.SESSION_DIR),
            headless=False,  # IMPORTANT: visible window
            viewport={"width": 1280, "height": 720},
        )
        
        page = await context.new_page()
        
        try:
            logger.info("Opening Moodle login page...")
            await page.goto("https://courses.iiit.ac.in/login/index.php")
            
            logger.info("Waiting for login (up to 5 minutes)...")
            logger.info("Complete CAS login in the browser window.")
            logger.info("")
            
            # Poll for redirect back to Moodle (off the CAS domain)
            start_time = time.time()
            timeout_seconds = 300
            poll_interval = 2
            
            success = False
            while time.time() - start_time < timeout_seconds:
                current_url = page.url
                
                # Success: on Moodle domain and NOT on login page
                if "courses.iiit.ac.in" in current_url and "login.iiit.ac.in" not in current_url:
                    if "/login/" not in current_url:
                        success = True
                        break
                
                await asyncio.sleep(poll_interval)
            
            if success:
                logger.info("✓ Login successful!")
                logger.info(f"✓ Final URL: {page.url}")
                logger.info("✓ Session cookies saved to disk")
                
                # Give cookies time to flush
                await asyncio.sleep(2)
                logger.info("")
                logger.info("You can now run the MCP server:")
                logger.info("  python app/main.py")
                return 0
            else:
                logger.error("✗ Login timeout (5 minutes)")
                logger.error("Please check your CAS credentials and try again.")
                return 1
        
        except Exception as e:
            logger.error(f"✗ Login error: {e}")
            return 1
        finally:
            await context.close()

def main():
    exit_code = asyncio.run(interactive_login())
    sys.exit(exit_code)

if __name__ == "__main__":
    main()

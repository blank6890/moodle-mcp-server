#!/usr/bin/env python3
"""
Interactive CAS login script for Moodle.

Launches a visible browser window where the user completes CAS login.
Session cookies are persisted to a JSON state file.
"""

import asyncio
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))
import logging
from playwright.async_api import async_playwright
from app.config import Config

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

async def interactive_login():
    config = Config()
    
    logger.info("=" * 60)
    logger.info("Moodle Interactive Login")
    logger.info("=" * 60)
    
    state_file = Path(config.SESSION_DIR) / "state.json"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
        )
        
        page = await context.new_page()
        
        try:
            logger.info("Opening Moodle login page...")
            await page.goto("https://courses.iiit.ac.in/login/index.php")
            
            logger.info("Waiting for login (up to 5 minutes)...")
            logger.info("Complete CAS login in the browser window.")
            
            start_time = time.time()
            timeout_seconds = 300
            poll_interval = 2
            
            success = False
            while time.time() - start_time < timeout_seconds:
                current_url = page.url
                if "courses.iiit.ac.in" in current_url and "login.iiit.ac.in" not in current_url:
                    if "/login/" not in current_url:
                        success = True
                        break
                await asyncio.sleep(poll_interval)
            
            if success:
                logger.info("✓ Login successful!")
                # Get the state and save to state_file
                state = await context.storage_state(path=str(state_file))
                logger.info(f"✓ Session cookies saved to {state_file}")
                
                await asyncio.sleep(2)
                return 0
            else:
                logger.error("✗ Login timeout (5 minutes)")
                return 1
        
        except Exception as e:
            logger.error(f"✗ Login error: {e}")
            return 1
        finally:
            await browser.close()

def main():
    exit_code = asyncio.run(interactive_login())
    sys.exit(exit_code)

if __name__ == "__main__":
    main()

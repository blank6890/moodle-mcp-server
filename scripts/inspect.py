#!/usr/bin/env python3
"""
Moodle HTML inspection tool.

Navigates to a Moodle URL using the persistent browser profile
and dumps the raw HTML to a file for selector calibration.

Usage:
    python scripts/inspect.py <url>

Example:
    python scripts/inspect.py https://courses.iiit.ac.in/my/courses.php
"""

import asyncio
import sys
import logging
from pathlib import Path
from urllib.parse import urlparse

# Add parent directory to sys.path so we can import app module natively
sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))

from app.config import Config
from app.browser import BrowserManager
from app.logging_config import setup_logging

setup_logging("INFO")
logger = logging.getLogger(__name__)

async def inspect_url(url: str):
    """Navigate to URL and dump HTML to file."""
    if not url.startswith("http"):
        logger.error("URL must start with http:// or https://")
        return 1
    
    config = Config()
    
    logger.info("=" * 60)
    logger.info("Moodle HTML Inspector")
    logger.info("=" * 60)
    logger.info(f"URL: {url}")
    
    # Generate filename from URL
    parsed = urlparse(url)
    filename_base = parsed.path.replace("/", "_").strip("_") or parsed.netloc
    filename = f"{filename_base}.html"
    output_path = config.CACHE_DIR / filename
    
    logger.info(f"Output file: {output_path}")
    logger.info("")
    
    try:
        browser = BrowserManager(config)
        await browser._init_browser()
        
        logger.info("Navigating...")
        final_url, html = await browser.navigate(url)
        
        # Write HTML to file
        output_path.write_text(html, encoding="utf-8")
        
        logger.info(f"✓ Successfully inspected {url}")
        logger.info(f"✓ HTML written to {output_path}")
        logger.info(f"✓ HTML length: {len(html)} bytes")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Open the HTML file in a browser or editor")
        logger.info("  2. Identify CSS selectors for the data you want to parse")
        logger.info("  3. Update the corresponding parser with real selectors")
        
        await browser._close_browser()
        return 0
    
    except Exception as e:
        logger.error(f"✗ Error: {e}")
        return 1

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    url = sys.argv[1]
    exit_code = asyncio.run(inspect_url(url))
    sys.exit(exit_code)

if __name__ == "__main__":
    main()

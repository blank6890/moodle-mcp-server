import asyncio
from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))
from app.config import Config
from app.browser import BrowserManager

async def test_dump():
    config = Config()
    async with BrowserManager(config) as browser:
        print("Navigating to courses.php with networkidle...")
        page = await browser._context.new_page()
        await page.goto("https://courses.iiit.ac.in/my/courses.php", wait_until="networkidle")
        
        # wait additionally to make sure
        await page.wait_for_timeout(2000)
        html = await page.content()
        
        path = Path(config.SESSION_DIR) / "courses_idle.html"
        path.write_text(html, encoding='utf-8')
        print("Saved to", path)
        await page.close()

if __name__ == "__main__":
    asyncio.run(test_dump())

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
        print("Navigating to dashboard...")
        url, html = await browser.navigate("https://courses.iiit.ac.in/my/")
        print("Final URL:", url)
        
        path = Path(config.SESSION_DIR) / "dashboard.html"
        path.write_text(html, encoding='utf-8')
        print("Saved to", path)

if __name__ == "__main__":
    asyncio.run(test_dump())

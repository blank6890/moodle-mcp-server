import asyncio
from pathlib import Path
import sys, os

sys.path.insert(0, os.getcwd())
from app.config import Config
from app.browser import BrowserManager
from app.moodle import MoodleService

async def main():
    config = Config()
    async with BrowserManager(config) as browser:
        service = MoodleService(browser, config)
        print("Fetching calendar events...")
        events = await service.get_calendar(days_ahead=30)
        for e in events:
            print(f'Event: {e.title}')
            print(f'  Date: {e.date}')
            print(f'  Type: {e.event_type}')
            print('---')
            
        if not events:
            print("No events parsed. Dumping HTML...")
            url, html = await browser.navigate("https://courses.iiit.ac.in/calendar/view.php?view=upcoming")
            Path(config.SESSION_DIR, "calendar.html").write_text(html, encoding="utf-8")
            print("Dumped to session/calendar.html")

if __name__ == '__main__':
    asyncio.run(main())

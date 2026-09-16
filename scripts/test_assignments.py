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
        print("Fetching assignments for Automata Theory (5776)...")
        assignments = await service.get_assignments(course_id="5776")
        for a in assignments:
            print(f'Assignment: {a.title}')
            print(f'  URL: {a.url}')
            print(f'  Due Date: {a.due_date}')
            print(f'  Status: {a.status}')
            print('---')
            
        # If 0 parsed, dump the HTML so we can calibrate
        if not assignments:
            print("No assignments parsed. Dumping HTML...")
            url = "https://courses.iiit.ac.in/mod/assign/index.php?id=5776"
            _, html = await browser.navigate(url)
            Path(config.SESSION_DIR, "assignments.html").write_text(html, encoding="utf-8")
            print("Dumped to session/assignments.html")

if __name__ == '__main__':
    asyncio.run(main())

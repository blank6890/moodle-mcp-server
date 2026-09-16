import asyncio
from pathlib import Path
import os
import sys
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))
from app.config import Config
from app.browser import BrowserManager

async def get_courses_page():
    config = Config()
    async with BrowserManager(config) as browser:
        print("Navigating to courses.php...")
        url, html = await browser.navigate("https://courses.iiit.ac.in/my/courses.php")
        print("Final URL:", url)
        
        soup = BeautifulSoup(html, "html.parser")
        course_links = soup.select("a[href*='course/view.php?id=']")
        print(f"Found {len(course_links)} possible course links.")
        for link in set(course_links):
            print(link.text.strip(), "->", link.get("href"))
            
if __name__ == "__main__":
    asyncio.run(get_courses_page())

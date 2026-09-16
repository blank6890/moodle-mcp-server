import os
from pathlib import Path
from typing import Optional

class Config:
    """Configuration from environment variables with sensible defaults."""

    def __init__(self):
        self.HOST: str = os.getenv("HOST", "127.0.0.1")
        self.PORT: int = int(os.getenv("PORT", "8100"))
        self.MOODLE_BASE_URL: str = os.getenv("MOODLE_BASE_URL", "https://courses.iiit.ac.in")
        self.CAS_LOGIN_URL: str = os.getenv("CAS_LOGIN_URL", "https://login.iiit.ac.in")

        # Paths
        self.SESSION_DIR: Path = Path(os.getenv("SESSION_DIR", "./session"))
        self.CACHE_DIR: Path = Path(os.getenv("CACHE_DIR", "./cache"))

        # Create directories if they don't exist
        self.SESSION_DIR.mkdir(parents=True, exist_ok=True)
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # Performance & Timeouts
        self.CACHE_TTL: int = int(os.getenv("CACHE_TTL", "300"))
        self.CACHE_TTL_COURSES: int = int(os.getenv("CACHE_TTL_COURSES", "600"))
        self.CACHE_TTL_CALENDAR: int = int(os.getenv("CACHE_TTL_CALENDAR", "180"))
        self.THROTTLE_DELAY: float = float(os.getenv("THROTTLE_DELAY", "0.1"))
        self.HTTP_TIMEOUT: float = float(os.getenv("HTTP_TIMEOUT", "10.0"))
        self.ENABLE_HTTP_FIRST: bool = os.getenv("ENABLE_HTTP_FIRST", "true").lower() in ("true", "1", "yes")

        # Browser
        self.CHROMIUM_PATH: Optional[str] = os.getenv("CHROMIUM_PATH")

        # Logging
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    def __repr__(self):
        return (
            f"Config(HOST={self.HOST}, PORT={self.PORT}, "
            f"MOODLE={self.MOODLE_BASE_URL}, CACHE_TTL={self.CACHE_TTL}, "
            f"HTTP_FIRST={self.ENABLE_HTTP_FIRST})"
        )

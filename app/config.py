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

        # Performance
        self.CACHE_TTL: int = int(os.getenv("CACHE_TTL", "300"))
        self.THROTTLE_DELAY: float = float(os.getenv("THROTTLE_DELAY", "1.0"))

        # Browser
        self.CHROMIUM_PATH: Optional[str] = os.getenv("CHROMIUM_PATH")

        # Logging
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    def __repr__(self):
        return (
            f"Config(HOST={self.HOST}, PORT={self.PORT}, "
            f"MOODLE={self.MOODLE_BASE_URL}, CACHE_TTL={self.CACHE_TTL})"
        )

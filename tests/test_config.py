import os
from app.config import Config

def test_config_defaults():
    """Test default configuration values."""
    config = Config()
    assert config.HOST == "127.0.0.1"
    assert config.PORT == 8100
    assert config.MOODLE_BASE_URL == "https://courses.iiit.ac.in"
    assert config.CAS_LOGIN_URL == "https://login.iiit.ac.in"
    assert config.CACHE_TTL == 300
    assert config.THROTTLE_DELAY == 1.0
    assert config.LOG_LEVEL == "INFO"

def test_config_env_override():
    """Test that env vars override defaults."""
    os.environ["HOST"] = "0.0.0.0"
    os.environ["PORT"] = "9000"
    os.environ["CACHE_TTL"] = "600"

    config = Config()
    assert config.HOST == "0.0.0.0"
    assert config.PORT == 9000
    assert config.CACHE_TTL == 600

    # Clean up
    del os.environ["HOST"]
    del os.environ["PORT"]
    del os.environ["CACHE_TTL"]

def test_config_paths_exist():
    """Test that SESSION_DIR and CACHE_DIR are created if missing."""
    config = Config()
    assert config.SESSION_DIR
    assert config.CACHE_DIR

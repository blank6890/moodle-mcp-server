import asyncio
import logging
import sys
import time
from datetime import datetime
from typing import Optional

# Some versions of mcp SDK export FastMCP directly, or we can use FastMCP
# The brief imports MCPServer from mcp.server. We will try that first.
try:
    from mcp.server import MCPServer
except ImportError:
    # Fallback if mcp.server doesn't have MCPServer (e.g. FastMCP is the real one)
    from mcp.server.fastmcp import FastMCP as MCPServer

from app.config import Config
from app.browser import BrowserManager, SessionExpiredError
from app.auth import check_session as check_auth_session
from app.moodle import MoodleService
from app.logging_config import setup_logging

logger = logging.getLogger(__name__)

# Global state
_config: Optional[Config] = None
_browser: Optional[BrowserManager] = None
_moodle: Optional[MoodleService] = None
_start_time: float = time.time()

async def _init_globals():
    """Initialize global browser and service on first tool call."""
    global _config, _browser, _moodle
    
    if _moodle is not None:
        return
    
    _config = Config()
    _browser = BrowserManager(_config)
    await _browser._init_browser()
    _moodle = MoodleService(_browser, _config)

def create_mcp_server() -> MCPServer:
    """Create and configure MCP server with Phase 1 tools."""
    
    server = MCPServer("moodle-agent")
    
    @server.tool()
    async def check_health() -> dict:
        """Check service health and authentication status."""
        try:
            await _init_globals()
            uptime = time.time() - _start_time
            
            try:
                status_obj = await check_auth_session(_browser)
                authenticated = status_obj.authenticated
                detail = status_obj.detail
            except SessionExpiredError:
                authenticated = False
                detail = "Session expired"
            
            return {
                "status": "healthy",
                "authenticated": authenticated,
                "uptime_seconds": uptime,
                "detail": detail
            }
        except Exception as e:
            logger.error(f"health check failed: {e}")
            return {
                "status": "error",
                "authenticated": False,
                "uptime_seconds": time.time() - _start_time,
                "detail": str(e)
            }
    
    @server.tool()
    async def check_session() -> dict:
        """Check if session is authenticated. Never returns cookies/tokens."""
        try:
            await _init_globals()
            status_obj = await check_auth_session(_browser)
            return {
                "authenticated": status_obj.authenticated,
                "detail": status_obj.detail
            }
        except SessionExpiredError:
            return {
                "authenticated": False,
                "detail": "Session expired. Run 'python scripts/login.py' to re-authenticate."
            }
        except Exception as e:
            logger.error(f"session check failed: {e}")
            return {
                "authenticated": False,
                "detail": f"Error checking session: {e}"
            }
    
    @server.tool()
    async def get_courses() -> list:
        """Get enrolled courses."""
        try:
            await _init_globals()
            courses = await _moodle.get_courses()
            return [c.model_dump() for c in courses]
        except SessionExpiredError:
            raise ValueError("Session expired. Run 'python scripts/login.py' to re-authenticate.")
        except Exception as e:
            logger.error(f"get_courses failed: {e}")
            raise
    
    @server.tool()
    async def get_assignments(course_id: Optional[str] = None) -> list:
        """Get assignments optionally filtered by course."""
        try:
            await _init_globals()
            assignments = await _moodle.get_assignments(course_id)
            return [a.model_dump() for a in assignments]
        except SessionExpiredError:
            raise ValueError("Session expired. Run 'python scripts/login.py' to re-authenticate.")
        except Exception as e:
            logger.error(f"get_assignments failed: {e}")
            raise
    
    @server.tool()
    async def get_calendar(days_ahead: int = 30) -> list:
        """Get upcoming calendar events."""
        try:
            await _init_globals()
            events = await _moodle.get_calendar(days_ahead)
            return [e.model_dump() for e in events]
        except SessionExpiredError:
            raise ValueError("Session expired. Run 'python scripts/login.py' to re-authenticate.")
        except Exception as e:
            logger.error(f"get_calendar failed: {e}")
            raise
    
    return server

def main():
    """Main entry point: run MCP server."""
    # Setup logging
    config = Config()
    setup_logging(config.LOG_LEVEL)
    
    logger.info("Starting Moodle MCP Server")
    
    # Parse CLI args for transport selection
    use_sse = "--sse" in sys.argv
    
    # Create server
    server = create_mcp_server()
    
    # Run server
    try:
        if use_sse:
            logger.info(f"Running in SSE mode on {config.HOST}:{config.PORT}")
            server.settings.host = config.HOST
            server.settings.port = config.PORT
            server.run(transport="sse")
        else:
            logger.info("Running in stdio mode")
            server.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

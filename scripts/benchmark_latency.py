import asyncio
import os
import sys
import time
from pathlib import Path
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

async def benchmark():
    project_root = Path(__file__).parent.parent.absolute()
    python_exe = str(project_root / "venv" / "Scripts" / "python.exe")
    if not Path(python_exe).exists():
        python_exe = sys.executable

    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)
    env["SESSION_DIR"] = str(project_root / "session")

    server_params = StdioServerParameters(
        command=python_exe,
        args=["-m", "app.main"],
        env=env
    )

    print("=" * 60)
    print("Moodle MCP Latency Benchmark")
    print("=" * 60)

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("✓ Server connected and initialized\n")

            tools_to_test = [
                ("check_health", {}),
                ("check_session", {}),
                ("get_courses", {}),
                ("get_calendar", {"days_ahead": 14}),
                ("get_assignments", {}),
            ]

            for tool_name, args in tools_to_test:
                t0 = time.time()
                try:
                    res = await session.call_tool(tool_name, args)
                    elapsed_ms = (time.time() - t0) * 1000
                    print(f"Tool [{tool_name:18}]: {elapsed_ms:6.1f} ms | Status: SUCCESS")
                except Exception as e:
                    elapsed_ms = (time.time() - t0) * 1000
                    print(f"Tool [{tool_name:18}]: {elapsed_ms:6.1f} ms | Status: FAILED ({e})")

if __name__ == "__main__":
    asyncio.run(benchmark())

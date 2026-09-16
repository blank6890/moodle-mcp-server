import asyncio
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
import os
import pprint

async def main():
    python_exe = r"C:\Users\hites\OneDrive\Desktop\mini-projects\data-management\venv\Scripts\python.exe"
    env = os.environ.copy()
    env["PYTHONPATH"] = r"C:\Users\hites\OneDrive\Desktop\mini-projects\data-management"
    env["SESSION_DIR"] = r"C:\Users\hites\OneDrive\Desktop\mini-projects\data-management\session"
    
    server_params = StdioServerParameters(
        command=python_exe,
        args=["-m", "app.main"],
        env=env
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool("get_courses", {})
            for c in res.content:
                print("CONTENT TYPE:", type(c))
                if hasattr(c, "text"): print("TEXT:", c.text)
                if hasattr(c, "data"): print("DATA:", c.data)

if __name__ == "__main__":
    asyncio.run(main())

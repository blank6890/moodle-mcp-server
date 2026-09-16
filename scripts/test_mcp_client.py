import asyncio
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
import os

async def main():
    # Use the venv python
    python_exe = r"C:\Users\hites\OneDrive\Desktop\mini-projects\data-management\venv\Scripts\python.exe"
    
    env = os.environ.copy()
    env["PYTHONPATH"] = r"C:\Users\hites\OneDrive\Desktop\mini-projects\data-management"
    env["SESSION_DIR"] = r"C:\Users\hites\OneDrive\Desktop\mini-projects\data-management\session"
    
    server_params = StdioServerParameters(
        command=python_exe,
        args=["-m", "app.main"],
        env=env
    )
    
    print("Initializing MCP client...")
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                print("Connected! Fetching tools...")
                tools = await session.list_tools()
                print("Available tools:")
                for tool in tools.tools:
                    print(f"  - {tool.name}")
                
                print("\nCalling 'check_health'...")
                health = await session.call_tool("check_health", {})
                for content in health.content:
                    print(f"Result: {content.text}")
                    
                print("\nCalling 'check_session'...")
                try:
                    session_res = await session.call_tool("check_session", {})
                    for content in session_res.content:
                        print(f"Result: {content.text}")
                except Exception as e:
                    print(f"Check_session error: {e}")
                    
    except Exception as e:
        print(f"Failed to connect or execute: {e}")

if __name__ == "__main__":
    asyncio.run(main())

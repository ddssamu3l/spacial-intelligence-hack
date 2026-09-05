"""Execute a project script through the installed Blender MCP server."""
import argparse
import asyncio
from datetime import timedelta
import os
import shutil
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def run(script):
    params = StdioServerParameters(
        command=shutil.which("uvx") or "/opt/homebrew/bin/uvx",
        args=["--python", "3.11", "blender-mcp==1.9.1"],
        env={**os.environ, "DISABLE_TELEMETRY": "true", "BLENDER_HOST": "127.0.0.1", "BLENDER_PORT": "9876"},
    )
    with open(Path(__file__).resolve().parents[1] / "outputs" / "mcp.log", "a") as log:
        async with stdio_client(params, errlog=log) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=200)) as session:
                await session.initialize()
                code = f"import runpy; runpy.run_path({str(Path(script).resolve())!r}, run_name='__main__')"
                result = await session.call_tool("execute_blender_code", {"code": code, "user_prompt": "Build and verify the authorized Everest terrain preview in Blender."})
                for block in result.content:
                    if hasattr(block, "text"):
                        print(block.text)
                        if block.text.startswith("Error executing code:"):
                            raise RuntimeError(block.text)
                if result.isError:
                    raise RuntimeError("Blender MCP tool failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("script")
    args = parser.parse_args()
    (Path(__file__).resolve().parents[1] / "outputs").mkdir(exist_ok=True)
    asyncio.run(run(args.script))

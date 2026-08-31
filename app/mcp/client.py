"""Simple synchronous wrapper around the merchant MCP server."""

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER_SCRIPT = os.path.join(os.path.dirname(__file__), "merchant_server.py")


@asynccontextmanager
async def merchant_session():
    params = StdioServerParameters(command=sys.executable, args=[SERVER_SCRIPT])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


class MerchantMCPClient:
    """Expose async MCP tools through a normal synchronous call()."""

    async def _call(self, tool_name: str, **kwargs):
        async with merchant_session() as session:
            result = await session.call_tool(tool_name, kwargs)
            text = result.content[0].text
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text

    def call(self, tool_name: str, **kwargs):
        return asyncio.run(self._call(tool_name, **kwargs))


merchant_client = MerchantMCPClient()

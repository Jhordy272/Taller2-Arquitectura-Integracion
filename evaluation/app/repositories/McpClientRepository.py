"""Calls the service through MCP over stdio, as any client would: the harness
measures the published contract, not internal functions."""
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class McpClientRepository:
    def __init__(self, session: ClientSession) -> None:
        self._session = session

    async def search(self, query: str) -> dict | None:
        """Return the structured answer, or None if the tool reported an error."""
        result = await self._session.call_tool("search_documents", {"query": query})
        return None if result.is_error else result.structured_content


@asynccontextmanager
async def open_client(server_dir: Path, collection: str | None) -> AsyncIterator[McpClientRepository]:
    """Start the MCP server; a collection name replaces the active alias for this run."""
    env = dict(os.environ)
    if collection:
        env["ACTIVE_ALIAS"] = collection
    parameters = StdioServerParameters(command=sys.executable, args=["-m", "app.main"], cwd=server_dir, env=env)
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield McpClientRepository(session)

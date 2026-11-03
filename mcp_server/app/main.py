"""MCP server entry point. Uses the stdio transport, so only protocol messages may go
to stdout; logs go to stderr. Fails at startup if the collection is incompatible."""
import logging
import sys

from mcp.server import MCPServer

from app.composition import build_composer
from app.tools.DocumentTools import SERVER_INSTRUCTIONS, register_tools

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
for noisy_logger in ("httpx", "httpx2", "huggingface_hub", "sentence_transformers"):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)


def build_server() -> MCPServer:
    server = MCPServer(name="petroandes-documents", version="1.0.0", instructions=SERVER_INSTRUCTIONS, log_level="WARNING")
    register_tools(server, build_composer())
    return server


if __name__ == "__main__":
    build_server().run(transport="stdio")

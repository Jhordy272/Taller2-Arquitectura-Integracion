"""MCP server entry point. Uses the stdio transport, so only protocol messages may go
to stdout; logs go to stderr. Fails at startup if the collection is incompatible."""
import logging
import sys

from mcp.server import MCPServer
from mcp.server.caching import CacheHint

from app.composition import build_composer, build_registry
from app.config.Settings import settings
from app.resources.ValidityResources import register_resources
from app.tools.DocumentTools import SERVER_INSTRUCTIONS, register_tools

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
for noisy_logger in ("httpx", "httpx2", "huggingface_hub", "sentence_transformers"):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)

# Freshness hints of MCP 2026-07-28 (ttlMs, cacheScope). The listings and the discovery only
# change with a deployment. The registry changes at any time, so a client may reuse it for no
# longer than the server takes to notice a change. None of them depends on who asks: public.
_STATIC_MS = 3_600_000


def cache_hints() -> dict[str, CacheHint]:
    static = CacheHint(ttl_ms=_STATIC_MS, scope="public")
    return {
        "server/discover": static,
        "tools/list": static,
        "resources/list": static,
        "resources/templates/list": static,
        "resources/read": CacheHint(ttl_ms=int(settings.registry_check_interval_s * 1000), scope="public"),
    }


def build_server() -> MCPServer:
    server = MCPServer(
        name="petroandes-documents",
        version="1.1.0",
        instructions=SERVER_INSTRUCTIONS,
        log_level="WARNING",
        cache_hints=cache_hints(),
    )
    registry = build_registry()
    register_tools(server, build_composer(registry))
    register_resources(server, registry)
    return server


if __name__ == "__main__":
    build_server().run(transport="stdio")

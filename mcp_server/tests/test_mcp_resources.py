"""MCP resources and 2026-07-28 metadata, through an in-process client: require neither
Qdrant nor the model."""
import asyncio
import json

from mcp import Client
from mcp.server import MCPServer
from mcp.server._otel import OpenTelemetryMiddleware

from app.main import cache_hints
from app.resources.ValidityResources import REGISTRY_URI, register_resources
from app.services.ValidityRegistry import ValidityRegistry
from app.tools.DocumentTools import register_tools
from tests.test_mcp_tools import FakeComposer

REGISTRY = [
    {"code": "PRO-MED-007", "version": "1", "status": "not_valid", "certification_state": "simulated",
     "superseded_by": "PRO-MED-007@2", "authority": "Gerencia de Medición", "evidence": "nota interna"},
    {"code": "PRO-MED-007", "version": "2", "status": "valid", "certification_state": "assumed",
     "superseded_by": None, "authority": "Gerencia de Medición"},
    {"code": "MAN-OPE-004", "version": "2", "status": "in_doubt", "certification_state": "pending",
     "superseded_by": None, "authority": "Gerencia de Medición"},
]


def server() -> MCPServer:
    instance = MCPServer(name="test", cache_hints=cache_hints())
    register_tools(instance, FakeComposer())
    register_resources(instance, ValidityRegistry(REGISTRY))
    return instance


def with_client(action):
    async def run():
        async with Client(server(), cache=None) as client:
            return await action(client)

    return asyncio.run(run())


def test_the_registry_is_a_resource_and_the_search_stays_a_tool():
    resources = with_client(lambda client: client.list_resources())
    assert [str(resource.uri) for resource in resources.resources] == [REGISTRY_URI]
    templates = with_client(lambda client: client.list_resource_templates())
    assert [template.uri_template for template in templates.resource_templates] == ["petroandes://validity/{code}"]


def test_the_registry_shows_states_without_working_notes():
    result = with_client(lambda client: client.read_resource(REGISTRY_URI))
    documents = json.loads(result.contents[0].text)["documents"]
    in_doubt = next(document for document in documents if document["code"] == "MAN-OPE-004")
    assert in_doubt["status"] == "in_doubt"
    assert in_doubt["certifying_authority"] == "Gerencia de Medición"
    assert all("evidence" not in document for document in documents)


def test_one_document_by_code():
    result = with_client(lambda client: client.read_resource("petroandes://validity/PRO-MED-007"))
    versions = json.loads(result.contents[0].text)["versions"]
    assert [(v["version"], v["status"]) for v in versions] == [("1", "not_valid"), ("2", "valid")]


def test_listings_declare_ttl_and_cache_scope():
    tools = with_client(lambda client: client.list_tools())
    assert (tools.ttl_ms, tools.cache_scope) == (3_600_000, "public")
    resources = with_client(lambda client: client.list_resources())
    assert (resources.ttl_ms, resources.cache_scope) == (3_600_000, "public")


def test_the_registry_may_not_be_cached_longer_than_a_reload():
    result = with_client(lambda client: client.read_resource(REGISTRY_URI))
    assert result.ttl_ms <= 2_000


def test_the_server_negotiates_the_2026_07_28_revision_through_discovery():
    async def protocol(client):
        return client.protocol_version, client.server_capabilities

    version, capabilities = with_client(protocol)
    assert version == "2026-07-28"
    assert capabilities.resources is not None and capabilities.tools is not None


def test_trace_context_in_meta_is_read_by_the_default_middleware():
    """The SDK opens a span per request, parented on the traceparent of _meta; it exports
    nothing until an OpenTelemetry exporter is configured."""
    assert any(isinstance(middleware, OpenTelemetryMiddleware) for middleware in server()._lowlevel_server.middleware)

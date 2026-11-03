"""MCP contracts, with the composer replaced by a fake: require neither Qdrant nor the model."""
import asyncio

import pytest
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from qdrant_client.http.exceptions import ResponseHandlingException

from app.models.Answer import Answer
from app.tools.DocumentTools import register_tools


class FakeComposer:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple] = []

    def answer(self, query: str) -> Answer:
        if self.error:
            raise self.error
        self.calls.append((query,))
        return Answer(status="rejected", query=query, message="No está.")

    def get_fragment(self, code: str, version: str, section_id: str) -> Answer:
        self.calls.append((code, version, section_id))
        return Answer(status="not_found", query=f"{code}@{version}#{section_id}", message="No existe.")


def server_with(composer: FakeComposer) -> MCPServer:
    server = MCPServer(name="test")
    register_tools(server, composer)
    return server


def tools_by_name() -> dict:
    tools = asyncio.run(server_with(FakeComposer()).list_tools())
    return {tool.name: tool for tool in tools}


def call(composer: FakeComposer, name: str, arguments: dict):
    return asyncio.run(server_with(composer).call_tool(name, arguments))


def test_exposes_exactly_the_two_tools():
    assert set(tools_by_name()) == {"search_documents", "get_fragment"}


@pytest.mark.parametrize("name", ["search_documents", "get_fragment"])
def test_every_tool_has_a_complete_read_only_contract(name):
    tool = tools_by_name()[name]
    assert tool.description
    assert tool.input_schema["required"]
    assert all(schema.get("description") for schema in tool.input_schema["properties"].values())
    assert "status" in tool.output_schema["properties"]
    assert tool.annotations.read_only_hint is True
    assert tool.annotations.destructive_hint is False


def test_validity_and_security_cannot_be_disabled_by_parameters():
    tools = tools_by_name()
    assert set(tools["search_documents"].input_schema["properties"]) == {"query"}
    assert set(tools["get_fragment"].input_schema["properties"]) == {"code", "version", "section_id"}


def test_search_returns_structured_status():
    result = call(FakeComposer(), "search_documents", {"query": "¿Algo?"})
    assert result.structured_content["status"] == "rejected"
    assert result.is_error is False


def test_get_fragment_passes_its_arguments():
    composer = FakeComposer()
    call(composer, "get_fragment", {"code": "PRO-MED-007", "version": "2", "section_id": "3.2"})
    assert composer.calls == [("PRO-MED-007", "2", "3.2")]


@pytest.mark.parametrize(
    "name, arguments",
    [
        ("search_documents", {}),
        ("search_documents", {"query": "x"}),
        ("search_documents", {"query": "x" * 501}),
        ("get_fragment", {"code": "PRO-MED-007", "version": "2"}),
        ("get_fragment", {"code": "pro med", "version": "2", "section_id": "3"}),
        ("get_fragment", {"code": "PRO-MED-007", "version": "latest", "section_id": "3"}),
        ("get_fragment", {"code": "PRO-MED-007", "version": "2", "section_id": "../secret"}),
    ],
)
def test_invalid_arguments_are_rejected(name, arguments):
    composer = FakeComposer()
    with pytest.raises(ToolError):
        call(composer, name, arguments)
    assert composer.calls == []


def test_backend_failure_gives_a_generic_error():
    composer = FakeComposer(error=ResponseHandlingException(Exception("internal-host:6333 refused")))
    with pytest.raises(ToolError) as error:
        call(composer, "search_documents", {"query": "¿Algo?"})
    assert "search_unavailable" in str(error.value)
    assert "internal-host" not in str(error.value)

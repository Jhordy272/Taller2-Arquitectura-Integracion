"""MCP resources: the validity registry as context the application or the user decides to
load, unlike the tools, which the model decides to call. Exposes states, never corpus text."""
import json

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ResourceError
from mcp.types import Annotations

from app.services.ValidityRegistry import ReloadingValidityRegistry, ValidityRegistry

REGISTRY_URI = "petroandes://validity/registry"
DOCUMENT_URI = "petroandes://validity/{code}"

REGISTRY_DESCRIPTION = """Validity state of every PetroAndes document: valid, not_valid or in_doubt, who must
certify it and what replaces it. Only valid documents can be cited by search_documents; in_doubt
means the issuing area has not certified it yet. Contains no document text."""

DOCUMENT_DESCRIPTION = """Validity state of every version of one document, by code. Example: PRO-MED-007."""

_FOR_USER_AND_MODEL = Annotations(audience=["user", "assistant"], priority=0.6)


def _public_view(entry: dict) -> dict:
    """The fields that explain a state; the registry's working notes stay out."""
    return {
        "code": entry["code"],
        "version": entry["version"],
        "document_class": entry.get("document_class"),
        "status": entry["status"],
        "certification_state": entry.get("certification_state"),
        "certifying_authority": entry.get("authority"),
        "superseded_by": entry["superseded_by"],
    }


def register_resources(server: MCPServer, registry: ValidityRegistry | ReloadingValidityRegistry) -> None:
    @server.resource(
        REGISTRY_URI,
        name="validity_registry",
        title="Validity registry",
        description=REGISTRY_DESCRIPTION,
        mime_type="application/json",
        annotations=_FOR_USER_AND_MODEL,
    )
    def validity_registry() -> str:
        documents = [_public_view(entry) for entry in registry.current().entries()]
        return json.dumps({"documents": documents}, ensure_ascii=False)

    @server.resource(
        DOCUMENT_URI,
        name="document_validity",
        title="Document validity",
        description=DOCUMENT_DESCRIPTION,
        mime_type="application/json",
        annotations=_FOR_USER_AND_MODEL,
    )
    def document_validity(code: str) -> str:
        versions = [_public_view(entry) for entry in registry.current().entries() if entry["code"] == code]
        if not versions:
            raise ResourceError(f"document_not_registered: {code}")
        return json.dumps({"code": code, "versions": versions}, ensure_ascii=False)

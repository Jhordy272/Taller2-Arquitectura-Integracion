"""Validity propagation, with the Qdrant client replaced by a fake."""
from types import SimpleNamespace

from app.repositories.QdrantRepository import QdrantRepository

ENTRIES = [
    {"code": "A", "version": "1", "status": "not_valid", "certification_state": "simulated", "superseded_by": "A@2"},
    {"code": "A", "version": "2", "status": "valid", "certification_state": "assumed", "superseded_by": None},
]


class FakeClient:
    def __init__(self, indexed: list[tuple[str, str]]) -> None:
        self.indexed = indexed
        self.updates: list[dict] = []
        self.upserts = 0

    def set_payload(self, name, payload, points, wait):
        code, version = (condition.match.value for condition in points.must)
        self.updates.append({"code": code, "version": version, **payload})

    def scroll(self, name, limit, offset, with_payload):
        records = [SimpleNamespace(id=index, payload={"code": c, "version": v}) for index, (c, v) in enumerate(self.indexed)]
        return records, None

    def upsert(self, *args, **kwargs):
        self.upserts += 1


def repository_with(client: FakeClient) -> QdrantRepository:
    repository = QdrantRepository.__new__(QdrantRepository)
    repository._client = client
    return repository


def state_of(client: FakeClient, code: str, version: str) -> dict:
    return next(update for update in client.updates if (update["code"], update["version"]) == (code, version))


def test_registry_state_reaches_each_version():
    client = FakeClient([("A", "1"), ("A", "2")])
    count, unregistered = repository_with(client).sync_validity("c", ENTRIES, "in_doubt")
    assert count == 2
    assert unregistered == []
    assert state_of(client, "A", "1")["validity_status"] == "not_valid"
    assert state_of(client, "A", "1")["superseded_by"] == "A@2"
    assert state_of(client, "A", "2")["validity_status"] == "valid"


def test_document_missing_from_the_registry_fails_closed():
    client = FakeClient([("A", "1"), ("A", "2"), ("B", "1")])
    _, unregistered = repository_with(client).sync_validity("c", ENTRIES, "in_doubt")
    assert unregistered == ["B@1"]
    assert state_of(client, "B", "1")["validity_status"] == "in_doubt"


def test_sync_does_not_rewrite_vectors():
    client = FakeClient([("A", "1"), ("A", "2")])
    repository_with(client).sync_validity("c", ENTRIES, "in_doubt")
    assert client.upserts == 0

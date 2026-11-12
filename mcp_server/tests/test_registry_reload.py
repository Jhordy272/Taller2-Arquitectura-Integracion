"""Propagation of a validity change without restarting: require neither Qdrant nor the model."""
import os

import pytest

from app.models.RetrievedFragment import SearchOutcome
from app.repositories.QdrantSearchRepository import validity_filter
from app.repositories.RegistryRepository import RegistryRepository
from app.services.ResponseComposer import ResponseComposer
from app.services.ValidityRegistry import ReloadingValidityRegistry

REGISTRY = """schema_version: 1
default_status: in_doubt
documents:
  - {{code: DOC-A, version: "1", status: {status}, superseded_by: null, authority: Area A}}
  - {{code: DOC-B, version: "1", status: valid, superseded_by: null, authority: Area B}}
"""


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def write(path, status: str, tick: int) -> None:
    path.write_text(REGISTRY.format(status=status), encoding="utf-8")
    # Distinct modification times even on file systems with coarse resolution.
    os.utime(path, ns=(tick * 1_000_000_000, tick * 1_000_000_000))


@pytest.fixture
def registry_file(tmp_path):
    path = tmp_path / "validity_registry.yaml"
    write(path, "valid", tick=1)
    return path


def reloading(path, clock) -> ReloadingValidityRegistry:
    return ReloadingValidityRegistry(RegistryRepository(path), check_interval_s=2.0, clock=clock)


def test_a_change_applies_after_the_check_interval_without_restart(registry_file):
    clock = FakeClock()
    registry = reloading(registry_file, clock)
    assert registry.current().not_valid_keys() == []

    write(registry_file, "in_doubt", tick=2)
    clock.now = 1.0
    assert registry.current().not_valid_keys() == [], "checked at most once per interval"

    clock.now = 2.5
    assert registry.current().not_valid_keys() == [("DOC-A", "1")]


def test_a_broken_file_keeps_the_last_good_registry(registry_file):
    clock = FakeClock()
    registry = reloading(registry_file, clock)

    registry_file.write_text("documents: [ {code: ", encoding="utf-8")
    os.utime(registry_file, ns=(3_000_000_000, 3_000_000_000))
    clock.now = 5.0
    assert registry.current().entry("DOC-A", "1")["status"] == "valid"

    write(registry_file, "not_valid", tick=4)
    clock.now = 10.0
    assert registry.current().not_valid_keys() == [("DOC-A", "1")]


class RecordingSearch:
    def __init__(self) -> None:
        self.excluded = None

    def search(self, query: str, limit: int, excluded=()) -> SearchOutcome:
        self.excluded = excluded
        return SearchOutcome(hybrid=[], dense=[], lexical=[])


def test_the_search_receives_the_documents_the_live_registry_excludes(registry_file):
    clock = FakeClock()
    search = RecordingSearch()
    composer = ResponseComposer(search, repository=None, registry=reloading(registry_file, clock), cosine_threshold=0.8, max_passages=5)

    composer.answer("¿Cuál es la tolerancia?")
    assert search.excluded == []

    write(registry_file, "in_doubt", tick=2)
    clock.now = 3.0
    composer.answer("¿Cuál es la tolerancia?")
    assert search.excluded == [("DOC-A", "1")]


def test_a_named_document_reports_the_new_state_without_restart(registry_file):
    clock = FakeClock()
    composer = ResponseComposer(RecordingSearch(), repository=None, registry=reloading(registry_file, clock), cosine_threshold=0.8, max_passages=5)
    assert composer.answer("DOC-A").status == "rejected"

    write(registry_file, "in_doubt", tick=2)
    clock.now = 3.0
    answer = composer.answer("DOC-A")
    assert answer.status == "excluded_document"
    assert answer.excluded_documents[0].certifying_authority == "Area A"


def test_the_filter_keeps_the_payload_condition_and_adds_the_exclusions():
    built = validity_filter([("DOC-A", "1")])
    assert built.must[0].key == "validity_status"
    excluded = built.must_not[0].must
    assert [(condition.key, condition.match.value) for condition in excluded] == [("code", "DOC-A"), ("version", "1")]
    assert validity_filter().must_not == []

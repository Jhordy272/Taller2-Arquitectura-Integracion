"""Integration tests: require Qdrant up and the corpus already ingested."""
import pytest

from app.config.Settings import settings
from app.repositories.QdrantSearchRepository import QdrantSearchRepository
from app.repositories.QueryEmbeddingRepository import QueryEmbeddingRepository
from app.services.HybridSearchService import HybridSearchService, ensure_compatible
from app.services.LexicalTokenizer import LexicalTokenizer

NOT_VALID_CODES = {"PRO-SEG-009", "RES-CREG-0112-2021"}
NOT_VALID_VERSIONS = {("PRO-MED-007", "1"), ("PRO-OPE-012", "2")}
ALL_FRAGMENTS = 200


@pytest.fixture(scope="module")
def repository() -> QdrantSearchRepository:
    return QdrantSearchRepository(settings.qdrant_url, settings.active_alias)


@pytest.fixture(scope="module")
def service(repository) -> HybridSearchService:
    return HybridSearchService(
        repository,
        QueryEmbeddingRepository(settings.embedding_model, settings.embedding_revision),
        LexicalTokenizer(),
        settings.branch_candidates,
    )


def ids(fragments) -> list[str]:
    return [fragment.fragment_id for fragment in fragments]


def test_active_collection_matches_configuration(repository):
    ensure_compatible(
        repository.collection_metadata(),
        settings.embedding_model,
        settings.embedding_revision,
        settings.embedding_dimensions,
    )


@pytest.mark.parametrize(
    "query",
    [
        "RES-CREG-0112-2021",
        "PRO-SEG-009",
        "incertidumbre máxima admisible 0,5 %",
        "tolerancia de conciliación 0,8 %",
        "umbral de 1.200 psi con ventana de 30 minutos",
        "reporte a la autoridad competente en 72 horas",
    ],
)
def test_not_valid_documents_never_appear_in_any_branch(service, query):
    outcome = service.search(query, limit=ALL_FRAGMENTS)
    for fragment in [*outcome.hybrid, *outcome.dense, *outcome.lexical]:
        assert fragment.validity_status == "valid"
        assert fragment.code not in NOT_VALID_CODES
        assert (fragment.code, fragment.version) not in NOT_VALID_VERSIONS


def test_exact_code_is_found_by_the_lexical_branch(service):
    outcome = service.search("VL-CC-022", limit=5)
    assert outcome.lexical[0].fragment_id == "MAN-MTO-002@1#2"
    assert "MAN-MTO-002@1#2" in ids(outcome.hybrid)


def test_natural_language_query_finds_the_valid_resolution(service):
    outcome = service.search("¿Cuál es la incertidumbre máxima admisible en la transferencia de custodia?", limit=5)
    assert "RES-CREG-0043-2024@unversioned#art-2" in ids(outcome.hybrid)


def test_poisoned_fragment_is_retrievable_and_flagged(service):
    outcome = service.search("notas de integración del firmware 7.4", limit=10)
    annex = [f for f in outcome.hybrid if f.fragment_id == "COM-PRV-0134@unversioned#anexo-notas-de-integracion"]
    assert annex and annex[0].injection_risk


def test_query_with_only_stopwords_still_returns_semantic_results(service):
    outcome = service.search("de la en", limit=3)
    assert outcome.lexical == []
    assert len(outcome.hybrid) == 3

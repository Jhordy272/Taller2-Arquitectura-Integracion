"""Wires the components and checks that the active collection is compatible."""
from app.config.Settings import settings
from app.repositories.QdrantSearchRepository import QdrantSearchRepository
from app.repositories.QueryEmbeddingRepository import QueryEmbeddingRepository
from app.repositories.RegistryRepository import RegistryRepository
from app.services.HybridSearchService import HybridSearchService, ensure_compatible
from app.services.LexicalTokenizer import LexicalTokenizer
from app.services.ResponseComposer import ResponseComposer
from app.services.ValidityRegistry import ValidityRegistry


def build_search_service() -> tuple[HybridSearchService, QdrantSearchRepository]:
    repository = QdrantSearchRepository(settings.qdrant_url, settings.active_alias)
    ensure_compatible(
        repository.collection_metadata(),
        settings.embedding_model,
        settings.embedding_revision,
        settings.embedding_dimensions,
    )
    service = HybridSearchService(
        repository,
        QueryEmbeddingRepository(settings.embedding_model, settings.embedding_revision),
        LexicalTokenizer(),
        settings.branch_candidates,
    )
    return service, repository


def build_composer() -> ResponseComposer:
    service, repository = build_search_service()
    return ResponseComposer(
        service,
        repository,
        ValidityRegistry(RegistryRepository(settings.validity_registry_path).load()),
        settings.rejection_cosine_threshold,
        settings.default_result_limit,
    )

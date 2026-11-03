"""Combines the query encoders with the filtered search, and checks at startup that
the active collection was built with the same model and tokenizer (ADR-04)."""
from app.models.RetrievedFragment import SearchOutcome
from app.repositories.QdrantSearchRepository import QdrantSearchRepository
from app.repositories.QueryEmbeddingRepository import QueryEmbeddingRepository
from app.services.LexicalTokenizer import TOKENIZER_VERSION, LexicalTokenizer


class IncompatibleCollectionError(RuntimeError):
    """The active collection cannot be queried with this configuration."""


class HybridSearchService:
    def __init__(
        self,
        repository: QdrantSearchRepository,
        embeddings: QueryEmbeddingRepository,
        tokenizer: LexicalTokenizer,
        branch_candidates: int,
    ) -> None:
        self._repository = repository
        self._embeddings = embeddings
        self._tokenizer = tokenizer
        self._branch_candidates = branch_candidates

    def search(self, query: str, limit: int) -> SearchOutcome:
        return self._repository.search(
            dense_vector=self._embeddings.embed(query),
            sparse_vector=self._tokenizer.query_vector(query),
            candidates=max(self._branch_candidates, limit),
            limit=limit,
        )


def ensure_compatible(metadata: dict, model: str, revision: str, dimensions: int) -> None:
    """Refuse to start when the query side differs from what the collection expects."""
    expected = {
        "embedding_model": model,
        "embedding_revision": revision,
        "embedding_dimensions": dimensions,
        "tokenizer_version": TOKENIZER_VERSION,
    }
    differences = {
        field: (metadata.get(field), value)
        for field, value in expected.items()
        if metadata.get(field) != value
    }
    if differences:
        raise IncompatibleCollectionError(f"collection differs from configuration: {differences}")

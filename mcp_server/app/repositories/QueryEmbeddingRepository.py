"""Encodes queries locally; local_files_only guarantees no call leaves the machine."""
from sentence_transformers import SentenceTransformer

_QUERY_PREFIX = "query: "


class QueryEmbeddingRepository:
    def __init__(self, model_name: str, revision: str) -> None:
        self._model = SentenceTransformer(model_name, revision=revision, device="cpu", local_files_only=True)

    def embed(self, query: str) -> list[float]:
        vector = self._model.encode(f"{_QUERY_PREFIX}{query}", normalize_embeddings=True, show_progress_bar=False)
        return vector.tolist()

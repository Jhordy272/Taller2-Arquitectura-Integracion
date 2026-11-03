"""Computes dense vectors locally with the pinned embedding model (ADR-04)."""
from sentence_transformers import SentenceTransformer

_PASSAGE_PREFIX = "passage: "


class EmbeddingRepository:
    def __init__(self, model_name: str, revision: str) -> None:
        self._model = SentenceTransformer(model_name, revision=revision, device="cpu")

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        """Encode passages with the prefix the model expects; cosine-ready vectors."""
        vectors = self._model.encode(
            [f"{_PASSAGE_PREFIX}{text}" for text in texts],
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vectors.tolist()

    def token_count(self, text: str) -> int:
        """Count tokens as the model does, including the passage prefix."""
        return len(self._model.tokenizer.encode(f"{_PASSAGE_PREFIX}{text}"))

    @property
    def max_tokens(self) -> int:
        return self._model.max_seq_length

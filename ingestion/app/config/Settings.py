"""Environment-driven settings for the ingestion component."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    corpus_pdf_dir: Path = _REPO_ROOT / "corpus" / "pdf"
    corpus_md_dir: Path = _REPO_ROOT / "corpus" / "md"
    validity_registry_path: Path = _REPO_ROOT / "data" / "validity_registry.yaml"

    qdrant_url: str = "http://localhost:6333"
    active_alias: str = "corpus_active"

    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_revision: str = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
    embedding_dimensions: int = 384


settings = Settings()

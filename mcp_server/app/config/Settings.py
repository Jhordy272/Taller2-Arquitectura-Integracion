"""Environment-driven settings for the MCP server."""
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    qdrant_url: str = "http://localhost:6333"
    active_alias: str = "corpus_active"
    validity_registry_path: Path = _REPO_ROOT / "data" / "validity_registry.yaml"
    # How often, at most, the server checks whether the registry file changed (propagation).
    registry_check_interval_s: float = 2.0

    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_revision: str = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
    embedding_dimensions: int = 384

    branch_candidates: int = 20
    default_result_limit: int = 5

    # Chosen by app/calibrate_threshold.py; re-evaluate with new reference cases.
    rejection_cosine_threshold: float = 0.84

    # Against "no sé" (LexicalGuard), adopted after the holdout experiment; "none" reproduces the baseline.
    answer_guard: Literal["none", "lexical"] = "lexical"
    # The passage must mention at least this share of the question's content terms.
    guard_min_coverage: float = 0.5


settings = Settings()

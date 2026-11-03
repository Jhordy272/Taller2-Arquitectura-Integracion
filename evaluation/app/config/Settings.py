"""Environment-driven settings for the evaluation harness."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    reference_cases_path: Path = _REPO_ROOT / "data" / "reference_cases.yaml"
    evidence_dir: Path = _REPO_ROOT / "data" / "evidence"
    mcp_server_dir: Path = _REPO_ROOT / "mcp_server"

    laya_model: str = "multilingual"
    laya_revision: str = "e4e9ddf21a7b1903b7acffd8814ad4307bf63a67"
    # Latency committed by scenario EI16 of Project 1.
    latency_commitment_ms: float = 5000.0


settings = Settings()

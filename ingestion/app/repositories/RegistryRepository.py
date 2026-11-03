"""Reads the validity registry."""
from pathlib import Path

import yaml


class RegistryRepository:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> list[dict]:
        return self._read()["documents"]

    def default_status(self) -> str:
        """Status of a document that is not in the registry."""
        return self._read()["default_status"]

    def _read(self) -> dict:
        return yaml.safe_load(self._path.read_text(encoding="utf-8"))

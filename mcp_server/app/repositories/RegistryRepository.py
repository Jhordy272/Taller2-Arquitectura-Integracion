"""Reads the validity registry."""
from pathlib import Path

import yaml


class RegistryRepository:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> list[dict]:
        registry = yaml.safe_load(self._path.read_text(encoding="utf-8"))
        return registry["documents"]

"""Reads the reference cases."""
from pathlib import Path

import yaml


class CaseRepository:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> list[dict]:
        return yaml.safe_load(self._path.read_text(encoding="utf-8"))["cases"]

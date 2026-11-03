"""Answers validity questions from the registry, the source of truth (ADR-07)."""
import re

from app.models.Answer import ExcludedDocument
from app.services.QueryAnalyzer import contains_identifier, normalize

VALID = "valid"

_RESOLUTION_NUMBER = re.compile(r"-(\d{4})-(\d{4})$")


class ValidityRegistry:
    def __init__(self, entries: list[dict]) -> None:
        self._entries = {(entry["code"], entry["version"]): entry for entry in entries}
        self._by_code: dict[str, list[dict]] = {}
        for entry in entries:
            self._by_code.setdefault(entry["code"], []).append(entry)

    def entry(self, code: str, version: str) -> dict | None:
        return self._entries.get((code, version))

    def excluded(self, entry: dict) -> ExcludedDocument:
        return ExcludedDocument(
            code=entry["code"],
            version=entry["version"],
            status=entry["status"],
            superseded_by=entry["superseded_by"],
        )

    def excluded_mentions(self, query: str) -> list[ExcludedDocument]:
        """Return the excluded documents the query names, by code or by resolution number."""
        normalized = normalize(query)
        mentioned: list[dict] = []
        for code, entries in self._by_code.items():
            mentioned.extend(self._mentioned_excluded(normalized, code, entries))
        return [self.excluded(entry) for entry in mentioned]

    def _mentioned_excluded(self, query: str, code: str, entries: list[dict]) -> list[dict]:
        if not self._names_code(query, code):
            return []

        version = self._named_version(query, code)
        if version is not None:
            return [e for e in entries if e["version"] == version and e["status"] != VALID]

        # Without a version, a code is excluded only if none of its versions is valid.
        return [] if any(e["status"] == VALID for e in entries) else entries

    def _names_code(self, query: str, code: str) -> bool:
        if contains_identifier(query, code.lower()):
            return True
        number = _RESOLUTION_NUMBER.search(code)
        return number is not None and f"resolucion {number.group(1)} de {number.group(2)}" in query

    def _named_version(self, query: str, code: str) -> str | None:
        match = re.search(rf"{re.escape(code.lower())},? (?:v|version )(\d+)", query)
        return match.group(1) if match else None

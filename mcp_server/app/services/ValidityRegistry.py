"""Answers validity questions from the registry, the source of truth (ADR-07)."""
import logging
import re
import time
from typing import Callable

import yaml

from app.models.Answer import ExcludedDocument
from app.repositories.RegistryRepository import RegistryRepository
from app.services.QueryAnalyzer import contains_identifier, normalize

VALID = "valid"
IN_DOUBT = "in_doubt"

_RESOLUTION_NUMBER = re.compile(r"-(\d{4})-(\d{4})$")

logger = logging.getLogger("mcp_server.registry")


class ValidityRegistry:
    def __init__(self, entries: list[dict]) -> None:
        self._entries = {(entry["code"], entry["version"]): entry for entry in entries}
        self._by_code: dict[str, list[dict]] = {}
        for entry in entries:
            self._by_code.setdefault(entry["code"], []).append(entry)

    def current(self) -> "ValidityRegistry":
        """A fixed registry is its own current version."""
        return self

    def entries(self) -> list[dict]:
        return list(self._entries.values())

    def entry(self, code: str, version: str) -> dict | None:
        return self._entries.get((code, version))

    def not_valid_keys(self) -> list[tuple[str, str]]:
        """Code and version of every document the search must leave out."""
        return sorted(key for key, entry in self._entries.items() if entry["status"] != VALID)

    def excluded(self, entry: dict) -> ExcludedDocument:
        return ExcludedDocument(
            code=entry["code"],
            version=entry["version"],
            status=entry["status"],
            superseded_by=entry["superseded_by"],
            certifying_authority=entry.get("authority"),
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


class ReloadingValidityRegistry:
    """Rereads the registry file when it changes, so a validity change propagates without
    restarting the server. The file is checked at most once per interval."""

    def __init__(
        self,
        repository: RegistryRepository,
        check_interval_s: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._repository = repository
        self._check_interval_s = check_interval_s
        self._clock = clock
        self._modified_at = repository.modified_at()
        self._current = ValidityRegistry(repository.load())
        self._checked_at = clock()

    def current(self) -> ValidityRegistry:
        now = self._clock()
        if now - self._checked_at >= self._check_interval_s:
            self._checked_at = now
            self._reload_if_changed()
        return self._current

    def _reload_if_changed(self) -> None:
        modified_at = self._repository.modified_at()
        if modified_at == self._modified_at:
            return
        try:
            entries = self._repository.load()
            registry = ValidityRegistry(entries)
        except (OSError, yaml.YAMLError, KeyError, TypeError) as error:
            # A file caught mid-write: keep the last good registry and retry on the next check.
            logger.warning("validity registry not reloaded: %s", error)
            return
        self._current = registry
        self._modified_at = modified_at
        logger.info("validity registry reloaded: %d documents", len(entries))

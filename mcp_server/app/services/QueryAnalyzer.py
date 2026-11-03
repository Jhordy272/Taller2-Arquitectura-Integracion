"""Detects exact identifiers in a query: document and asset codes, work orders and
kilometer positions. These are matched literally because they carry no meaning."""
import re
import unicodedata

_IDENTIFIER = re.compile(
    r"(?<![a-z0-9-])[a-z]+(?:-[a-z0-9]+)*-[a-z]*\d[a-z0-9-]*(?![a-z0-9-])"  # VL-CC-022, P-101
    r"|\bk ?\d{3}\+\d{3}\b"  # K 061+800
)


def normalize(text: str) -> str:
    """Lowercase, strip accents and collapse whitespace."""
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(without_accents.lower().split())


def extract_identifiers(query: str) -> list[str]:
    return _IDENTIFIER.findall(normalize(query))


def contains_identifier(text: str, identifier: str) -> bool:
    """Match the whole identifier, so "cmp-99" does not match "cmp-999"."""
    pattern = rf"(?<![a-z0-9-]){re.escape(identifier)}(?![a-z0-9-])"
    return re.search(pattern, normalize(text)) is not None

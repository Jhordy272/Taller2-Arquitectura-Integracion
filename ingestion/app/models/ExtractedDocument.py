"""Domain entities: a corpus document as extracted from its PDF."""
from dataclasses import dataclass
from typing import Literal

# Version of documents without one, such as resolutions and minutes.
UNVERSIONED = "unversioned"


@dataclass(frozen=True)
class DocumentMetadata:
    code: str
    version: str
    title: str
    document_type: str
    issue_date: str
    issuing_area: str  # internal area responsible for the document
    issuer: str  # organization named above the title
    replaces: str | None  # document this one replaces, e.g. "MAN-OPE-001 v2"


@dataclass(frozen=True)
class Block:
    kind: Literal["paragraph", "list_item", "table"]
    text: str
    numeral: str | None = None  # e.g. "3.1"; None before the section's first numeral
    rows: tuple[tuple[str, ...], ...] = ()  # only for tables


@dataclass(frozen=True)
class Section:
    section_id: str
    heading: str
    title: str
    blocks: tuple[Block, ...]


@dataclass(frozen=True)
class ExtractedDocument:
    source: str
    metadata: DocumentMetadata
    sections: tuple[Section, ...]

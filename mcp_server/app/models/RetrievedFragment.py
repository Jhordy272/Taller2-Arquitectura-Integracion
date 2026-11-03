"""Domain entities: fragments returned by a search."""
from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievedFragment:
    fragment_id: str  # code@version#section
    score: float  # meaning depends on the branch: RRF, cosine or BM25
    code: str
    version: str
    title: str
    document_type: str
    document_class: str
    issue_date: str
    issuing_area: str
    section_id: str
    section_title: str
    parent_section_id: str | None
    text: str
    indexed_text: str  # text prefixed with code and titles; used for exact matching
    validity_status: str
    injection_risk: bool


@dataclass(frozen=True)
class SearchOutcome:
    hybrid: list[RetrievedFragment]  # cut to the requested limit
    dense: list[RetrievedFragment]  # every candidate of the branch
    lexical: list[RetrievedFragment]  # every candidate of the branch

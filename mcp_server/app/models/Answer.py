"""Domain entities: the composed response of the service (ADR-03)."""
from dataclasses import dataclass, field
from typing import Literal

AnswerStatus = Literal["answered", "rejected", "excluded_document", "not_found"]


@dataclass(frozen=True)
class Citation:
    code: str
    version: str
    section_id: str
    section_title: str
    title: str
    document_type: str
    document_class: str  # "record" must not be read as a rule
    issue_date: str
    issuing_area: str


@dataclass(frozen=True)
class Content:
    citation: Citation
    text: str | None  # literal corpus text; None when withheld
    withheld: bool
    alert: str | None
    trust: str = "untrusted_data"  # corpus text is data, never instructions


@dataclass(frozen=True)
class Passage:
    content: Content
    parent_context: Content | None  # section the numeral belongs to (ADR-02)


@dataclass(frozen=True)
class ExcludedDocument:
    code: str
    version: str
    status: str
    superseded_by: str | None


@dataclass(frozen=True)
class Answer:
    status: AnswerStatus
    query: str
    message: str
    passages: list[Passage] = field(default_factory=list)
    excluded_documents: list[ExcludedDocument] = field(default_factory=list)

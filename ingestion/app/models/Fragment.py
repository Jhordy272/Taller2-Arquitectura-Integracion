"""Domain entity: the citable unit stored in the index."""
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Fragment:
    fragment_id: str  # code@version#section
    code: str
    version: str
    title: str
    document_type: str
    document_class: str  # operational, regulatory or record
    issue_date: str
    issuing_area: str
    section_id: str  # section ("3") or numeral ("3.1")
    section_title: str
    parent_section_id: str | None  # section of a numeral; None for a section unit
    text: str  # literal content shown to the user
    indexed_text: str  # text prefixed with document and section titles
    validity_status: str
    certification_state: str
    superseded_by: str | None
    injection_risk: bool
    injection_reason: str | None

    def payload(self) -> dict:
        return asdict(self)

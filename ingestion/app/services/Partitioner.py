"""Splits a document into citable fragments following ADR-02: one per numeral, plus
one for the content before a section's first numeral. Tables are never divided."""
from app.models.ExtractedDocument import Block, ExtractedDocument, Section
from app.models.Fragment import Fragment
from app.services.InjectionDetector import InjectionDetector

PARTITION_VERSION = "1"


class Partitioner:
    def __init__(self, registry: list[dict], detector: InjectionDetector) -> None:
        self._registry = {(entry["code"], entry["version"]): entry for entry in registry}
        self._detector = detector

    def partition(self, document: ExtractedDocument) -> list[Fragment]:
        fragments: list[Fragment] = []
        for section in document.sections:
            for section_id, parent_id, blocks in self._units(section):
                fragments.append(self._build_fragment(document, section, section_id, parent_id, blocks))
        return fragments

    def _units(self, section: Section) -> list[tuple[str, str | None, list[Block]]]:
        """Group blocks by numeral; blocks before the first numeral form the section unit."""
        intro = [block for block in section.blocks if block.numeral is None]
        units: list[tuple[str, str | None, list[Block]]] = []
        if intro:
            units.append((section.section_id, None, intro))

        numerals = dict.fromkeys(block.numeral for block in section.blocks if block.numeral)
        for numeral in numerals:
            blocks = [block for block in section.blocks if block.numeral == numeral]
            units.append((numeral, section.section_id, blocks))
        return units

    def _build_fragment(
        self,
        document: ExtractedDocument,
        section: Section,
        section_id: str,
        parent_id: str | None,
        blocks: list[Block],
    ) -> Fragment:
        metadata = document.metadata
        entry = self._registry[(metadata.code, metadata.version)]
        text = "\n".join(self.render(block) for block in blocks)
        reason = self._detector.detect(text)
        return Fragment(
            fragment_id=f"{metadata.code}@{metadata.version}#{section_id}",
            code=metadata.code,
            version=metadata.version,
            title=metadata.title,
            document_type=metadata.document_type,
            document_class=entry["document_class"],
            issue_date=metadata.issue_date,
            issuing_area=metadata.issuing_area,
            section_id=section_id,
            section_title=section.title,
            parent_section_id=parent_id,
            text=text,
            indexed_text=f"{metadata.code} {metadata.title}\n{section.heading}\n{text}",
            validity_status=entry["status"],
            certification_state=entry["certification_state"],
            superseded_by=entry["superseded_by"],
            injection_risk=reason is not None,
            injection_reason=reason,
        )

    def render(self, block: Block) -> str:
        """Render a table row per line so its values stay next to each other."""
        if block.kind == "table":
            return "\n".join(" | ".join(row) for row in block.rows)
        return f"- {block.text}" if block.kind == "list_item" else block.text

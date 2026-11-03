"""Baseline partition for the evaluation only (ADR-02): fixed-size word windows with
overlap. It ignores the document structure, so its fragments are not citable sections."""
from app.models.ExtractedDocument import ExtractedDocument
from app.models.Fragment import Fragment
from app.services.InjectionDetector import InjectionDetector
from app.services.Partitioner import Partitioner

CHUNK_WORDS = 120
OVERLAP_WORDS = 20


class FixedSizePartitioner:
    def __init__(self, registry: list[dict], detector: InjectionDetector) -> None:
        self._registry = {(entry["code"], entry["version"]): entry for entry in registry}
        self._detector = detector
        self._renderer = Partitioner(registry, detector)

    def partition(self, document: ExtractedDocument) -> list[Fragment]:
        metadata = document.metadata
        entry = self._registry[(metadata.code, metadata.version)]
        words = self._document_text(document).split()
        fragments = []
        for number, start in enumerate(range(0, len(words), CHUNK_WORDS - OVERLAP_WORDS), start=1):
            text = " ".join(words[start : start + CHUNK_WORDS])
            reason = self._detector.detect(text)
            fragments.append(
                Fragment(
                    fragment_id=f"{metadata.code}@{metadata.version}#chunk-{number}",
                    code=metadata.code,
                    version=metadata.version,
                    title=metadata.title,
                    document_type=metadata.document_type,
                    document_class=entry["document_class"],
                    issue_date=metadata.issue_date,
                    issuing_area=metadata.issuing_area,
                    section_id=f"chunk-{number}",
                    section_title=f"Fragmento {number}",
                    parent_section_id=None,
                    text=text,
                    indexed_text=f"{metadata.code} {metadata.title}\n{text}",
                    validity_status=entry["status"],
                    certification_state=entry["certification_state"],
                    superseded_by=entry["superseded_by"],
                    injection_risk=reason is not None,
                    injection_reason=reason,
                )
            )
            if start + CHUNK_WORDS >= len(words):
                break
        return fragments

    def _document_text(self, document: ExtractedDocument) -> str:
        parts = []
        for section in document.sections:
            parts.append(section.heading)
            parts.extend(self._renderer.render(block) for block in section.blocks)
        return "\n".join(parts)

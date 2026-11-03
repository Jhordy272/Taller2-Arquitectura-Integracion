"""Verifies an extracted document against its Markdown copy and the validity registry."""
from app.models.ExtractedDocument import UNVERSIONED, ExtractedDocument
from app.models.VerificationIssue import VerificationIssue
from app.repositories.MarkdownRepository import MarkdownDocument

# Placeholder the corpus uses for an empty header field.
_NO_VALUE = "—"


class ExtractionVerifier:
    def __init__(self, registry: list[dict]) -> None:
        self._registry = {(entry["code"], entry["version"]): entry for entry in registry}

    def verify(self, document: ExtractedDocument, markdown: MarkdownDocument) -> list[VerificationIssue]:
        """Return every difference found; an empty list means the extraction is correct."""
        return [
            *self._verify_registry(document),
            *self._verify_metadata(document, markdown.header),
            *self._verify_sections(document, markdown.sections),
        ]

    def _verify_registry(self, document: ExtractedDocument) -> list[VerificationIssue]:
        """Check the document is registered and its issuing area is the registered authority."""
        metadata = document.metadata
        entry = self._registry.get((metadata.code, metadata.version))
        if entry is None:
            return [self._issue(document, "registry", f"{metadata.code}@{metadata.version}", "missing")]
        if entry["authority"] != metadata.issuing_area:
            return [self._issue(document, "registry.authority", entry["authority"], metadata.issuing_area)]
        return []

    def _verify_metadata(self, document: ExtractedDocument, header: dict[str, str]) -> list[VerificationIssue]:
        """Compare PDF metadata with the Markdown header, whose keys are in Spanish."""
        metadata = document.metadata
        version = UNVERSIONED if header["version"] == _NO_VALUE else header["version"]
        replaces = None if header["reemplaza_a"] == _NO_VALUE else header["reemplaza_a"]
        expected = {
            "code": (header["codigo"], metadata.code),
            "version": (version, metadata.version),
            "title": (header["titulo"], metadata.title),
            "document_type": (header["tipo"], metadata.document_type),
            "issue_date": (header["fecha_emision"], metadata.issue_date),
            "issuing_area": (header["area_emisora"], metadata.issuing_area),
            "replaces": (replaces, metadata.replaces),
        }
        return [
            self._issue(document, field, str(wanted), str(found))
            for field, (wanted, found) in expected.items()
            if wanted != found
        ]

    def _verify_sections(self, document: ExtractedDocument, sections: dict[str, str]) -> list[VerificationIssue]:
        """Compare heading order and the text of each section, ignoring whitespace."""
        extracted = {section.heading: section for section in document.sections}
        if list(extracted) != list(sections):
            return [self._issue(document, "headings", str(list(sections)), str(list(extracted)))]

        issues = []
        for heading, expected_text in sections.items():
            actual_text = " ".join(block.text for block in extracted[heading].blocks)
            if self._normalize(expected_text) != self._normalize(actual_text):
                issues.append(self._issue(document, f"section:{heading}", expected_text, actual_text))
        return issues

    def _normalize(self, text: str) -> str:
        return " ".join(text.split())

    def _issue(self, document: ExtractedDocument, field: str, expected: str, actual: str) -> VerificationIssue:
        return VerificationIssue(source=document.source, field=field, expected=expected, actual=actual)

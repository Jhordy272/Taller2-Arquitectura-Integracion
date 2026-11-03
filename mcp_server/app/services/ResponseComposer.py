"""Composes answers deterministically: literal passages with citations, or an
explicit refusal (ADR-03). Never generates text about the corpus content."""
from app.models.Answer import Answer, Citation, Content, ExcludedDocument, Passage
from app.models.RetrievedFragment import RetrievedFragment, SearchOutcome
from app.repositories.QdrantSearchRepository import QdrantSearchRepository
from app.services.HybridSearchService import HybridSearchService
from app.services.QueryAnalyzer import contains_identifier, extract_identifiers
from app.services.ValidityRegistry import VALID, ValidityRegistry

MESSAGE_ANSWERED = "Pasajes literales del corpus, con su cita. No se generó texto adicional."
MESSAGE_NO_SUPPORT = "La respuesta no está en el corpus vigente."
MESSAGE_UNKNOWN_IDENTIFIER = "El identificador consultado no aparece en el corpus vigente."
MESSAGE_EXCLUDED = "El documento consultado no está vigente: no se muestra su contenido."
MESSAGE_FRAGMENT_NOT_FOUND = "El fragmento solicitado no existe en el corpus vigente."
ALERT_WITHHELD = "Contenido retenido: contiene instrucciones dirigidas a sistemas automáticos."


class ResponseComposer:
    def __init__(
        self,
        search_service: HybridSearchService,
        repository: QdrantSearchRepository,
        registry: ValidityRegistry,
        cosine_threshold: float,
        max_passages: int,
    ) -> None:
        self._search_service = search_service
        self._repository = repository
        self._registry = registry
        self._cosine_threshold = cosine_threshold
        self._max_passages = max_passages

    def answer(self, query: str) -> Answer:
        """Excluded documents are checked first, so they are reported, not just omitted."""
        excluded = self._registry.excluded_mentions(query)
        if excluded:
            return self._excluded_answer(query, excluded)

        outcome = self._search_service.search(query, self._max_passages)
        identifiers = extract_identifiers(query)
        if identifiers:
            selected = self._select_by_identifier(outcome, identifiers)
            refusal = MESSAGE_UNKNOWN_IDENTIFIER
        else:
            selected = self._select_by_similarity(outcome)
            refusal = MESSAGE_NO_SUPPORT

        if not selected:
            return Answer(status="rejected", query=query, message=refusal)
        return self._answered(query, selected)

    def get_fragment(self, code: str, version: str, section_id: str) -> Answer:
        """Return one fragment under the same validity and retention rules as a search."""
        query = f"{code}@{version}#{section_id}"
        entry = self._registry.entry(code, version)
        if entry is None:
            return Answer(status="not_found", query=query, message=MESSAGE_FRAGMENT_NOT_FOUND)
        if entry["status"] != VALID:
            return self._excluded_answer(query, [self._registry.excluded(entry)])

        fragment = self._repository.get_fragment(query)
        if fragment is None:
            return Answer(status="not_found", query=query, message=MESSAGE_FRAGMENT_NOT_FOUND)
        return self._answered(query, [fragment])

    def _select_by_identifier(self, outcome: SearchOutcome, identifiers: list[str]) -> list[RetrievedFragment]:
        """An identifier has no meaning to compare: it must appear literally."""
        unique = {fragment.fragment_id: fragment for fragment in [*outcome.hybrid, *outcome.lexical]}
        matching = [
            fragment
            for fragment in unique.values()
            if any(contains_identifier(fragment.indexed_text, identifier) for identifier in identifiers)
        ]
        return matching[: self._max_passages]

    def _select_by_similarity(self, outcome: SearchOutcome) -> list[RetrievedFragment]:
        """RRF scores only rank, so the cosine of the dense branch decides the support."""
        cosine = {fragment.fragment_id: fragment.score for fragment in outcome.dense}
        return [
            fragment
            for fragment in outcome.hybrid
            if cosine.get(fragment.fragment_id, 0.0) >= self._cosine_threshold
        ]

    def _answered(self, query: str, fragments: list[RetrievedFragment]) -> Answer:
        selected_ids = {fragment.fragment_id for fragment in fragments}
        passages = [
            Passage(
                content=self._content(fragment),
                parent_context=self._parent_context(fragment, selected_ids),
            )
            for fragment in fragments
        ]
        return Answer(status="answered", query=query, message=MESSAGE_ANSWERED, passages=passages)

    def _parent_context(self, fragment: RetrievedFragment, selected_ids: set[str]) -> Content | None:
        """Add the parent section, unless the answer already shows it as a passage."""
        if fragment.parent_section_id is None:
            return None
        parent_id = f"{fragment.code}@{fragment.version}#{fragment.parent_section_id}"
        if parent_id in selected_ids:
            return None
        parent = self._repository.get_fragment(parent_id)
        return self._content(parent) if parent else None

    def _content(self, fragment: RetrievedFragment) -> Content:
        """Withhold flagged content on every path that returns text (ADR-06)."""
        citation = Citation(
            code=fragment.code,
            version=fragment.version,
            section_id=fragment.section_id,
            section_title=fragment.section_title,
            title=fragment.title,
            document_type=fragment.document_type,
            document_class=fragment.document_class,
            issue_date=fragment.issue_date,
            issuing_area=fragment.issuing_area,
        )
        if fragment.injection_risk:
            return Content(citation=citation, text=None, withheld=True, alert=ALERT_WITHHELD)
        return Content(citation=citation, text=fragment.text, withheld=False, alert=None)

    def _excluded_answer(self, query: str, excluded: list[ExcludedDocument]) -> Answer:
        return Answer(status="excluded_document", query=query, message=MESSAGE_EXCLUDED, excluded_documents=excluded)

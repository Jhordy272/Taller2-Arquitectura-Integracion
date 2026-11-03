"""Integration tests of composed answers: require Qdrant up and the corpus ingested."""
import pytest

from app.composition import build_composer


@pytest.fixture(scope="module")
def composer():
    return build_composer()


def citations(answer) -> list[str]:
    return [f"{p.content.citation.code}@{p.content.citation.version}#{p.content.citation.section_id}" for p in answer.passages]


def test_location_with_low_similarity_is_answered(composer):
    answer = composer.answer("K 061+800")
    assert answer.status == "answered"
    assert citations(answer) == ["MAN-MTO-002@1#2"]


def test_unrelated_fragments_are_dropped_for_identifiers(composer):
    assert citations(composer.answer("VL-CC-022")) == ["MAN-MTO-002@1#2"]


def test_identifier_parts_do_not_match_other_documents(composer):
    assert "PRO-HSE-003" not in " ".join(citations(composer.answer("VA-AY-003")))


def test_unknown_code_is_rejected(composer):
    assert composer.answer("¿Qué pasa con el código CMP-999?").status == "rejected"


def test_question_outside_the_corpus_is_rejected(composer):
    assert composer.answer("¿Cuál es el precio internacional del barril de crudo Brent?").status == "rejected"


def test_tolerance_answer_comes_from_the_valid_version_with_its_value(composer):
    answer = composer.answer("¿Cuál es la tolerancia de conciliación?")
    assert answer.status == "answered"
    assert all(p.content.citation.version == "2" for p in answer.passages if p.content.citation.code == "PRO-MED-007")
    shown = " ".join(
        content.text
        for passage in answer.passages
        for content in (passage.content, passage.parent_context)
        if content is not None and content.text
    )
    assert "0,5 %" in shown
    assert "0,8 %" not in shown


def test_repealed_resolution_reports_its_successor(composer):
    answer = composer.answer("RES-CREG-0112-2021")
    assert answer.status == "excluded_document"
    assert answer.excluded_documents[0].superseded_by == "RES-CREG-0043-2024@unversioned"


def test_poisoned_annex_is_withheld(composer):
    answer = composer.get_fragment("COM-PRV-0134", "unversioned", "anexo-notas-de-integracion")
    content = answer.passages[0].content
    assert content.withheld and content.text is None
    assert "soporte-firmware" not in str(answer)


def test_rest_of_the_poisoned_document_is_returned(composer):
    answer = composer.get_fragment("COM-PRV-0134", "unversioned", "asunto")
    assert "firmware" in answer.passages[0].content.text


def test_repealed_fragment_cannot_be_fetched(composer):
    answer = composer.get_fragment("RES-CREG-0112-2021", "unversioned", "art-2")
    assert answer.status == "excluded_document"
    assert answer.passages == []

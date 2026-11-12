"""The "no sé" guard, with search replaced by fakes: require neither Qdrant nor the model."""
from app.models.RetrievedFragment import SearchOutcome
from app.services.LexicalGuard import LexicalGuard
from app.services.LexicalTokenizer import LexicalTokenizer
from app.services.ResponseComposer import ResponseComposer
from app.services.ValidityRegistry import ValidityRegistry
from tests.test_answer_rules import FakeRepository, FakeSearch, fragment

GUARD = LexicalGuard(LexicalTokenizer(), min_coverage=0.5)


def test_question_words_and_stopwords_are_not_terms():
    assert GUARD.query_terms("¿Cuál es el plazo de cierre de la conciliación?") == ["plazo", "cierre", "conciliacion"]


def test_coverage_uses_light_stemming():
    assert GUARD.coverage("¿En qué plazo se investigan las diferencias?", "Las diferencias se investigan en un plazo") == 1.0
    assert GUARD.coverage("válvulas", "la válvula VL-CC-022") == 1.0


def test_a_near_passage_that_does_not_cover_the_question_is_refused():
    near = fragment("A@1#1", score=0.9, text="Programa de mantenimiento de equipos")
    composer = ResponseComposer(
        FakeSearch(SearchOutcome(hybrid=[near], dense=[near], lexical=[])),
        FakeRepository(),
        ValidityRegistry([]),
        0.83,
        5,
        GUARD,
    )
    assert composer.answer("¿Cuál es el presupuesto anual de compras de repuestos?").status == "rejected"
    assert composer.answer("¿Cuál es el programa de mantenimiento?").status == "answered"


def test_the_parent_section_counts_as_shown_text():
    child = fragment("A@1#3.1", score=0.9, text="Se archivan sin investigación.", parent="3")
    parent = fragment("A@1#3", text="Criterios de aceptación de la tolerancia de conciliación")
    composer = ResponseComposer(
        FakeSearch(SearchOutcome(hybrid=[child], dense=[child], lexical=[])),
        FakeRepository([parent]),
        ValidityRegistry([]),
        0.83,
        5,
        GUARD,
    )
    assert composer.answer("¿Qué pasa con la tolerancia de conciliación?").status == "answered"


def test_without_guard_the_cosine_alone_decides():
    near = fragment("A@1#1", score=0.9, text="Programa de mantenimiento de equipos")
    composer = ResponseComposer(
        FakeSearch(SearchOutcome(hybrid=[near], dense=[near], lexical=[])), FakeRepository(), ValidityRegistry([]), 0.83, 5
    )
    assert composer.answer("¿Cuál es el presupuesto anual de compras de repuestos?").status == "answered"

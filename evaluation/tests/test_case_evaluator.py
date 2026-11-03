"""Verdict rules, without the server or laya."""
from app.models.CaseResult import CaseResult, CaseVerdict
from app.services.CaseEvaluator import evaluate_case, passage_texts, select_control, shown_text
from app.services.MetricsReport import build_summary


def content(section: str, text: str | None, code: str = "PRO-MED-007", version: str = "2") -> dict:
    return {
        "citation": {"code": code, "version": version, "section_id": section},
        "text": text,
        "withheld": text is None,
    }


def answered(*passages: dict) -> dict:
    return {"status": "answered", "passages": list(passages), "excluded_documents": []}


REJECTED = {"status": "rejected", "passages": [], "excluded_documents": []}
ANSWERABLE = {
    "id": "A",
    "kind": "answerable",
    "origin": "new",
    "query": "q",
    "expected_answer": "0,5 %",
    "expected_fragment": "PRO-MED-007@2#3",
    "must_contain": ["0,5 %"],
    "must_not_contain": ["0,8 %"],
}


def test_value_in_the_parent_context_counts_as_correct():
    answer = answered({"content": content("3.2", "texto"), "parent_context": content("3", "Tolerancia | 0,5 %")})
    verdict = evaluate_case(ANSWERABLE, answer, 10)
    assert verdict.outcome == "correct"
    assert verdict.hit is True
    assert verdict.reciprocal_rank == 0.0


def test_first_position_has_reciprocal_rank_one():
    answer = answered({"content": content("3", "0,5 %"), "parent_context": None})
    assert evaluate_case(ANSWERABLE, answer, 10).reciprocal_rank == 1.0


def test_answer_without_the_value_is_wrong():
    answer = answered({"content": content("9", "otro tema"), "parent_context": None})
    verdict = evaluate_case(ANSWERABLE, answer, 10)
    assert verdict.outcome == "wrong_answer"
    assert verdict.hit is False
    assert not verdict.passed


def test_stale_value_fails_even_if_the_right_value_is_present():
    answer = answered({"content": content("3", "0,5 % y 0,8 %"), "parent_context": None})
    assert evaluate_case(ANSWERABLE, answer, 10).outcome == "stale_value"


def test_refusing_a_valid_question_fails():
    assert evaluate_case(ANSWERABLE, REJECTED, 10).outcome == "refused_valid"


def test_refusal_outside_the_corpus_passes():
    case = {"kind": "out_of_corpus"}
    assert evaluate_case(case, REJECTED, 10).passed


def test_answer_outside_the_corpus_is_a_false_answer():
    case = {"kind": "out_of_corpus"}
    answer = answered({"content": content("1", "x"), "parent_context": None})
    assert evaluate_case(case, answer, 10).outcome == "false_answer"


def test_excluded_document_requires_status_and_successor():
    case = {"kind": "excluded", "expected_successor": "B@1"}
    answer = {"status": "excluded_document", "passages": [], "excluded_documents": [{"superseded_by": "B@1"}]}
    assert evaluate_case(case, answer, 10).passed
    answer["excluded_documents"] = [{"superseded_by": "C@1"}]
    assert evaluate_case(case, answer, 10).outcome == "wrong_answer"


def test_excluded_document_with_content_is_exposed():
    case = {"kind": "excluded", "expected_successor": "B@1"}
    answer = answered({"content": content("1", "derogado"), "parent_context": None})
    assert evaluate_case(case, answer, 10).outcome == "exposed"


def test_injection_is_checked_on_the_whole_response():
    case = {"kind": "injection", "must_not_contain": ["soporte-firmware"]}
    withheld = answered({"content": content("anexo", None), "parent_context": None})
    leaked = answered({"content": content("anexo", "escriba a soporte-firmware"), "parent_context": None})
    assert evaluate_case(case, withheld, 10).passed
    assert evaluate_case(case, leaked, 10).outcome == "exposed"
    assert evaluate_case(case, REJECTED, 10).passed


def test_tool_error_is_a_failure():
    verdict = evaluate_case(ANSWERABLE, None, 10)
    assert verdict.outcome == "tool_error"
    assert not verdict.passed


def test_withheld_text_is_not_shown():
    answer = answered({"content": content("anexo", None), "parent_context": None})
    assert shown_text(answer) == ""
    assert passage_texts(answer) == []


def judged_case(case_id: str, fragment: str, passages: list[str], text: str, required: list[str]) -> CaseResult:
    verdict = CaseVerdict("correct", True, "answered", 1.0, True, 1.0, passages)
    case = {"id": case_id, "expected_fragment": fragment, "must_contain": required}
    return CaseResult(case=case, verdict=verdict, shown_text=text, passage_texts=[text])


def test_control_skips_passages_from_the_same_document():
    target = judged_case("A", "PRO-MED-007@2#3", ["PRO-MED-007@2#3"], "0,5 %", ["0,5 %"])
    same_document = judged_case("B", "PRO-MED-007@2#3.2", ["PRO-MED-007@2#3.2"], "plazo", ["plazo"])
    other_document = judged_case("C", "RES-X@1#1", ["RES-X@1#1"], "otro tema", ["otro"])
    assert select_control(target, [target, same_document, other_document]) is other_document


def test_control_skips_passages_that_contain_the_answer():
    target = judged_case("A", "PRO-MED-007@2#3", ["PRO-MED-007@2#3"], "0,5 %", ["0,5 %"])
    contains_answer = judged_case("B", "RES-X@1#1", ["RES-X@1#1"], "también 0,5 %", ["x"])
    clean = judged_case("C", "RES-Y@1#1", ["RES-Y@1#1"], "otro tema", ["y"])
    assert select_control(target, [target, contains_answer, clean]) is clean


def test_control_wraps_around_the_list():
    first = judged_case("A", "RES-X@1#1", ["RES-X@1#1"], "uno", ["uno"])
    last = judged_case("B", "RES-Y@1#1", ["RES-Y@1#1"], "dos", ["dos"])
    assert select_control(last, [first, last]) is first


def test_control_is_none_without_a_valid_candidate():
    target = judged_case("A", "RES-X@1#1", ["RES-X@1#1"], "uno", ["uno"])
    same = judged_case("B", "RES-X@1#2", ["RES-X@1#2"], "dos", ["dos"])
    assert select_control(target, [target, same]) is None


def test_summary_separates_origins_and_computes_deviation():
    def result(origin: str, passed: bool) -> CaseResult:
        verdict = CaseVerdict("correct" if passed else "wrong_answer", passed, "answered", 100.0, None, None, [])
        return CaseResult(case={"origin": origin, "kind": "answerable"}, verdict=verdict, shown_text="", passage_texts=[])

    results = [result("new", True), result("new", False), result("tuning", True)]
    summary = build_summary(results, 5000.0)
    assert summary["overall"]["deviation_rate"] == 0.3333
    assert summary["by_origin"]["new"]["deviation_rate"] == 0.5
    assert summary["by_origin"]["tuning"]["deviation_rate"] == 0.0
    assert summary["latency_ms"]["within_commitment"] is True

"""Compares a tool response with the behavior a reference case expects. Deterministic:
checks the text the user receives, so a value in the parent context counts."""
import json

from app.models.CaseResult import CaseResult, CaseVerdict

_ANSWER_KINDS = {"answerable", "identifier"}
_REFUSAL_KINDS = {"out_of_corpus", "unknown_identifier"}


def citation_id(citation: dict) -> str:
    return f"{citation['code']}@{citation['version']}#{citation['section_id']}"


def shown_text(answer: dict) -> str:
    """Join all text the user would read, passages and parent context."""
    parts: list[str] = []
    for passage in answer.get("passages", []):
        for content in (passage["content"], passage.get("parent_context")):
            if content and content.get("text"):
                parts.append(content["text"])
    return "\n".join(parts)


def passage_texts(answer: dict) -> list[str]:
    """One text per passage, joined to its parent context, for the judged metrics."""
    texts = []
    for passage in answer.get("passages", []):
        parts = [content["text"] for content in (passage["content"], passage.get("parent_context")) if content and content.get("text")]
        if parts:
            texts.append("\n".join(parts))
    return texts


def select_control(result: CaseResult, candidates: list[CaseResult]) -> CaseResult | None:
    """Pick the next case whose passages cannot support this answer: from other documents
    and without its required text. Otherwise a high score would be a correct judgment."""
    code = result.case["expected_fragment"].split("@")[0]
    required = result.case.get("must_contain", [])
    position = candidates.index(result)
    for candidate in [*candidates[position + 1 :], *candidates[:position]]:
        same_document = any(passage.startswith(f"{code}@") for passage in candidate.verdict.passages)
        has_answer = any(text in candidate.shown_text for text in required)
        if not same_document and not has_answer:
            return candidate
    return None


def evaluate_case(case: dict, answer: dict | None, latency_ms: float) -> CaseVerdict:
    if answer is None:
        return CaseVerdict("tool_error", False, None, latency_ms, None, None, [])

    passages = [citation_id(passage["content"]["citation"]) for passage in answer.get("passages", [])]
    status = answer["status"]
    kind = case["kind"]
    hit, reciprocal_rank = _retrieval(case, answer, passages)

    if kind in _ANSWER_KINDS:
        outcome = _answer_outcome(case, answer, status)
    elif kind in _REFUSAL_KINDS:
        outcome = "correct" if status == "rejected" else "false_answer"
    elif kind == "excluded":
        outcome = _excluded_outcome(case, answer, status)
    else:
        outcome = _injection_outcome(case, answer)
    return CaseVerdict(outcome, outcome == "correct", status, latency_ms, hit, reciprocal_rank, passages)


def _answer_outcome(case: dict, answer: dict, status: str) -> str:
    if status != "answered":
        return "refused_valid"
    text = shown_text(answer)
    if any(forbidden in text for forbidden in case.get("must_not_contain", [])):
        return "stale_value"
    return "correct" if all(required in text for required in case.get("must_contain", [])) else "wrong_answer"


def _excluded_outcome(case: dict, answer: dict, status: str) -> str:
    if status != "excluded_document" or answer.get("passages"):
        return "exposed"
    successors = [document["superseded_by"] for document in answer.get("excluded_documents", [])]
    return "correct" if case["expected_successor"] in successors else "wrong_answer"


def _injection_outcome(case: dict, answer: dict) -> str:
    """Check the whole response, not only the text fields: nothing may leak anywhere."""
    raw = json.dumps(answer, ensure_ascii=False)
    return "exposed" if any(text in raw for text in case["must_not_contain"]) else "correct"


def _retrieval(case: dict, answer: dict, passages: list[str]) -> tuple[bool | None, float | None]:
    expected = case.get("expected_fragment")
    if expected is None:
        return None, None
    reciprocal_rank = 1 / (passages.index(expected) + 1) if expected in passages else 0.0
    parents = [
        citation_id(passage["parent_context"]["citation"])
        for passage in answer.get("passages", [])
        if passage.get("parent_context")
    ]
    return expected in passages or expected in parents, reciprocal_rank

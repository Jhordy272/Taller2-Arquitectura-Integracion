"""Domain entities: the deterministic verdict and the judged scores of one case."""
from dataclasses import dataclass


@dataclass(frozen=True)
class CaseVerdict:
    outcome: str  # correct, wrong_answer, stale_value, refused_valid, false_answer, exposed, tool_error
    passed: bool
    status: str | None
    latency_ms: float
    hit: bool | None  # expected fragment among passages or parent context; None if not applicable
    reciprocal_rank: float | None
    passages: list[str]  # code@version#section of each passage


@dataclass(frozen=True)
class CaseResult:
    case: dict
    verdict: CaseVerdict
    shown_text: str
    passage_texts: list[str]
    anchored: float | None = None  # P(the passages support the expected answer)
    control_anchored: float | None = None  # same question against another case's passages
    relevant_fraction: float | None = None  # share of passages judged relevant

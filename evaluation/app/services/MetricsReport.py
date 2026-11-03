"""Aggregates case results into metrics, overall and by origin, because cases used to
choose the threshold are not independent evidence."""
from collections import Counter
from statistics import mean, median, quantiles

from app.models.CaseResult import CaseResult

ORIGINS = ("new", "validation", "tuning")
KINDS = ("answerable", "out_of_corpus", "identifier", "unknown_identifier", "excluded", "injection")


def _mean(values: list[float]) -> float | None:
    return round(mean(values), 4) if values else None


def _rate(results: list[CaseResult]) -> float | None:
    return round(sum(not result.verdict.passed for result in results) / len(results), 4) if results else None


def _group_metrics(results: list[CaseResult]) -> dict:
    with_fragment = [result for result in results if result.verdict.hit is not None]
    return {
        "cases": len(results),
        "deviation_rate": _rate(results),
        "outcomes": dict(Counter(result.verdict.outcome for result in results)),
        "hit_rate": _mean([float(result.verdict.hit) for result in with_fragment]),
        "mrr": _mean([result.verdict.reciprocal_rank for result in with_fragment]),
        "anchoring": _mean([r.anchored for r in results if r.anchored is not None]),
        "anchoring_control": _mean([r.control_anchored for r in results if r.control_anchored is not None]),
        "relevance": _mean([r.relevant_fraction for r in results if r.relevant_fraction is not None]),
    }


def build_summary(results: list[CaseResult], latency_commitment_ms: float) -> dict:
    latencies = [result.verdict.latency_ms for result in results]
    p95 = quantiles(latencies, n=20)[-1] if len(latencies) >= 2 else latencies[0]
    return {
        "overall": _group_metrics(results),
        "by_origin": {origin: _group_metrics([r for r in results if r.case["origin"] == origin]) for origin in ORIGINS},
        "by_kind": {kind: _group_metrics([r for r in results if r.case["kind"] == kind]) for kind in KINDS},
        "latency_ms": {
            "median": round(median(latencies), 1),
            "p95": round(p95, 1),
            "max": round(max(latencies), 1),
            "commitment": latency_commitment_ms,
            "within_commitment": max(latencies) <= latency_commitment_ms,
        },
    }


def case_rows(results: list[CaseResult]) -> list[list]:
    """One row per case for the CSV evidence."""
    return [
        [
            result.case["id"],
            result.case["kind"],
            result.case["origin"],
            result.case["query"],
            result.verdict.outcome,
            result.verdict.status,
            round(result.verdict.latency_ms, 1),
            result.case.get("expected_fragment", ""),
            "" if result.verdict.hit is None else result.verdict.hit,
            "" if result.verdict.reciprocal_rank is None else round(result.verdict.reciprocal_rank, 3),
            " ; ".join(result.verdict.passages),
            "" if result.anchored is None else round(result.anchored, 4),
            "" if result.control_anchored is None else round(result.control_anchored, 4),
            "" if result.relevant_fraction is None else round(result.relevant_fraction, 4),
        ]
        for result in results
    ]


CASE_HEADER = [
    "id", "kind", "origin", "query", "outcome", "status", "latency_ms", "expected_fragment",
    "hit", "reciprocal_rank", "passages", "anchored", "control_anchored", "relevant_fraction",
]

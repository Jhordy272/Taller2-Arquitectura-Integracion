"""Prints the hybrid, semantic and lexical rankings of a query, to compare them."""
import argparse
import logging
import sys
import time

from app.composition import build_search_service
from app.config.Settings import settings
from app.models.RetrievedFragment import RetrievedFragment

for noisy_logger in ("httpx", "httpx2", "huggingface_hub", "sentence_transformers"):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)


def print_ranking(name: str, description: str, fragments: list[RetrievedFragment]) -> None:
    print(f"\n{name}\n  {description}")
    if not fragments:
        print("  No results.")
    for position, fragment in enumerate(fragments, start=1):
        flag = "  [injection risk: content will be withheld]" if fragment.injection_risk else ""
        print(f"  {position}. {fragment.score:7.4f}  {fragment.fragment_id}  ({fragment.section_title}){flag}")


def run(query: str, limit: int) -> int:
    service, _ = build_search_service()

    started = time.perf_counter()
    outcome = service.search(query, limit)
    elapsed_ms = (time.perf_counter() - started) * 1000

    print(f"Query: {query}")
    print(f"Search latency: {elapsed_ms:.0f} ms (excludes loading the model)")
    print("Only valid documents are searched. Results read: position, score, code@version#section (section title).")
    print("Scores are only comparable within the same list.")
    print_ranking(
        "Hybrid (RRF)",
        "Main result: merges the two lists below by position, favoring fragments that rank high in both.",
        outcome.hybrid,
    )
    print_ranking(
        "Semantic only (cosine)",
        "Finds similar meaning, even with different words. Always returns results, even if unrelated.",
        outcome.dense[:limit],
    )
    print_ranking(
        "Lexical only (BM25)",
        "Finds the exact words or codes of the query. Returns nothing if none of them appear.",
        outcome.lexical[:limit],
    )
    return 0


if __name__ == "__main__":
    arguments = argparse.ArgumentParser()
    arguments.add_argument("query")
    arguments.add_argument("--limit", type=int, default=settings.default_result_limit)
    parsed = arguments.parse_args()
    sys.exit(run(parsed.query, parsed.limit))

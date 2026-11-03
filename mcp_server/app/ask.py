"""Prints the composed answer to a query, or one fragment, as JSON."""
import argparse
import json
import logging
import sys
from dataclasses import asdict

from app.composition import build_composer

for noisy_logger in ("httpx", "httpx2", "huggingface_hub", "sentence_transformers"):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)


def run(query: str | None, fragment: list[str] | None) -> int:
    composer = build_composer()
    answer = composer.get_fragment(*fragment) if fragment else composer.answer(query)
    print(json.dumps(asdict(answer), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    arguments = argparse.ArgumentParser()
    arguments.add_argument("query", nargs="?")
    arguments.add_argument("--fragment", nargs=3, metavar=("CODE", "VERSION", "SECTION"))
    parsed = arguments.parse_args()
    if not parsed.query and not parsed.fragment:
        arguments.error("provide a query or --fragment")
    sys.exit(run(parsed.query, parsed.fragment))

"""Measures how long a validity change takes to reach the answers of a running server,
from the write of the registry file to the first answer that reflects it. Works on a
temporary copy of the registry, so the real one is never touched. Saves CSV evidence."""
import argparse
import csv
import logging
import shutil
import statistics
import tempfile
import time
from pathlib import Path

import yaml

from app.config.Settings import settings

for noisy_logger in ("httpx", "httpx2", "huggingface_hub", "sentence_transformers"):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)

_EVIDENCE_DIR = Path(__file__).resolve().parents[2] / "data" / "evidence"

# An identifier only this document contains: while it is valid the query is answered, and
# once excluded it is refused, with no restart and no payload synchronization.
TARGET = ("MAN-MTO-002", "1")
QUERY = "VL-CC-022"
POLL_INTERVAL_S = 0.05
TIMEOUT_S = 60.0


def set_status(path: Path, status: str) -> None:
    registry = yaml.safe_load(path.read_text(encoding="utf-8"))
    for entry in registry["documents"]:
        if (entry["code"], entry["version"]) == TARGET:
            entry["status"] = status
    path.write_text(yaml.safe_dump(registry, allow_unicode=True, sort_keys=False), encoding="utf-8")


def wait_for(composer, expected_status: str) -> tuple[float, int]:
    started = time.perf_counter()
    polls = 0
    while time.perf_counter() - started < TIMEOUT_S:
        polls += 1
        if composer.answer(QUERY).status == expected_status:
            return (time.perf_counter() - started) * 1000, polls
        time.sleep(POLL_INTERVAL_S)
    raise TimeoutError(f"the answer did not become {expected_status} in {TIMEOUT_S} s")


def main(runs: int) -> None:
    with tempfile.TemporaryDirectory() as directory:
        registry_copy = Path(directory) / "validity_registry.yaml"
        shutil.copyfile(settings.validity_registry_path, registry_copy)
        settings.validity_registry_path = registry_copy

        from app.composition import build_composer  # after redirecting the registry

        composer = build_composer()
        assert composer.answer(QUERY).status == "answered", "the target must start valid"

        rows = []
        for run in range(1, runs + 1):
            for change, status, expected in (("valid -> in_doubt", "in_doubt", "rejected"), ("in_doubt -> valid", "valid", "answered")):
                set_status(registry_copy, status)
                latency_ms, polls = wait_for(composer, expected)
                rows.append([run, change, round(latency_ms, 1), polls])

    _EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    output = _EVIDENCE_DIR / "propagation_latency.csv"
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["run", "change", "latency_ms", "polls"])
        writer.writerows(rows)

    latencies = [row[2] for row in rows]
    print(
        f"{len(rows)} changes, check interval {settings.registry_check_interval_s} s: "
        f"median {statistics.median(latencies):.0f} ms, max {max(latencies):.0f} ms -> {output}"
    )


if __name__ == "__main__":
    arguments = argparse.ArgumentParser(description=__doc__)
    arguments.add_argument("--runs", type=int, default=5, help="number of exclude and restore cycles")
    main(arguments.parse_args().runs)

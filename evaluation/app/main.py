"""Evaluation harness: runs the reference cases through the MCP server, judges them
with laya unless --no-judge is given, and saves the evidence as CSV and JSON."""
import argparse
import asyncio
import csv
import json
import logging
import time
from dataclasses import replace

from app.config.Settings import settings
from app.models.CaseResult import CaseResult
from app.repositories.CaseRepository import CaseRepository
from app.repositories.McpClientRepository import open_client
from app.services.CaseEvaluator import evaluate_case, passage_texts, select_control, shown_text
from app.services.MetricsReport import CASE_HEADER, build_summary, case_rows

logging.basicConfig(level=logging.INFO)
for noisy_logger in ("httpx", "httpx2", "huggingface_hub", "sentence_transformers", "mcp"):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)
logger = logging.getLogger("evaluation")


async def run_cases(cases: list[dict], collection: str | None) -> list[CaseResult]:
    results = []
    async with open_client(settings.mcp_server_dir, collection) as client:
        for case in cases:
            started = time.perf_counter()
            answer = await client.search(case["query"])
            latency_ms = (time.perf_counter() - started) * 1000
            verdict = evaluate_case(case, answer, latency_ms)
            results.append(
                CaseResult(
                    case=case,
                    verdict=verdict,
                    shown_text=shown_text(answer) if answer else "",
                    passage_texts=passage_texts(answer) if answer else [],
                )
            )
            logger.info("%s %s -> %s", case["id"], case["kind"], verdict.outcome)
    return results


def judge(results: list[CaseResult]) -> list[CaseResult]:
    """Add the laya scores. The control pairs each expected answer with passages that do
    not contain it: if it scores like the real pairing, the anchoring score means little."""
    from app.repositories.LayaJudge import LayaJudge

    judge_model = LayaJudge(settings.laya_model, settings.laya_revision)
    answered = [result for result in results if result.passage_texts and result.case.get("expected_answer")]

    judged: dict[str, CaseResult] = {}
    for result in answered:
        control = select_control(result, answered)
        relevant = [judge_model.is_relevant(result.case["query"], text) for text in result.passage_texts]
        judged[result.case["id"]] = replace(
            result,
            anchored=judge_model.anchored(result.shown_text, result.case["expected_answer"]),
            control_anchored=judge_model.anchored(control.shown_text, result.case["expected_answer"]) if control else None,
            relevant_fraction=sum(relevant) / len(relevant),
        )
        logger.info("judged %s", result.case["id"])
    return [judged.get(result.case["id"], result) for result in results]


def save_evidence(results: list[CaseResult], summary: dict, label: str) -> None:
    settings.evidence_dir.mkdir(parents=True, exist_ok=True)
    cases_path = settings.evidence_dir / f"evaluation_{label}_cases.csv"
    with cases_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(CASE_HEADER)
        writer.writerows(case_rows(results))
    summary_path = settings.evidence_dir / f"evaluation_{label}_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved {cases_path}\nSaved {summary_path}")


def print_summary(summary: dict) -> None:
    print("\nDeviation rate = share of cases that do not behave as expected (lower is better).")
    print(f"{'Group':<20}{'Cases':>6}{'Deviation':>11}{'Hit':>7}{'MRR':>7}{'Anchor':>8}{'Control':>9}{'Relevant':>10}")
    groups = [("overall", summary["overall"])]
    groups += [(f"origin: {name}", metrics) for name, metrics in summary["by_origin"].items()]
    groups += [(f"kind: {name}"[:19], metrics) for name, metrics in summary["by_kind"].items()]

    def cell(value: float | None) -> str:
        return "-" if value is None else f"{value:.2f}"

    for name, metrics in groups:
        print(
            f"{name:<20}{metrics['cases']:>6}{cell(metrics['deviation_rate']):>11}{cell(metrics['hit_rate']):>7}"
            f"{cell(metrics['mrr']):>7}{cell(metrics['anchoring']):>8}{cell(metrics['anchoring_control']):>9}"
            f"{cell(metrics['relevance']):>10}"
        )
    print(f"\nOutcomes: {summary['overall']['outcomes']}")
    print(f"Latency (ms): {summary['latency_ms']}")


async def check_reproducibility(cases: list[dict], collection: str | None) -> int:
    """Run the cases on two separate server starts and report any difference in the
    status or in the ordered passages of a case."""
    first = await run_cases(cases, collection)
    second = await run_cases(cases, collection)
    differences = [
        [one.case["id"], one.verdict.status, " ; ".join(one.verdict.passages), two.verdict.status, " ; ".join(two.verdict.passages)]
        for one, two in zip(first, second)
        if (one.verdict.status, one.verdict.passages) != (two.verdict.status, two.verdict.passages)
    ]
    print(f"\nReproducibility: {len(cases) - len(differences)}/{len(cases)} cases identical in two runs.")
    for difference in differences:
        print(f"  {difference[0]}\n    run 1: {difference[2]}\n    run 2: {difference[4]}")

    settings.evidence_dir.mkdir(parents=True, exist_ok=True)
    path = settings.evidence_dir / "evaluation_reproducibility.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(["id", "status_run_1", "passages_run_1", "status_run_2", "passages_run_2", "identical"])
        for one, two in zip(first, second):
            same = (one.verdict.status, one.verdict.passages) == (two.verdict.status, two.verdict.passages)
            writer.writerow([
                one.case["id"], one.verdict.status, " ; ".join(one.verdict.passages),
                two.verdict.status, " ; ".join(two.verdict.passages), same,
            ])
    print(f"Saved {path}")
    return 1 if differences else 0


async def run(collection: str | None, label: str, use_judge: bool, reproducibility: bool) -> int:
    cases = CaseRepository(settings.reference_cases_path).load()
    if reproducibility:
        return await check_reproducibility(cases, collection)
    results = await run_cases(cases, collection)
    if use_judge:
        results = judge(results)
    summary = build_summary(results, settings.latency_commitment_ms)
    print_summary(summary)
    save_evidence(results, summary, label)
    return 0


if __name__ == "__main__":
    arguments = argparse.ArgumentParser()
    arguments.add_argument("--collection", help="evaluate this collection instead of the active alias")
    arguments.add_argument("--label", default="structural", help="name of the evidence files")
    arguments.add_argument("--no-judge", action="store_true", help="skip the laya metrics")
    arguments.add_argument("--reproducibility", action="store_true", help="compare two runs instead of measuring")
    parsed = arguments.parse_args()
    raise SystemExit(asyncio.run(run(parsed.collection, parsed.label, not parsed.no_judge, parsed.reproducibility)))

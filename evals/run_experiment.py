"""Run the pipeline over the Langfuse dataset `cx-tickets` and score it. Spec: docs/specs/evals.md.

    python -m evals.run_experiment --run-name jev-prompt-v1
    python -m evals.run_experiment --classify-only --classifier haiku --run-name haiku-classify
    python -m evals.run_experiment --prompt-label staging --run-name prompt-v2
"""

import argparse
import asyncio
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from langfuse import Evaluation

from app.data import load_customers, load_kb
from app.domain import Ticket
from app.observability import init_tracing
from app.pipeline import RunOptions, process_ticket, summary
from app.tools import KBIndex
from evals.judge import judge
from evals.scoring import (
    calibration, classification_scores, escalation_correct, format_ok, guardrail_blocked, tool_recall,
)
from evals.upload_dataset import DATASET

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def make_task(options: RunOptions):
    customers, kb = load_customers(), KBIndex(load_kb())

    async def task(*, item, **kwargs) -> dict:
        ticket = Ticket(**item.input, labels=item.expected_output)
        # to_thread copies the context, so the pipeline spans nest under the experiment item trace
        r = await asyncio.to_thread(process_ticket, ticket, customers, kb=kb, options=options)
        return {**summary(r), "tool_outputs": r.agent.tool_outputs if r.agent else []}

    return task


def deterministic(*, input, output, expected_output, **kwargs) -> list[Evaluation]:
    evals = [Evaluation(name=k, value=v, data_type="BOOLEAN") for k, v in
             classification_scores(output, expected_output).items()]
    confidence = (output.get("confidence") or {}).get("category")
    if confidence is not None:
        evals.append(Evaluation(name="category_confidence", value=confidence))
    evals.append(Evaluation(name="escalation_correct", value=escalation_correct(output, expected_output),
                            data_type="BOOLEAN", comment=", ".join(output["reasons"])))
    recall = tool_recall(output, expected_output)
    if recall is not None:
        evals.append(Evaluation(name="tool_recall", value=recall,
                                comment=f"used {output['tool_calls']}, expected {expected_output['expected_tools']}"))
        evals.append(Evaluation(name="guardrail_blocked", value=guardrail_blocked(output), data_type="BOOLEAN"))
        evals.append(Evaluation(name="cost_usd", value=output["cost_usd"]))
    if output.get("draft"):
        evals.append(Evaluation(name="format_ok", value=format_ok(output["draft"], input["channel"]),
                                data_type="BOOLEAN", comment=input["channel"]))
    return evals


async def judged(*, input, output, expected_output, **kwargs) -> list[Evaluation]:
    if not output.get("draft"):
        return []
    verdict = await asyncio.to_thread(
        judge, f"{input['subject']}\n\n{input['body']}", expected_output["key_points"],
        output["draft"], output["tool_outputs"],
    )
    missed = [k.key_point for k in verdict.key_points if not k.covered]
    return [
        Evaluation(name="key_points_coverage", value=verdict.coverage,
                   comment="missed: " + "; ".join(missed) if missed else "all covered"),
        Evaluation(name="groundedness", value=verdict.grounded,
                   comment="; ".join(verdict.unsupported_claims) or "all claims supported"),
    ]


def aggregate(*, item_results, **kwargs) -> list[Evaluation]:
    values = defaultdict(list)
    for r in item_results:
        for e in r.evaluations:
            values[e.name].append(float(e.value))
    evals = [Evaluation(name=f"avg_{name}", value=sum(v) / len(v)) for name, v in sorted(values.items())
             if name != "cost_usd"]
    if values["cost_usd"]:
        evals.append(Evaluation(name="total_cost_usd", value=sum(values["cost_usd"])))
    pairs = [((r.output.get("confidence") or {}).get("category"),
              (r.output.get("classification") or {}).get("category") == r.item.expected_output["category"])
             for r in item_results if r.output]
    pairs = [(c, ok) for c, ok in pairs if c is not None]
    if pairs:
        ece, table = calibration(pairs)
        evals.append(Evaluation(name="category_ece", value=ece, comment=json.dumps(table)))
    return evals


def main() -> None:
    parser = argparse.ArgumentParser(prog="evals.run_experiment")
    parser.add_argument("--run-name")
    parser.add_argument("--classifier", choices=["jev", "haiku"], default="jev")
    parser.add_argument("--prompt-label", default="production")
    parser.add_argument("--classify-only", action="store_true")
    parser.add_argument("--threshold", type=float, help="Override ESCALATION_CONFIDENCE")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()

    options = RunOptions(classifier=args.classifier, prompt_label=args.prompt_label,
                         classify_only=args.classify_only,
                         **({"escalation_confidence": args.threshold} if args.threshold is not None else {}))
    run_name = args.run_name or f"{args.classifier}-{args.prompt_label}-{datetime.now():%m%d-%H%M}"

    langfuse = init_tracing()
    items = langfuse.get_dataset(DATASET).items[: args.limit]
    result = langfuse.run_experiment(
        name="cx-copilot",
        run_name=run_name,
        description=f"{options}",
        data=items,
        task=make_task(options),
        evaluators=[deterministic] if args.classify_only else [deterministic, judged],
        run_evaluators=[aggregate],
        max_concurrency=args.concurrency,
        metadata={"classifier": args.classifier, "prompt_label": args.prompt_label,
                  "classify_only": str(args.classify_only)},
    )
    langfuse.flush()

    RESULTS_DIR.mkdir(exist_ok=True)
    report = {"run_name": run_name, "options": vars(args),
              "run": {e.name: e.value for e in result.run_evaluations},
              "calibration": next((json.loads(e.comment) for e in result.run_evaluations
                                   if e.name == "category_ece"), []),
              "items": [{"ticket": r.item.input["id"], "output": r.output,  # tool_outputs kept: re-judge offline
                         "scores": {e.name: e.value for e in r.evaluations},
                         "comments": {e.name: e.comment for e in r.evaluations if e.comment}}
                        for r in result.item_results]}
    (RESULTS_DIR / f"{run_name}.json").write_text(json.dumps(report, indent=1, ensure_ascii=False, default=str),
                                                  encoding="utf-8")
    print(f"\n{run_name}: {len(result.item_results)} items")
    for e in result.run_evaluations:
        if e.name != "category_ece":
            print(f"  {e.name:28} {e.value:.3f}")
    if report["calibration"]:
        print(f"  category_ece                 {report['run']['category_ece']:.3f}")
        for row in report["calibration"]:
            print(f"    conf {row['bin']}: n={row['n']:2} confidence={row['confidence']:.2f} "
                  f"accuracy={row['accuracy']:.2f}")
    print(f"  {getattr(result, 'dataset_run_url', '') or ''}")


if __name__ == "__main__":
    main()

"""Argparse CLI entry point: python -m smart_insights <subcommand>."""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m smart_insights",
        description="OptinMonster smart-insights micro-agent (see SPEC.md)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser(
        "preprocess",
        help="stage 2 (LLM): derive segment map + per-row notes/anomalies, "
        "write committed artifacts. The one command that hits the API.",
    )
    p.add_argument("--input", default="data/optinmonster_users.json")
    p.add_argument("--out", default="data/enriched.json")

    p = sub.add_parser(
        "clean",
        help="stages 3-4 over the committed artifact: segments, anomaly flags, "
        "benchmark table. No API calls.",
    )
    p.add_argument("--enriched", default="data/enriched.json")

    p = sub.add_parser("run", help="stages 3-7: benchmark, insight, validation, report")
    p.add_argument("--enriched", default="data/enriched.json")
    p.add_argument("--out", default="out/insights.json")
    p.add_argument("--id", type=int, default=None, help="run a single row")
    p.add_argument("--no-llm", action="store_true", help="stop after stage 4")

    p = sub.add_parser(
        "evaluate",
        help="re-run validate.py checks against a saved output file; "
        "exits nonzero on any failure",
    )
    p.add_argument("--insights", default="out/insights.json")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "preprocess":
        from smart_insights import get_client
        from smart_insights.preprocess import preprocess

        try:
            client = get_client()
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        preprocess(args.input, args.out, client)
        return 0

    if args.command == "clean":
        from smart_insights.audit import audit
        from smart_insights.benchmark import compute_benchmarks
        from smart_insights.models import load_enriched_rows
        from smart_insights.report import print_segment_table

        rows = compute_benchmarks(audit(load_enriched_rows(args.enriched)))
        print_segment_table(rows)
        return 0

    if args.command == "run":
        return _cmd_run(args)

    if args.command == "evaluate":
        return _cmd_evaluate(args)

    raise AssertionError(f"unhandled command {args.command}")


def _cmd_run(args: argparse.Namespace) -> int:
    """Stages 3-7: audit, benchmark, insight, validate, report."""
    from smart_insights.audit import audit
    from smart_insights.benchmark import build_facts, compute_benchmarks
    from smart_insights.models import load_enriched_rows
    from smart_insights.report import output_row, print_run_summary, write_insights

    rows = compute_benchmarks(audit(load_enriched_rows(args.enriched)))

    selected = rows
    if args.id is not None:
        selected = [row for row in rows if row.id == args.id]
        if not selected:
            print(f"error: no row with id {args.id}", file=sys.stderr)
            return 1

    client = None
    if not args.no_llm:
        from smart_insights import get_client

        try:
            client = get_client()
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

    entries = []
    for row in selected:
        if row.is_anomalous:
            # Processed correctly: the anomaly fields tell the story (§4.7).
            entries.append(output_row(row, facts=None, status="ok"))
            continue
        facts = build_facts(row, rows)
        if args.no_llm:
            entries.append(output_row(row, facts, status="llm_skipped"))
            continue
        from smart_insights.insights import generate_insight

        insight, error = generate_insight(facts, client)
        row.insight = insight
        entry = output_row(row, facts, status="ok" if error is None else "needs_review")
        entry["status_reason"] = error
        entries.append(entry)

    write_insights(entries, args.out)
    print_run_summary(entries)
    print(f"wrote {args.out}")
    return 0


def _cmd_evaluate(args: argparse.Namespace) -> int:
    """Re-verify a saved output file offline; nonzero exit on any failure."""
    import json
    from pathlib import Path

    from smart_insights.validate import evaluate_entries

    entries = json.loads(Path(args.insights).read_text(encoding="utf-8"))
    results = evaluate_entries(entries)
    failures = 0
    for row_id, problems in results:
        if problems:
            failures += 1
            print(f"{row_id:>3}  FAIL  {'; '.join(problems)}")
        else:
            print(f"{row_id:>3}  pass")
    print(f"\n{len(results) - failures}/{len(results)} rows pass")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

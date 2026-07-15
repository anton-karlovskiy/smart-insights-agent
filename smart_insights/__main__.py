"""Argparse CLI entry point: python -m smart_insights <subcommand>."""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from smart_insights.models import EnrichedRow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m smart_insights",
        description="Smart Insights Agent (see SPEC.md)",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    preprocess_parser = subcommands.add_parser(
        "preprocess",
        help="stage 2 (LLM): derive segment map + per-row notes/anomalies, "
        "write committed artifacts. The one command that hits the API.",
    )
    preprocess_parser.add_argument("--input", default="data/optinmonster_users.json")
    preprocess_parser.add_argument("--output", default="data/enriched.json")

    clean_parser = subcommands.add_parser(
        "clean",
        help="stages 3-4 over the committed artifact: segments, anomaly flags, "
        "benchmark table. No API calls.",
    )
    clean_parser.add_argument("--input", default="data/enriched.json")

    run_parser = subcommands.add_parser(
        "run", help="stages 3-7: benchmark, insight, validation, report"
    )
    run_parser.add_argument("--input", default="data/enriched.json")
    run_parser.add_argument("--output", default="out/insights.json")
    run_parser.add_argument("--id", type=int, default=None, help="run a single row")
    run_parser.add_argument("--no-llm", action="store_true", help="stop after stage 4")

    evaluate_parser = subcommands.add_parser(
        "evaluate",
        help="re-run validate.py checks against a saved output file; exits nonzero on any failure",
    )
    evaluate_parser.add_argument("--input", default="out/insights.json")

    return parser


def main(argv: list[str] | None = None) -> int:
    # LLM prose can contain characters a cp1252 Windows console cannot encode
    # (e.g. U+2011 non-breaking hyphen); degrade to '?' instead of crashing.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    args = build_parser().parse_args(argv)

    if args.command == "preprocess":
        from smart_insights import get_client
        from smart_insights.preprocess import preprocess

        try:
            # PreprocessError is a RuntimeError: a missing key and a dead API
            # both end this command the same way — a message, not a traceback.
            preprocess(args.input, args.output, get_client())
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        return 0

    if args.command == "clean":
        from smart_insights.report import print_segment_table

        print_segment_table(_prepare_rows(args.input))
        return 0

    if args.command == "run":
        return _cmd_run(args)

    if args.command == "evaluate":
        return _cmd_evaluate(args)

    raise AssertionError(f"unhandled command {args.command}")


def _prepare_rows(input_path: str) -> list[EnrichedRow]:
    """Stages 3-4, shared by `clean` and `run`: load the committed artifact,
    flag impossible rates, benchmark the clean rows. Offline and fast, so the
    bar exists to name the stage that failed, not to pass the time."""
    from smart_insights.audit import flag_impossible_rates
    from smart_insights.benchmark import compute_benchmarks
    from smart_insights.models import load_enriched_rows
    from smart_insights.progress import Progress

    with Progress("prepare", 3) as progress:
        rows = load_enriched_rows(input_path)
        progress.advance(f"loaded {len(rows)} rows")
        rows = flag_impossible_rates(rows)
        progress.advance("flagged impossible rates")
        rows = compute_benchmarks(rows)
        progress.advance("computed benchmarks")
    return rows


def _cmd_run(args: argparse.Namespace) -> int:
    """Stages 3-7: audit, benchmark, insight, validate, report."""
    from smart_insights.benchmark import build_insight_facts
    from smart_insights.progress import Progress
    from smart_insights.report import build_output_entry, print_run_summary, write_insights

    rows = _prepare_rows(args.input)

    selected_rows = rows
    if args.id is not None:
        selected_rows = [row for row in rows if row.id == args.id]
        if not selected_rows:
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
    with Progress("insights", len(selected_rows)) as progress:
        for row in selected_rows:
            progress.start(f"row {row.id} {row.website_url}")
            if row.is_anomalous:
                # Processed correctly: the anomaly fields tell the story.
                entry = build_output_entry(row, facts=None, status="ok")
                error = None
            elif args.no_llm:
                entry = build_output_entry(
                    row, build_insight_facts(row, rows), status="llm_skipped"
                )
                error = None
            else:
                from smart_insights.insights import generate_insight

                facts = build_insight_facts(row, rows)
                insight, error = generate_insight(facts, client)
                row.insight = insight
                entry = build_output_entry(
                    row, facts, status="ok" if error is None else "needs_review"
                )
            entry["status_reason"] = error
            entries.append(entry)
            progress.advance(f"row {row.id} {entry['status']}")

    write_insights(entries, args.output)
    print_run_summary(entries)
    print(f"wrote {args.output}")
    return 0


def _cmd_evaluate(args: argparse.Namespace) -> int:
    """Re-verify a saved output file offline; nonzero exit on any failure."""
    import json
    from pathlib import Path

    from smart_insights.progress import Progress
    from smart_insights.validate import evaluate_entry

    entries = json.loads(Path(args.input).read_text(encoding="utf-8"))
    results = []
    with Progress("evaluate", len(entries)) as progress:
        for entry in entries:
            results.append((entry["id"], evaluate_entry(entry)))
            progress.advance(f"row {entry['id']}")

    failure_count = 0
    for row_id, problems in results:
        if problems:
            failure_count += 1
            print(f"{row_id:>3}  FAIL  {'; '.join(problems)}")
        else:
            print(f"{row_id:>3}  pass")
    print(f"\n{len(results) - failure_count}/{len(results)} rows pass")
    return 1 if failure_count else 0


if __name__ == "__main__":
    sys.exit(main())

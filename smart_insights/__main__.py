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
    print(f"{args.command}: not implemented yet")
    return 1


if __name__ == "__main__":
    sys.exit(main())
